"""Repeat operator mistakes for Wednesday, both Friday modes, and Sunday."""
import json
import subprocess
from pathlib import Path
import pytest
from media_automation.web.original.work_store import WorkStore, RevisionConflict
from media_automation.web.original.generation import generate, _asset

PARSER = Path(__file__).resolve().parents[1]/'src/media_automation/web/original/ui/notice-parser.js'
CASES = [('wednesday',None,'2026-10-07'), ('friday','zoom','2026-10-09'),
         ('friday','in_person','2026-10-09'), ('sunday',None,'2026-10-11')]


def parse(method, text, service='friday'):
    script = 'const p=require(process.argv[1]);console.log(JSON.stringify(p[process.argv[2]](process.argv[3],["성경 본문","설교 제목","추가 찬양"],{},process.argv[4])));'
    return json.loads(subprocess.check_output(['node','-e',script,str(PARSER),method,text,service],text=True))


@pytest.fixture(params=CASES, ids=['수요','금요Zoom','금요대면','주일'])
def context(tmp_path, request):
    service, mode, day = request.param
    store = WorkStore(tmp_path/'work.db')
    data = {'fields':{'성경 본문':{'state':'VALUE','value':'단 1:8~9'},
                     '설교 제목':{'state':'VALUE','value':'실수 시험'}}, 'outputs':{}}
    if mode: data['fridayMode'] = mode
    store.save(day,service,0,data)
    body = {'date':day,'service':service,'revision':1,'groups':[['말씀',['성경 본문','설교 제목']]]}
    return store, body


@pytest.mark.parametrize('raw', ['성경 본문\n단 1:8~9 / 시험 제목',
                                '• 말씀 봉독：단 1:8～9 | 시험 제목'])
def test_common_paste_for_each_service(context,raw):
    _, body = context
    fields = parse('parseCommon',raw,body['service'])['fields']
    assert fields['성경 본문']['value'] == '단 1:8~9'
    assert fields['설교 제목']['value'] == '시험 제목'


@pytest.mark.parametrize('marker',['없음','이번 주 없음','해당 없음'])
def test_common_no_song_for_each_service(context,marker):
    _, body = context
    assert parse('parseCommon','추가 찬양: '+marker,body['service'])['fields']['추가 찬양'] == {'state':'NONE','value':''}


def test_stale_save_and_empty_state_for_each_service(context):
    store, body = context; day,service = body['date'],body['service']
    before = store.get(day,service)
    with pytest.raises(RevisionConflict): store.save(day,service,0,{'fields':{}})
    for state,value in [('NONE','옛 곡'),('UNSET','추측'),('VALUE',' ')]:
        with pytest.raises(ValueError): store.save(day,service,1,{'fields':{'찬양':{'state':state,'value':value}}})
    assert store.get(day,service) == before


def test_invalid_date_and_next_week_no_inheritance(context):
    store, body = context
    with pytest.raises(ValueError): store.save('2026-02-30',body['service'],0,{'fields':{}})
    assert '성경 본문' not in store.get('2026-10-18',body['service'])['data'].get('fields',{})


def test_duplicate_upload_and_stale_removal_for_each_service(context):
    store,body = context; day,service = body['date'],body['service']
    a = store.attach(day,service,'찬양 1','a.mp3',b'original')
    b = store.attach(day,service,'찬양 1','a.mp3',b'original')
    assert a['digest'] == b['digest'] and len(store.attachments(day,service)) == 1
    newer = store.attach(day,service,'찬양 1','b.mp3',b'newer')
    store.remove_original({'date':day,'service':service,'slot':'찬양 1','digest':a['digest']})
    assert store.attachments(day,service)[0]['digest'] == newer['digest']


def test_ambiguous_song_is_not_chosen_for_each_service(context):
    store,body = context
    for filename,content in [('a.mp3',b'a'),('b.mp3',b'b')]:
        song = store.register_song({'title':'중복곡'})
        asset = store.attach_song_asset(song['id'],filename,content)
        store.review_asset(song['id'],asset['digest'],{'technical':True,'church':True,'permission':'allowed'})
    assert _asset(store,body,{'key':'찬양 1','content':'중복곡'}) is None


@pytest.mark.parametrize('edition,number',[('new',0),('new',True),('new','79'),(None,79),('typo',79)])
def test_hymn_registration_mistakes_for_each_service(context,edition,number):
    store,_ = context
    with pytest.raises(ValueError): store.register_song({'title':'찬송가','edition':edition,'number':number})
    assert store.songs() == []


def test_missing_and_unknown_label_for_each_service(context):
    _,body = context
    result = parse('parseCommon','설교 제목: 제목\n본뭄: 단 1:8~9',body['service'])
    assert '성경 본문' not in result['fields'] and '추가 찬양' not in result['fields']
    assert '본뭄: 단 1:8~9' in result['unknown']


@pytest.mark.parametrize('fault',['missing_song','invalid_bible','stale_revision'])
def test_actual_generation_does_not_hide_mistake_for_each_service(context,fault):
    store,body = context
    data = store.get(body['date'],body['service'])['data']
    if fault == 'stale_revision':
        body['revision'] = 0
        with pytest.raises(ValueError,match='변경'): generate(store,body)
        return
    if fault == 'invalid_bible': data['fields']['성경 본문']['value'] = '단 1:999'
    else:
        data['fields']['시작 찬양 1'] = {'state':'VALUE','value':'미확보곡'}
        body['groups'].insert(0,['시작 찬양',['시작 찬양 1']])
    body['revision'] = store.save(body['date'],body['service'],1,data)['revision']
    result = generate(store,body)
    assert result['complete'] is False
    label = '성경 본문:' if fault == 'invalid_bible' else '시작 찬양 1:'
    assert any(x.startswith(label) for x in result['unresolved'])
    assert store.get(body['date'],body['service'])['data'] == data


@pytest.mark.parametrize('mode',['zoom','in_person'])
@pytest.mark.parametrize('line',['단 1:8~9 / 시험 제목', '• 단 1：8～9 | 시험 제목', '단 1:8–9 / 시험 제목'])
def test_friday_specific_body_punctuation(mode,line):
    fields = parse('parseFriday','[금요 기도회 순서] 10/9\n'+line)['fields']
    assert fields['성경 본문']['value'].replace('–','~') == '단 1:8~9'
    assert fields['설교 제목']['value'] == '시험 제목'


@pytest.mark.parametrize('mode',['zoom','in_person'])
@pytest.mark.parametrize('marker',['없음','이번 주 없음','해당 없음'])
def test_friday_specific_explicit_absence(mode,marker):
    fields = parse('parseFriday','1) '+marker+'\n단 1:8~9 / 제목\n읽을 말씀: '+marker)['fields']
    assert fields['찬양 1'] == {'state':'NONE','value':''}
    assert fields['추가 말씀'] == {'state':'NONE','value':''}


def test_friday_blank_placeholder_and_explicit_blank_are_distinct():
    fields = parse('parseFriday','1) ~ 2)\n3)\n단 1:8~9 / 제목')['fields']
    assert fields['찬양 1']['state'] == fields['찬양 2']['state'] == 'UNSET'
    assert fields['찬양 3']['state'] == 'NONE'


@pytest.mark.parametrize('marker',['없음','이번 주 없음','해당 없음'])
def test_sunday_bulletin_explicit_no_afternoon(marker):
    assert parse('parseBulletin','오후 예배: '+marker,'sunday')['fields']['오후예배'] == {'state':'NONE','value':''}


def test_sunday_bulletin_three_hymns_and_conflicting_body():
    fields = parse('parseBulletin','찬양: 79, 337, 382장','sunday')['fields']
    assert [fields[k]['value'] for k in ['별도 찬송','봉헌 찬송','결단 찬송']] == ['79장','337장','382장']
    result = parse('parseBulletin','오전 예배 순서\n성경 봉독\n단 1:8~9\n* 교회 소식\n<목장 말씀 나누기>\n<삼상 18:6~11 / 제목>','sunday')
    assert result['fields']['성경 본문']['value'] == '단 1:8~9'
    assert any('다릅니다' in v for v in result['unknown'])


@pytest.mark.parametrize('marker',['없음','이번 주 없음','해당 없음'])
def test_sunday_serving_table_explicit_absence(marker):
    def cell(row,column,text): return dict(row=row,column=column,rowspan=1,colspan=1,text=text)
    table = {'rows':2,'columns':4,'cells':[cell(0,2,'기도'),cell(0,3,'봉헌기도'),
             cell(1,0,'이번 주'),cell(1,1,'2부'),cell(1,2,marker),cell(1,3,'김한섭 집사')]}
    script = 'const p=require(process.argv[1]);console.log(JSON.stringify(p.parseBulletin("",JSON.parse(process.argv[2]))));'
    fields = json.loads(subprocess.check_output(['node','-e',script,str(PARSER),json.dumps([table])],text=True))['fields']
    assert fields['2부 기도 담당자'] == {'state':'NONE','value':''}
    assert fields['2부 봉헌기도 담당자']['value'] == '김한섭'
