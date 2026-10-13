/* Shared OneDrive connection; credentials are never persisted in the browser. */
const CloudMedia=(()=>{
 const app=window.MediaApp;const {key,msg,syncState,render,persistDraft,refreshSongs,songCaption,assets,page}=app;
 let state=null, folderPurpose='source', folderStack=[], requestSerial=0, searchTimer;
 const el=id=>document.getElementById(id);
 const text=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n;};
 async function api(action,body){const r=await fetch('/api/onedrive/'+action,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'OneDrive 요청 실패');return data;}
 function button(label,action){const b=text('button',label);b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){msg(e.message);}finally{b.disabled=false;}};return b;}
 async function refresh(strict=false){
  try{state=await api('status');}catch(e){state=null;el('cloud-status').textContent=e.message;if(strict)throw e;return;}
  el('cloud-status').textContent=state.connected?'연결됨 · '+(state.account.username||'개인 Microsoft 계정'):state.configured?'로그인 대기':'Microsoft 설정 필요';
  el('cloud-status').className='status '+(state.connected?'info':'warning');
  el('cloud-client-id').value=state.client_id;
  el('cloud-redirect').textContent=state.redirect_uri;
  el('cloud-connect').disabled=!state.configured;
  el('cloud-connect').textContent=state.connected?'다시 로그인':'OneDrive 연결';
  el('cloud-disconnect').hidden=!state.connected;
  for(const purpose of ['source','archive']){
   el('cloud-'+purpose+'-folder').textContent=state.folders[purpose]?.name||'폴더 미지정';
   el('cloud-pick-'+purpose).disabled=!state.connected;
  }
  el('cloud-library-state').textContent=state.connected?(state.folders.source?'OneDrive · '+state.folders.source.name:'원본 폴더를 선택하세요.'):'OneDrive 연결 전 · 등록 곡은 서버에서 검색합니다.';
  el('cloud-library-search').disabled=!state.connected||!state.folders.source;
  const storage=el('storage-status');if(storage)storage.textContent=state.connected?'OneDrive 연결됨 · 검수 후 제작 완료 표시하면 완료본 보관을 시도합니다.':'OneDrive 연결 전 · 완료본은 서버에 보존됩니다.';
 }
 async function browseFolders(id='root'){
  const items=(await api('folders?id='+encodeURIComponent(id))).items;
  const root=el('cloud-folder-list');root.replaceChildren();
  root.append(button('상위 폴더',async()=>{if(folderStack.length>1){folderStack.pop();await browseFolders(folderStack.at(-1).id);}}));
  el('cloud-folder-location').textContent=folderStack.map(f=>f.name).join(' / ');
  el('cloud-folder-select').disabled=id==='root';
  for(const item of items){const row=text('div',undefined,'asset-row');row.append(text('strong',item.name),button('폴더 열기',async()=>{folderStack.push({id:item.id,name:item.name});await browseFolders(item.id);}));root.append(row);}
  if(!items.length)root.append(text('p','하위 폴더가 없습니다. 현재 폴더를 선택할 수 있습니다.','hint'));
 }
 async function chooseFolder(purpose){folderPurpose=purpose;folderStack=[{id:'root',name:'내 OneDrive'}];el('cloud-folder-title').textContent=purpose==='source'?'찬양 원본 폴더 선택':'완료본 최상위 폴더 선택 · 예배 완료본';el('cloud-folder-dialog').showModal();await browseFolders();}
 let autoBusy=null;
 function searchState(status,extra={}){window.MediaCloudSearch={status,...extra};window.dispatchEvent(new Event('media-cloud-search'));}

 async function autoConnect(){
  if(autoBusy)return autoBusy;
  autoBusy=(async()=>{searchState('searching');await refresh(true);if(!state?.connected){searchState('disconnected');return;}if(!state.folders.source){searchState('folder-required');return;}
   const result=await api('auto-connect',{});await refreshSongs();
   const root=el('cloud-library-list');root.replaceChildren();
   root.append(text('p','자동 연결 '+result.linked+'개 · 기존 연결 '+result.unchanged+'개 · 확인 필요 '+result.choices.length+'개'+(result.pending?' · 다음 확인에서 연결 '+result.pending+'개':''),'hint'));
   for(const item of [...result.choices,...result.errors])root.append(text('p',item.name+' · '+item.reason,'hint'));
   root.append(text('p','새 원본은 확인 상태에서 내용·사용 허락을 검수한 뒤 제작에 사용합니다.','hint'));
   searchState('searched',{result});return result;
  })();try{return await autoBusy;}catch(error){searchState('error',{message:error.message});throw error;}finally{autoBusy=null;}
 }
 async function sources(){
  const serial=++requestSerial,root=el('cloud-library-list');root.replaceChildren(text('p','OneDrive에서 검색 중…','hint'));
  try{const items=(await api('files?purpose=source&q='+encodeURIComponent(el('library-search').value.trim()))).items;if(serial!==requestSerial)return;
   root.replaceChildren();const files=items.filter(f=>f.file&&/\.(pptx?|mp4|mp3|wav|pdf)$/i.test(f.name));
   for(const item of files){const row=text('div',undefined,'asset-row'),info=text('div');info.append(text('h3',item.name),text('p','OneDrive 원본 · '+Math.round(item.size/1024)+' KB','hint'));
    const select=document.createElement('select');select.setAttribute('aria-label',item.name+' 연결할 곡');select.add(new Option('연결할 등록 곡 선택',''));for(const song of app.songCatalog)select.add(new Option(songCaption(song),song.id));
    info.append(select,button('이 곡의 원본으로 연결',async()=>{if(!select.value)throw Error('등록 곡을 선택하세요. 목록에 없으면 먼저 곡 정보를 등록하세요.');const result=await api('import',{id:item.id,song_id:select.value});await refreshSongs();if(app.tab==='assets')assets();msg(result.duplicate?'이미 저장된 동일 원본을 연결했습니다.':'OneDrive 원본을 연결했습니다. 확인 상태에서 내용과 사용 허락을 확인하세요.');}));row.append(info);root.append(row);
   }
   if(!files.length)root.append(text('p','일치하는 원본 파일이 없습니다. 폴더 안에 악보 PPT·영상·음원·PDF를 올려 두세요.','empty'));
   if(!el('library-search').value.trim()&&items.some(i=>i.folder))root.append(text('p','하위 폴더의 원본은 곡명 또는 번호를 입력해 검색하세요.','hint'));
  }catch(e){if(serial===requestSerial)root.replaceChildren(text('p',e.message,'empty'));}
 }
 async function archives(id){const root=el('cloud-archive-list');root.replaceChildren(text('p','보관 자료 불러오는 중…','hint'));
  try{const items=(await api('files?purpose=archive'+(id?'&id='+encodeURIComponent(id):''))).items;root.replaceChildren();if(id)root.append(button('완료본 폴더로',()=>archives()));
   for(const item of items){const row=text('div',undefined,'asset-row');row.append(text('strong',item.name));if(item.folder)row.append(button('폴더 열기',()=>archives(item.id)));else if(/\.(pptx?|pdf)$/i.test(item.name)){const link=text('a','다운로드','cloud-download');link.href='/api/onedrive/download?id='+encodeURIComponent(item.id);link.download=item.name;row.append(link);}root.append(row);}
   if(!items.length)root.append(text('p','아직 보관한 완료본이 없습니다. 결과를 검수하고 제작 완료 표시한 뒤 보관하세요.','empty'));
  }catch(e){root.replaceChildren(text('p',e.message,'empty'));}
 }
 async function archiveCurrent(k=key(),kind=app.output){await refresh();if(!state.connected||!state.folders.archive)return msg('제작 완료 표시는 저장됐습니다. OneDrive 연결·완료본 폴더 선택 후 보관할 수 있습니다.');const [currentService,currentDate]=k.split(':');const result=await api('archive',{date:currentDate,service:currentService,kind});const st=syncState(k);if(st.dirty||st.busy){if(!st.busy)st.revision=result.work.revision;persistDraft(k);msg('OneDrive에 이전 완료본을 보관했습니다. 화면의 새 입력은 유지됩니다.');return;}app.records[k]=result.work.data;st.revision=result.work.revision;render();msg('완료본을 OneDrive에 보관했습니다. 보관 자료에서 확인할 수 있습니다.');}
 async function syncOriginal(songId,digest){await refresh();if(!state.connected||!state.folders.source)return;await api('upload-source',{song_id:songId,digest});}
 function init(){
  el('cloud-copy-redirect').onclick=async()=>{try{await navigator.clipboard.writeText(el('cloud-redirect').textContent);msg('반환 주소를 복사했습니다. Microsoft 앱의 Web 반환 주소에 붙여 넣으세요.');}catch{msg('표시된 반환 주소를 직접 복사하세요.');}};
  el('cloud-save-config').onclick=async()=>{const b=el('cloud-save-config');b.disabled=true;try{await api('configure',{client_id:el('cloud-client-id').value.trim(),secret:el('cloud-secret').value});el('cloud-secret').value='';await refresh();msg('연결 설정을 서버에 저장했습니다. OneDrive 연결을 눌러 로그인하세요.');}catch(e){msg(e.message);}finally{b.disabled=false;}};
  el('cloud-connect').onclick=async()=>{const b=el('cloud-connect');b.disabled=true;try{if(state?.local_url&&location.origin!==new URL(state.local_url).origin){window.location.assign(state.local_url+'/?onedrive=setup');return;}const result=await api('connect',{});window.location.assign(result.url);}catch(e){msg(e.message);b.disabled=false;}};
  el('cloud-disconnect').onclick=async()=>{if(!confirm('이 서버의 OneDrive 연결을 해제할까요? OneDrive 파일은 삭제하지 않습니다.'))return;await api('disconnect',{});await refresh();msg('서버의 연결 정보를 해제했습니다. Microsoft 계정의 앱 권한 취소는 Microsoft 계정 설정에서 할 수 있습니다.');};
  for(const purpose of ['source','archive'])el('cloud-pick-'+purpose).onclick=()=>chooseFolder(purpose).catch(e=>msg(e.message));
  el('cloud-folder-select').onclick=async()=>{try{await api('folders',{purpose:folderPurpose,id:folderStack.at(-1).id});el('cloud-folder-dialog').close();await refresh();msg('OneDrive 폴더를 저장했습니다.');}catch(e){msg(e.message);}};
  el('cloud-auto-connect').onclick=()=>autoConnect().catch(e=>msg(e.message));
  el('cloud-library-search').onclick=sources;el('cloud-archive-refresh').onclick=()=>archives();el('cloud-archive-current').onclick=()=>archiveCurrent().catch(e=>msg('완료 표시는 유지됩니다. '+e.message));
  el('library-search').addEventListener('input',()=>{if(!state?.connected||!state.folders.source||!el('cloud-library-list').children.length)return;clearTimeout(searchTimer);searchTimer=setTimeout(sources,450);});
  window.addEventListener('focus',refresh);
  document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.page==='settings')refresh();if(b.dataset.page==='library')autoConnect().catch(e=>msg(e.message));if(b.dataset.page==='archive')archives();}));
  el('mobile-page').addEventListener('change',e=>{if(e.target.value==='archive')archives();else if(e.target.value==='library')autoConnect().catch(e=>msg(e.message));else refresh();});
  if(['connected','setup'].includes(new URLSearchParams(location.search).get('onedrive'))){history.replaceState(null,'','/');page('settings');msg('OneDrive 설정에서 연결 상태를 확인하고 원본·완료본 폴더를 선택하세요.');}
  refresh();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
 return {refresh,sources,archives,archiveCurrent,syncOriginal,autoConnect};
})();
