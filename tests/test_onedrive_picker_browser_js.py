"""Node-based UI regression: actual JS filtering and folder picker events."""
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "src/media_automation/web/original/ui/onedrive.js"


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js runtime unavailable")
def test_live_javascript_one_drive_filter_and_direct_zoom_folder_selection():
    javascript = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

class Elem {
 constructor(id='') {
  this.id=id;
  this.textContent='';
  this.value='';
  this.className='';
  this.hidden=false;
  this.disabled=false;
  this.children=[];
  this.events={};
  this.showing=false;
 }
 append(...items){this.children.push(...items)}
 replaceChildren(...items){this.children=[...items]}
 addEventListener(name,fn){this.events[name]=fn}
 showModal(){this.showing=true}
 close(){this.showing=false}
}
const elements = new Map();
const element = name => {
 if(!elements.has(name))elements.set(name,new Elem(name));
 return elements.get(name);
};
let savedFolders = {
 source: {id:'scores',name:'악보 PPT'},
 archive: {id:'archive',name:'예배 완료본'}
};
let shouldFailSelection=false;
let selected=[];
const searches=[];
const filesByFolder = {
 source: [
  {id:'one',name:'380장 악보.PPT',file:{},size:25,source_role:'score'},
  {id:'two',name:'찬송_380장.pptx',file:{},size:25,source_role:'score'},
  {id:'bad',name:'cover.pptx',file:{},source_role:'bulletin'},
 ],
 source_video: [
  {id:'vid',name:'찬양영상.MP4',file:{},source_role:'song_video'},
  {id:'prayer',name:'기도배경.MP3',file:{},source_role:'prayer_audio'}
 ]
};
async function fetchMock(url,options={}) {
 const u = new URL(url,'http://localhost:18877');
 const path=u.pathname.split('/').pop(), method=options.method||'GET';
 let data={};
 if(path==='status')data={
  configured:true,connected:true,client_id:'test-app',redirect_uri:'http://localhost/test',
  account:{username:'example@invalid.local'},folders:savedFolders
 };
 else if(path==='files'){
  const folder=u.searchParams.get('purpose');
  searches.push(folder);
  data={items:filesByFolder[folder]||[]};
 }
 else if(path==='folders' && method==='GET')data={items:[
  {id:'zoom-folder-id',name:'Zoom 영상',folder:{}}
 ]};
 else if(path==='folders' && method==='POST'){
  const body=JSON.parse(options.body);
  selected.push(body);
  if(shouldFailSelection)return {ok:false,status:400,json:async()=>({error:'악보 PPT 폴더와 Zoom 원본 폴더가 겹칩니다.'})};
  savedFolders[body.purpose]={id:body.id,name:'Zoom 영상'};
  data={folders:savedFolders};
 }
 return {ok:true,status:200,json:async()=>data};
}
const doc={
 readyState:'loading',
 events:{},
 getElementById:element,
 createElement:tag=>new Elem(tag),
 querySelectorAll:()=>[],
 addEventListener(name,fn){this.events[name]=fn}
};
const context={
 window:{MediaApp:{},addEventListener(){}},
 document:doc,
 fetch:fetchMock,
 location:{search:'',origin:'http://localhost:18877'},
 history:{replaceState(){}},
 URL,URLSearchParams,
 console,
 setTimeout:()=>0,
 clearTimeout:()=>{},
};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8')+'\nthis.cloudMedia=CloudMedia;',context);
async function main(){
 const cm=context.cloudMedia;
 let a=await cm.searchWorshipSource('380장','score');
 assert.equal(a.status,'ok');
 assert.equal(a.items.length,2,'PPT and PPTX must both show');
 assert.equal(a.items[0].name,'380장 악보.PPT');
 assert.deepEqual(searches,['source']);
 // Mimic page startup: registered events and connected Microsoft account.
 doc.events.DOMContentLoaded();
 await Promise.resolve();await Promise.resolve();await Promise.resolve();
 assert.equal(typeof element('cloud-pick-source_video').onclick,'function');
 await element('cloud-pick-source_video').onclick();
 assert.equal(element('cloud-folder-dialog').showing,true);
 const root=element('cloud-folder-list');
 assert.ok(root.children.length>0,'folder row should be visible');
 const directSelect=root.children[0].children[1];
 assert.equal(directSelect.textContent,'이 폴더 선택');
 await directSelect.onclick();
 assert.equal(selected.at(-1).purpose,'source_video');
 assert.equal(savedFolders.source_video.id,'zoom-folder-id');
 assert.equal(element('cloud-folder-dialog').showing,false);

 a=await cm.searchWorshipSource('찬양','video');
 assert.equal(a.items.length,1,'Friday Zoom MP4 accepted');
 a=await cm.searchWorshipSource('기도','audio');
 assert.equal(a.items.length,1,'Friday Zoom prayer MP3 accepted');

 // Failed selection must not dismiss the modal or silently look successful.
 shouldFailSelection=true;
 await element('cloud-pick-source_video').onclick();
 const badSelect=element('cloud-folder-list').children[0].children[1];
 await badSelect.onclick();
 assert.equal(element('cloud-folder-dialog').showing,true);
 assert.equal(element('cloud-folder-error').hidden,false);
 assert.ok(element('cloud-folder-error').textContent.includes('겹칩니다'));
}
main().catch(error=>{console.error(error);process.exitCode=1});
"""
    result = subprocess.run(["node", "-e", javascript, str(SCRIPT)],
                            text=True, capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
