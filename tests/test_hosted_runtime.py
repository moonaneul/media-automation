from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest
import requests

from media_automation.cloud.artifacts import download_verified, upload_verified
from media_automation.cloud.dispatcher import Dispatcher
from media_automation.cloud.http import Hosted
from media_automation.cloud.sessions import Sessions
from media_automation.cloud.supabase_auth import AuthUnavailable, Member
from media_automation.cloud.supabase_work_store import WorkStoreUnavailable
from media_automation.cloud.worker import execute, render_artifact
from media_automation.web.original.onedrive import CloudError
from media_automation.web.original.work_store import RevisionConflict


def response(status, data):
    result=Mock(status_code=status)
    result.json.return_value=data
    return result


def test_shared_sessions_survive_restart_and_logout_revokes_every_instance():
    rows={}
    def remote(method,url,headers,**kwargs):
        assert headers['apikey']=='sb_secret_fake'
        if method=='POST':
            row=deepcopy(kwargs['json']);rows[row['id']]=row
            assert 'upstream-token' not in row['ciphertext']
            return response(201,[row])
        params=kwargs.get('params',{})
        identifier=params.get('id','').removeprefix('eq.')
        if method=='DELETE':
            if identifier:rows.pop(identifier,None)
            return response(200,[])
        return response(200,[rows[identifier]] if identifier in rows else [])
    key=Fernet.generate_key()
    with patch('media_automation.cloud.sessions.requests.request',side_effect=remote):
        first=Sessions('https://example.supabase.co','sb_secret_fake',key)
        cookie=first.create('upstream-token',Member(str(uuid4()),'admin'))
        assert len(cookie)==43 and cookie!='upstream-token'
        second=Sessions('https://example.supabase.co','sb_secret_fake',key)
        assert second.read(cookie)=='upstream-token'
        second.delete(cookie)
        assert first.read(cookie) is None


def test_session_backend_failure_is_not_anonymous_access():
    sessions=Sessions('https://example.supabase.co','sb_secret_fake',Fernet.generate_key())
    with patch('media_automation.cloud.sessions.requests.request',side_effect=requests.Timeout):
        with pytest.raises(AuthUnavailable):sessions.read('a'*43)


def test_session_purpose_tampering_and_expiration_fail_closed():
    sessions=Sessions('https://example.supabase.co','sb_secret_fake',Fernet.generate_key())
    for state in ({'purpose':'wrong','user_id':'x','expires':9999999999,'token':'secret'},
                  {'purpose':'media-http-session-v1','user_id':'x','expires':1,'token':'secret'}):
        row={'user_id':'x','ciphertext':sessions.cipher.encrypt(json.dumps(state).encode()).decode()}
        with patch.object(sessions,'_request',return_value=[row]):assert sessions.read('a'*43) is None


def test_dispatcher_uses_only_fixed_worker_and_validated_uuid():
    backend=Mock();backend.call.return_value={'dispatch':True};http=Mock();http.post.return_value=response(200,{})
    dispatcher=Dispatcher('projects/church/locations/asia-northeast3/jobs/media-worker',backend,http)
    identifier=str(uuid4())
    assert dispatcher.start(identifier)
    options=http.post.call_args.kwargs['json']
    assert options=={'overrides':{'containerOverrides':[{'name':'worker','env':[{'name':'MEDIA_JOB_ID','value':identifier}]}],'taskCount':1}}
    with pytest.raises(ValueError):dispatcher.start('bad;command')
    assert http.post.call_count==1


def test_dispatch_unknown_and_duplicate_never_trigger_second_execution():
    backend=Mock();backend.call.side_effect=[{'dispatch':True},{'dispatch':False}]
    http=Mock();http.post.side_effect=requests.Timeout
    dispatcher=Dispatcher('projects/church/locations/asia-northeast3/jobs/media-worker',backend,http)
    identifier=str(uuid4())
    with pytest.raises(WorkStoreUnavailable):dispatcher.start(identifier)
    assert not dispatcher.start(identifier)
    assert http.post.call_count==1


def cloud_download(data=b'valid'):
    cloud=Mock()
    item={'id':'abc','file':{},'size':len(data),'parentReference':{'driveId':'drive'},
          '@microsoft.graph.downloadUrl':'https://files.1drv.com/source'}
    cloud.item.return_value=item;cloud.within.return_value=True
    stream=Mock(status_code=200);stream.iter_content.return_value=[data]
    context=Mock();context.__enter__=Mock(return_value=stream);context.__exit__=Mock(return_value=False)
    cloud.http.get.return_value=context
    record={'item_id':'abc','drive_id':'drive','size':len(data),'digest':hashlib.sha256(data).hexdigest()}
    return cloud,record


@pytest.mark.parametrize('fault',['hash','size','location','url'])
def test_wrong_download_never_leaves_a_partial_artifact(tmp_path,fault):
    cloud,record=cloud_download()
    if fault=='hash':record['digest']='a'*64
    if fault=='size':record['size']+=1
    if fault=='location':cloud.within.return_value=False
    if fault=='url':cloud.item.return_value['@microsoft.graph.downloadUrl']='https://evil.example/secret'
    target=tmp_path/'output'
    with pytest.raises(CloudError):download_verified(cloud,record,target)
    assert not target.exists()


def test_existing_download_destination_is_preserved(tmp_path):
    cloud,record=cloud_download();target=tmp_path/'keep';target.write_bytes(b'keep')
    with pytest.raises(FileExistsError):download_verified(cloud,record,target)
    assert target.read_bytes()==b'keep'


def test_upload_uses_conflict_fail_and_checks_download_hash(tmp_path):
    cloud,record=cloud_download(b'valid');target=tmp_path/'file.pptx';target.write_bytes(b'valid')
    cloud.graph.return_value={'uploadUrl':'https://uploads.1drv.com/session'}
    cloud.http.put.return_value=response(201,{'id':'abc','size':5,'parentReference':{'driveId':'drive'}})
    uploaded=upload_verified(cloud,target,{'id':'abc'},'unique.pptx')
    assert cloud.graph.call_args.kwargs['body']['item']['@microsoft.graph.conflictBehavior']=='fail'
    assert uploaded['digest']==record['digest']
    assert cloud.http.get.call_count==1
    assert not target.with_name('file.pptx.verified').exists()


@pytest.fixture
def production(tmp_path):
    identifier=str(uuid4());backend=Mock();cloud=Mock()
    snapshot={'day':'2026-10-14','service':'wednesday','catalog_revision':3,
              'work':{'revision':1,'data':{'fields':{}}}}
    backend.claim.return_value={'claimed':True,'id':identifier,'output':'ppt','groups':[],'snapshot':snapshot}
    backend.call.return_value={'active':True};backend.finish.return_value={'finished':True}
    store=SimpleNamespace(path=str(tmp_path/'work.db'))
    directory=Path(store.path).with_suffix('.generated');directory.mkdir()
    file_id='a'*32
    def generate(store,body):
        assert body['revision']==1 and body['date']=='2026-10-14'
        (directory/(file_id+'.pptx')).write_bytes(b'ppt')
        (directory/(file_id+'.json')).write_text(json.dumps({'fields':{},'unresolved':[]}))
        return {'file_id':file_id,'filename':'output.pptx','unresolved':[],'slide_count':1}
    @contextmanager
    def materialize(snapshot,cloud,output):yield store
    render=Mock(return_value=(directory/(file_id+'.pptx'),{'rendered':True,'visual_review_pending':True}))
    return identifier,backend,cloud,generate,materialize,render


def test_worker_finishes_only_after_generation_render_and_verified_uploads(production):
    identifier,backend,cloud,generate,materialize,render=production
    uploads=[]
    def upload(cloud,path,*args,**kwargs):
        uploads.append(path.suffix)
        assert render.called
        return {'filename':path.name,'item_id':'abc','digest':'a'*64,'drive_id':'d','size':3}
    with patch('media_automation.cloud.worker.materialize',materialize),patch('media_automation.web.original.generation.generate',generate),patch('media_automation.cloud.worker.upload_verified',side_effect=upload):
        result=execute(identifier,'execution',backend,cloud,render)
    assert result['succeeded']
    assert uploads==['.pptx','.json']
    result=backend.finish.call_args.args[3]
    assert result['complete'] is False and result['visual_review_pending'] is True


@pytest.mark.parametrize('stage',['render','upload','revoked'])
def test_worker_failure_cannot_publish_success(production,stage):
    identifier,backend,cloud,generate,materialize,render=production
    if stage=='render':render.side_effect=ValueError('render failed')
    if stage=='revoked':backend.call.return_value={'active':False}
    with patch('media_automation.cloud.worker.materialize',materialize),patch('media_automation.web.original.generation.generate',generate),patch('media_automation.cloud.worker.upload_verified',side_effect=ValueError('upload failed')):
        result=execute(identifier,'execution',backend,cloud,render)
    assert result['succeeded'] is False
    assert backend.finish.call_args.args[2] is False
    assert 'render failed' not in json.dumps(result)


def test_duplicate_claim_does_not_generate(production):
    identifier,backend,cloud,generate,materialize,render=production
    backend.claim.return_value={'claimed':False}
    assert execute(identifier,'execution',backend,cloud,render)=={'claimed':False}
    render.assert_not_called();backend.finish.assert_not_called()


def test_catalog_conflict_never_reports_success():
    client=Mock();client._request.return_value={'saved':False,'revision':7}
    with pytest.raises(RevisionConflict):Hosted.edit(client,{'catalog_revision':6},'review',{})


def test_bulletin_render_rejects_wrong_page_size(tmp_path):
    import pymupdf
    path=tmp_path/'wrong.pdf'
    with pymupdf.open() as doc:
        doc.new_page(width=400,height=400);doc.new_page(width=400,height=400);doc.save(path)
    with pytest.raises(ValueError,match='landscape A4'):render_artifact(path,'pdf',{})


def test_upload_capability_cannot_be_reused_by_another_member():
    key=Fernet.generate_key();sessions=SimpleNamespace(cipher=Fernet(key))
    hosted=Hosted(Mock(),sessions,Mock(),Mock(),Mock())
    sealed=sessions.cipher.encrypt(json.dumps({'purpose':'media-source-upload-v1','expires':9999999999,'user_id':'owner'}).encode()).decode()
    with pytest.raises(ValueError):hosted.upload_finish(Mock(),Member('other','editor'),{'sealed':sealed,'item_id':'abc'})
    hosted.cloud.item.assert_not_called()


def test_generated_result_can_be_loaded_on_another_device_without_local_files():
    client=Mock()
    data={'fields':{'설교 제목':{'state':'VALUE','value':'확정 제목'}}}
    client.list.return_value=[{'status':'succeeded','input':deepcopy(data),'output':'ppt',
        'result':{'file_id':'a'*32,'filename':'예배.pptx','unresolved':[]}}]
    current={'revision':4,'data':deepcopy(data)}
    restored=Hosted.with_results(client,'2026-10-14','wednesday',current)
    assert restored['data']['outputs']['ppt']['fileId']=='a'*32
    assert 'outputs' not in current['data']
    changed=deepcopy(current);changed['data']['fields']['설교 제목']['value']='수정 제목'
    assert 'outputs' not in Hosted.with_results(client,'2026-10-14','wednesday',changed)['data']
    stale=deepcopy(current)
    stale['data']['outputs']={'ppt':{'fileId':'old-local-file','changed':True,'complete':False}}
    assert Hosted.with_results(client,'2026-10-14','wednesday',stale)['data']['outputs']['ppt']['fileId']=='a'*32
    stale['data']['outputs']['ppt']['complete']=True
    assert Hosted.with_results(client,'2026-10-14','wednesday',stale)['data']['outputs']['ppt']['fileId']=='old-local-file'
