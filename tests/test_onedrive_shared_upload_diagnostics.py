"""Safe regression for long-running Microsoft Graph uploads in the local server.

No real Microsoft login, external requests, or historical church assets used.
"""
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from media_automation.web.original.onedrive import OneDrive
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore


def test_archive_status_remains_readable_during_remote_wait(tmp_path, monkeypatch):
    day='2026-10-18'
    store=WorkStore(tmp_path/'work.db')
    artifact='a'*32
    store.save(day,'sunday',0,{'fields':{},'outputs':{
        'pdf':{'fileId':artifact,'generated':True,'complete':True,'changed':False},
        'ppt':{},
    }})
    generated=Path(store.path).with_suffix('.generated')
    generated.mkdir()
    (generated/(artifact+'.pdf')).write_bytes(b'%PDF-1.4\\nmock only\\n%%EOF')
    upload_started=threading.Event()
    allow_upload=threading.Event()
    background_result=[]

    def destination(_self,_service,_kind,_mode=None):
        return {'id':'team-folder','name':'00.주보'}

    def upload(_self,parent,name,content,**_kw):
        assert parent=='team-folder'
        upload_started.set()
        assert allow_upload.wait(timeout=7),'test timeout'
        return {'id':'remote-upload','name':name,'size':len(content),'file':{}}

    def graph(_self,path,**_kw):
        if path.endswith('/children?$top=1'):
            return {'value':[]}
        if path=='/me/drive/items/team-folder':
            return {'folder':{},'name':'00.주보'}
        raise AssertionError('Unexpected Graph path: '+path)

    monkeypatch.setattr(OneDrive,'archive_destination',destination)
    monkeypatch.setattr(OneDrive,'upload_file',upload)
    monkeypatch.setattr(OneDrive,'graph',graph)
    server=make_server(store,0)
    host=f'http://127.0.0.1:{server.server_port}'
    srv=threading.Thread(target=server.serve_forever,daemon=True)
    srv.start()

    def do_archive():
        data=json.dumps({'date':day,'service':'sunday','kind':'pdf'}).encode('utf8')
        with urlopen(Request(host+'/api/onedrive/archive',data=data,
                headers={'Content-Type':'application/json'},method='POST'),timeout=8) as response:
            background_result.append((response.status,json.load(response)))

    pending=threading.Thread(target=do_archive,daemon=True)
    try:
        pending.start()
        assert upload_started.wait(3), 'archive was not started'
        # Previously the HTTP handler held cloud.lock for the entire upload,
        # so these GET calls would block even with ThreadingHTTPServer.
        with urlopen(host+'/api/onedrive/archive-progress?date='+day+
                     '&service=sunday&kind=pdf',timeout=2) as response:
            progress=json.load(response)
        assert progress['active'] is True
        assert progress['stage']=='Microsoft OneDrive 업로드 요청 중'
        assert 'token' not in str(progress).lower()
        assert 'drive_id' not in str(progress)
        with urlopen(host+'/api/onedrive/archive-check?service=sunday&kind=pdf',timeout=2) as response:
            check=json.load(response)
        assert check['folder_readable']
        assert check['target']=='00.주보'
        assert not check['write_verified']
        assert not background_result
    finally:
        allow_upload.set()
        pending.join(timeout=8)
        server.shutdown()
        server.server_close()
        srv.join(timeout=4)
    assert background_result[0][0]==201
    assert background_result[0][1]['work']['data']['outputs']['pdf']['archiveStatus']=='uploaded'


def test_shared_lookup_redeems_link_persistently(tmp_path,monkeypatch):
    from unittest.mock import Mock
    from media_automation.web.original.onedrive import GRAPH
    cloud=OneDrive(WorkStore(tmp_path/'work.db'))
    monkeypatch.setattr(cloud,'_token',lambda:'fake-token')
    response=Mock(status_code=200)
    response.json.return_value={'folder':{}}
    cloud.http=Mock()
    cloud.http.request.return_value=response
    cloud.graph('/shares/u!aabbccdd/driveItem')
    kwargs=cloud.http.request.call_args.kwargs
    assert kwargs['headers']['Prefer']=='redeemSharingLink'
    assert kwargs['headers']['Authorization']=='Bearer fake-token'
    assert 'Prefer' not in cloud.http.request.call_args.args
