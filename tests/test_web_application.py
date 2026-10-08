import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from media_automation.web.application import Application
from media_automation.web.server import make_server


def app(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    for name in ('sunday','wednesday','friday','bulletin'):
        (repo/f'{name}.py').write_text("from pathlib import Path\np=Path('output/result.pdf');p.parent.mkdir(exist_ok=True);p.write_bytes(b'%PDF-test')\n")
    return Application(repo,tmp_path/'jobs')


def test_adapter_generation_and_failed_result_visibility(tmp_path):
    a=app(tmp_path);j=a.create('bulletin','2026-09-27')['job_id']
    a.upload(j,'input/notice.txt',b'explicit')
    with pytest.raises(ValueError):a.upload(j,'output/old.pdf',b'old')
    with pytest.raises(ValueError):a.upload(j,'input/evil.py',b'code')
    with pytest.raises(ValueError):a.upload(j,'../escape.txt',b'escape')
    a.start(j)
    deadline=time.monotonic()+5
    while a.active and time.monotonic()<deadline:time.sleep(.01)
    assert a.active is None
    assert a.get(j)['state']=='generated'
    assert a.artifact(j,'output/result.pdf').read_bytes()==b'%PDF-test'
    with pytest.raises(ValueError):a.artifact(j,'output/unknown.pdf')
    a.upload(j,'input/new.txt',b'revised')
    assert a.get(j)['state']=='needs_input'
    with pytest.raises(ValueError):a.artifact(j,'output/result.pdf')


def test_recovery_and_source_validation(tmp_path):
    a=app(tmp_path);j=a.create('sunday','2026-09-27')['job_id']
    with pytest.raises(ValueError):a.start(j, '../escape.pptx')
    record=a.get(j);record.update(state='running',artifacts=['output/old.pdf'])
    a.jobs._save(a.jobs._directory(j),record)
    a.recover()
    assert a.get(j)['state']=='interrupted'
    assert a.get(j)['artifacts']==[]
    with pytest.raises(ValueError):a.start(j,'input/a.pptx')


def test_http_auth_origin_and_actual_create_upload(tmp_path):
    a=app(tmp_path);server,token=make_server(a,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path,body=None,headers=None):
        data=json.dumps(body).encode() if body is not None else None
        return urlopen(Request(base+path,data=data,headers=headers or {}),timeout=3)
    try:
        assert b'<html lang="ko">' in request('/').read()
        with pytest.raises(HTTPError) as rejected:request('/api/jobs')
        assert rejected.value.code==401
        headers={'Authorization':'Bearer '+token}
        with pytest.raises(HTTPError) as rejected:request('/api/jobs',headers={**headers,'Origin':'https://evil.example'})
        assert rejected.value.code==403
        j=json.load(request('/api/jobs',{'service':'bulletin','date':'2026-09-27'},headers))['job_id']
        result=json.load(urlopen(Request(base+f'/api/jobs/{j}/files?path=input/notice.txt',data=b'latest',headers=headers),timeout=3))
        assert 'input/notice.txt' in result['inputs']
        assert len(json.load(request('/api/jobs',headers=headers)))==1
    finally:
        server.shutdown();server.server_close();thread.join()
