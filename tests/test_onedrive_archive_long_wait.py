"""Long OneDrive response and overlapping retries must not corrupt an approved output."""
import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from media_automation.web.original.onedrive import CloudError, OneDrive
from media_automation.web.original.work_store import WorkStore


def test_while_one_archive_is_uploading_second_request_is_rejected(tmp_path,monkeypatch):
    store=WorkStore(tmp_path/'review.db')
    day='2026-10-18'
    identifier='a'*32
    store.save(day,'sunday',0,{'fields':{},'outputs':{
        'pdf':{'fileId':identifier,'complete':True,'changed':False},'ppt':{}
    }})
    folder=Path(store.path).with_suffix('.generated')
    folder.mkdir()
    (folder/(identifier+'.pdf')).write_bytes(b'%PDF-1.4\\nREVIEWED\\n%%EOF')
    cloud=OneDrive(store)
    monkeypatch.setattr(cloud,'archive_destination',lambda *_: {'id':'some_folder'})
    started=threading.Event()
    released=threading.Event()
    sent=[]
    responses=[]

    def upload(parent,name,data,**kwargs):
        started.set()
        if not released.wait(5):
            raise AssertionError('test upload mock never released')
        sent.append((parent,name,data))
        return {'id':'uploaded','name':name,'size':len(data),'file':{}}

    monkeypatch.setattr(cloud,'upload_file',upload)
    def run():
        try:
            responses.append(cloud.archive(day,'sunday','pdf'))
        except Exception as exc:
            responses.append(exc)
    thread=threading.Thread(target=run,daemon=True)
    thread.start()
    try:
        assert started.wait(2), 'original upload did not start'
        with pytest.raises(CloudError,match='업로드 중'):
            cloud.archive(day,'sunday','pdf')
        assert not sent
        assert 'archiveStatus' not in store.get(day,'sunday')['data']['outputs']['pdf']
    finally:
        released.set()
        thread.join(timeout=5)
    assert len(sent)==1
    assert len(responses)==1 and isinstance(responses[0],dict)
    assert store.get(day,'sunday')['data']['outputs']['pdf']['complete']
    assert store.get(day,'sunday')['data']['outputs']['pdf']['archiveStatus']=='uploaded'


def test_browser_archive_timeout_unlocks_without_claiming_failure(tmp_path):
    if not shutil.which('node'):
        pytest.skip('node is unavailable')
    script=r"""
    const fs=require('fs');
    const src=fs.readFileSync(process.argv[2], 'utf8');
    const part=src.slice(src.indexOf(' async function archiveCurrent('),
                         src.indexOf(' async function syncOriginal('));
    const k='sunday:2026-10-18';
    const output={fileId:'a'.repeat(32),complete:true,changed:false};
    const app={output:'pdf',records:{[k]:{outputs:{pdf:output}}}};
    const state={connected:true,folders:{},shared_archives:{archive_sunday_pdf:{name:'00.주보'}}};
    const status={textContent:''},button={disabled:false};
    const el=id=>id==='storage-status'?status:id==='cloud-archive-current'?button:null;
    const refresh=async()=>{};
    const calls=[];
    const api=async(action,body,options)=>{
      calls.push(action);
      return await new Promise((resolve,reject)=>{
        if(!options?.signal)throw Error('timeout needs cancellable fetch');
        options.signal.addEventListener('abort',()=>reject(Error('request cancelled')));
      });
    };
    let cleared=false;
    const fakeTimeout=fn=>{queueMicrotask(fn);return 1;};
    const fakeClear=()=>{cleared=true;};
    const fn=new Function('state','el','key','app','refresh','api','syncState','render',
      'persistDraft','msg','setTimeout','clearTimeout','setInterval','clearInterval',
      'AbortController',part+';return archiveCurrent;');
    const archiveCurrent=fn(state,el,()=>k,app,refresh,api,()=>({dirty:false,busy:false}),
      ()=>{},()=>{},()=>{},fakeTimeout,fakeClear,()=>1,()=>{},AbortController);
    (async()=>{
      let error=null;
      try{await archiveCurrent(k,'pdf');}catch(e){error=e;}
      if(!error?.uncertain || button.disabled || !status.textContent.includes('결과 미확인')||
         !cleared||calls.join(',')!=='archive'){
        throw Error(JSON.stringify({error:String(error),locked:button.disabled,text:status.textContent,cleared,calls}));
      }
      console.log('browser retry recovery passed');
    })().catch(e=>{console.error(e);process.exitCode=1;});
    """
    js=tmp_path/'check.js';js.write_text(script)
    result=subprocess.run(['node',str(js),'src/media_automation/web/original/ui/onedrive.js'],
        text=True,capture_output=True,timeout=5)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert 'browser retry recovery passed' in result.stdout
