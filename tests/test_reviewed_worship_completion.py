"""Completing a worship PPT requires explicit review, even when optional media stays blank."""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from media_automation.web.original.generation import FRIDAY_TYPOGRAPHY_VERSION, render_configuration
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore


def attempt_complete(base, request):
    with urlopen(Request(
        base + '/api/complete',
        data=json.dumps(request, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json'},
    ), timeout=3) as response:
        return json.load(response)


@pytest.mark.parametrize('unresolved,ack,expected_status', [
    ([], [], 200),
    (['시작 찬양 1:score_asset'], [], 400),
    (['시작 찬양 1:score_asset'], ['시작 찬양 1:score_asset'], 200),
    (['배경음악 첫 기도:audio_asset'], ['배경음악 첫 기도:audio_asset'], 200),
    (['성경 본문:bible_text'], ['성경 본문:bible_text'], 400),
    (['성경 본문:bible_review'], ['성경 본문:bible_review'], 400),
    (['설교 제목:input'], ['설교 제목:input'], 400),
    (['예배 전 안내:template'], ['예배 전 안내:template'], 400),
    (['시작 찬양 1:original_review'], ['시작 찬양 1:original_review'], 400),
])
def test_completion_rejects_unreviewed_or_mandatory_gaps(tmp_path, unresolved, ack, expected_status):
    day, service, identifier = '2026-10-16', 'friday', 'f' * 32
    store = WorkStore(tmp_path / 'work.db')
    data = {
        'fields': {'성경 본문': {'state': 'VALUE', 'value': '시 1:1'}},
        'fridayMode': 'zoom',
        'outputs': {'ppt': {'fileId': identifier, 'changed': False, 'complete': False}},
    }
    revision = store.save(day, service, 0, data)['revision']
    directory = Path(store.path).with_suffix('.generated')
    directory.mkdir()
    (directory / (identifier + '.pptx')).write_bytes(b'test PPT')
    (directory / (identifier + '.json')).write_text(json.dumps({
        'date': day, 'service': service, 'format': 'pptx',
        'fields': data['fields'], 'unresolved': unresolved,
        'attachments': [], 'typography_version': FRIDAY_TYPOGRAPHY_VERSION,
        'render_configuration': render_configuration(data),
    }, ensure_ascii=False))
    server = make_server(store, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        request = {
            'date': day, 'service': service, 'revision': revision,
            'file_id': identifier, 'reviewed': True,
            'acknowledged_unresolved': ack,
        }
        if expected_status == 200:
            result = attempt_complete(f'http://127.0.0.1:{server.server_port}', request)
            completed = result['data']['outputs']['ppt']
            assert completed['complete'] is True
            assert completed['archiveStatus'] == 'pending_connection'
            assert completed['acknowledgedUnresolved'] == ack
        else:
            with pytest.raises(HTTPError) as rejected:
                attempt_complete(f'http://127.0.0.1:{server.server_port}', request)
            assert rejected.value.code == 400
            assert store.get(day, service)['data']['outputs']['ppt']['complete'] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_worship_completion_ui_passes_acknowledged_media_list():
    html = Path('src/media_automation/web/original/ui/index.html').read_text()
    handler = html[html.index("const completePdf=$('complete').onclick;"):
                   html.index("document.querySelectorAll('[data-workflow-target]')", html.index("const completePdf=$('complete').onclick;"))]
    assert 'acknowledged_unresolved:acknowledged' in handler
    assert "item.endsWith(':score_asset')" in handler
    assert "item.endsWith(':audio_asset')" in handler
    assert 'if(blocked.length)' in handler
    assert 'if(!confirm(' in handler
