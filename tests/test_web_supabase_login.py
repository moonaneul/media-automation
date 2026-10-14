import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import Mock
import pytest
from media_automation.cloud.supabase_auth import AccessDenied, AuthUnavailable, Member
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore

@pytest.fixture
def app(tmp_path):
    provider=Mock()
    provider.login.return_value='upstream-secret-token'
    provider.authenticate.return_value=Member('test-user','admin')
    server=make_server(WorkStore(tmp_path/'test.db'),supabase_auth=provider)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}',provider
    server.shutdown();server.server_close();thread.join()

def request(base,path,cookie=None,data=None):
    headers={}
    if cookie: headers['Cookie']=cookie
    if data is not None: headers['Content-Type']='application/json'
    return urlopen(Request(base+path,headers=headers,data=None if data is None else json.dumps(data).encode()),timeout=5)

def login(base):
    with request(base,'/api/login',data={'email':'test@example.com','password':'test-password'}) as r:
        cookie=r.headers['Set-Cookie']
        assert 'HttpOnly' in cookie and 'SameSite=Strict' in cookie
        assert 'upstream-secret-token' not in cookie
        return cookie.split(';')[0]

@pytest.mark.parametrize('path',['/api/work?date=2026-10-14&service=wednesday','/api/generated?id='+'a'*32+'&format=pptx','/api/original?digest=test','/api/bulletin-settings'])
def test_anonymous_blocked(app,path):
    base,_=app
    with pytest.raises(HTTPError) as exc: request(base,path)
    assert exc.value.code==401

def test_login_work_logout(app):
    base,provider=app
    with request(base,'/api/mode') as r:
        mode=json.load(r);assert mode['password_required'] and mode['auth_provider']=='supabase'
        assert not mode['authenticated']
    cookie=login(base)
    with request(base,'/api/work?date=2026-10-14&service=wednesday',cookie) as r: assert r.status==200
    provider.authenticate.assert_called_with('Bearer upstream-secret-token')
    with request(base,'/api/logout',cookie,data={}) as r: assert r.status==200
    with pytest.raises(HTTPError) as exc: request(base,'/api/bulletin-settings',cookie)
    assert exc.value.code==401

@pytest.mark.parametrize('error,code',[(AccessDenied('revoked'),401),(AuthUnavailable('offline'),503)])
def test_revoked_or_unavailable_denies_existing_session(app,error,code):
    base,provider=app;cookie=login(base);provider.authenticate.side_effect=error
    with pytest.raises(HTTPError) as exc: request(base,'/api/bulletin-settings',cookie)
    assert exc.value.code==code

def test_invalid_login_never_sets_cookie(app):
    base,provider=app;provider.login.side_effect=AccessDenied('wrong password')
    with pytest.raises(HTTPError) as exc: request(base,'/api/login',data={'email':'test@example.com','password':'bad'})
    assert exc.value.code==401 and 'Set-Cookie' not in exc.value.headers
