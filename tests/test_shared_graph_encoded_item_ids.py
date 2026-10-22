"""Microsoft Graph shared OneDrive paths must accept URL-encoded item separators.

valid_id() encodes '!' as '%21'. The graph whitelist must validate the
resulting URL-encoded path, not the unencoded Graph item IDs. This reproduces
the '허용되지 않은 OneDrive 요청입니다.' experienced in the live UI without
accessing Microsoft or using any real user share URLs.
"""
from pathlib import Path
from unittest.mock import Mock

import pytest

from media_automation.web.original.onedrive import CloudError, OneDrive, valid_id
from media_automation.web.original.work_store import WorkStore


def test_shared_one_drive_item_encoded_bang_allowed(tmp_path, monkeypatch):
    cloud=OneDrive(WorkStore(tmp_path/'work.db'))
    monkeypatch.setattr(cloud,'_token',lambda:'mock-token')
    response=Mock(status_code=200)
    response.json.return_value={'id':'SHARED!123','folder':{}}
    cloud.http=Mock()
    cloud.http.request.return_value=response

    drive=valid_id('DRIVE!123')
    item=valid_id('SHARED!123')
    assert drive=='DRIVE%21123'
    assert item=='SHARED%21123'
    paths=[
        '/drives/'+drive+'/items/'+item,
        '/drives/'+drive+'/items/'+item+'/children?$top=1',
        '/drives/'+drive+'/items/'+item+'/createUploadSession',
        '/drives/'+drive+'/items/'+item+':/church%20bulletin.pdf:/content',
        '/drives/'+drive+'/items/'+item+':/church%20bulletin.pdf:/createUploadSession',
    ]
    for path in paths:
        assert cloud.graph(path)['id']=='SHARED!123'
    assert cloud.http.request.call_count==len(paths)
    assert all(call.args[1].startswith('https://graph.microsoft.com/v1.0/drives/')
               for call in cloud.http.request.call_args_list)


def test_select_real_shape_shared_id_with_bang_is_not_blocked(tmp_path,monkeypatch):
    cloud=OneDrive(WorkStore(tmp_path/'work.db'))
    monkeypatch.setattr(cloud,'_token',lambda:'mock-token')
    sent=[]
    def request(method,url,**kwargs):
        sent.append((method,url,kwargs))
        result=Mock(status_code=200)
        if '/shares/u!' in url:
            result.json.return_value={
                'id':'owner!shared_folder','name':'00.주보',
                'parentReference':{'driveId':'owner!drive'},'folder':{}
            }
        else:
            assert url.endswith('/drives/owner%21drive/items/owner%21shared_folder')
            result.json.return_value={'id':'owner!shared_folder','name':'00.주보','folder':{}}
        return result
    cloud.http=Mock()
    cloud.http.request.side_effect=request

    selected=cloud.select_shared_archive(
        'https://1drv.ms/f/c/fakeowner/fakefolder','archive_sunday_pdf'
    )
    assert selected=={'enabled':True,'name':'00.주보'}
    assert len(sent)==2
    assert sent[0][2]['headers']['Prefer']=='redeemSharingLink'
    assert cloud.status('http://localhost:18877')['shared_archives']['archive_sunday_pdf']['name']=='00.주보'


@pytest.mark.parametrize('unsafe',[
    '/drives/drive%2Fsecret/items/file',
    '/drives/drive/items/file%2Fsecret',
    '/drives/drive/items/file/../../me/drive',
    '/drives/drive/items/file/permissionCheck',
    'https://untrusted.example/v1.0/drives/drive/items/file',
])
def test_encoded_id_path_allowlist_still_blocks_unrelated_graph_requests(
    tmp_path, monkeypatch, unsafe
):
    cloud=OneDrive(WorkStore(tmp_path/'work.db'))
    monkeypatch.setattr(cloud,'_token',lambda:'mock-token')
    cloud.http=Mock()
    with pytest.raises(CloudError,match='허용되지 않은 OneDrive 요청'):
        cloud.graph(unsafe)
    cloud.http.request.assert_not_called()


def test_personal_completed_folder_configuration_removed_but_sources_remain():
    html=Path('src/media_automation/web/original/ui/index.html').read_text(encoding='utf-8')
    js=Path('src/media_automation/web/original/ui/onedrive.js').read_text(encoding='utf-8')
    assert 'id="cloud-pick-source"' in html
    assert 'id="cloud-pick-source_video"' in html
    assert 'id="cloud-pick-archive"' not in html
    assert 'id="archive-folder-overrides"' not in html
    for role in ('archive_sunday_pdf','archive_sunday_ppt','archive_wednesday','archive_friday'):
        assert f'id="cloud-set-{role}"' in html
    assert "['source','source_video']" in js
    assert "['source','archive',...otherFolders]" not in js
    assert '설정에서 완료본 폴더를 먼저 선택하세요.' not in js
