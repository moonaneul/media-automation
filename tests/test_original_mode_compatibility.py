import json,subprocess
from pathlib import Path
import pytest
from media_automation.web.original.work_store import WorkStore
from media_automation.web.original.generation import generate,compatible_original

@pytest.mark.parametrize('service,mode,suffix,expected',[('friday','zoom','.mp4',True),('friday','in_person','.mp4',False),('friday','in_person','.pptx',True),('sunday','zoom','.mp4',False),('sunday','zoom','.ppt',True),('friday','zoom','.pptx',False)])
def test_mode_contract(service,mode,suffix,expected):
    assert compatible_original('original'+suffix,service,mode,'찬양 1') is expected

@pytest.mark.parametrize('state',['VALUE','UNSET'])
def test_existing_zoom_attachment_is_reported_missing_in_person(tmp_path,state):
    store=WorkStore(tmp_path/'work.db');date='2026-10-09'
    fields={k:{'state':'VALUE','value':v} for k,v in [('성경 본문','단 1:8'),('설교 제목','시험')]}
    fields['찬양 1']={'state':state,'value':'임재' if state=='VALUE' else ''}
    store.save(date,'friday',0,{'fields':fields,'fridayMode':'in_person'})
    original=store.attach(date,'friday','찬양 1','original.mp4',b'video-fixture')
    result=generate(store,{'date':date,'service':'friday','revision':1,'groups':[['찬양',['찬양 1']],['말씀',['성경 본문','설교 제목']]]})
    report=json.loads((Path(store.path).with_suffix('.generated')/(result['file_id']+'.json')).read_text())
    assert report['connections']['찬양 1']['status']=='incompatible_format'
    item=next(m for m in report['mapping'] if m['key']=='찬양 1')
    assert item['status'] in ('missing_song_asset','input_pending')
    assert not result['complete']
    assert store.attachments(date,'friday')[0]['digest']==original['digest']


def test_ui_rejects_incompatible_original_and_missing_title():
    html=Path('src/media_automation/web/original/ui/index.html').read_text()
    functions=html[html.index('function originalCompatible('):html.index('function assets()')]
    code="const window={addEventListener(){}};const service='friday';function fridayMode(){return 'in_person';}"+functions+"console.log(JSON.stringify([originalStatus({filename:'song.mp4'},'찬양 1',{}),originalStatus({filename:'song.pptx'},'찬양 1',{}),originalCompatible('song.pptx','찬양 1')]));"
    result=json.loads(subprocess.check_output(['node','-e',code],text=True))
    assert result==['자료 미연결 · 현재 방식에 맞지 않는 파일','원본 보관됨 · 곡 입력 필요',True]


def test_library_selects_score_without_video_causing_ambiguity(tmp_path):
    from media_automation.web.original.generation import _asset
    store=WorkStore(tmp_path/'work.db')
    store.save('2026-10-09','friday',0,{'fridayMode':'in_person'})
    song=store.register_song({'title':'임재','aliases':[]})
    score=store.attach_song_asset(song['id'],'score.pptx',b'score-fixture')
    video=store.attach_song_asset(song['id'],'video.mp4',b'video-fixture')
    for asset in (score,video):store.review_asset(song['id'],asset['digest'],{'technical':True,'church':True,'permission':'allowed'})
    result=_asset(store,{'date':'2026-10-09','service':'friday'},{'key':'찬양 1','content':'임재'})
    assert result[1]=='.pptx'
    assert result[2]['digest']==score['digest']
