"""Common operator mistakes, isolated from church inputs and originals."""
import json
import subprocess
from pathlib import Path
import pytest
from media_automation.web.original.work_store import WorkStore
from media_automation.web.original.generation import _asset

PARSER = Path(__file__).resolve().parents[1] / 'src/media_automation/web/original/ui/notice-parser.js'


def parse(raw, method='parseCommon'):
    script = 'const p=require(process.argv[1]);console.log(JSON.stringify(p[process.argv[2]](process.argv[3],["성경 본문","설교 제목","추가 찬양"],{},"wednesday")));'
    return json.loads(subprocess.check_output(['node', '-e', script, str(PARSER), method, raw], text=True))


@pytest.mark.parametrize('raw', [
    '• 말씀 봉독：삼상 18:6～11 / 질투에 사로잡히면',
    '  말씀   봉독 : 삼상 18:6~11 | 질투에 사로잡히면 ',
    '성경 본문\r\n삼상 18:6~11 / 질투에 사로잡히면',
    '본문: 삼상 18:6~11 / 질투에 사로잡히면\n설교 제목: 수정된 제목',
])
def test_pasted_notice_spacing_and_latest_title(raw):
    fields = parse(raw)['fields']
    assert fields['성경 본문']['value'].replace('～','~') == '삼상 18:6~11'
    assert fields['설교 제목']['value'] == ('수정된 제목' if '수정된' in raw else '질투에 사로잡히면')


@pytest.mark.parametrize('marker', ['', '없음', '이번 주 없음', '해당 없음'])
@pytest.mark.parametrize('method,label', [('parseCommon','추가 찬양'), ('parseWednesday','찬양 1곡')])
def test_explicit_no_song_is_none_not_a_song_name(marker, method, label):
    field = parse(label + ': ' + marker, method)['fields']['추가 찬양']
    assert field == {'state': 'NONE', 'value': ''}


def test_missing_field_and_explicit_empty_are_different():
    assert '추가 찬양' not in parse('설교 제목: 제목')['fields']
    assert parse('추가 찬양:')['fields']['추가 찬양']['state'] == 'NONE'


@pytest.mark.parametrize('next_label', ['설교 제목: 제목', '설교 제목\n제목'])
def test_empty_heading_before_next_item_is_explicit_none(next_label):
    fields = parse('추가 찬양\n' + next_label)['fields']
    assert fields['추가 찬양'] == {'state':'NONE','value':''}
    assert fields['설교 제목']['value'] == '제목'


def test_unknown_label_is_kept_for_review_not_silently_discarded():
    result = parse('본뭄: 삼상 18:6~11\n설교 제목: 제목')
    assert '성경 본문' not in result['fields']
    assert '본뭄: 삼상 18:6~11' in result['unknown']


def test_person_title_and_multiple_names_are_not_part_of_lookup_name():
    fields = parse('기도: 김한섭 집사님\n폐회 기도: 이은철 목사님', 'parseWednesday')['fields']
    assert fields['기도 담당자']['value'] == '김한섭'
    assert fields['폐회 기도 담당자']['value'] == '이은철'


@pytest.mark.parametrize('day,service', [('2026-02-30','sunday'), ('2026-1-7','wednesday'),
                                       ('2026/10/11','sunday'), ('2026-10-11','typo')])
def test_wrong_date_or_service_does_not_create_record(tmp_path, day, service):
    store = WorkStore(tmp_path/'work.db')
    with pytest.raises(ValueError): store.save(day, service, 0, {'fields': {}})
    with store.connect() as db: assert db.execute('SELECT count(*) FROM works').fetchone()[0] == 0


@pytest.mark.parametrize('field', [{'state':'VALUE','value':'   '}, {'state':'NONE','value':'지난주 곡'},
                                  {'state':'UNSET','value':'추측한 곡'}])
def test_conflicting_checkbox_and_text_preserves_previous_save(tmp_path, field):
    store = WorkStore(tmp_path/'work.db'); store.save('2026-10-07','wednesday',0,{'fields':{}})
    before = store.get('2026-10-07','wednesday')
    with pytest.raises(ValueError): store.save('2026-10-07','wednesday',1,{'fields':{'찬양':field}})
    assert store.get('2026-10-07','wednesday') == before


def test_other_week_does_not_inherit_this_week(tmp_path):
    store = WorkStore(tmp_path/'work.db')
    store.save('2026-10-07','wednesday',0,{'fields':{'기도 담당자':{'state':'VALUE','value':'한미선'}}})
    assert store.get('2026-10-14','wednesday')['data'] == {}


def test_double_upload_and_stale_delete_preserve_replacement(tmp_path):
    store = WorkStore(tmp_path/'work.db')
    first = store.attach('2026-10-07','wednesday','찬양 1','a.mp3',b'original')
    second = store.attach('2026-10-07','wednesday','찬양 1','a.mp3',b'original')
    assert first['digest'] == second['digest'] and len(store.attachments('2026-10-07','wednesday')) == 1
    replacement = store.attach('2026-10-07','wednesday','찬양 1','b.mp3',b'replacement')
    store.remove_original({'date':'2026-10-07','service':'wednesday','slot':'찬양 1','digest':first['digest']})
    assert store.attachments('2026-10-07','wednesday')[0]['digest'] == replacement['digest']


@pytest.mark.parametrize('edition,number', [('new',0),('new',True),('new','79'),(None,79),('typo',79)])
def test_mistyped_hymn_registration_is_rejected(tmp_path, edition, number):
    store = WorkStore(tmp_path/'work.db')
    with pytest.raises(ValueError): store.register_song({'title':'찬송가','edition':edition,'number':number})
    assert store.songs() == []


def test_ambiguous_identical_titles_are_not_automatically_chosen(tmp_path):
    store = WorkStore(tmp_path/'work.db'); store.save('2026-10-07','wednesday',0,{'fields':{}})
    for name, content in [('a.mp3',b'a'),('b.mp3',b'b')]:
        song = store.register_song({'title':'같은 제목'})
        asset = store.attach_song_asset(song['id'],name,content)
        store.review_asset(song['id'],asset['digest'],{'technical':True,'church':True,'permission':'allowed'})
    assert _asset(store,{'date':'2026-10-07','service':'wednesday'}, {'key':'찬양 1','content':'같은 제목'}) is None
