import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest
import yaml

from media_automation.web.application import Application
from media_automation.web.inputs import OPERATIONAL, typed_path
from media_automation.web.server import make_server


def app(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    for name in ('sunday', 'wednesday', 'friday', 'bulletin'):
        (repo / f'{name}.py').write_text('print("not invoked without required inputs")\n')
    return Application(repo, tmp_path / 'jobs')


def intake(date, service, statuses=None):
    statuses = statuses or {}
    fields = {name: {'status': statuses.get(name, 'provided'), 'value': '이번 주 확인값'}
              for name in OPERATIONAL[service]}
    return yaml.safe_dump({'date': {'status': 'provided', 'value': date},
                           'fields': fields, 'review_required': False}, allow_unicode=True).encode()


def test_typed_path_rejects_wrong_slot_and_does_not_guess(tmp_path):
    assert typed_path('wednesday', '2026-10-07', 'score', 'my-song.pptx', 'opening_song_1') == 'input/wednesday/20261007/opening_song_1.pptx'
    assert typed_path('bulletin', '2026-10-11', 'transfer', '전달_주보.hwpx') == 'input/bulletin/20261011/transfer.hwpx'
    with pytest.raises(ValueError):typed_path('sunday', '2026-10-11', 'score', 'wrong.jpg', 'opening_song_1')
    with pytest.raises(ValueError):typed_path('wednesday', '2026-10-07', 'score', 'wrong.pptx', 'special_song')
    with pytest.raises(ValueError):typed_path('friday', '2026-10-09', 'media', 'song.mp3', 'opening_song_1')
    with pytest.raises(ValueError):typed_path('sunday', '2026-10-11', 'notice', '../../escape.txt')
    with pytest.raises(ValueError):typed_path('friday', '2026-10-09', 'notice', 'C:\\escape.txt')


def test_missing_intake_is_blocked_and_none_remains_none(tmp_path):
    a = app(tmp_path); j = a.create('wednesday', '2026-10-07')['job_id']
    a.upload_typed(j, 'notice', 'notice.txt', b'new week')
    a.upload_typed(j, 'source', 'reference.pptx', b'fake reference')
    a.upload_typed(j, 'bible', 'bible.json', '{"translation":"개역개정"}'.encode('utf-8'))
    record = a.get(j)
    assert not record['requirements']['ready']
    with pytest.raises(ValueError, match='필수 자료'): a.start(j)
    a.upload_typed(j, 'intake', 'parsed.yaml', intake('2026-10-07', 'wednesday', {'additional_scripture': 'blank', 'prayer': 'missing'}))
    req = a.get(j)['requirements']
    states = {field['name']: field['state'] for field in req['fields']}
    assert states['additional_scripture'] == 'NONE'
    assert states['prayer'] == 'UNSET'
    assert not req['ready']
    with pytest.raises(FileExistsError):a.upload_typed(j, 'intake', 'another.yaml', intake('2026-10-07', 'wednesday'))


def test_later_revision_cannot_silently_reuse_old_intake(tmp_path):
    a = app(tmp_path); j = a.create('sunday', '2026-10-11')['job_id']
    a.upload_typed(j, 'notice', 'first.txt', b'first')
    a.upload_typed(j, 'source', 'source.pptx', b'week template')
    a.upload_typed(j, 'bible', 'bible.json', b'{}')
    a.upload_typed(j, 'intake', 'intake.yaml', intake('2026-10-11', 'sunday'))
    assert a.get(j)['requirements']['ready']
    a.upload_typed(j, 'revision', 'revision.txt', b'new sermon title')
    a.upload_typed(j, 'revision', 'revision.txt', b'another explicit instruction')
    job = a.get(j)
    assert sum('revision_' in p for p in job['inputs']) == 2
    assert not job['requirements']['ready']
    assert any('수정' in problem for problem in job['requirements']['checks'])
    with pytest.raises(ValueError):a.start(j)


def test_wrong_date_and_bulletin_number_are_blocked(tmp_path):
    a = app(tmp_path); j = a.create('wednesday', '2026-10-07')['job_id']
    a.upload_typed(j, 'notice', 'new.txt', b'a')
    a.upload_typed(j, 'source', 'ref.pptx', b'ref')
    a.upload_typed(j, 'bible', 'text.json', b'{}')
    a.upload_typed(j, 'intake', 'intake.yml', intake('2026-09-30', 'wednesday'))
    assert any('날짜' in s for s in a.get(j)['requirements']['checks'])
    b = a.create('bulletin', '2026-10-11')['job_id']
    with pytest.raises(ValueError):a.set_bulletin_number(b,'13-39 다음호')
    a.upload_typed(b,'transfer','transfer.hwpx', b'fake HWPX (not verified)')
    assert not a.get(b)['requirements']['ready']
    a.set_bulletin_number(b, '13-40')
    assert '명시적으로 확인된 주보 호수' in a.get(b)['requirements']['present']
    with pytest.raises(FileExistsError):a.set_bulletin_number(b, '13-41')


def test_http_typed_files_and_catalog_and_run_gate(tmp_path):
    a = app(tmp_path);server, token = make_server(a,0)
    t = threading.Thread(target=server.serve_forever,daemon=True);t.start()
    base = f'http://127.0.0.1:{server.server_port}'
    headers = {'Authorization': 'Bearer '+token}
    def request(path, data=None):
        return urlopen(Request(base + path,data=data,headers=headers), timeout=3)
    try:
        job = json.load(request('/api/jobs', json.dumps({'date':'2026-10-11','service':'sunday'}).encode()))['job_id']
        kinds = json.load(request(f'/api/jobs/{job}/input-types'))
        assert any(k['kind']=='score' for k in kinds)
        q = urlencode({'kind':'notice','filename':'week.txt'})
        uploaded = json.load(request(f'/api/jobs/{job}/typed-files?{q}', b'week specific'))
        assert 'input/sunday/20261011/notices/initial.txt' in uploaded['inputs']
        with pytest.raises(HTTPError) as err:
            request(f'/api/jobs/{job}/run', b'{}')
        assert err.value.code == 400
        assert not json.load(request(f'/api/jobs/{job}'))['requirements']['ready']
        with pytest.raises(HTTPError) as err:
            request(f'/api/jobs/{job}/typed-files?{urlencode({"kind":"score","filename":"wrong.mp3","slot":"opening_song_1"})}', b'abc')
        assert err.value.code == 400
    finally:
        server.shutdown();server.server_close();t.join()
