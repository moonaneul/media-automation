"""Shared OneDrive is an output-only target; original score folders stay unchanged.

No network, Microsoft credentials, live church work, or remote writes are used.
"""
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest

from media_automation.web.original.onedrive import OneDrive, CloudError
from media_automation.web.original.work_store import WorkStore


@pytest.fixture
def cloud(tmp_path):
    cloud = OneDrive(WorkStore(tmp_path / 'work.db'))
    with cloud.lock:
        cloud._write({
            'client_id': 'test-app-id',
            'account': {'username': 'tester@invalid.example'},
            'folders': {
                'source': {'id': 'source','name':'악보 PPT'},
                'source_video': {'id':'video','name':'찬양 영상'},
                'archive': {'id':'personal_archive','name':'개인 완료본'},
            },
        })
    return cloud


@pytest.mark.parametrize('link', [
    'http://onedrive.live.com/folder',
    'https://evil.example/onedrive/file',
    'https://onedrive.live.com.evil.example/folder',
    'https://user:secret@1drv.ms/f/folder',
    'https://1drv.ms/f/link#fragment',
])
def test_shared_folder_url_never_calls_unsafe_host(cloud, monkeypatch, link):
    monkeypatch.setattr(cloud, 'graph', lambda *_a, **_kw: pytest.fail('untrusted Graph request'))
    with pytest.raises(CloudError):
        cloud.select_shared_archive(link)


def test_share_selection_validates_remote_folder_and_preserves_originals(cloud, monkeypatch):
    calls=[]
    def graph(path, **kwargs):
        calls.append(path)
        if path.startswith('/shares/u!') and path.endswith('/driveItem'):
            return {'id':'team_folder', 'name':'미디어팀 완료본', 'folder': {},
                    'parentReference':{'driveId':'remote_drive'}}
        assert path == '/drives/remote_drive/items/team_folder'
        return {'id':'team_folder', 'name':'미디어팀 완료본', 'folder':{}}
    monkeypatch.setattr(cloud,'graph',graph)
    result=cloud.select_shared_archive('https://1drv.ms/f/s!test-team-link')
    assert result == {'enabled':True, 'name':'미디어팀 완료본'}
    status=cloud.status('http://localhost:18877')
    assert status['shared_archive'] == result
    assert 'drive_id' not in str(status) and 'test-team-link' not in str(status)
    assert status['folders']['source']['id']=='source'
    assert status['folders']['source_video']['id']=='video'
    assert len(calls)==2
    assert calls[0].startswith('/shares/u!')


def test_share_link_file_rejected_and_old_archive_kept(cloud, monkeypatch):
    monkeypatch.setattr(cloud,'graph',lambda *_a, **_kw:{
        'id':'another_file','name':'somefile.pptx','file':{},
        'parentReference':{'driveId':'remote_drive'},
    })
    with pytest.raises(CloudError,match='폴더'):
        cloud.select_shared_archive('https://1drv.ms/f/s!test-team-link')
    assert cloud._read()['folders']['archive']['id'] == 'personal_archive'
    assert not cloud._read().get('shared_archive')


def test_share_selection_requires_graph_rights_without_destroying_old_settings(cloud, monkeypatch):
    monkeypatch.setattr(cloud,'graph',lambda path, **_kw: (
        {'id':'team_folder','folder':{},'parentReference':{'driveId':'remote_drive'}}
        if path.startswith('/shares/') else
        (_ for _ in ()).throw(CloudError('권한이 없습니다.'))
    ))
    with pytest.raises(CloudError,match='권한'):
        cloud.select_shared_archive('https://1drv.ms/f/s!test-team-link')
    assert cloud._read().get('shared_archive') is None


def test_shared_archive_upload_uses_remote_drive_without_changing_sources(cloud, monkeypatch):
    def graph(path, method='GET', body=None, **kwargs):
        if path.startswith('/shares/u!'):
            return {'id':'team_folder', 'name':'미디어팀 완료본', 'folder':{},
                    'parentReference':{'driveId':'remote_drive'}}
        if path == '/drives/remote_drive/items/team_folder':
            return {'id':'team_folder','name':'미디어팀 완료본','folder':{}}
        assert path.startswith('/drives/remote_drive/items/')
        if method=='POST':
            return {'id':{'주일 예배':'created_sunday','주보':'created_bulletin'}[body['name']], 'name':body['name'], 'folder':{}}
        raise AssertionError(path)
    monkeypatch.setattr(cloud,'graph',graph)
    cloud.select_shared_archive('https://1drv.ms/f/s!test-team-link')
    scans=[]
    def children(parent, query='', *, drive_id=None):
        scans.append((parent,drive_id))
        return []
    monkeypatch.setattr(cloud,'children',children)
    folder=cloud.archive_destination('sunday','pdf')
    assert folder['drive_id']=='remote_drive'
    assert folder['name']=='주보'
    assert scans == [('team_folder','remote_drive'),
                     ('created_sunday','remote_drive')]
    day='2026-10-18'
    ident='a'*32
    cloud.store.save(day,'sunday',0,{'fields':{},'outputs':{'pdf':{
        'fileId':ident,'complete':True,'changed':False},'ppt':{}}})
    generated=Path(cloud.store.path).with_suffix('.generated')
    generated.mkdir()
    (generated/(ident+'.pdf')).write_bytes(b'%PDF-1.4\nEXAMPLE\n%%EOF')
    written=[]
    def upload(parent,name,content,*,drive_id=None):
        written.append((parent,name,content,drive_id))
        return {'id':'uploaded','name':name,'size':len(content),'file':{}}
    monkeypatch.setattr(cloud,'upload_file',upload)
    result=cloud.archive(day,'sunday','pdf')
    assert len(written)==1
    assert written[0][0]=='created_bulletin'
    assert written[0][3]=='remote_drive'
    assert result['work']['data']['outputs']['pdf']['archiveStatus']=='uploaded'
    assert cloud._read()['folders']['source']['id']=='source'
    assert cloud._read()['folders']['archive']['id']=='personal_archive'
    cloud.clear_shared_archive()
    assert not cloud.status('http://localhost:18877')['shared_archive']['enabled']
    assert cloud.selected('archive')['id']=='personal_archive'


def test_microsoft_graph_shared_path_guard(cloud, monkeypatch):
    cloud._token=lambda: 'fake'
    response=Mock();response.status_code=200;response.json.return_value={'ok':True}
    cloud.http=Mock();cloud.http.request.return_value=response
    assert cloud.graph('/shares/u!aabbccdd/driveItem')=={'ok':True}
    assert cloud.graph('/drives/remote_drive/items/team_folder')=={'ok':True}
    for bad in ['/users/someone/drive','/sites/root',
                'https://untrusted.example/v1.0/drives/remote_drive/items/team_folder']:
        with pytest.raises(CloudError):
            cloud.graph(bad)
    assert cloud.http.request.call_count==2


def test_ui_has_separate_shared_archive_selector_and_no_browser_link_storage():
    source=Path('src/media_automation/web/original/ui/index.html').read_text(encoding='utf-8')
    script=Path('src/media_automation/web/original/ui/onedrive.js').read_text(encoding='utf-8')
    assert 'id="cloud-apply-shared-archive"' in source
    assert 'id="cloud-clear-shared-archive"' in source
    assert "await api('shared-archive',{url:link})" in script
    assert "el('cloud-shared-archive-link').value='';" in script
    assert 'localStorage.setItem' not in script
    assert 'state.shared_archive?.enabled' in script
