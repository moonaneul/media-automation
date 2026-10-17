/* Cloud Run builds stay asynchronous; existing screens and review flow remain. */
(()=>{'use strict';
const originalFetch=window.fetch.bind(window);
const pendingKey='media-cloud-pending-build';
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function jsonResponse(status,body){return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});}
let statusPanel=null;
function showStatus(jobId,message){
 if(!statusPanel){statusPanel=document.createElement('aside');statusPanel.setAttribute('role','status');statusPanel.style='position:fixed;bottom:16px;left:16px;right:16px;z-index:10000;padding:16px;background:white;border:1px solid #bbb;border-radius:12px';document.body.append(statusPanel);}
 statusPanel.replaceChildren();const text=document.createElement('span');text.textContent=message;statusPanel.append(text);
 const cancel=document.createElement('button');cancel.type='button';cancel.textContent='제작 취소';cancel.style.marginLeft='16px';
 cancel.onclick=async()=>{cancel.disabled=true;try{const r=await originalFetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:jobId})});if(!r.ok)throw Error();text.textContent='취소 요청을 보냈습니다. 작업 상태를 확인합니다.';}catch{text.textContent='취소 결과를 확인하지 못했습니다. 다시 시도하세요.';cancel.disabled=false;}};statusPanel.append(cancel);
}
async function waitForJob(id){
 for(let attempts=0;attempts<240;attempts++){
  showStatus(id,'클라우드에서 제작 중입니다. 이 컴퓨터를 꺼도 서버 작업은 계속됩니다.');
  const response=await originalFetch('/api/jobs?id='+encodeURIComponent(id));
  if(!response.ok)return response;
  const job=await response.json();
  if(job.status==='succeeded'){sessionStorage.removeItem(pendingKey);statusPanel?.remove();statusPanel=null;return jsonResponse(200,job.result);}
  if(job.status==='failed'){sessionStorage.removeItem(pendingKey);statusPanel?.remove();statusPanel=null;return jsonResponse(409,{error:job.result?.error||'제작이 완료되지 않았습니다.'});}
  await sleep(4000);
 }
 return jsonResponse(503,{error:'제작 상태 확인 시간이 지났습니다. 새로고침해 작업 상태를 확인하세요.'});
}
window.fetch=async(input,options)=>{
 const url=new URL(input instanceof Request?input.url:input,location.href);
 if(url.origin!==location.origin)return originalFetch(input,options);
 if(['/api/attachments','/api/song-assets'].includes(url.pathname)&&options?.body instanceof Blob){
  const file=options.body;if(!file.size||file.size>128*1024*1024)return jsonResponse(413,{error:'원본 파일은 128MB 이하로 등록하세요.'});
  const hash=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
  const digest=Array.from(new Uint8Array(hash),v=>v.toString(16).padStart(2,'0')).join('');
  const request={route:url.pathname,query:Object.fromEntries(url.searchParams),filename:url.searchParams.get('filename'),size:file.size,digest};
  const begin=await originalFetch('/api/upload-start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
  if(!begin.ok)return begin;const upload=await begin.json();let item;
  for(let start=0;start<file.size;start+=upload.chunk_size){
   const end=Math.min(start+upload.chunk_size,file.size),chunk=file.slice(start,end);
   const part=await originalFetch(upload.upload_url,{method:'PUT',headers:{'Content-Range':`bytes ${start}-${end-1}/${file.size}`},body:chunk,credentials:'omit',redirect:'error'});
   if(end===file.size&&(part.status===200||part.status===201)){item=await part.json();}
   else if(part.status!==202)return jsonResponse(503,{error:'원본 업로드가 중단됐습니다. 기존 자료는 유지됩니다.'});
  }
  if(!item?.id)return jsonResponse(503,{error:'원본 업로드 완료를 확인하지 못했습니다.'});
  return originalFetch('/api/upload-finish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sealed:upload.sealed,item_id:item.id})});
 }
 if(url.pathname!=='/api/build'){const response=await originalFetch(input,options);if(url.pathname==='/api/work'&&(!options?.method||options.method==='GET')&&response.ok)showJobs(url.searchParams.get('date'),url.searchParams.get('service')).catch(()=>{});return response;}
 const body=JSON.parse(options.body);const previous=JSON.parse(sessionStorage.getItem(pendingKey)||'null');
 const signature=JSON.stringify(body);
 const requestKey=previous?.signature===signature?previous.requestKey:crypto.randomUUID();
 sessionStorage.setItem(pendingKey,JSON.stringify({signature,requestKey,body}));
 const response=await originalFetch(input,{...options,body:JSON.stringify({...body,request_key:requestKey})});
 if(response.status!==202)return response;
 const queued=await response.json();sessionStorage.setItem(pendingKey,JSON.stringify({signature,requestKey,body,id:queued.id}));
 return waitForJob(queued.id);
};
async function showJobs(date,service){
 const response=await originalFetch('/api/jobs?date='+encodeURIComponent(date)+'&service='+encodeURIComponent(service));if(!response.ok)return;
 const {jobs}=await response.json();let panel=document.getElementById('cloud-job-history');
 if(!panel){panel=document.createElement('section');panel.id='cloud-job-history';panel.style='margin:24px;padding:20px;background:white;border:1px solid #ddd;border-radius:12px';document.body.append(panel);}
 panel.replaceChildren();const heading=document.createElement('h2');heading.textContent=date+' 클라우드 제작 기록';panel.append(heading);
 const refresh=document.createElement('button');refresh.type='button';refresh.textContent='상태 새로고침';refresh.onclick=()=>showJobs(date,service);panel.append(refresh);
 if(!jobs.length){const empty=document.createElement('p');empty.textContent='아직 제작 기록이 없습니다.';panel.append(empty);return;}
 const list=document.createElement('ul');panel.append(list);
 for(const job of jobs){const item=document.createElement('li');item.style.margin='12px 0';
  const labels={queued:'실행 대기',running:'제작 중',succeeded:'제작됨 · 검수 필요',failed:'완료되지 않음'};
  item.textContent=(job.output==='pdf'?'주보 PDF':'예배 PPT')+' · '+(labels[job.status]||job.status)+' ';
  if(job.status==='succeeded'){const link=document.createElement('a');link.href='/api/generated?id='+encodeURIComponent(job.result.file_id)+'&format='+(job.output==='pdf'?'pdf':'pptx');link.textContent='다운로드';link.download=job.result.filename;item.append(link);}
  if(['queued','running'].includes(job.status)){const cancel=document.createElement('button');cancel.type='button';cancel.textContent='제작 취소';cancel.onclick=async()=>{await originalFetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:job.id})});await showJobs(date,service);};item.append(cancel);}
  list.append(item);
 }
}
// Recover an existing request after reload; this never creates or retries a job.
async function recover(){
 const pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null');if(!pending?.id)return;
 const response=await waitForJob(pending.id);if(!response.ok)return;
 const result=await response.json();const app=window.MediaApp;const k=pending.body.service+':'+pending.body.date;
 const state=app.syncState(k);if(!state.loaded||state.revision!==pending.body.revision){app.msg('클라우드 제작이 끝났습니다. 입력 저장 버전이 달라 파일 연결을 다시 확인해야 합니다.');return;}
 const record=app.records[k];if(!record)return;const kind=pending.body.output;
 record.outputs??={};record.outputs[kind]={...record.outputs[kind],generated:true,complete:false,changed:false,
  fileId:result.file_id,filename:result.filename,format:kind==='pdf'?'pdf':'pptx',unresolved:result.unresolved,
  engineVersion:result.engine_version,typographyVersion:result.typography_version,layoutVersion:result.layout_version};
 app.persistDraft(k);app.render();app.msg('클라우드 제작 결과를 복구했습니다. 화면과 실제 내용을 검수하세요.');
}
setTimeout(()=>{recover().catch(()=>window.MediaApp?.msg('제작 상태를 다시 확인하세요.'));const k=window.MediaApp?.key();if(k){const [service,date]=k.split(':');showJobs(date,service).catch(()=>{});}},2000);
})();
