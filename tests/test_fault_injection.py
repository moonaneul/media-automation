"""Deliberate faults against isolated stores and a real local HTTP server."""
import json
import threading
from pathlib import Path
from unittest.mock import Mock
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest
import requests
from media_automation.web.original.work_store import WorkStore
from media_automation.web.original.server import make_server
from media_automation.web.original.onedrive import OneDrive, CloudError


@pytest.fixture
def app(tmp_path):
    store = WorkStore(tmp_path / 'work.db')
    data = {'fields': {'성경 본문': {'state': 'VALUE', 'value': '삼상 18:6~11'},
                       '설교 제목': {'state': 'VALUE', 'value': '오류 복구 시험'}}, 'outputs': {}}
    store.save('2026-10-07', 'wednesday', 0, data)
    server = make_server(store, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, body=None, raw=None, content_type='application/json'):
        payload = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        req = Request(f'http://127.0.0.1:{server.server_port}' + path, data=payload,
                      headers={'Content-Type': content_type})
        try:
            with urlopen(req, timeout=30) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)
    yield store, request
    server.shutdown(); server.server_close(); thread.join()


def build_body():
    return {'date': '2026-10-07', 'service': 'wednesday', 'revision': 1,
            'groups': [['말씀', ['성경 본문', '설교 제목']]]}


@pytest.mark.parametrize('raw', [b'{broken', b'[]', b'null'])
def test_bad_request_preserves_inputs_and_next_request_works(app, raw):
    store, request = app
    before = store.get('2026-10-07', 'wednesday')
    status, result = request('/api/build', raw=raw)
    assert status == 400 and result['error']
    assert store.get('2026-10-07', 'wednesday') == before
    assert request('/api/build', build_body())[0] == 200


@pytest.mark.parametrize('filename', ['broken.hwp', 'broken.hwpx', 'wrong.txt'])
def test_broken_notice_has_text_fallback_and_keeps_saved_input(app, filename):
    store, request = app
    before = store.get('2026-10-07', 'wednesday')
    status, result = request('/api/notice-file?filename=' + filename,
                             raw=b'not a document', content_type='application/octet-stream')
    assert status == 400 and '텍스트' in result['error']
    assert store.get('2026-10-07', 'wednesday') == before


def test_stale_window_cannot_overwrite_newer_input(app):
    store, request = app
    before = store.get('2026-10-07', 'wednesday')
    status, result = request('/api/work?date=2026-10-07&service=wednesday',
                             {'revision': 0, 'data': {'fields': {}}})
    assert status == 409 and result['current']['revision'] == 1
    assert store.get('2026-10-07', 'wednesday') == before


def test_failed_generation_releases_lock_and_retry_works(app, monkeypatch):
    import media_automation.web.original.server as module
    store, request = app
    before = store.get('2026-10-07', 'wednesday')
    real = module.generate
    monkeypatch.setattr(module, 'generate', Mock(side_effect=OSError('disk failure')))
    status, result = request('/api/build', build_body())
    assert status == 500 and '입력은 유지' in result['error']
    assert store.get('2026-10-07', 'wednesday') == before
    monkeypatch.setattr(module, 'generate', real)
    assert request('/api/build', build_body())[0] == 200


def test_double_click_during_generation_is_rejected_without_losing_input(app, monkeypatch):
    import media_automation.web.original.server as module
    store, request = app
    entered, release = threading.Event(), threading.Event()
    results = []
    before = store.get('2026-10-07', 'wednesday')
    def delayed(*args):
        entered.set()
        assert release.wait(5)
        return {'complete': False, 'file_id': 'test-only'}
    monkeypatch.setattr(module, 'generate', delayed)
    worker = threading.Thread(target=lambda: results.append(request('/api/build', build_body())))
    worker.start()
    try:
        assert entered.wait(5)
        status, result = request('/api/build', build_body())
        assert status == 409 and '진행 중' in result['error']
    finally:
        release.set(); worker.join(5)
    assert results[0][0] == 200
    assert request('/api/build', build_body())[0] == 200
    assert store.get('2026-10-07', 'wednesday') == before


def test_pdf_failure_names_pdf_and_retains_inputs(app, monkeypatch):
    import media_automation.web.original.server as module
    store, request = app
    before = store.get('2026-10-07', 'wednesday')
    monkeypatch.setattr(module, 'generate_bulletin', Mock(side_effect=OSError('disk failure')))
    body = build_body(); body['output'] = 'pdf'
    status, result = request('/api/build', body)
    assert status == 500 and '주보 PDF' in result['error'] and '입력은 유지' in result['error']
    assert store.get('2026-10-07', 'wednesday') == before


@pytest.mark.parametrize('fault', ['missing', 'modified', 'corrupt'])
def test_song_file_fault_never_claims_complete(app, fault):
    store, request = app
    store.attach('2026-10-07', 'wednesday', '시작 찬양 1', 'broken.pptx', b'broken zip')
    attachment = store.attachments('2026-10-07', 'wednesday')[0]
    path = Path(store.path).with_suffix('.files') / attachment['digest']
    if fault == 'missing': path.unlink()
    if fault == 'modified': path.write_bytes(b'changed content')
    data = store.get('2026-10-07', 'wednesday')['data']
    data['fields']['시작 찬양 1'] = {'state': 'VALUE', 'value': '시험 찬양'}
    store.save('2026-10-07', 'wednesday', 1, data)
    body = build_body(); body['revision'] = 2
    body['groups'].insert(0, ['시작 찬양', ['시작 찬양 1']])
    status, result = request('/api/build', body)
    if fault == 'corrupt':
        assert status in (400, 500) and result['error']
        assert not list(Path(store.path).with_suffix('.generated').glob('*.pptx'))
    else:
        assert status == 200 and result['complete'] is False
        assert '시작 찬양 1:score_asset' in result['unresolved']
    assert store.get('2026-10-07', 'wednesday')['data'] == data


@pytest.mark.parametrize('reference', ['없는책 1:1', '삼상 18:999', '삼상 18:11~6'])
def test_invalid_bible_reference_is_reported_not_substituted(app, reference):
    store, request = app
    data = store.get('2026-10-07', 'wednesday')['data']
    data['fields']['성경 본문']['value'] = reference
    store.save('2026-10-07', 'wednesday', 1, data)
    body = build_body(); body['revision'] = 2
    status, result = request('/api/build', body)
    assert status == 400 or (status == 200 and result['complete'] is False
                            and any(x.startswith('성경 본문:') for x in result['unresolved']))
    assert store.get('2026-10-07', 'wednesday')['data'] == data


@pytest.mark.parametrize('code', [401, 403, 404, 429, 507, 503])
def test_cloud_fault_is_actionable_and_retry_works(tmp_path, monkeypatch, code):
    cloud = OneDrive(WorkStore(tmp_path / 'work.db'))
    monkeypatch.setattr(cloud, '_token', lambda: 'test-token')
    failed = Mock(status_code=code)
    failed.json.return_value = {'error': 'private diagnostic'}
    recovered = Mock(status_code=200)
    recovered.json.return_value = {'id': 'recovered'}
    cloud.http = Mock(); cloud.http.request.side_effect = [failed, recovered]
    with pytest.raises(CloudError) as error: cloud.graph('/me/drive/root')
    assert 'private diagnostic' not in str(error.value)
    expected = {401: '로그인', 403: '권한', 404: '폴더', 429: '잠시', 507: '공간', 503: '잠시'}
    assert expected[code] in str(error.value)
    assert cloud.graph('/me/drive/root')['id'] == 'recovered'


def test_cloud_timeout_is_sanitized_and_retry_works(tmp_path, monkeypatch):
    cloud = OneDrive(WorkStore(tmp_path / 'work.db'))
    monkeypatch.setattr(cloud, '_token', lambda: 'test-token')
    recovered = Mock(status_code=200); recovered.json.return_value = {'id': 'recovered'}
    cloud.http = Mock(); cloud.http.request.side_effect = [requests.Timeout('secret-url'), recovered]
    with pytest.raises(CloudError, match='잠시') as error: cloud.graph('/me/drive/root')
    assert 'secret-url' not in str(error.value)
    assert cloud.graph('/me/drive/root')['id'] == 'recovered'
