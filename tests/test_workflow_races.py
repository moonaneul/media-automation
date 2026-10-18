"""Execute the real UI handlers while switching views or editing mid-request."""
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock
import pytest
from media_automation.web.original.onedrive import OneDrive, CloudError
from media_automation.web.original.work_store import WorkStore

HTML = Path('src/media_automation/web/original/ui/index.html')


@pytest.mark.parametrize('service,kind',[('wednesday','ppt'),('friday','ppt'),('sunday','ppt'),('sunday','pdf')])
@pytest.mark.parametrize('phase',['flush','cloud','response','edit'])
def test_build_response_stays_with_requested_week(service,kind,phase):
    code = r"""
    const fs=require('fs'),vm=require('vm');const html=fs.readFileSync(process.argv[1],'utf8');
    const handler=html.split('\n').find(x=>x.startsWith("$('simulate-build').onclick="));
    const [service,kind,phase]=process.argv.slice(2);const origin=service+':2026-10-11',other='sunday:2026-10-18';
    const records={[origin]:{fields:{title:'original'},outputs:{ppt:{},pdf:{}}},[other]:{fields:{title:'other week'},outputs:{ppt:{},pdf:{}}}};
    const elements={};let active=origin,request,saved,tab;const st={revision:7,loaded:true};
    const switchNow=()=>{active=other;ctx.service='sunday';ctx.output=kind==='ppt'?'pdf':'ppt'};
    const ctx={service,output:kind,shared:true,records,structuredClone,
      $:id=>elements[id]??=( {close(){}} ),key:()=>active,record:()=>records[active],
      currentGroups:()=>[['original',['title']]],syncState:()=>st,msg:()=>{},save:k=>{saved=k},
      flushShared:async()=>{if(phase==='flush')switchNow()},
      CloudMedia:{autoConnect:async()=>{if(phase==='cloud')switchNow()}},
      fetch:async(url,options)=>{request=JSON.parse(options.body);if(phase==='response')switchNow();
        if(phase==='edit')records[origin].fields.title='new input';
        return {ok:true,json:async()=>({file_id:'test-file',slide_count:5,filename:'test.pptx',unresolved:[]})}},
      setTab:x=>{tab=x},iso:()=> '2026-10-18',day:()=>null};
    vm.createContext(ctx);vm.runInContext(handler,ctx);
    elements['simulate-build'].onclick().then(()=>{if(request.service!==service||request.date!=='2026-10-11'||request.output!==kind)throw Error('wrong request');
      if(saved!==origin||records[origin].outputs[kind].fileId!=='test-file')throw Error('wrong saved week');
      if(records[other].outputs.ppt.fileId||records[other].outputs.pdf.fileId)throw Error('other week contaminated');
      if(phase==='edit'&&(!records[origin].outputs[kind].changed||records[origin].fields.title!=='new input'))throw Error('new input lost');
      console.log('ok');}).catch(e=>{console.error(e);process.exitCode=1});
    """
    assert subprocess.check_output(['node','-e',code,str(HTML),service,kind,phase],text=True).strip() == 'ok'


@pytest.mark.parametrize('server_revision',[7,8,'ack'])
def test_pending_draft_survives_refresh_without_overwriting_newer_server(server_revision):
    code=r"""
    const fs=require('fs'),vm=require('vm');const html=fs.readFileSync(process.argv[1],'utf8');
    const ack=process.argv[2]==='ack',revision=ack?9:Number(process.argv[2]),k='friday:2026-10-09',st={revision:7,loaded:true,dirty:true};
    const cache=new Map(),records={[k]:{fields:{title:'unsaved'}}};
    const ctx={records,prefix:'test:',syncState:()=>st,msg:()=>{},key:()=>k,endpoint:()=>'/test',syncLabel:()=>{},render:()=>{},syncBanner:()=>{},document:{activeElement:null},
      sessionStorage:{setItem:(k,v)=>cache.set(k,v),getItem:k=>cache.get(k)||null,removeItem:k=>cache.delete(k)},
      fetch:async()=>({ok:true,json:async()=>({revision,data:{fields:{title:ack?'unsaved':'server'}}})})};
    vm.createContext(ctx);for(const name of ['persistDraft','clearDraft','readDraft','loadShared']){
      const line=html.split('\n').find(x=>x.startsWith('function '+name+'(')||x.startsWith('async function '+name+'('));vm.runInContext(line,ctx);}
    ctx.persistDraft(k);delete records[k];st.loaded=false;st.dirty=false;st.revision=0;
    ctx.loadShared(k).then(()=>{if(ack){if(st.dirty||st.conflict||cache.size)throw Error('already saved draft kept');console.log('ok');return;}
      if(records[k].fields.title!=='unsaved'||!st.dirty)throw Error('draft lost');
      if(Boolean(st.conflict)!==(revision!==7))throw Error('newer server overwritten');console.log('ok');}).catch(e=>{console.error(e);process.exitCode=1});
    """
    assert subprocess.check_output(['node','-e',code,str(HTML),str(server_revision)],text=True).strip() == 'ok'


@pytest.mark.parametrize('fault',['edit_during_save','timeout','none'])
def test_save_acknowledgment_keeps_newer_input_and_pending_draft(fault):
    code=r"""
    const fs=require('fs'),vm=require('vm');const html=fs.readFileSync(process.argv[1],'utf8'),fault=process.argv[2];
    const k='wednesday:2026-10-07',st={revision:7,loaded:true,dirty:true},records={[k]:{fields:{title:'original'}}},cache=new Map();
    let calls=0;const ctx={records,prefix:'test:',syncState:()=>st,key:()=>k,endpoint:()=>'/test',syncLabel:()=>{},msg:()=>{},syncBanner:()=>{},
      sessionStorage:{setItem:(k,v)=>cache.set(k,v),getItem:k=>cache.get(k)||null,removeItem:k=>cache.delete(k)},
      fetch:async()=>{calls++;if(calls===1&&fault==='timeout')throw Error('test disconnect');
        if(calls===1&&fault==='edit_during_save'){records[k].fields.title='newer';st.dirty=true;ctx.persistDraft(k);}
        return {ok:true,status:200,json:async()=>({revision:calls+7})}}};
    vm.createContext(ctx);for(const name of ['persistDraft','clearDraft','readDraft','flushShared']){
      vm.runInContext(html.split('\n').find(x=>x.startsWith('function '+name+'(')||x.startsWith('async function '+name+'(')),ctx);}
    ctx.persistDraft(k);ctx.flushShared(k).then(async()=>{
      if(fault==='none'){if(st.dirty||cache.size)throw Error('saved draft not cleared');}
      else{if(!st.dirty||!cache.size||st.busy)throw Error('pending input lost');
        if(fault==='edit_during_save'){const draft=ctx.readDraft(k);if(draft.revision!==8||draft.data.fields.title!=='newer')throw Error('wrong pending version');}
        await ctx.flushShared(k);if(st.dirty||cache.size)throw Error('retry failed');}
      console.log('ok');}).catch(e=>{console.error(e);process.exitCode=1});
    """
    assert subprocess.check_output(['node','-e',code,str(HTML),fault],text=True).strip()=='ok'


@pytest.mark.parametrize('dirty',[False,True])
def test_actual_cloud_module_uses_live_app_bridge_and_preserves_edits(dirty):
    code=r"""
    const fs=require('fs'),vm=require('vm'),dirty=process.argv[1]==='True';
    const k='wednesday:2026-10-07',records={[k]:{title:'edited',outputs:{ppt:{complete:true}}}},st={revision:2,dirty};let sent,persisted=false;
    const app={key:()=>k,output:'ppt',records,syncState:()=>st,msg:()=>{},render:()=>{},persistDraft:()=>{persisted=true},refreshSongs:async()=>{},songCaption:()=>'',assets:()=>{},page:()=>{}};
    const elements={};const ctx={window:{MediaApp:app},document:{readyState:'loading',addEventListener:()=>{},getElementById:id=>elements[id]??={}},
      fetch:async(url,options)=>({ok:true,json:async()=>{if(url.endsWith('/status'))return {connected:true,account:{},folders:{source:{},archive:{}},configured:true};
        sent=JSON.parse(options.body);return {item:{id:'uploaded',name:'test.pptx'},work:{revision:3,data:{title:'server old'}}}}})};
    vm.createContext(ctx);const cloud=vm.runInContext(fs.readFileSync('src/media_automation/web/original/ui/onedrive.js','utf8')+';CloudMedia',ctx);
    cloud.archiveCurrent().then(()=>{if(sent.date!=='2026-10-07'||sent.service!=='wednesday')throw Error('wrong target');
      if(records[k].title!==(dirty?'edited':'server old')||persisted!==dirty)throw Error('input overwritten');console.log('ok');}).catch(e=>{console.error(e);process.exitCode=1});
    """
    assert subprocess.check_output(['node','-e',code,str(dirty)],text=True).strip()=='ok'


@pytest.mark.parametrize('changed',['week','file'])
def test_pdf_review_dialog_does_not_approve_another_file(changed):
    code=r"""
    const fs=require('fs'),vm=require('vm'),changed=process.argv[2],html=fs.readFileSync(process.argv[1],'utf8');
    const elements={};let sent=false,message='';
    const ctx={reviewedPdf:{key:'sunday:2026-10-11',fileId:'reviewed'},key:()=>changed==='week'?'sunday:2026-10-18':'sunday:2026-10-11',
      record:()=>({outputs:{pdf:{fileId:changed==='file'?'new-file':'reviewed'}}}),$:id=>elements[id]??={checked:true},
      msg:x=>{message=x},flushShared:async()=>{},fetch:async()=>{sent=true}};
    vm.createContext(ctx);vm.runInContext(html.split('\n').find(x=>x.startsWith("$('confirm-bulletin-complete').onclick=")),ctx);
    elements['confirm-bulletin-complete'].onclick().then(()=>{if(sent||!message.includes('바뀌었습니다'))throw Error('wrong PDF approved');console.log('ok')}).catch(e=>{console.error(e);process.exitCode=1});
    """
    assert subprocess.check_output(['node','-e',code,str(HTML),changed],text=True).strip()=='ok'


def test_input_is_backed_up_before_deferred_server_save():
    code=r"""
    const fs=require('fs'),vm=require('vm'),html=fs.readFileSync(process.argv[1],'utf8'),cache=new Map();
    const k='sunday:2026-10-11',st={loaded:true,revision:7,dirty:false},ctx={shared:true,prefix:'test:',records:{[k]:{title:'new input'}},
      key:()=>k,syncState:()=>st,syncLabel:()=>{},msg:()=>{},clearTimeout:()=>{},setTimeout:()=>1,flushShared:()=>{},
      sessionStorage:{setItem:(k,v)=>cache.set(k,v)}};
    vm.createContext(ctx);vm.runInContext(html.split('\n').find(x=>x.startsWith('function persistDraft(')),ctx);
    vm.runInContext(html.match(/function save\([\s\S]+?(?=const fridayInPersonGroups)/)[0],ctx);
    ctx.save();if(!st.dirty||JSON.parse(cache.get('test:draft:'+k)).data.title!=='new input')throw Error('no immediate backup');console.log('ok');
    """
    assert subprocess.check_output(['node','-e',code,str(HTML)],text=True).strip()=='ok'


@pytest.mark.parametrize('during_upload',['edit','new_file','none'])
def test_archive_upload_does_not_overwrite_edits_and_retry_is_safe(tmp_path,monkeypatch,during_upload):
    store=WorkStore(tmp_path/'work.db');cloud=OneDrive(store)
    identifier='a'*32
    data={'fields':{'title':{'state':'VALUE','value':'original'}},'outputs':{'ppt':{'fileId':identifier,'complete':True,'changed':False}}}
    store.save('2026-10-11','sunday',0,data)
    directory=Path(store.path).with_suffix('.generated');directory.mkdir();(directory/(identifier+'.pptx')).write_bytes(b'PPT test')
    monkeypatch.setattr(cloud,'selected',lambda _: {'id':'archive'})
    monkeypatch.setattr(cloud,'archive_destination',lambda *_: {'id':'target'})
    calls=[]
    def upload(folder,name,content):
        calls.append(name)
        if len(calls)==1:raise CloudError('test-only interruption')
        if during_upload!='none':
            current=store.get('2026-10-11','sunday');r=current['data']
            r['fields']['title']['value']='edited'
            if during_upload=='new_file':r['outputs']['ppt']['fileId']='b'*32
            else:r['outputs']['ppt']['changed']=True
            store.save('2026-10-11','sunday',current['revision'],r)
        return {'id':'saved','name':name,'size':len(content),'file':{},'parentReference':{'id':'target'}}
    monkeypatch.setattr(cloud,'upload_file',upload)
    with pytest.raises(CloudError):cloud.archive('2026-10-11','sunday','ppt')
    assert store.get('2026-10-11','sunday')['data']==data
    cloud.archive('2026-10-11','sunday','ppt')
    assert calls[0]==calls[1]
    result=store.get('2026-10-11','sunday')['data']
    if during_upload=='none':assert result['outputs']['ppt']['archiveStatus']=='uploaded'
    else:
        assert result['fields']['title']['value']=='edited'
        assert result['outputs']['ppt'].get('archiveStatus')!='uploaded'
