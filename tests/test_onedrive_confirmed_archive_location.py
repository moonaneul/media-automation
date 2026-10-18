"""A Microsoft HTTP 200 response is not evidence of a file in 00.주보.

Read-back must use the owner drive, the exact selected folder and a new
folder listing before marking any weekly output as uploaded. No live Graph.
"""
from pathlib import Path

import pytest

from media_automation.web.original.onedrive import CloudError, OneDrive
from media_automation.web.original.work_store import WorkStore


@pytest.fixture
def prepared(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    day='2026-10-18'
    ident='a'*32
    data=b'%PDF-1.4\nmock church bulletin\n%%EOF\n'
    store.save(day,'sunday',0,{'fields':{},'outputs':{
        'ppt':{},'pdf':{'fileId':ident,'complete':True,'changed':False},
    }})
    generated=Path(store.path).with_suffix('.generated')
    generated.mkdir()
    (generated/(ident+'.pdf')).write_bytes(data)
    cloud=OneDrive(store)
    with cloud.lock:
        cloud._write({'client_id':'mock','account':{'username':'test@example.invalid'},
                      'folders':{'source':{'id':'score-source','name':'악보 PPT'}},
                      'shared_archives':{'archive_sunday_pdf':{
                          'id':'team-folder','drive_id':'owner-drive','name':'00.주보','redeemed':True,
                      }}})
    return cloud,day,ident,data


def fake_graph(cloud,monkeypatch,day,ident,data,*,listed=True,parent='team-folder',
               full_name=True,size_match=True,item_found=True):
    filename=f'{day}_sunday_pdf_{ident}.pdf'
    size=len(data) if size_match else len(data)+1
    item={'id':'returned-item','name':filename if full_name else 'other.pdf',
          'size':size,'file':{},'webUrl':'https://onedrive.live.com/?id=returned-item',
          'parentReference':{'driveId':'owner-drive','id':parent}}
    folder={'id':'team-folder','name':'00.주보','folder':{},
            'webUrl':'https://onedrive.live.com/?id=team-folder'}
    def graph(path,*_a,**_kw):
        if path=='/drives/owner-drive/items/team-folder':return folder
        if path=='/drives/owner-drive/items/returned-item':
            if not item_found:raise CloudError('OneDrive 파일·폴더를 찾지 못했습니다.')
            return item
        if path=='/drives/owner-drive/items/team-folder/children?$top=200':
            return {'value':[item] if listed else []}
        raise AssertionError(path)
    monkeypatch.setattr(cloud,'graph',graph)
    return item


def test_verified_real_folder_upload_can_be_audited_and_opened(prepared,monkeypatch):
    cloud,day,ident,data=prepared
    remote=fake_graph(cloud,monkeypatch,day,ident,data)
    monkeypatch.setattr(cloud,'upload_file',lambda *_args,**_kwargs:dict(remote))
    result=cloud.archive(day,'sunday','pdf')
    assert result['verified'] is True
    assert result['target']=='00.주보'
    assert result['itemUrl'].startswith('https://onedrive.live.com/')
    output=cloud.store.get(day,'sunday')['data']['outputs']['pdf']
    assert output['archiveStatus']=='uploaded'
    assert output['cloudVerified'] is True
    checked=cloud.verify_saved_archive(day,'sunday','pdf')
    assert checked['verified'] is True
    assert checked['target']=='00.주보'
    assert checked['targetUrl'].startswith('https://onedrive.live.com/')
    assert checked['itemUrl'].startswith('https://onedrive.live.com/')
    assert cloud.store.get(day,'sunday')['data']['outputs']['pdf']==output


@pytest.mark.parametrize('issue,reason',[
    ('unlisted','폴더 목록'),
    ('wrong_folder','실제 저장 위치'),
    ('wrong_size','생성본과 일치하지'),
    ('wrong_name','생성본과 일치하지'),
])
def test_microsoft_success_in_wrong_location_never_marks_uploaded(
    prepared,monkeypatch,issue,reason
):
    cloud,day,ident,data=prepared
    remote=fake_graph(cloud,monkeypatch,day,ident,data,
                      listed=issue!='unlisted',
                      parent='different-folder' if issue=='wrong_folder' else 'team-folder',
                      size_match=issue!='wrong_size',
                      full_name=issue!='wrong_name')
    monkeypatch.setattr(cloud,'upload_file',lambda *_args,**_kwargs:dict(remote))
    # read-back retries may be eventually consistent, but still must fail.
    monkeypatch.setattr('media_automation.web.original.onedrive.time.sleep',lambda *_:None)
    with pytest.raises(CloudError,match=reason):
        cloud.archive(day,'sunday','pdf')
    saved=cloud.store.get(day,'sunday')['data']['outputs']['pdf']
    assert saved['complete'] is True
    assert saved.get('archiveStatus')!='uploaded'
    assert saved.get('cloudVerified') is not True
    with cloud.store.connect() as db:
        tables=[row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert 'cloud_archives' not in tables


def test_previous_false_positive_can_be_checked_without_another_upload(prepared,monkeypatch):
    cloud,day,ident,data=prepared
    fake_graph(cloud,monkeypatch,day,ident,data,item_found=False)
    current=cloud.store.get(day,'sunday')
    old=current['data']
    old['outputs']['pdf'].update({'archiveStatus':'uploaded',
                                  'cloudItem':{'id':'returned-item','name':f'{day}_sunday_pdf_{ident}.pdf'}})
    cloud.store.save(day,'sunday',current['revision'],old)
    result=cloud.verify_saved_archive(day,'sunday','pdf')
    assert result['verified'] is False
    assert result['status']=='not_in_target'
    assert result['target']=='00.주보'
    assert '실제 공유폴더' in result['message']
    assert 'targetUrl' in result
    assert cloud.store.get(day,'sunday')['data']['outputs']['pdf']['complete'] is True
    assert cloud.store.get(day,'sunday')['data']['outputs']['pdf']['archiveStatus']=='uploaded'


def test_existing_success_without_cloud_item_reports_unverified(prepared,monkeypatch):
    cloud,day,ident,data=prepared
    fake_graph(cloud,monkeypatch,day,ident,data)
    response=cloud.verify_saved_archive(day,'sunday','pdf')
    assert response['status']=='no_record' and not response['verified']


def test_unsafe_microsoft_item_url_not_rendered(prepared,monkeypatch):
    cloud,day,ident,data=prepared
    remote=fake_graph(cloud,monkeypatch,day,ident,data)
    remote['webUrl']='https://onedrive.live.com.evil.example/credential'
    monkeypatch.setattr(cloud,'upload_file',lambda *_args,**_kwargs:dict(remote))
    result=cloud.archive(day,'sunday','pdf')
    assert result['verified']
    assert result['itemUrl'] is None
