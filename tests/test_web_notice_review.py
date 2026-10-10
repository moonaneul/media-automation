"""The review step must not infer weekly information or overwrite confirmed data."""
import json
import shutil
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import yaml

from media_automation.web.application import Application
from media_automation.web.server import make_server

PARSERS = Path(__file__).resolve().parents[1] / 'scripts'


def make_app(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'scripts').mkdir(parents=True)
    for service in ('sunday', 'wednesday', 'friday'):
        name = 'parse_friday_zoom_notice.py' if service == 'friday' else f'parse_{service}_notice.py'
        shutil.copy2(PARSERS / name, repo / 'scripts' / name)
    for name in ('sunday', 'wednesday', 'friday', 'bulletin'):
        (repo / f'{name}.py').write_text('print("stub")\n', encoding='utf-8')
    return Application(repo, tmp_path / 'jobs')


def test_preview_merges_explicit_revision_and_preserves_blank(tmp_path):
    a = make_app(tmp_path)
    job = a.create('wednesday', '2026-10-14')['job_id']
    a.upload_typed(job, 'notice', 'original.txt', (
        '날짜: 2026-10-14\n찬양1: A\n찬양2: B\n찬양3: C\n'
        '기도: 전임자\n추가 찬양: D\n본문: 시 24:3~5\n'
        '설교 제목: 최초 제목\n읽을 말씀:\n결단 찬송: E\n'
    ).encode('utf8'))
    a.upload_typed(job, 'revision', 'updated.txt', '기도: 수정 담당\n설교 제목: 수정 제목\n'.encode())
    draft = a.notice_preview(job)
    values = {f['name']: f for f in draft['fields']}
    assert draft['can_confirm']
    assert values['prayer']['value'] == '수정 담당'
    assert values['sermon_title']['value'] == '수정 제목'
    assert values['scripture']['value'] == '시 24:3~5'
    assert values['additional_scripture']['state'] == 'NONE'
    assert values['opening_song_2']['value'] == 'B'
    assert values['prayer']['source'].endswith('revision_001.txt')
    assert values['opening_song_2']['source'].endswith('initial.txt')
    saved = a.confirm_notice(job)
    relative = 'output/wednesday_intake/wednesday_20261014_intake.yaml'
    assert relative in saved['inputs']
    workspace = a.jobs._directory(job) / 'workspace'
    intake = yaml.safe_load((workspace / relative).read_text())
    assert intake['fields']['additional_scripture']['status'] == 'blank'
    assert intake['fields']['prayer']['value'] == '수정 담당'
    assert len(intake['web_review']['confirmed_sources']) == 2
    with pytest.raises(FileExistsError): a.confirm_notice(job)
    a.upload_typed(job, 'revision', 'later.txt', '설교 제목: 다시 변경\n'.encode())
    assert not a.get(job)['requirements']['ready']


def test_revision_none_and_missing_are_different(tmp_path):
    a = make_app(tmp_path)
    job = a.create('sunday', '2026-10-11')['job_id']
    a.upload_typed(job, 'notice', 'n.txt', '날짜: 2026-10-11\n본문: 삼상 1:1~3\n특송: 이전 특송\n'.encode())
    a.upload_typed(job, 'revision', 'r.txt', '특송:\n'.encode())
    draft = a.notice_preview(job)
    fields = {f['name']: f for f in draft['fields']}
    assert fields['special_song']['state'] == 'NONE'
    assert fields['scripture']['value'] == '삼상 1:1~3'
    assert fields['second_service_prayer']['state'] == 'UNSET'
    assert not draft['can_confirm']
    with pytest.raises(ValueError): a.confirm_notice(job)


def test_unknown_or_multislot_revision_needs_review(tmp_path):
    a = make_app(tmp_path)
    job = a.create('sunday', '2026-10-11')['job_id']
    a.upload_typed(job, 'notice', 'n.txt', '날짜: 2026-10-11\n찬양1: 지정곡\n'.encode())
    a.upload_typed(job, 'revision', 'r.txt', '찬양3(인도자)\n'.encode())
    draft = a.notice_preview(job)
    assert any('다중 항목' in r.get('reason', '') for r in draft['review_items'])
    assert next(f for f in draft['fields'] if f['name']=='opening_song_1')['value']=='지정곡'
    assert next(f for f in draft['fields'] if f['name']=='opening_song_2')['state']=='UNSET'
    assert not draft['can_confirm']


def test_no_date_inference_and_explicit_wrong_date_blocked(tmp_path):
    a = make_app(tmp_path)
    j1 = a.create('wednesday', '2026-10-14')['job_id']
    a.upload_typed(j1, 'notice', 'notice.txt', '설교 제목: 입력 제목\n'.encode())
    assert a.notice_preview(j1)['date_state']=='UNSET'
    assert not a.notice_preview(j1)['can_confirm']
    j2 = a.create('wednesday', '2026-10-14')['job_id']
    a.upload_typed(j2, 'notice', 'notice.txt', '날짜: 2026-10-07\n설교 제목: 입력 제목\n'.encode())
    assert any('날짜' in x for x in a.notice_preview(j2)['checks'])


def test_friday_implicit_step_not_a_revision_of_explicit_none(tmp_path):
    a = make_app(tmp_path)
    job = a.create('friday','2026-10-16')['job_id']
    a.upload_typed(job,'notice','notice.txt', '날짜: 2026-10-16\n개인 기도:\n본문: 요 1:1~3\n'.encode())
    a.upload_typed(job,'revision','rev.txt', '설교 제목: 새 제목\n'.encode())
    fields = {f['name']: f for f in a.notice_preview(job)['fields']}
    assert fields['personal_prayer']['state']=='NONE'
    assert fields['sermon_title']['value']=='새 제목'


def test_notice_api_does_not_confirm_unresolved_content(tmp_path):
    a = make_app(tmp_path)
    server, token = make_server(a,0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f'http://127.0.0.1:{server.server_port}'
    headers = {'Authorization':'Bearer '+token}
    def req(path, body=None):
        return urlopen(Request(root+path, data=body, headers=headers),timeout=3)
    try:
        j = a.create('wednesday','2026-10-14')['job_id']
        a.upload_typed(j,'notice','n.txt','날짜: 2026-10-14\n이 문장은 무엇인가\n'.encode())
        data=json.load(req(f'/api/jobs/{j}/notice-preview'))
        assert not data['can_confirm']
        assert any('무엇인가' in x['line'] for x in data['review_items'])
        with pytest.raises(HTTPError) as error:
            req(f'/api/jobs/{j}/confirm-notice',b'{}')
        assert error.value.code==400
        assert not any('intake.yaml' in x for x in a.get(j)['inputs'])
    finally:
        server.shutdown();server.server_close();thread.join()


def _ready_sunday_files(a, sunday, date='2026-10-11'):
    from media_automation.web.inputs import OPERATIONAL
    fields = {name: {'status': 'provided', 'value': '명시 확인'} for name in OPERATIONAL['sunday']}
    fields['sermon_title']['value'] = '예시 설교 제목'
    fields['scripture']['value'] = '요 3:16-18'
    fields['special_song'] = {'status': 'blank', 'value': None}
    fields['additional_scripture'] = {'status': 'blank', 'value': None}
    intake = {'date': {'status': 'provided', 'value':date},
              'fields': fields, 'review_required': False}
    a.upload_typed(sunday, 'intake', 'intake.yaml',
                   yaml.safe_dump(intake, allow_unicode=True).encode())
    weekly = yaml.safe_load((Path(__file__).resolve().parents[1] / 'samples/weekly/sunday.example.yaml').read_text())
    weekly['date'] = date
    token = date.replace('-','')
    for suffix in ('-base.yaml','.yaml'):
        a.upload(sunday, f'output/sunday_intake/sunday-{token}{suffix}',
                 yaml.safe_dump(weekly,allow_unicode=True).encode())
    rec = a.get(sunday)
    rec['state'] = 'generated'
    a.jobs._save(a.jobs._directory(sunday), rec)


def test_explicit_same_week_import_provenance_and_no_overwrite(tmp_path):
    a = make_app(tmp_path)
    sunday = a.create('sunday','2026-10-11')['job_id']
    bulletin = a.create('bulletin','2026-10-11')['job_id']
    _ready_sunday_files(a, sunday)
    response = a.import_sunday_week(bulletin, sunday)
    assert response['state'] == 'needs_input'
    assert response['sunday_source_job_id'] == sunday
    assert len([name for name in response['inputs'] if 'sunday_intake' in name]) == 3
    common = a.sunday_common_summary(bulletin)
    assert common['consistent']
    assert next(f for f in common['fields'] if f['name']=='sermon_title')['value']=='예시 설교 제목'
    with pytest.raises(FileExistsError):
        a.import_sunday_week(bulletin,sunday)
    assert not a.get(bulletin)['requirements']['ready']  # transfer and bulletin number remain missing


def test_refuse_cross_week_and_not_generated_sunday_copy(tmp_path):
    a = make_app(tmp_path)
    sunday = a.create('sunday','2026-10-11')['job_id']
    target = a.create('bulletin','2026-10-18')['job_id']
    with pytest.raises(ValueError,match='주차'):
        a.import_sunday_week(target, sunday)
    same = a.create('bulletin','2026-10-11')['job_id']
    with pytest.raises(ValueError,match='생성'):
        a.import_sunday_week(same,sunday)


def test_refuse_same_week_but_edited_sermon_mismatch(tmp_path):
    a = make_app(tmp_path)
    sunday = a.create('sunday','2026-10-11')['job_id']
    bulletin = a.create('bulletin','2026-10-11')['job_id']
    _ready_sunday_files(a, sunday)
    token='20261011'
    workspace = a.jobs._directory(sunday)/'workspace'
    weekly = workspace / f'output/sunday_intake/sunday-{token}.yaml'
    raw = yaml.safe_load(weekly.read_text())
    raw['worship']['sermon_title']['text'] = '서로 다른 제목'
    weekly.write_text(yaml.safe_dump(raw,allow_unicode=True))
    with pytest.raises(ValueError,match='공통 데이터 불일치'):
        a.import_sunday_week(bulletin,sunday)
    assert not [name for name in a.get(bulletin)['inputs'] if 'sunday_intake' in name]


def test_editing_confirmed_notice_bytes_breaks_review_provenance(tmp_path):
    a = make_app(tmp_path)
    job = a.create('wednesday', '2026-10-14')['job_id']
    a.upload_typed(job, 'notice', 'notice.txt', (
        '날짜: 2026-10-14\n찬양1: A\n찬양2: B\n찬양3: C\n'
        '기도: 사람\n추가 찬양: D\n본문: 시 24:3~5\n'
        '설교 제목: 제목\n읽을 말씀:\n결단 찬송: E\n'
    ).encode())
    assert a.notice_preview(job)['can_confirm']
    a.confirm_notice(job)
    workspace = a.jobs._directory(job) / 'workspace'
    notice = workspace / 'input/wednesday/20261014/notices/initial.txt'
    notice.write_text(notice.read_text() + '\n추가 안내: 바뀜\n')
    assert any('확정 시점' in error for error in a.get(job)['requirements']['checks'])


def test_bulletin_gate_rejects_mismatched_sunday_intake_date(tmp_path):
    a = make_app(tmp_path)
    bulletin = a.create('bulletin','2026-10-11')['job_id']
    intake = {'date':{'status':'provided','value':'2026-09-27'}, 'fields':{},'review_required':False}
    a.upload_typed(bulletin, 'sunday_intake', 'intake.yaml',yaml.safe_dump(intake).encode())
    assert any('날짜' in p for p in a.get(bulletin)['requirements']['checks'])


def test_http_common_data_import_explicit_same_week(tmp_path):
    a = make_app(tmp_path)
    sunday = a.create('sunday','2026-10-11')['job_id']
    bulletin = a.create('bulletin','2026-10-11')['job_id']
    _ready_sunday_files(a,sunday)
    server, token = make_server(a,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path, body=None):
        return urlopen(Request(base+path,data=body,headers={'Authorization':'Bearer '+token}),timeout=3)
    try:
        payload=json.dumps({'sunday_job_id':sunday}).encode()
        data=json.load(request(f'/api/jobs/{bulletin}/import-sunday-week',payload))
        assert data['sunday_source_job_id']==sunday
        report=json.load(request(f'/api/jobs/{bulletin}/sunday-common'))
        assert report['consistent']
        assert any(field['name']=='scripture' for field in report['fields'])
        with pytest.raises(HTTPError) as err:
            request(f'/api/jobs/{bulletin}/import-sunday-week',payload)
        assert err.value.code==400
    finally:
        server.shutdown();server.server_close();thread.join()
