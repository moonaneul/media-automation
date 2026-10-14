"""The current UI downloads through the existing bounded-memory sender."""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore
from media_automation.web.streaming_download import CHUNK_SIZE


@pytest.mark.parametrize('extension,mime', [
    ('pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
    ('pdf', 'application/pdf'),
])
def test_current_download_streams_exact_bytes_after_auth(tmp_path, monkeypatch, extension, mime):
    store = WorkStore(tmp_path / 'work.db')
    identifier = 'a' * 32
    directory = Path(store.path).with_suffix('.generated')
    directory.mkdir(exist_ok=True)
    artifact = directory / (identifier + '.' + extension)
    content = b'0123456789' * (CHUNK_SIZE // 10 * 2 + 123)
    artifact.write_bytes(content)
    original = Path.read_bytes
    def reject_full_read(path):
        if path == artifact:
            raise AssertionError('The artifact must not be read into memory at once')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', reject_full_read)
    server = make_server(store, 0, password='test-password')
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    route = f'/api/generated?id={identifier}&format={extension}'
    try:
        with pytest.raises(HTTPError) as blocked:
            urlopen(base + route, timeout=3)
        assert blocked.value.code == 401
        login = Request(base + '/api/login', data=json.dumps({'password':'test-password'}).encode(), headers={'Content-Type':'application/json'})
        with urlopen(login, timeout=3) as response:
            cookie = response.headers['Set-Cookie'].split(';', 1)[0]
        headers = {'Cookie':cookie}
        with urlopen(Request(base + route, headers=headers), timeout=3) as response:
            assert response.headers['Content-Type'] == mime
            assert int(response.headers['Content-Length']) == len(content)
            assert response.headers['Cache-Control'] == 'no-store'
            assert response.read() == content
        for query, code in [('id=../work&format=pdf',400), ('id='+'a'*32+'&format=zip',400), ('id='+'b'*32+'&format=pdf',404)]:
            with pytest.raises(HTTPError) as error:
                urlopen(Request(base + '/api/generated?' + query, headers=headers), timeout=3)
            assert error.value.code == code
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
