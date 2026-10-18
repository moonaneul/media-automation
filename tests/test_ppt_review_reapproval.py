"""Explicitly revoke and renew PPT review for one generated file, preserving cloud artifacts.

All checks run against a localhost mock HTTP server and temporary SQLite DB;
no real OneDrive login, private worship source or remote transfer is used.
"""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from media_automation.web.original.generation import FRIDAY_TYPOGRAPHY_VERSION, render_configuration
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore


def post(url,body):
    data=json.dumps(body,ensure_ascii=False).encode('utf-8')
    with urlopen(Request(url,data=data,method='POST',
                         headers={'Content-Type':'application/json'}),timeout=5) as response:
        return json.load(response)


@pytest.fixture
def reviewed_server(tmp_path):
    store=WorkStore(tmp_path/'review.db')
    date='2026-10-16';service='friday';ident='a'*32
    unresolved=['성경 본문:bible_review','추가 말씀 1:bible_review']
    fields={'성경 본문':{'state':'VALUE','value':'창 1:1'},
            '추가 말씀 1':{'state':'VALUE','value':'창 1:2'}}
    ppt={'fileId':ident,'changed':False,'complete':True,
         'unresolved':unresolved,
         'archiveStatus':'uploaded','cloudVerified':True,
         'cloudItem':{'id':'remote-file','name':'approved.pptx'},
         'confirmedManualReviews':unresolved[:]}
    record={'fields':fields,'fridayMode':'zoom','outputs':{'ppt':ppt}}
    revision=store.save(date,service,0,record)['revision']
    directory=Path(store.path).with_suffix('.generated')
    directory.mkdir()
    path=directory/(ident+'.pptx')
    path.write_bytes(b'previous approved PPT - keep unchanged')
    (directory/(ident+'.json')).write_text(json.dumps({
        'date':date,'service':service,'format':'pptx','fields':fields,
        'unresolved':unresolved,'attachments':[],
        'typography_version':FRIDAY_TYPOGRAPHY_VERSION,
        'render_configuration':render_configuration(record),
    },ensure_ascii=False))
    server=make_server(store,0)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        yield store,f'http://127.0.0.1:{server.server_port}',date,service,ident,revision,path,unresolved
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=4)


def test_legacy_completion_can_be_cancelled_and_reapproved_without_cloud_duplication(reviewed_server):
    store,url,date,service,ident,revision,path,unresolved=reviewed_server
    original=path.read_bytes()
    before=store.get(date,service)['data']['outputs']['ppt']
    assert before['complete'] and 'reviewedAt' not in before # old review record
    canceled=post(url+'/api/reopen-ppt-review', {
        'date':date,'service':service,'revision':revision,
        'file_id':ident,'confirmed':True,
    })
    revoked=canceled['data']['outputs']['ppt']
    assert revoked['complete'] is False
    assert revoked['reviewRevokedAt']
    for name in ('archiveStatus','cloudVerified','cloudItem','confirmedManualReviews'):
        assert revoked[name]==before[name],name
    assert path.read_bytes()==original
    assert store.get(date,service)['data']['outputs']['ppt']['complete'] is False

    approved=post(url+'/api/complete',{
        'date':date,'service':service,'revision':canceled['revision'],
        'file_id':ident,'reviewed':True,
        'acknowledged_unresolved':unresolved,
        'confirmed_manual_reviews':unresolved,
    })
    new=approved['data']['outputs']['ppt']
    assert new['complete'] is True
    assert new['reviewedAt'] # explicit time-stamped approval
    assert 'reviewRevokedAt' not in new
    assert new['confirmedManualReviews']==unresolved
    for name in ('archiveStatus','cloudVerified','cloudItem'):
        assert new[name]==before[name],name
    assert path.read_bytes()==original
    assert len(list(path.parent.glob('*.pptx')))==1


def test_re_review_existing_completed_ppt_does_not_reset_archive(reviewed_server):
    store,url,date,service,ident,revision,path,unresolved=reviewed_server
    result=post(url+'/api/complete',{
        'date':date,'service':service,'revision':revision,
        'file_id':ident,'reviewed':True,
        'acknowledged_unresolved':unresolved,
        'confirmed_manual_reviews':unresolved
    })
    reviewed=result['data']['outputs']['ppt']
    assert reviewed['complete'] and reviewed['reviewedAt']
    assert reviewed['archiveStatus']=='uploaded'
    assert reviewed['cloudVerified'] is True
    assert reviewed['cloudItem']['id']=='remote-file'


def test_reopening_requires_explicit_confirmation_and_matching_file(reviewed_server):
    store,url,date,service,ident,revision,path,unresolved=reviewed_server
    for wrong in [
        {'file_id':ident,'confirmed':False},
        {'file_id':'f'*32,'confirmed':True},
    ]:
        req={'date':date,'service':service,'revision':revision,**wrong}
        with pytest.raises(HTTPError) as failure:
            post(url+'/api/reopen-ppt-review',req)
        assert failure.value.code in (400,409)
        assert store.get(date,service)['data']['outputs']['ppt']['complete'] is True
    assert path.exists()


def test_re_review_still_requires_manual_bible_confirmation(reviewed_server):
    store,url,date,service,ident,revision,path,unresolved=reviewed_server
    canceled=post(url+'/api/reopen-ppt-review',{
        'date':date,'service':service,'revision':revision,
        'file_id':ident,'confirmed':True
    })
    with pytest.raises(HTTPError) as failure:
        post(url+'/api/complete',{
            'date':date,'service':service,'revision':canceled['revision'],
            'file_id':ident,'reviewed':True,
            'acknowledged_unresolved':unresolved,
            'confirmed_manual_reviews':[]
        })
    assert failure.value.code==400
    assert store.get(date,service)['data']['outputs']['ppt']['complete'] is False


def test_reopen_uses_revision_conflict_to_reject_stale_window(reviewed_server):
    store,url,date,service,ident,revision,path,unresolved=reviewed_server
    current=store.get(date,service)
    store.save(date,service,current['revision'],current['data'])
    with pytest.raises(HTTPError) as failure:
        post(url+'/api/reopen-ppt-review',{
            'date':date,'service':service,'revision':revision,
            'file_id':ident,'confirmed':True
        })
    assert failure.value.code==409
    assert store.get(date,service)['data']['outputs']['ppt']['complete'] is True


def test_review_ui_offers_cancel_and_rereview_without_claiming_automatic_bible_check():
    html=Path('src/media_automation/web/original/ui/index.html').read_text('utf-8')
    assert 'id="ppt-review-cancel"' in html
    assert 'id="ppt-review-history"' in html
    assert "'PPT 다시 검수'" in html
    assert 'PPT 검수 완료 기록' in html
    assert '이번 화면에서 새로 검수했다는 뜻은 아닙니다.' in html
    assert "fetch('/api/reopen-ppt-review'" in html
    assert 'confirmed_manual_reviews:manualReview' in html
    assert '자동 검증 아님' in html
    assert 'if(previouslyComplete||previousCloudRecord)' in html
