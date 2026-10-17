import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from unittest.mock import Mock
import pytest
from media_automation.web.original.onedrive import OneDrive,CloudError,CLIENT_ID,GRAPH
from media_automation.web.original.work_store import WorkStore

@pytest.fixture
def cloud(tmp_path):
    return OneDrive(WorkStore(tmp_path/'work.db'))


def prepare(cloud):
    cloud.configure(CLIENT_ID,'test-secret-value-never-returned')
    with cloud.lock:
        data=cloud._read();data['account']={'home_account_id':'account-1','username':'test@example.invalid'}
        data['folders']={'source':{'id':'source','name':'원본','parentReference':{'id':'root','driveId':'drive-1'}},
                         'archive':{'id':'archive','name':'완료본','parentReference':{'id':'root','driveId':'drive-1'}}}
        cloud._write(data)


def item(identifier,parent='source',folder=False):
    return dict(id=identifier,name=identifier+'.pptx',size=4,parentReference={'id':parent,'driveId':'drive-1'},**({'folder':{}} if folder else {'file':{}}))


def test_secrets_encrypted_and_status_redacted(cloud):
    prepare(cloud)
    status=cloud.status('http://127.0.0.1:8769')
    assert status['redirect_uri']=='http://localhost:8769/api/onedrive/callback'
    assert 'secret' not in status and 'cache' not in status
    assert b'test-secret' not in (cloud.folder/'connection.enc').read_bytes()
    assert (cloud.folder/'connection.enc').stat().st_mode & 0o777==0o600
    assert (cloud.folder/'encryption.key').stat().st_mode & 0o777==0o600
    assert cloud.folder.stat().st_mode & 0o777==0o700


def test_disconnect_keeps_configuration_but_removes_credentials(cloud):
    prepare(cloud);cloud.disconnect();data=cloud._read()
    assert data['secret'] and not data.get('account') and not data.get('folders') and not data.get('cache')


def fake_app():
    app=Mock();cache=Mock()
    app.initiate_auth_code_flow.return_value={'state':'one-time-state','auth_uri':'https://login.microsoftonline.com/test'}
    app.acquire_token_by_auth_code_flow.return_value={'access_token':'token-secret'}
    app.get_accounts.return_value=[{'home_account_id':'account-1','username':'test@example.invalid'}]
    cache.serialize.return_value='cache-secret'
    return app,cache


def test_callback_bound_to_browser_and_single_use(cloud,monkeypatch):
    prepare(cloud);app,cache=fake_app();monkeypatch.setattr(cloud,'_app',lambda _: (app,cache))
    cloud.begin('http://localhost:8769','browser-binding','server-session')
    cloud.finish({'state':'one-time-state','code':'authorization-code'},'browser-binding',lambda s:s=='server-session')
    assert cloud._read()['cache']=='cache-secret'
    with pytest.raises(CloudError):cloud.finish({'state':'one-time-state','code':'authorization-code'},'browser-binding',lambda _:True)


@pytest.mark.parametrize('failure',['wrong-browser','expired','expired-login','missing-state'])
def test_oauth_rejects_unbound_or_expired_attempt(cloud,monkeypatch,failure):
    prepare(cloud);app,cache=fake_app();monkeypatch.setattr(cloud,'_app',lambda _: (app,cache))
    cloud.begin('http://localhost:8769','browser-binding','server-session')
    if failure=='expired':cloud.pending['one-time-state']['expires']=time.time()-1
    with pytest.raises(CloudError):cloud.finish({'state':'bad' if failure=='missing-state' else 'one-time-state','code':'code'},'bad' if failure=='wrong-browser' else 'browser-binding',lambda _:failure!='expired-login')
    app.acquire_token_by_auth_code_flow.assert_not_called()


def test_folder_search_paginates_and_rejects_external_next_link(cloud,monkeypatch):
    pages=[{'value':[item('one')],'@odata.nextLink':GRAPH+'/me/drive/items/source/children?$skiptoken=two'},{'value':[item('two')]}]
    monkeypatch.setattr(cloud,'graph',lambda _:pages.pop(0))
    assert [i['id'] for i in cloud.children('source')]==['one','two']
    cloud.http=Mock()
    with pytest.raises(CloudError):OneDrive.graph(cloud,'https://evil.invalid/v1.0/me/drive')
    cloud.http.request.assert_not_called()


def test_import_checks_ancestry_deduplicates_and_keeps_review_required(cloud,monkeypatch):
    prepare(cloud);song=cloud.store.register_song({'title':'검증곡'})
    monkeypatch.setattr(cloud,'item',lambda i: item(i,parent='source'))
    monkeypatch.setattr(cloud,'_download',lambda _:b'PPT!')
    first=cloud.import_song('one',song['id']);second=cloud.import_song('one',song['id'])
    assert not first['duplicate'] and second['duplicate']
    assert len(cloud.store.songs()[0]['assets'])==1
    assert cloud.store.songs()[0]['assets'][0]['eligible'] is False
    monkeypatch.setattr(cloud,'item',lambda i:item(i,parent='outside'))
    with pytest.raises(CloudError):cloud.import_song('one',song['id'])


def test_folder_selection_rejects_overlapping_folders(cloud,monkeypatch):
    prepare(cloud)
    monkeypatch.setattr(cloud,'item',lambda i:item(i,parent='archive',folder=True))
    with pytest.raises(CloudError):cloud.select_folder('source','nested')
    with pytest.raises(CloudError):cloud.select_folder('source','root')


def test_download_never_sends_token_to_file_host_and_limits_urls(cloud):
    data=item('one');data['@microsoft.graph.downloadUrl']='http://127.0.0.1/secret'
    cloud.http=Mock()
    with pytest.raises(CloudError):cloud._download(data)
    cloud.http.get.assert_not_called()
    response=Mock();response.status_code=200;response.iter_content.return_value=[b'PPT!'];response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    cloud.http.get.return_value=response;data['@microsoft.graph.downloadUrl']='https://public.dm.files.1drv.com/file'
    assert cloud._download(data)==b'PPT!'
    assert 'headers' not in cloud.http.get.call_args.kwargs


def test_archive_only_completed_and_retry_preserves_history(cloud,monkeypatch):
    prepare(cloud)
    cloud.store.save('2026-10-11','sunday',0,{'fields':{},'outputs':{'pdf':{'fileId':'a'*32,'complete':False}}})
    with pytest.raises(CloudError):cloud.archive('2026-10-11','sunday','pdf')
    current=cloud.store.get('2026-10-11','sunday');current['data']['outputs']['pdf']['complete']=True
    cloud.store.save('2026-10-11','sunday',current['revision'],current['data'])
    path=Path(cloud.store.path).with_suffix('.generated');path.mkdir();(path/('a'*32+'.pdf')).write_bytes(b'PDF!')
    calls=[]
    def graph(url,**kw):calls.append(url);assert kw['content']==b'PDF!';return item('saved',parent='archive')
    monkeypatch.setattr(cloud,'graph',graph)
    monkeypatch.setattr(cloud,'archive_destination',lambda service,kind: {'id':'bulletin'})
    cloud.archive('2026-10-11','sunday','pdf');cloud.archive('2026-10-11','sunday','pdf')
    assert calls[0]==calls[1] # repeated save uses same exact file path
    assert 'a'*32 in calls[0]
    output=cloud.store.get('2026-10-11','sunday')['data']['outputs']['pdf']
    assert output['complete'] and output['archiveStatus']=='uploaded'
    with cloud.store.connect() as db:assert db.execute('SELECT count(*) FROM cloud_archives').fetchone()[0]==1


def test_remote_upload_failure_keeps_completed_output(cloud,monkeypatch):
    prepare(cloud);path=Path(cloud.store.path).with_suffix('.generated');path.mkdir();(path/('a'*32+'.pdf')).write_bytes(b'PDF!')
    cloud.store.save('2026-10-11','sunday',0,{'fields':{},'outputs':{'pdf':{'fileId':'a'*32,'complete':True,'archiveStatus':'pending_connection'}}})
    monkeypatch.setattr(cloud,'graph',Mock(side_effect=CloudError('offline')))
    with pytest.raises(CloudError):cloud.archive('2026-10-11','sunday','pdf')
    assert cloud.store.get('2026-10-11','sunday')['data']['outputs']['pdf']['complete']
    assert (path/('a'*32+'.pdf')).read_bytes()==b'PDF!'


def test_http_connection_is_authenticated_and_origin_checked(tmp_path):
    import threading
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    from media_automation.web.original.server import make_server
    server=make_server(WorkStore(tmp_path/'work.db'),0,password='test-password-123456')
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    def req(path,data=None,cookie=None,origin=None):
        headers={'Content-Type':'application/json'}
        if cookie:headers['Cookie']=cookie
        if origin:headers['Origin']=origin
        return urlopen(Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers),timeout=4)
    try:
        with pytest.raises(HTTPError) as e:req('/api/onedrive/status')
        assert e.value.code==401
        r=req('/api/login',{'password':'test-password-123456'});cookie=r.headers['Set-Cookie'].split(';',1)[0]
        status=json.load(req('/api/onedrive/status',cookie=cookie))
        assert not status['connected'] and status['redirect_uri'].startswith('http://localhost:')
        saved=json.load(req('/api/onedrive/configure',{'client_id':CLIENT_ID,'secret':'test-only-secret'},cookie=cookie))
        assert saved['configured'] and 'secret' not in saved
        with pytest.raises(HTTPError) as e:req('/api/onedrive/disconnect',{},cookie=cookie,origin='https://evil.invalid')
        assert e.value.code==403
        with pytest.raises(HTTPError) as e:req('/api/onedrive/callback?state=unbound&code=not-a-token')
        assert e.value.code==400
        html=req('/',cookie=cookie).read()
        assert b'cloud-secret' in html and b'onedrive.js' in html
        assert b'test-only-secret' not in html
        assert b'CloudMedia' in req('/onedrive.js').read()
        # localhost is explicitly permitted only for this loopback server.
        local=f'http://localhost:{server.server_port}'
        assert urlopen(local+'/',timeout=4).status==200
    finally:
        server.shutdown();server.server_close()


def test_token_refresh_rotation_saved_encrypted(cloud,monkeypatch):
    prepare(cloud);app,cache=fake_app();cache.has_state_changed=True
    app.acquire_token_silent.return_value={'access_token':'access-token-test'}
    monkeypatch.setattr(cloud,'_app',lambda _: (app,cache))
    assert cloud._token()=='access-token-test'
    assert cloud._read()['cache']=='cache-secret'
    assert b'cache-secret' not in (cloud.folder/'connection.enc').read_bytes()


def test_no_redirect_can_leak_bearer_token(cloud,monkeypatch):
    monkeypatch.setattr(cloud,'_token',lambda:'private-bearer')
    cloud.http=Mock();cloud.http.request.return_value.status_code=302
    with pytest.raises(CloudError):cloud.graph('/me/drive/root')
    assert cloud.http.request.call_args.kwargs['allow_redirects'] is False


def test_source_versions_get_distinct_remote_paths(cloud,monkeypatch):
    prepare(cloud);song=cloud.store.register_song({'title':'검증곡'})
    first=cloud.store.attach_song_asset(song['id'],'same.pptx',b'one')
    second=cloud.store.attach_song_asset(song['id'],'same.pptx',b'two')
    calls=[]
    def graph(url,**kw):calls.append(url);return item('saved')
    monkeypatch.setattr(cloud,'graph',graph)
    cloud.upload_song(song['id'],first['digest']);cloud.upload_song(song['id'],second['digest'])
    assert calls[0]!=calls[1] and first['digest'] in calls[0] and second['digest'] in calls[1]


def test_snapshot_includes_private_connection_with_permissions(cloud,tmp_path):
    from media_automation.web.original.migration import snapshot_store
    prepare(cloud);destination=tmp_path/'backup'/'snapshot.db'
    snapshot_store(cloud.store.path,destination)
    copy=destination.with_suffix('.onedrive')
    assert (copy/'connection.enc').read_bytes()==(cloud.folder/'connection.enc').read_bytes()
    assert (copy/'encryption.key').stat().st_mode&0o777==0o600
    assert copy.stat().st_mode&0o777==0o700


def test_account_switch_uses_fresh_login_cache_and_clears_old_folders(cloud,monkeypatch):
    prepare(cloud)
    app,cache=fake_app()
    app.get_accounts.return_value=[{'home_account_id':'new-account','username':'new@example.invalid'}]
    inputs=[]
    def factory(data):
        inputs.append(data)
        return app,cache
    monkeypatch.setattr(cloud,'_app',factory)
    cloud.begin('http://localhost:8769','browser','session')
    cloud.finish({'state':'one-time-state','code':'code'},'browser',lambda _:True)
    assert all('cache' not in data for data in inputs)
    assert cloud._read()['account']['home_account_id']=='new-account'
    assert not cloud._read().get('folders')


@pytest.mark.parametrize('service,kind,names',[
    ('wednesday','ppt',['수요 예배']),('friday','ppt',['금요 기도회']),
    ('sunday','ppt',['주일 예배','예배 PPT']),('sunday','pdf',['주일 예배','주보'])])
def test_archive_destination_reuses_existing_and_creates_missing(cloud,monkeypatch,service,kind,names):
    prepare(cloud)
    created=[]
    def children(identifier):
        if identifier=='archive':
            v=item('existing',parent='archive',folder=True);v['name']=names[0];return [v]
        return []
    def graph(path,**kwargs):
        created.append((path,kwargs['body']))
        v=item('created',parent='existing',folder=True);v['name']=kwargs['body']['name'];return v
    monkeypatch.setattr(cloud,'children',children)
    monkeypatch.setattr(cloud,'graph',graph)
    destination=cloud.archive_destination(service,kind)
    assert destination['id']==('existing' if len(names)==1 else 'created')
    assert [body['name'] for _,body in created]==names[1:]
    assert all(body['@microsoft.graph.conflictBehavior']=='fail' for _,body in created)


def test_archive_folder_name_collision_never_uploads_into_file(cloud,monkeypatch):
    prepare(cloud);v=item('bad');v['name']='수요 예배'
    monkeypatch.setattr(cloud,'children',lambda _: [v])
    with pytest.raises(CloudError):cloud.archive_destination('wednesday','ppt')


def test_silent_login_filters_accounts_using_supported_msal_api(cloud,monkeypatch):
    prepare(cloud);app,cache=fake_app();cache.has_state_changed=False
    app.get_accounts.return_value=[{'home_account_id':'other'}, {'home_account_id':'account-1'}]
    app.acquire_token_silent.return_value={'access_token':'test-token'}
    monkeypatch.setattr(cloud,'_app',lambda _: (app,cache))
    assert cloud._token()=='test-token'
    app.get_accounts.assert_called_once_with()
    assert app.acquire_token_silent.call_args.kwargs['account']['home_account_id']=='account-1'


@pytest.mark.parametrize('name,expected',[
    ('새찬송가 79장 주 하나님 지으신 모든 세계.ppt','new79'),
    ('79장 주 하나님 지으신 모든 세계.ppt','new79'),
    ('79장.ppt',None),('구찬송가 79장.ppt','old79'),
    ('주 하나님 지으신 모든 세계.pptx','new79'),('79장 다른 제목.ppt',None)])
def test_filename_match_never_guesses_edition_or_conflicting_title(name,expected):
    songs=[{'id':'new79','title':'주 하나님 지으신 모든 세계','number':79,'edition':'new'},
           {'id':'old79','title':'다른 곡','number':79,'edition':'old'}]
    result=OneDrive.filename_song(name,songs)
    assert (result['id'] if result else None)==expected


def test_auto_connection_recurses_deduplicates_and_respects_deleted_original(cloud,monkeypatch):
    prepare(cloud);song=cloud.store.register_song({'title':'찬양 테스트','aliases':[]})
    original=item('song');original.update(name='찬양 테스트.mp3',lastModifiedDateTime='one')
    monkeypatch.setattr(cloud,'children',lambda identifier:[item('sub',folder=True)] if identifier=='source' else [original])
    def imported(identifier,song_id):return cloud.store.attach_song_asset(song_id,original['name'],b'test')
    importer=Mock(side_effect=imported);monkeypatch.setattr(cloud,'import_song',importer)
    assert cloud.auto_connect()['linked']==1
    assert cloud.auto_connect()['unchanged']==1
    assert importer.call_count==1
    asset=cloud.store.songs()[0]['assets'][0]
    assert not asset['eligible']
    cloud.store.remove_original({'song_id':song['id'],'digest':asset['digest']})
    assert cloud.auto_connect()['choices'][0]['reason'].startswith('삭제')
    assert importer.call_count==1


def test_multiple_remote_originals_require_choice(cloud,monkeypatch):
    prepare(cloud);cloud.store.register_song({'title':'같은 곡','aliases':[]})
    a=item('a');b=item('b');a['name']=b['name']='같은 곡.mp3'
    monkeypatch.setattr(cloud,'children',lambda _: [a,b])
    importer=Mock();monkeypatch.setattr(cloud,'import_song',importer)
    assert len(cloud.auto_connect()['choices'])==2
    importer.assert_not_called()


def test_new_song_metadata_parses_actual_named_files():
    parsed=OneDrive.filename_metadata('193장_성령의 봄바람 불어오니_새찬송가악보_PPT.ppt')
    assert parsed['title']=='성령의 봄바람 불어오니' and parsed['edition']=='new' and parsed['number']==193
    assert OneDrive.filename_metadata('교회여 일어나라_노수미&호산나싱어즈.mp4')['title']=='교회여 일어나라'
    assert OneDrive.filename_metadata('79장.ppt') is None


def test_large_upload_chunks_without_bearer_and_verifies_size(cloud,monkeypatch):
    content=b'x'*(5*1024*1024+10)
    monkeypatch.setattr(cloud,'children',lambda _: [])
    monkeypatch.setattr(cloud,'graph',lambda *a,**k: {'uploadUrl':'https://test.up.1drv.com/upload'})
    first=Mock(status_code=202);last=Mock(status_code=201)
    last.json.return_value={'id':'uploaded','size':len(content),'file':{}}
    cloud.http.put=Mock(side_effect=[first,last])
    assert cloud.upload_file('source','song.mp3',content)['id']=='uploaded'
    calls=cloud.http.put.call_args_list
    assert len(calls)==2 and len(calls[0].kwargs['data'])==5*1024*1024
    assert calls[1].kwargs['headers']['Content-Range']==f'bytes {5*1024*1024}-{len(content)-1}/{len(content)}'
    assert all('Authorization' not in c.kwargs['headers'] and not c.kwargs['allow_redirects'] for c in calls)


def test_large_upload_reuses_same_immutable_filename(cloud,monkeypatch):
    content=b'x'*(4*1024*1024)
    monkeypatch.setattr(cloud,'children',lambda _: [{'name':'same.mp3','size':len(content),'file':{},'id':'existing'}])
    graph=Mock();monkeypatch.setattr(cloud,'graph',graph)
    assert cloud.upload_file('source','same.mp3',content)['id']=='existing'
    graph.assert_not_called()


def test_archive_ui_uses_actual_week_key_and_captures_requested_output():
    import subprocess
    code=r"""
    const fs=require('fs'),vm=require('vm');
    const source=fs.readFileSync('src/media_automation/web/original/ui/onedrive.js','utf8');
    const fn=source.slice(source.indexOf('async function archiveCurrent('),source.indexOf('async function syncOriginal('));
    let sent,notice='',stored='',button={disabled:false};
    const work={'wednesday:2026-10-07':{outputs:{ppt:{complete:true}}}};
    const context={
      key:()=> 'sunday:2026-10-11',state:{connected:true,folders:{archive:{id:'archive'}}},
      el:id=>id==='cloud-archive-current'?button:{set textContent(v){stored=v}},
      refresh:async()=>{},api:async(a,b)=>{sent=b;return {item:{id:'new',name:'worship.pptx'},work:{data:work['wednesday:2026-10-07'],revision:2}}},
      syncState:()=>({}),render:()=>{},msg:value=>notice=value,
      app:{output:'pdf',records:work}
    };
    const archive=vm.runInNewContext('('+fn.trim()+')',context);
    archive('wednesday:2026-10-07','ppt').then(()=>console.log(JSON.stringify({sent,disabled:button.disabled,stored})));
    """
    data=json.loads(subprocess.check_output(['node','-e',code],text=True))
    assert data['sent']=={'date':'2026-10-07','service':'wednesday','kind':'ppt'}
    assert data['disabled'] is False
    assert '보관 완료' in data['stored']


def test_large_completed_ppt_uses_archive_limit(cloud,monkeypatch):
    from media_automation.web.original.onedrive import MAX_FILE, MAX_ARCHIVE_FILE
    prepare(cloud)
    identifier='b'*32
    cloud.store.save('2026-10-09','friday',0,{'outputs':{'ppt':{'fileId':identifier,'complete':True,'changed':False}}})
    path=Path(cloud.store.path).with_suffix('.generated')/(identifier+'.pptx');path.parent.mkdir()
    with path.open('wb') as f:f.truncate(260*1024*1024)
    real_read=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda self:b'test-content' if self==path else real_read(self))
    uploaded=[]
    monkeypatch.setattr(cloud,'archive_destination',lambda service,kind:{'id':'archive'})
    monkeypatch.setattr(cloud,'upload_file',lambda folder,name,content:uploaded.append((folder,name,content)) or item('saved',parent='archive'))
    cloud.archive('2026-10-09','friday','ppt')
    assert uploaded and MAX_FILE==128*1024*1024
    with path.open('wb') as f:f.truncate(MAX_ARCHIVE_FILE+1)
    with pytest.raises(CloudError,match='512MB'):cloud.archive('2026-10-09','friday','ppt')
    assert len(uploaded)==1


def test_auto_connect_never_registers_non_song_files(cloud, monkeypatch):
    prepare(cloud)
    names = [
        'bulletin-runtime-original-design.pdf',
        'cover.pptx',
        'community-prayer.mp3',
        'worship-template.pptx',
        '교회여 일어나라.mp4',
    ]
    files = []
    for i, name in enumerate(names):
        entry = item(str(i))
        entry['name'] = name
        files.append(entry)
    monkeypatch.setattr(cloud, 'children', lambda _: files)
    importer = Mock()
    monkeypatch.setattr(cloud, 'import_song', importer)
    result = cloud.auto_connect()
    assert cloud.store.songs() == []
    assert result['linked'] == 0
    # The unregistered video is reported for a manual song selection,
    # never silently registered with an unverified title.
    assert [choice['name'] for choice in result['choices']] == ['교회여 일어나라.mp4']
    importer.assert_not_called()


def test_auto_connect_still_links_existing_song_score(cloud, monkeypatch):
    prepare(cloud)
    song = cloud.store.register_song({'title': '찬양 테스트'})
    original = item('song')
    original['name'] = '찬양 테스트.pptx'
    monkeypatch.setattr(cloud, 'children', lambda _: [original])
    importer = Mock(return_value={'digest': 'a' * 64})
    monkeypatch.setattr(cloud, 'import_song', importer)
    result = cloud.auto_connect()
    assert result['linked'] == 1
    importer.assert_called_once_with('song', song['id'])
