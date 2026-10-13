import hashlib
import json
import sqlite3
import pytest
from media_automation.web.original.work_store import WorkStore
from media_automation.web.original.migration import merge_stores


def stores(tmp_path):
    a=WorkStore(tmp_path/'a.db');b=WorkStore(tmp_path/'b.db')
    a.save('2026-10-11','sunday',0,{'fields':{'본문':{'state':'VALUE','value':'단 1:8~9'}}})
    b.save('2026-10-11','sunday',0,{'fields':{'본문':{'state':'VALUE','value':'마 5:43~48'}}})
    b.save('2026-10-09','friday',0,{'fields':{}})
    b.attach('2026-10-09','friday','찬양 1','song.mp4',b'video-bytes')
    return a,b


def test_merge_preserves_sources_and_archives_explicit_conflict(tmp_path):
    a,b=stores(tmp_path)
    before=[hashlib.sha256(open(s.path,'rb').read()).hexdigest() for s in (a,b)]
    path,report=merge_stores(a.path,b.path,tmp_path/'combined',keep_primary_works=[('2026-10-11','sunday')])
    result=WorkStore(path)
    assert result.get('2026-10-11','sunday')==a.get('2026-10-11','sunday')
    assert result.get('2026-10-09','friday')==b.get('2026-10-09','friday')
    with sqlite3.connect(path) as db:
        payload=db.execute('SELECT payload FROM migration_work_history').fetchone()[0]
    assert json.loads(payload)==b.get('2026-10-11','sunday')['data']
    assert len(result.attachments('2026-10-09','friday'))==1
    assert before==[hashlib.sha256(open(s.path,'rb').read()).hexdigest() for s in (a,b)]
    assert report['archived_work_conflicts']==[['2026-10-11','sunday']]


def test_unapproved_conflict_never_publishes(tmp_path):
    a,b=stores(tmp_path)
    with pytest.raises(ValueError,match='충돌'):
        merge_stores(a.path,b.path,tmp_path/'combined')
    assert not (tmp_path/'combined').exists()


def test_file_collision_aborts_even_with_approved_work_conflict(tmp_path):
    a,b=stores(tmp_path)
    from pathlib import Path
    for store,content in [(a,b'first'),(b,b'second')]:
        folder=Path(store.path).with_suffix('.generated');folder.mkdir();(folder/'same.pptx').write_bytes(content)
    with pytest.raises(ValueError,match='다른 자료'):
        merge_stores(a.path,b.path,tmp_path/'combined',keep_primary_works=[('2026-10-11','sunday')])
    assert not (tmp_path/'combined').exists()


def test_friday_title_and_scripture_share_screen_and_numbers_stay_explicit():
    from media_automation.web.original.production_order import build_order, combine_friday_prayers
    fields={
        '첫 기도 제목 1':{'state':'VALUE','value':'주님을 바라보도록'},
        '첫 기도 내용 1':{'state':'VALUE','value':'시 62:1'},
        '첫 기도 제목 2':{'state':'VALUE','value':'믿음으로 나아가도록'},
        '첫 기도 내용 2':{'state':'NONE','value':''},
    }
    order=build_order([['첫 기도',list(fields)]],fields,'friday')
    folded=combine_friday_prayers(order,{'첫 기도 내용 1':{'resolved_content':'[1] 확인된 인용문','text_review_pending':True}})
    prayers=[b for b in folded if '제목' in b['key']]
    assert prayers[0]['content']=='1. 주님을 바라보도록\n\n[1] 확인된 인용문'
    assert prayers[1]['content']=='2. 믿음으로 나아가도록'
    assert prayers[0]['supporting_review_pending']
    assert not any('내용' in b['key'] for b in folded)
    assert folded[-1]['key']=='개인 기도'
