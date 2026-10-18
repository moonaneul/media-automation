/* Shared OneDrive connection; credentials are never persisted in the browser. */
const CloudMedia=(()=>{
 const app=window.MediaApp;const {key,msg,syncState,render,persistDraft,refreshSongs,songCaption,assets,page}=app;
 let state=null, folderPurpose='source', folderStack=[], requestSerial=0, searchTimer;
 const sharedDestinations=[
  ['archive_sunday_pdf','00.주보'],
  ['archive_sunday_ppt','01.주일예배'],
  ['archive_wednesday','02.수요예배'],
  ['archive_friday','03.금요예배']
 ];
 const otherFolders=['source_video','archive_wednesday','archive_friday_zoom','archive_friday_in_person','archive_sunday_ppt','archive_sunday_pdf'];
 const el=id=>document.getElementById(id);
 function setTargetLink(value, label='Microsoft OneDrive에서 열기 ↗'){
  const link=el('cloud-target-folder-link');
  if(!link)return;
  let u;
  try{u=new URL(value||'');}catch{u=null;}
  const host=u?.hostname?.toLowerCase()||'';
  const official=['onedrive.live.com','1drv.ms','1drv.com','sharepoint.com'];
  const allowed=u?.protocol==='https:'&&official.some(d=>host===d||host.endsWith('.'+d));
  link.hidden=!allowed;
  if(allowed){link.href=u.href;link.textContent=label;}
  else{link.removeAttribute('href');link.textContent='';}
 }

 const text=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n;};
 async function api(action,body,options={}){const init=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};if(options.signal)init.signal=options.signal;const r=await fetch('/api/onedrive/'+action,init);const data=await r.json();if(!r.ok)throw Error(data.error||'OneDrive 요청 실패');return data;}
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
  for(const purpose of ['source','archive',...otherFolders]){
   el('cloud-'+purpose+'-folder').textContent=state.folders[purpose]?.name||(purpose.startsWith('archive_')?'기본 경로 사용':'폴더 미지정');
   el('cloud-pick-'+purpose).disabled=!state.connected;
  }
  const assignments=state.shared_archives||{},count=Object.keys(assignments).length;
  el('cloud-shared-archive-status').textContent=count?
    '기존 미디어팀 공유폴더 '+count+'/4개 연결 · 미연결 예배 업로드 차단 · 원본 OneDrive 연결 유지':
    '미디어팀 공유 완료본 폴더 연결 전 · 원본 OneDrive 연결 유지';
  for(const [purpose,expected] of sharedDestinations){
   const chosen=assignments[purpose];
   el('cloud-shared-'+purpose+'-status').textContent=chosen?
     (chosen.reconnectRequired?'재연결 필요 · '+chosen.name+' · 공유 링크를 다시 붙여 넣어 주세요.':
       '연결됨 · '+chosen.name+' · 이 폴더에 직접 보관'):
     '미연결 · '+expected+' 공유폴더 링크를 연결하세요.';
   el('cloud-set-'+purpose).disabled=!state.connected;
   el('cloud-unset-'+purpose).hidden=!chosen;
  }
  el('cloud-library-state').textContent=state.connected?(state.folders.source?'OneDrive · '+state.folders.source.name:'원본 폴더를 선택하세요.'):'OneDrive 연결 전 · 등록 곡은 서버에서 검색합니다.';
  el('cloud-library-search').disabled=!state.connected||!state.folders.source;
  const storage=el('storage-status');if(storage)storage.textContent=state.connected?'OneDrive 연결됨 · 검수 후 제작 완료 표시하면 완료본 보관을 시도합니다.':'OneDrive 연결 전 · 완료본은 서버에 보존됩니다.';
 }
 function folderError(message){
  const target=el('cloud-folder-error');
  target.textContent=message||'';
  target.hidden=!message;
 }
 async function saveFolder(identifier,displayName){
  const selectedName=displayName||folderStack.at(-1)?.name||'선택한 폴더';
  folderError('');
  el('cloud-folder-select').disabled=true;
  try{
   await api('folders',{purpose:folderPurpose,id:identifier});
   await refresh(true);
   el('cloud-folder-dialog').close();
   msg('OneDrive 폴더 지정 완료 · '+selectedName);
  }catch(e){
   folderError('폴더를 지정하지 못했습니다 · '+e.message+' 다른 원본·완료본 폴더와 겹치지 않는지도 확인하세요.');
  }finally{
   el('cloud-folder-select').disabled=folderStack.at(-1)?.id==='root';
  }
 }
 async function browseFolders(id='root'){
  folderError('');
  const root=el('cloud-folder-list');
  root.replaceChildren(text('p','OneDrive 폴더 불러오는 중…','hint'));
  el('cloud-folder-location').textContent=folderStack.map(f=>f.name).join(' / ');
  el('cloud-folder-select').disabled=id==='root';
  try{
   const items=(await api('folders?id='+encodeURIComponent(id))).items;
   root.replaceChildren();
   if(folderStack.length>1)root.append(button('← 상위 폴더',async()=>{folderStack.pop();await browseFolders(folderStack.at(-1).id);}));
   for(const item of items){
    const row=text('div',undefined,'asset-row');
    const details=text('div');details.append(text('strong',item.name));
    row.append(details,button('이 폴더 선택',()=>saveFolder(item.id,item.name)),
                 button('하위 폴더 보기',async()=>{folderStack.push({id:item.id,name:item.name});await browseFolders(item.id);}));
    root.append(row);
   }
   if(!items.length)root.append(text('p',id==='root'?'OneDrive에서 선택할 하위 폴더를 찾지 못했습니다.':'이 폴더 아래에 다른 폴더가 없습니다. 아래 현재 폴더 선택을 누르세요.','hint'));
  }catch(e){
   folderError('OneDrive 폴더 목록을 불러오지 못했습니다 · '+e.message);
   root.replaceChildren(text('p','폴더 목록을 확인하지 못했습니다. 연결 상태 또는 접근 권한을 확인하세요.','hint'));
  }
 }
 async function chooseFolder(purpose){
  folderPurpose=purpose;folderStack=[{id:'root',name:'내 OneDrive'}];
  const names={source:'대면예배 악보 PPT 폴더',source_video:'금요 Zoom 영상·음원 폴더',archive:'예배 완료본 최상위 폴더',archive_wednesday:'수요예배 PPT 저장 폴더',archive_friday_zoom:'금요 Zoom PPT 저장 폴더',archive_friday_in_person:'금요 대면 PPT 저장 폴더',archive_sunday_ppt:'주일예배 PPT 저장 폴더',archive_sunday_pdf:'주일 주보 PDF 저장 폴더'};
  el('cloud-folder-title').textContent=names[purpose]||'OneDrive 폴더 선택';
  folderError('');
  el('cloud-folder-dialog').showModal();
  await browseFolders();
 }
 let autoBusy=null;
 function searchState(status,extra={}){window.MediaCloudSearch={status,...extra};window.dispatchEvent(new Event('media-cloud-search'));}

 async function autoConnect(){
  if(autoBusy)return autoBusy;
  autoBusy=(async()=>{searchState('searching');await refresh(true);if(!state?.connected){searchState('disconnected');return;}if(!state.folders.source){searchState('folder-required');return;}
   const result=await api('auto-connect',{});await refreshSongs();
   const root=el('cloud-library-list');root.replaceChildren();
   root.append(text('p','자동 연결 '+result.linked+'개 · 기존 연결 '+result.unchanged+'개 · 확인 필요 '+result.choices.length+'개'+(result.pending?' · 다음 확인에서 연결 '+result.pending+'개':''),'hint'));
   const issues=[...result.choices,...result.errors];if(issues.length){const details=text('details');details.append(text('summary','확인할 자료 '+issues.length+'개 · 펼치기'));for(const item of issues.slice(0,30))details.append(text('p',item.name+' · '+item.reason,'hint'));if(issues.length>30)details.append(text('p','그 밖의 '+(issues.length-30)+'개는 생략했습니다. 필요한 곡명으로 검색하세요.','hint'));root.append(details);}
   root.append(text('p','새 원본은 확인 상태에서 내용·사용 허락을 검수한 뒤 제작에 사용합니다.','hint'));
   searchState('searched',{result});return result;
  })();try{return await autoBusy;}catch(error){searchState('error',{message:error.message});throw error;}finally{autoBusy=null;}
 }
 async function sources(){
   const serial=++requestSerial,root=el('cloud-library-list');const query=el('library-search').value.trim();if(!query){root.replaceChildren(text('p','먼저 검색할 찬양 곡명이나 번호를 입력하세요.','hint'));return;}root.replaceChildren(text('p','OneDrive에서 검색 중…','hint'));
   try{const items=(await api('files?purpose=source&q='+encodeURIComponent(query))).items;if(serial!==requestSerial)return;
    root.replaceChildren();const mode=el('library-kind').value;const files=items.filter(f=>{if(!f.file)return false;const name=f.name||'',role=f.source_role;if(role&&!['score','song_video','audio_candidate',...(mode==='audio'?['prayer_audio']:[])].includes(role))return false;if(!role&&/^(cover(?:[-_.]|$)|bulletin(?:[-_.]|$)|community[-_]prayer|worship[-_]template|주보|표지)/i.test(name))return false;return mode==='score'?/\.pptx?$/i.test(name):mode==='media'?/\.mp4$/i.test(name):/\.(pptx?|mp4)$/i.test(name);});
   for(const item of files){const row=text('div',undefined,'asset-row'),info=text('div');info.append(text('h3',item.name),text('p','OneDrive 원본 · '+Math.round(item.size/1024)+' KB','hint'));
    const select=document.createElement('select');select.setAttribute('aria-label',item.name+' 연결할 곡');select.add(new Option('연결할 등록 곡 선택',''));for(const song of app.songCatalog)select.add(new Option(songCaption(song),song.id));
    info.append(select,button('이 곡의 원본으로 연결',async()=>{if(!select.value)throw Error('등록 곡을 선택하세요. 목록에 없으면 먼저 곡 정보를 등록하세요.');const result=await api('import',{id:item.id,song_id:select.value});await refreshSongs();if(app.tab==='assets')assets();msg(result.duplicate?'이미 저장된 동일 원본을 연결했습니다.':'OneDrive 원본을 연결했습니다. 확인 상태에서 내용과 사용 허락을 확인하세요.');}));row.append(info);root.append(row);
   }
   if(!files.length)root.append(text('p','선택한 종류에서 일치하는 악보 PPT 또는 찬양 영상이 없습니다. 곡명·자료 종류를 확인하세요.','empty'));
   if(!el('library-search').value.trim()&&items.some(i=>i.folder))root.append(text('p','하위 폴더의 원본은 곡명 또는 번호를 입력해 검색하세요.','hint'));
  }catch(e){if(serial===requestSerial)root.replaceChildren(text('p',e.message,'empty'));}
 }
 async function searchWorshipSource(query, mode){
  await refresh(true);
  if(!state?.connected)return {status:'disconnected',configured:!!state?.configured};
  const purpose=mode==='score'?'source':'source_video';
  if(!state.folders?.[purpose])return {status:'folder-required',purpose};
  const textQuery=String(query||'').trim();
  if(!textQuery)return {status:'query-required'};
  const items=(await api('files?purpose='+purpose+'&q='+encodeURIComponent(textQuery))).items;
  const matches=items.filter(item=>{
   if(!item.file)return false;
   const name=item.name||'',role=item.source_role;
   if(role&&!['score','song_video','audio_candidate',...(mode==='audio'?['prayer_audio']:[])].includes(role))return false;
   return mode==='score'?/\.pptx?$/i.test(name):mode==='video'?/\.mp4$/i.test(name):mode==='audio'?/\.mp3$/i.test(name):false;
  });
  return {status:'ok',items:matches,folder:state.folders[purpose].name};
 }
 async function importWorshipSource(itemId,day,service,slot){
  const result=await api('import-to-slot',{id:itemId,date:day,service,slot});
  return result;
 }
 async function archives(purpose=null,id=null){
  const root=el('cloud-archive-list');root.replaceChildren(text('p','보관 자료 불러오는 중…','hint'));
  try{
   await refresh();
   const configured=state?.shared_archives||{};
   const purposes=Object.keys(configured).length?[
    ['archive_sunday_pdf','00.주보'],
    ['archive_sunday_ppt','01.주일예배'],
    ['archive_wednesday','02.수요예배'],
    ['archive_friday_zoom','03.금요예배']
   ].filter(([key])=>configured[key==='archive_friday_zoom'?'archive_friday':key]):state?.shared_archive?.enabled?
     [['archive','미디어팀 공유 완료본']]:[
    ['archive','완료본 전체'],
    ['archive_wednesday','수요예배'],
    ['archive_friday_zoom','금요 Zoom'],
    ['archive_friday_in_person','금요 대면'],
    ['archive_sunday_ppt','주일 PPT'],
    ['archive_sunday_pdf','주일 주보']
   ].filter(([key])=>state?.folders?.[key]);
   if(!purposes.length){root.replaceChildren(text('p','설정에서 완료본 폴더를 먼저 선택하세요.','empty'));return;}
   const chosen=purposes.some(([key])=>key===purpose)?purpose:purposes[0][0];
   const query='files?purpose='+encodeURIComponent(chosen)+(id?'&id='+encodeURIComponent(id):'');
   const items=(await api(query)).items;
   root.replaceChildren();
   if(purposes.length>1){
    const chooser=text('div',undefined,'actions');
    for(const [key,label] of purposes)chooser.append(button(label+(key===chosen?' · 선택됨':''),()=>archives(key)));
    root.append(chooser);
   }
   if(id)root.append(button('이전 폴더로',()=>archives(chosen)));
   for(const item of items){
    const row=text('div',undefined,'asset-row');row.append(text('strong',item.name));
    if(item.folder)row.append(button('폴더 열기',()=>archives(chosen,item.id)));
    else if(/\.(pptx?|pdf)$/i.test(item.name)){
     // Large Zoom decks may exceed the server's 128 MB source-download limit.
     // The official OneDrive URL is the proper archive retrieval location.
     let address;
     try{address=new URL(item.webUrl||'');}catch{}
     if(address?.protocol==='https:'&&/\.((?:live\.com)|(?:1drv\.com)|(?:sharepoint\.com))$/i.test(address.hostname)){
      const link=text('a','OneDrive에서 열기','cloud-download');
      link.href=address.href;link.target='_blank';link.rel='noopener noreferrer';row.append(link);
     }
    }
    root.append(row);
   }
   if(!items.length)root.append(text('p','이 폴더에는 아직 완료본이 없습니다. 다른 예배 폴더도 확인하세요.','empty'));
  }catch(e){root.replaceChildren(text('p',e.message,'empty'));}
 }
 async function archiveCurrent(k=key(),kind=app.output){
  const button=el('cloud-archive-current'),status=el('storage-status');
  const requireBeforeUpload=message=>{const error=new Error(message);error.beforeUpload=true;throw error;};
  // A response-less Microsoft request must not leave this button locked forever.
  // Aborting browser wait does NOT guarantee the server stopped its upload.
  const supportsTimeout=typeof AbortController==='function'&&typeof setTimeout==='function';
  const controller=supportsTimeout?new AbortController():null;
  const maxWait=kind==='pdf'?180000:900000;
  let ticker=null,timeout=null;
  button.disabled=true;
  try{
   await refresh();
   const [svc,date]=k.split(':'),mode=app.records[k]?.fridayMode||'zoom';
   const keyName=svc==='wednesday'?'archive_wednesday':svc==='friday'?(mode==='in_person'?'archive_friday_in_person':'archive_friday_zoom'):(kind==='pdf'?'archive_sunday_pdf':'archive_sunday_ppt');
   if(!state?.connected)requireBeforeUpload('OneDrive 연결이 필요합니다. 설정에서 로그인하세요.');
   const role=svc==='friday'?'archive_friday':keyName;
   // This church's personal drive is source-only. Never silently fall back
   // to its 5 GB '예배 완료본' archive when the team share is unconnected.
   if(!state.shared_archives?.[role])requireBeforeUpload(
     '미디어팀 공유 OneDrive '+({
       archive_sunday_pdf:'00.주보',archive_sunday_ppt:'01.주일예배',
       archive_wednesday:'02.수요예배',archive_friday:'03.금요예배'
     }[role]||role)+' 폴더가 미연결입니다. 설정에서 연결하세요. 개인 OneDrive에는 업로드하지 않습니다.');
   if(!app.records[k]?.outputs?.[kind]?.complete)requireBeforeUpload('먼저 실제 결과를 검수하고 제작 완료 표시를 해 주세요.');
   if(app.records[k]?.outputs?.[kind]?.changed)requireBeforeUpload('입력이 변경된 이전 생성본입니다. 최신 파일을 다시 제작하고 검수 완료 표시를 해 주세요.');
   const began=Date.now();
   status.textContent='OneDrive에 완료본 업로드 중… 파일이 크면 시간이 걸릴 수 있습니다.';
   if(supportsTimeout){
    if(typeof setInterval==='function')ticker=setInterval(async()=>{
     const seconds=Math.max(0,Math.floor((Date.now()-began)/1000));
     const prefix='OneDrive 업로드 · '+Math.floor(seconds/60)+'분 '+(seconds%60)+'초 경과';
     try{
      const progress=await api('archive-progress?date='+encodeURIComponent(date)+
       '&service='+encodeURIComponent(svc)+'&kind='+encodeURIComponent(kind));
      status.textContent=prefix+' · '+(progress.stage||'상태 확인 중')+
       (progress.percent!==undefined?' · '+progress.percent+'%':'')+
       (progress.error?' · '+progress.error:'');
     }catch{
      status.textContent=prefix+' · 서버 응답을 기다리는 중';
     }
    },5000);
    timeout=setTimeout(()=>controller.abort(),maxWait);
   }
   const result=await api('archive',{date,service:svc,kind},
      controller?{signal:controller.signal}:{});
   if(!result.item?.id)throw Error('OneDrive 업로드 응답에서 파일 ID를 확인하지 못했습니다.');
   if(Object.keys(state.shared_archives||{}).length&&!result.verified)
    throw Error('실제 공유폴더 파일 조회 확인이 없어서 보관 완료로 표시할 수 없습니다.');
   if(result.verified)setTargetLink(result.itemUrl,'업로드된 파일을 OneDrive에서 열기 ↗');
   const st=syncState(k);
   if(st.dirty||st.busy){
    if(!st.busy)st.revision=result.work.revision;
    persistDraft(k);
    status.textContent='OneDrive 보관 완료 · 화면의 새 입력은 별도로 유지됨';
    msg('OneDrive에 이전 완료본을 보관했습니다. 새 입력은 유지됩니다.');
    return result;
   }
   app.records[k]=result.work.data;st.revision=result.work.revision;render();
   status.textContent=result.verified?
     'OneDrive 공유폴더에서 파일 실제 존재 확인 완료 · '+(result.target||'')+' · '+(result.item.name||'완료 파일'):
     'OneDrive 보관 완료 응답 기록됨 · '+(result.item.name||'완료 파일')+' · 실제 위치 추가 확인 필요';
   msg('완료본을 OneDrive에 보관했습니다. 보관 자료에서 확인할 수 있습니다.');
   return result;
  }catch(e){
   if(controller?.signal.aborted){
    const uncertain=new Error('OneDrive 응답 대기 시간이 초과됐습니다. 업로드는 서버에서 계속 진행 중일 수 있습니다. 공유폴더에서 파일 존재 여부를 확인한 뒤 다시 시도하세요.');
    uncertain.uncertain=true;e=uncertain;
   }
   status.textContent=(e.beforeUpload?'OneDrive 보관 준비 필요 · ':e.uncertain?'OneDrive 업로드 결과 미확인 · ':'OneDrive 업로드 실패 · ')+e.message+
     (e.beforeUpload?' · 파일은 서버에 유지됩니다.':e.uncertain?' · 검수 완료 파일은 서버에 보존됩니다.':' · 만든 파일은 유지됩니다. 다시 시도할 수 있습니다.');
   throw e;
  }finally{
   if(ticker!==null)clearInterval(ticker);
   if(timeout!==null)clearTimeout(timeout);
   button.disabled=false;
  }
 }
 async function syncOriginal(songId,digest){await refresh();if(!state?.connected||!state.folders.source)return {uploaded:false};const result=await api('upload-source',{song_id:songId,digest});return {uploaded:!!result?.item?.id,item:result?.item||null};}
 function init(){
  el('cloud-copy-redirect').onclick=async()=>{try{await navigator.clipboard.writeText(el('cloud-redirect').textContent);msg('반환 주소를 복사했습니다. Microsoft 앱의 Web 반환 주소에 붙여 넣으세요.');}catch{msg('표시된 반환 주소를 직접 복사하세요.');}};
  el('cloud-save-config').onclick=async()=>{const b=el('cloud-save-config');b.disabled=true;try{await api('configure',{client_id:el('cloud-client-id').value.trim(),secret:el('cloud-secret').value});el('cloud-secret').value='';await refresh();msg('연결 설정을 서버에 저장했습니다. OneDrive 연결을 눌러 로그인하세요.');}catch(e){msg(e.message);}finally{b.disabled=false;}};
  el('cloud-connect').onclick=async()=>{const b=el('cloud-connect');b.disabled=true;try{if(state?.local_url&&location.origin!==new URL(state.local_url).origin){window.location.assign(state.local_url+'/?onedrive=setup');return;}const result=await api('connect',{});window.location.assign(result.url);}catch(e){msg(e.message);b.disabled=false;}};
  el('cloud-disconnect').onclick=async()=>{if(!confirm('이 서버의 OneDrive 연결을 해제할까요? OneDrive 파일은 삭제하지 않습니다.'))return;await api('disconnect',{});await refresh();msg('서버의 연결 정보를 해제했습니다. Microsoft 계정의 앱 권한 취소는 Microsoft 계정 설정에서 할 수 있습니다.');};
  for(const purpose of ['source','archive',...otherFolders])el('cloud-pick-'+purpose).onclick=()=>chooseFolder(purpose).catch(e=>msg(e.message));
  for(const [purpose,folderName] of sharedDestinations){
   el('cloud-set-'+purpose).onclick=async()=>{
    const input=el('cloud-shared-'+purpose+'-link');
    const indicator=el('cloud-shared-'+purpose+'-status');
    const link=input.value.trim();
    if(!link){
     indicator.textContent='미연결 · '+folderName+' 폴더에서 “공유 → 링크 복사”한 주소를 입력하세요.';
     return msg(folderName+' 공유폴더 링크를 입력하세요.');
    }
    const btn=el('cloud-set-'+purpose);
    btn.disabled=true;
    indicator.textContent='연결 확인 중 · Microsoft 공유폴더 접근과 폴더 이름을 확인하고 있습니다…';
    try{
     const r=await api('shared-archive',{url:link,purpose});
     // The POST succeeded: persist visible success even if refreshing the
     // status later fails, so a temporary network issue cannot look like
     // a failed folder connection.
     indicator.textContent='연결 성공 · '+r.name+' · 공유 완료본 저장 위치로 사용합니다.';
     input.value='';
     try{await refresh(true);}
     catch(e){indicator.textContent='연결 저장 성공 · 상태 재조회 실패: '+e.message;return;}
     msg(folderName+' → 미디어팀 OneDrive 공유폴더 연결 완료 · 기존 원본 자료는 유지됩니다.');
    }catch(e){
     // A toast elsewhere on the page is not sufficient in a long settings
     // form. Keep the exact actionable message next to this field.
     indicator.textContent='미연결 · '+folderName+' 연결 실패: '+(e.message||'Microsoft 요청 확인 필요')+
       ' · 개인 OneDrive에는 완료본을 대신 저장하지 않습니다.';
     msg(folderName+' 연결 실패: '+(e.message||'Microsoft 요청 확인 필요'));
    }finally{btn.disabled=false;}
   };
   el('cloud-unset-'+purpose).onclick=async()=>{
    if(!confirm(folderName+' 완료본 저장 위치 연결을 해제할까요? OneDrive 파일은 삭제하지 않습니다.'))return;
    try{await api('clear-shared-archive',{purpose});await refresh(true);msg(folderName+' 연결 해제됨 · 기존 파일은 유지됩니다.');}
    catch(e){msg(e.message);}
   };
  }
  el('cloud-folder-select').onclick=()=>saveFolder(folderStack.at(-1).id,folderStack.at(-1).name);
  el('cloud-auto-connect').onclick=()=>{if(confirm('OneDrive 전체 원본을 검색하고 정확히 일치하는 자료는 자동으로 연결합니다. 검수와 사용 허락은 별도이며, OneDrive 파일은 삭제하지 않습니다. 계속할까요?'))autoConnect().catch(e=>msg(e.message));};
  el('cloud-library-search').onclick=sources;el('cloud-archive-refresh').onclick=()=>archives();el('cloud-archive-current').onclick=()=>archiveCurrent().catch(e=>msg(e.beforeUpload?e.message:'완료 표시는 유지됩니다. '+e.message));
  el('cloud-verify-current').onclick=async()=>{
   const button=el('cloud-verify-current'),status=el('storage-status');
   const [svc,date]=key().split(':'),kind=app.output;
   button.disabled=true;
   setTargetLink(null);
   status.textContent='OneDrive 기존 보관 기록과 실제 공유폴더의 파일 위치를 대조 중…';
   try{
    const params=new URLSearchParams({date,service:svc,kind});
    const result=await api('archive-verify?'+params.toString());
    setTargetLink(result.targetUrl,'현재 지정된 '+result.target+' 공유폴더 열기 ↗');
    if(result.verified){
     status.textContent='실제 보관 위치 검증 성공 · '+result.target+' · 파일 ID·이름·크기·상위 폴더 모두 일치';
     setTargetLink(result.itemUrl||result.targetUrl,'확인된 OneDrive 파일 열기 ↗');
    }else{
     status.textContent='보관 완료 기록 불일치 · '+result.target+' · '+result.message+
       ' · 실제 파일이 있는 것으로 확인되지 않았으므로 업로드 성공으로 간주하지 않습니다.';
    }
    msg(result.message);
   }catch(e){status.textContent='실제 저장 위치 검증 실패 · '+e.message;msg(e.message);}
   finally{button.disabled=false;}
  };
  el('cloud-check-current').onclick=async()=>{
   const button=el('cloud-check-current'),status=el('storage-status');
   const [svc]=key().split(':'),kind=app.output;
   button.disabled=true;
   status.textContent='OneDrive 저장 폴더의 읽기 접근을 점검 중… (파일을 업로드하지 않습니다.)';
   try{
    const mode=svc==='friday'?(app.records[key()]?.fridayMode||'zoom'):'zoom';
    const params=new URLSearchParams({service:svc,kind,mode});
    const result=await api('archive-check?'+params);
    status.textContent=result.target+' · 폴더 조회 성공 · 파일 쓰기는 실제 승인본 업로드에서 확인합니다.';
    msg(result.target+' 저장 폴더를 읽을 수 있습니다. 업로드 가능 여부는 별도로 확인해야 합니다.');
   }catch(e){
    status.textContent='OneDrive 저장 폴더 연결 점검 실패 · '+e.message;
    msg(e.message);
   }finally{button.disabled=false;}
  };
  el('library-search').addEventListener('input',()=>{if(!el('cloud-library-tools').open||!state?.connected||!state.folders.source)return;clearTimeout(searchTimer);searchTimer=setTimeout(sources,600);});
  window.addEventListener('focus',refresh);
  document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.page==='settings')refresh();if(b.dataset.page==='library')refresh();if(b.dataset.page==='archive')archives();}));
  el('mobile-page').addEventListener('change',e=>{if(e.target.value==='archive')archives();else if(e.target.value==='library')refresh();else refresh();});
  const connectionReturn=new URLSearchParams(location.search).get('onedrive');
  if(['connected','setup'].includes(connectionReturn)){
   history.replaceState(null,'','/');
   let back=null;
   try{back=JSON.parse(sessionStorage.getItem('media-onedrive-return')||'null');sessionStorage.removeItem('media-onedrive-return');}catch{}
   if(back&&connectionReturn==='connected'){
    app.restoreCloudSong(back);
    msg('OneDrive 로그인에서 돌아왔습니다. 이 예배 찬양의 악보 찾기를 다시 확인하세요.');
   }else{
    page('settings');
    msg('OneDrive 설정에서 연결 상태를 확인하고 원본·완료본 폴더를 선택하세요.');
   }
  }
  refresh();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
 return {refresh,sources,archives,archiveCurrent,syncOriginal,autoConnect,searchWorshipSource,importWorshipSource};
})();
