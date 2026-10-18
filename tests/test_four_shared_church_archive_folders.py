"""Existing four separately shared media-team folders are independent upload roots.

Only mocked Graph calls and temporary SQLite storage are used: this must never
mutate a live OneDrive folder or any historical worship PPT/PDF.
"""
import base64

import pytest

from media_automation.web.original.onedrive import CloudError, OneDrive
from media_automation.web.original.work_store import WorkStore


ROLE_INFO = [
    ('archive_sunday_pdf', '00.주보', 'sunday', 'pdf', None),
    ('archive_sunday_ppt', '01.주일예배', 'sunday', 'ppt', None),
    ('archive_wednesday', '02.수요예배', 'wednesday', 'ppt', None),
    ('archive_friday', '03.금요예배', 'friday', 'ppt', 'zoom'),
]


@pytest.fixture
def cloud(tmp_path):
    c=OneDrive(WorkStore(tmp_path/'review.db'))
    with c.lock:
        c._write({'client_id':'app-id','account':{'home_account_id':'tester'},
                  'folders':{'source':{'id':'score-id','name':'악보 PPT'},
                             'source_video':{'id':'media-id','name':'Zoom 영상'},
                             'archive':{'id':'personal-full','name':'개인 용량 부족'}}})
    return c


def install_fake_graph(monkeypatch, cloud):
    requests=[]
    names={role:(name,'share_drive_'+str(i),'share_folder_'+str(i))
           for i,(role,name,_,_,_) in enumerate(ROLE_INFO)}
    def graph(path, method='GET', **kwargs):
        requests.append((path,method))
        assert method == 'GET', 'Target choice must not create folders remotely'
        if path.startswith('/shares/u!') and path.endswith('/driveItem'):
            token=path.split('/')[2][2:]
            link=base64.urlsafe_b64decode(token+'='*(-len(token)%4)).decode('utf8')
            role=link.rsplit('/',1)[-1]
            folder,drive,ident=names[role]
            return {'id':ident,'name':folder,'folder':{},
                    'parentReference':{'driveId':drive}}
        for role,(folder,drive,ident) in names.items():
            if path == f'/drives/{drive}/items/{ident}':
                return {'id':ident,'name':folder,'folder':{}}
        raise AssertionError('unexpected Graph read: '+path)
    monkeypatch.setattr(cloud,'graph',graph)
    return requests, names


def test_four_independent_existing_folders_are_exact_destination_not_new_subfolders(
    cloud,monkeypatch
):
    calls,names=install_fake_graph(monkeypatch,cloud)
    for role,name,_,_,_ in ROLE_INFO:
        status=cloud.select_shared_archive(f'https://1drv.ms/f/{role}',role)
        assert status == {'enabled':True,'name':name}
    public=cloud.status('http://localhost:18877')
    assert set(public['shared_archives']) == set(names)
    assert 'share_drive' not in str(public) and 'share_folder' not in str(public)
    assert cloud.selected('source')['id']=='score-id'
    assert cloud.selected('source_video')['id']=='media-id'
    assert cloud.selected('archive')['id']=='personal-full'
    calls.clear()
    for role,name,service,kind,mode in ROLE_INFO:
        actual=cloud.archive_destination(service,kind,mode)
        _,drive,ident=names[role]
        assert actual['id']==ident and actual['drive_id']==drive
        assert actual['name']==name
    assert cloud.archive_destination('friday','ppt','in_person')['id']==names['archive_friday'][2]
    assert calls == [],'Selecting a known target must not scan or create folders'


@pytest.mark.parametrize('wrong_role,correct_role',[
    ('archive_sunday_pdf','archive_sunday_ppt'),
    ('archive_friday','archive_wednesday'),
])
def test_wrong_shared_folder_link_rejected_and_source_preserved(cloud,monkeypatch,wrong_role,correct_role):
    _, names=install_fake_graph(monkeypatch,cloud)
    with pytest.raises(CloudError,match='아닙니다'):
        cloud.select_shared_archive(f'https://1drv.ms/f/{correct_role}',wrong_role)
    assert not cloud.status('http://localhost:18877')['shared_archives']
    assert cloud.selected('source')['id']=='score-id'


def test_partial_setup_blocks_fallback_to_full_personal_storage(cloud,monkeypatch):
    install_fake_graph(monkeypatch,cloud)
    cloud.select_shared_archive('https://1drv.ms/f/archive_sunday_pdf','archive_sunday_pdf')
    assert cloud.archive_destination('sunday','pdf')['name']=='00.주보'
    with pytest.raises(CloudError,match='01.주일예배'):
        cloud.archive_destination('sunday','ppt')
    with pytest.raises(CloudError,match='02.수요예배'):
        cloud.archive_destination('wednesday','ppt')
    with pytest.raises(CloudError,match='03.금요예배'):
        cloud.archive_destination('friday','ppt')


def test_shared_roles_can_be_cleared_independently_without_deleting_originals(cloud,monkeypatch):
    install_fake_graph(monkeypatch,cloud)
    for role,_,_,_,_ in ROLE_INFO:
        cloud.select_shared_archive(f'https://1drv.ms/f/{role}',role)
    cloud.clear_shared_archive('archive_sunday_pdf')
    status=cloud.status('http://localhost:18877')
    assert 'archive_sunday_pdf' not in status['shared_archives']
    assert len(status['shared_archives'])==3
    assert cloud.selected('source_video')['id']=='media-id'
    with pytest.raises(CloudError):
        cloud.clear_shared_archive('source')
    assert len(cloud.status('http://localhost:18877')['shared_archives'])==3


def test_browsing_uses_role_drive_and_rejects_going_outside_role_root(cloud,monkeypatch):
    calls,names=install_fake_graph(monkeypatch,cloud)
    for role,_,_,_,_ in ROLE_INFO:
        cloud.select_shared_archive(f'https://1drv.ms/f/{role}',role)
    scans=[]
    monkeypatch.setattr(cloud,'children',lambda identifier,query='',*,drive_id=None:
                        scans.append((identifier,drive_id)) or [])
    for role,purpose in [('archive_sunday_pdf','archive_sunday_pdf'),
                         ('archive_sunday_ppt','archive_sunday_ppt'),
                         ('archive_wednesday','archive_wednesday'),
                         ('archive_friday','archive_friday_zoom')]:
        assert cloud.list_selected(purpose)==[]
        assert scans[-1]==(names[role][2], names[role][1])
    with pytest.raises(CloudError):
        cloud.list_selected('archive',identifier='not-part-of-shared-root')
    assert cloud.selected('source')['id']=='score-id'


def test_four_shared_folders_do_not_require_second_microsoft_account(cloud,monkeypatch):
    install_fake_graph(monkeypatch,cloud)
    cloud.select_shared_archive('https://1drv.ms/f/archive_sunday_pdf','archive_sunday_pdf')
    data=cloud._read()
    assert data['account']=={'home_account_id':'tester'}
    assert 'archive_sunday_pdf' in data['shared_archives']
    assert 'cache' not in data



def test_reviewed_bulletin_archives_to_00_folder_without_creating_nested_directories(
    cloud,monkeypatch
):
    from pathlib import Path
    calls,names=install_fake_graph(monkeypatch,cloud)
    cloud.select_shared_archive(
        'https://1drv.ms/f/archive_sunday_pdf', 'archive_sunday_pdf'
    )
    day='2026-10-18'
    identifier='a'*32
    cloud.store.save(day,'sunday',0,{'fields':{},'outputs':{
        'pdf':{'fileId':identifier,'complete':True,'changed':False},'ppt':{}
    }})
    generated=Path(cloud.store.path).with_suffix('.generated')
    generated.mkdir()
    source=b'%PDF-1.4\\nreal approval required only in user interface\\n%%EOF'
    (generated/(identifier+'.pdf')).write_bytes(source)
    uploaded=[]
    def upload(folder_id,name,data,*,drive_id=None):
        uploaded.append((folder_id,name,data,drive_id))
        return {'id':'archived-item','name':name,'file':{},'size':len(data)}
    monkeypatch.setattr(cloud,'upload_file',upload)
    monkeypatch.setattr(cloud,'_find_exact_shared_file',lambda folder,item_id,name,size:
                        {'id':item_id,'name':name,'size':size,'file':{},
                         'parentReference':{'driveId':folder['drive_id'],'id':folder['id']}})
    calls.clear()
    response=cloud.archive(day,'sunday','pdf')
    expected_folder,expected_drive,expected_id=names['archive_sunday_pdf']
    assert uploaded==[(expected_id,
                       f'{day}_sunday_pdf_{identifier}.pdf',
                       source,expected_drive)]
    assert response['work']['data']['outputs']['pdf']['archiveStatus']=='uploaded'
    assert response['work']['data']['outputs']['ppt']=={}
    assert calls == [],'The upload path must not auto-create folders'
