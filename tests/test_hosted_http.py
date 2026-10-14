import json
from types import SimpleNamespace
import threading
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from media_automation.cloud.http import Hosted
from media_automation.cloud.supabase_auth import AuthUnavailable, Member
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import RevisionConflict


@pytest.fixture
def hosted_app():
    auth=Mock(url='https://example.supabase.co',key='sb_publishable_fake')
    auth.login.return_value='upstream-private-token';auth.authenticate.return_value=Member('approved','admin')
    state={}
    sessions=Mock()
    def create(token,member):state['a'*43]=token;return 'a'*43
    sessions.create.side_effect=create;sessions.read.side_effect=lambda cookie:state.get(cookie)
    sessions.delete.side_effect=lambda cookie:state.pop(cookie,None)
    hosted=Hosted(auth,sessions,Mock(),Mock(),Mock())
    client=Mock();client.list.return_value=[];client.get.return_value={'revision':2,'data':{'fields':{}},'updated_at':None}
    hosted.client=Mock(return_value=client)
    server=make_server(SimpleNamespace(path='/nonexistent/no-local-db'),bind_host='127.0.0.1',
        public_origin='https://media.example.test',supabase_auth=auth,hosted=hosted)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(path,body=None,cookie='',host='media.example.test',origin='https://media.example.test'):
        headers={'Host':host,'X-Forwarded-Proto':'https','Content-Type':'application/json'}
        if origin is not None:headers['Origin']=origin
        if cookie:headers['Cookie']='media_session='+cookie
        try:
            response=urlopen(Request(f'http://127.0.0.1:{server.server_port}'+path,
                data=json.dumps(body).encode() if body is not None else None,headers=headers),timeout=3)
        except HTTPError as error:response=error
        with response:
            content=response.read()
            return response.status,content,response.headers
    yield hosted,client,auth,request
    server.shutdown();server.server_close();thread.join()


def login(request):
    code,body,headers=request('/api/login',{'email':'test@example.test','password':'private'})
    assert code==200
    cookie=headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=Strict' in cookie
    assert 'upstream' not in cookie
    return cookie.split(';')[0].split('=',1)[1]


def test_existing_ui_and_health_check_do_not_require_credentials(hosted_app):
    _,_,_,request=hosted_app
    assert request('/healthz',host='health-probe',origin=None)[0]==200
    code,html,_=request('/')
    assert code==200 and b'cloud-runtime.js' in html and b'notice-parser.js' in html


@pytest.mark.parametrize('path',['/api/work?date=2026-10-14&service=wednesday','/api/songs','/api/jobs?id=bad','/api/generated?id=bad'])
def test_every_cloud_data_endpoint_blocks_anonymous_users(hosted_app,path):
    _,client,_,request=hosted_app
    assert request(path)[0]==401
    client.get.assert_not_called()


def test_cloud_work_uses_user_token_and_never_creates_local_db(hosted_app):
    hosted,client,_,request=hosted_app;cookie=login(request)
    code,content,_=request('/api/work?date=2026-10-14&service=wednesday',cookie=cookie)
    assert code==200 and json.loads(content)['revision']==2
    hosted.client.assert_called_with('upstream-private-token')
    client.get.assert_called_with('2026-10-14','wednesday')
    assert b'upstream-private-token' not in content


@pytest.mark.parametrize('origin',[None,'https://evil.example'])
def test_hosted_mutations_require_exact_origin(hosted_app,origin):
    _,client,_,request=hosted_app
    cookie=login(request)
    assert request('/api/work?date=2026-10-14&service=wednesday',{'revision':2,'data':{}},cookie=cookie,origin=origin)[0]==403
    client.save.assert_not_called()


def test_logout_revokes_shared_session(hosted_app):
    _,client,_,request=hosted_app;cookie=login(request)
    assert request('/api/logout',{},cookie=cookie)[0]==200
    assert request('/api/work?date=2026-10-14&service=wednesday',cookie=cookie)[0]==401


def test_conflict_and_unavailable_store_never_fall_back(hosted_app):
    _,client,_,request=hosted_app;cookie=login(request)
    client.save.side_effect=RevisionConflict({'revision':3,'data':{}})
    code,body,_=request('/api/work?date=2026-10-14&service=wednesday',{'revision':2,'data':{}},cookie=cookie)
    assert code==409 and json.loads(body)['current']['revision']==3
    client.get.side_effect=RuntimeError('secret-in-upstream-error')
    code,body,_=request('/api/work?date=2026-10-14&service=wednesday',cookie=cookie)
    assert code==503 and b'secret-in-upstream-error' not in body


def test_session_backend_outage_does_not_bypass_login(hosted_app):
    hosted,client,_,request=hosted_app;cookie=login(request)
    hosted.sessions.read.side_effect=AuthUnavailable()
    assert request('/api/work?date=2026-10-14&service=wednesday',cookie=cookie)[0]==503
    client.get.assert_not_called()


def test_build_returns_job_id_without_waiting_or_exposing_snapshot(hosted_app):
    hosted,client,_,request=hosted_app;cookie=login(request)
    client.start.return_value={'queued':True,'id':'pending-job','status':'queued'}
    code,content,_=request('/api/build',{'date':'2026-10-14','service':'wednesday','revision':2,
        'output':'ppt','groups':[],'request_key':'request'},cookie=cookie)
    assert code==202 and json.loads(content)['id']=='pending-job'
    hosted.dispatcher.start.assert_called_once_with('pending-job')
    assert 'snapshot' not in json.loads(content)


def test_generated_download_uses_chunked_transfer_and_preserves_exact_bytes(hosted_app,tmp_path,monkeypatch):
    hosted,client,_,request=hosted_app;cookie=login(request)
    content=b'0123456789'*200000
    record={'filename':'verified.pptx'}
    client.artifact_job.return_value={'output':'ppt','result':{'artifact':record}}
    def download(cloud,record,target):
        target.write_bytes(content)
        return target
    monkeypatch.setattr('media_automation.cloud.http.download_verified',download)
    code,body,headers=request('/api/generated?id='+('a'*32)+'&format=pptx',cookie=cookie)
    assert code==200 and body==content
    assert headers['Transfer-Encoding']=='chunked'
    assert headers.get('Content-Length') is None
    assert headers['Connection']=='close'
