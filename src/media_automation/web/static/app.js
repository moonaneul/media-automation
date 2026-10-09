const $=id=>document.getElementById(id);
let token=location.hash.slice(1)||sessionStorage.getItem('media-token')||'';
if(token){sessionStorage.setItem('media-token',token);history.replaceState(null,'',location.pathname);}
let current=null,types=[],jobsCache=[];
const labels={needs_input:'자료 확인 대기',queued:'제작 대기',running:'제작 중',generated:'생성 완료 · 검수 필요',failed:'제작 실패',interrupted:'중단됨 · 새 작업 필요'};
const names={bulletin:'주일 주보',sunday:'주일예배',wednesday:'수요예배',friday:'금요기도회 Zoom'};
async function api(path,options={}){const r=await fetch(path,{...options,headers:{Authorization:'Bearer '+token,...options.headers}});if(!r.ok){let message='요청 실패';try{message=(await r.json()).error||message;}catch{}throw Error(message);}return r;}
async function json(path,body){return (await api(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();}
function error(e){$('message').textContent=e.message;}
function item(parent,tag,text){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e;}
function updateType(){const kind=types.find(x=>x.kind===$('input-kind').value);$('slot-wrap').hidden=!(kind&&kind.slots.length);$('input-slot').replaceChildren();if(kind){for(const slot of kind.slots){const opt=document.createElement('option');opt.value=slot;opt.textContent=slot;$('input-slot').append(opt);}$('file').accept=kind.extensions.join(',');$('file').value='';}}
$('input-kind').onchange=updateType;
async function refresh(){try{const rows=await json('/api/jobs');jobsCache=rows;$('jobs').replaceChildren();for(const job of rows){const b=item($('jobs'),'button',`${job.date} · ${names[job.service]} · ${labels[job.state]||job.state}`);b.onclick=()=>show(job.job_id);}if(current)await show(current);}catch(e){error(e);}}
async function show(id){
 const changed=current!==id;current=id;const job=await json('/api/jobs/'+id);
 $('detail').hidden=false;$('title').textContent=job.date+' '+names[job.service];$('state').textContent=(labels[job.state]||job.state)+(job.message?' — '+job.message:'');
 if(changed||!types.length){types=await json('/api/jobs/'+id+'/input-types');$('input-kind').replaceChildren();for(const type of types){const opt=document.createElement('option');opt.value=type.kind;opt.textContent=type.label;$('input-kind').append(opt);}updateType();}
 $('number-form').hidden=job.service!=='bulletin';$('inputs').replaceChildren();for(const path of job.inputs)item($('inputs'),'li',path);
 const pane=$('notice-pane');pane.hidden=job.service==='bulletin';
 if(!pane.hidden){
   const draft=await json('/api/jobs/'+id+'/notice-preview');
   $('notice-summary').replaceChildren();$('notice-fields').replaceChildren();$('notice-review').replaceChildren();
   if(!draft.available){item($('notice-summary'),'p',draft.note);}
   else{
     item($('notice-summary'),'p',`작업 날짜 ${job.date} · 안내 날짜 ${draft.date_value||'미제공'} (${draft.date_state}) · 안내 원본 ${draft.sources.length}개`);
     const list=item($('notice-fields'),'ul','');
     for(const field of draft.fields){
       const value=field.state==='VALUE'?(Array.isArray(field.value)?field.value.join(' / '):(field.value??(field.asset_required?'곡명은 검수 악보에서 확인':''))):'';
       item(list,'li',`${field.name} · ${field.state}${value?' — '+value:''}${field.source?' · 출처: '+field.source:''}`);
     }
     for(const check of draft.checks)item($('notice-review'),'p','확인 필요: '+check);
     for(const row of draft.review_items)item($('notice-review'),'p',`인식되지 않은 문장 (${row.source}): ${row.line}${row.reason?' — '+row.reason:''}`);
     if(draft.can_confirm)item($('notice-review'),'p','안내 해석 상태 확인 가능. 악보·본문·주보 정합성은 별도 검수입니다.');
   }
   const hasIntake=job.inputs.some(path=>path.endsWith(`_${job.date.replaceAll('-','')}_intake.yaml`));
   $('confirm-notice').disabled=!draft.available||!draft.can_confirm||hasIntake||['queued','running','interrupted'].includes(job.state);
   if(hasIntake)item($('notice-review'),'p','안내 해석 YAML이 이미 등록되어 있습니다. 덮어쓰기 없이 새 작업에서 수정할 수 있습니다.');
 }


 $('common-pane').hidden=!['sunday','bulletin'].includes(job.service);
 if(!$('common-pane').hidden){
   const shared=await json('/api/jobs/'+id+'/sunday-common');
   $('common-summary').replaceChildren();
   item($('common-summary'),'p',shared.note||'');
   if(shared.available){
     const ul=item($('common-summary'),'ul','');
     for(const f of shared.fields){const value=Array.isArray(f.value)?f.value.join(' / '):f.value;item(ul,'li',`${f.name}: ${f.state}${value?' — '+value:''}`);}
     for(const problem of shared.checks)item($('common-summary'),'p','확인 필요: '+problem);
   }
   const candidates=jobsCache.filter(j=>j.service==='sunday'&&j.date===job.date&&j.state==='generated');
   const form=$('import-sunday');form.hidden=job.service!=='bulletin'||!candidates.length;
   const previousSelection=$('source-sunday-job').value;
   $('source-sunday-job').replaceChildren();
   for(const candidate of candidates){const option=document.createElement('option');option.value=candidate.job_id;option.textContent=`${candidate.date} · ${candidate.job_id.slice(0,8)} · 생성 완료(검수 별도)`;$('source-sunday-job').append(option);}
   if(candidates.some(c=>c.job_id===previousSelection))$('source-sunday-job').value=previousSelection;
   if(job.service==='bulletin'&&!candidates.length)item($('common-summary'),'p','가져올 수 있는 같은 주 주일 생성 작업이 없습니다.');
 }
 const r=job.requirements;$('readiness').replaceChildren();item($('readiness'),'p',r.ready?'필수 자료의 기초 확인 통과 · 내용과 화면 검수는 별도':'제작 전 확인 필요');
 for(const name of r.missing)item($('readiness'),'p','미등록: '+name);
 for(const check of r.checks)item($('readiness'),'p','확인 필요: '+check);
 if(!r.missing.length&&!r.checks.length)item($('readiness'),'p',r.note);
 $('field-states').replaceChildren();if(r.fields.length){item($('field-states'),'h4','이번 주 안내 항목 상태');const ul=item($('field-states'),'ul','');for(const field of r.fields)item(ul,'li',`${field.name}: ${field.state}`);}
 $('run').disabled=!r.ready||['queued','running','interrupted'].includes(job.state);
 $('run-help').textContent=r.ready?'제작기가 추가 내용 검증에 실패하면 성공 결과는 노출되지 않습니다.':'필수 입력과 미확인 항목이 해결되기 전에는 실행할 수 없습니다.';
 await qaSelect(job,changed);
 $('artifacts').replaceChildren();for(const path of job.artifacts||[]){if(job.state!=='generated')continue;const b=item($('artifacts'),'button',path.split('/').pop());b.onclick=async()=>{try{const resp=await api('/api/jobs/'+id+'/artifact?path='+encodeURIComponent(path));const url=URL.createObjectURL(await resp.blob());const a=document.createElement('a');a.href=url;a.download=path.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){error(e);}};}
}
$('create').onsubmit=async e=>{e.preventDefault();try{const job=await json('/api/jobs',{service:$('service').value,date:$('date').value});current=null;$('message').textContent='새 작업을 준비했습니다.';await show(job.job_id);await refresh();}catch(e){error(e);}};
$('upload').onsubmit=async e=>{e.preventDefault();if(!current)return;const file=$('file').files[0],kind=$('input-kind').value,slot=$('slot-wrap').hidden?'':$('input-slot').value;if(!file)return;
 try{const query=new URLSearchParams({kind,filename:file.name});if(slot)query.set('slot',slot);await api('/api/jobs/'+current+'/typed-files?'+query,{method:'POST',body:file});$('message').textContent='입력 파일을 등록했습니다. 내용 검증은 별개입니다.';await refresh();}catch(e){error(e);}};
$('number-form').onsubmit=async e=>{e.preventDefault();try{await json('/api/jobs/'+current+'/bulletin-number',{number:$('bulletin-number').value});$('message').textContent='명시적으로 확인한 호수를 등록했습니다.';await refresh();}catch(e){error(e);}};
$('run').onclick=async()=>{try{await json('/api/jobs/'+current+'/run',{});$('message').textContent='제작을 시작했습니다.';await refresh();}catch(e){error(e);}};
refresh();setInterval(refresh,5000);

$('confirm-notice').onclick=async()=>{if(!current)return;try{await json('/api/jobs/'+current+'/confirm-notice',{});$('message').textContent='검토한 이번 주 안내를 해석 YAML로 저장했습니다. 추가 자료와 제작 검수는 별도로 필요합니다.';await refresh();}catch(e){error(e);}};

$('import-sunday').onsubmit=async e=>{e.preventDefault();if(!current)return;try{await json('/api/jobs/'+current+'/import-sunday-week',{sunday_job_id:$('source-sunday-job').value});$('message').textContent='이번 주 주일 작업의 공통 입력 3개를 명시적으로 가져왔습니다. 주보 원문과의 교차검수는 제작기에서 별도로 합니다.';await refresh();}catch(e){error(e);}};


let qaCurrent=null;
async function qaSelect(job,changed){
 const select=$('qa-artifact'),paths=job.state==='generated'?(job.artifacts||[]):[];
 const previous=select.value;
 select.replaceChildren();
 for(const path of paths){const opt=document.createElement('option');opt.value=path;opt.textContent=path.split('/').pop();select.append(opt);}
 if(paths.includes(previous))select.value=previous;
 const ready=paths.length>0;
 $('qa-empty').hidden=ready;select.disabled=!ready;$('qa-run').disabled=!ready;
 if(!ready){$('qa-results').replaceChildren();$('qa-human').hidden=true;$('qa-report').hidden=true;qaCurrent=null;return;}
 if(changed)$('qa-reference').value='';
 if(changed||qaCurrent?.artifact!==select.value) await qaLoad();
}
async function qaLoad(){
 if(!current||!$('qa-artifact').value)return;
 const path=$('qa-artifact').value;
 const result=await json('/api/jobs/'+current+'/qa?path='+encodeURIComponent(path));
 qaCurrent=result;
 const box=$('qa-results');box.replaceChildren();
 $('qa-human').hidden=!result.available;$('qa-report').hidden=!result.available;
 if(!result.available){item(box,'p',result.message||'검수 전입니다.');return;}
 const a=result.automatic;
 item(box,'p',`자동검사: 오류 ${a.summary.error}건, 확인 필요 ${a.summary.review}건. 렌더링 및 재생은 자동 확인하지 않았습니다.`);
 const ul=item(box,'ul','');
 for(const issue of a.issues)item(ul,'li',`${issue.severity==='error'?'오류':'확인 필요'}: ${issue.message}${issue.slide?' (슬라이드 '+issue.slide+')':''}`);
 item(box,'p',result.review_record_complete?'모든 사람 검수 항목 기록 완료 (자동 오류 없음)':'최종 검수 미완료');
 $('qa-reviewer').value=result.human.reviewer||'';
 $('qa-note').value=result.human.note||'';
 const checks=$('qa-checks');checks.replaceChildren();
 for(const [key,label] of Object.entries(result.check_labels)){
  const wrap=item(checks,'label',label),select=document.createElement('select');select.dataset.qaCheck=key;
  for(const [value,name] of [['pending','미확인'],['checked','확인 완료'],['issue','문제 발견']]){const opt=document.createElement('option');opt.value=value;opt.textContent=name;select.append(opt);}
  select.value=result.human.checks[key]||'pending';wrap.append(select);
 }
}
$('qa-artifact').onchange=()=>qaLoad().catch(error);
$('qa-run').onclick=async()=>{try{const path=$('qa-artifact').value;await json('/api/jobs/'+current+'/qa/inspect',{path,reference:$('qa-reference').value});$('message').textContent='자동 검수 완료. 이전 사람 검수 기록은 초기화되었습니다.';await qaLoad();}catch(e){error(e);}};
$('qa-human').onsubmit=async e=>{e.preventDefault();try{
 const checks={};for(const select of document.querySelectorAll('[data-qa-check]'))checks[select.dataset.qaCheck]=select.value;
 await json('/api/jobs/'+current+'/qa/confirm',{path:$('qa-artifact').value,sha256:qaCurrent.sha256,reviewer:$('qa-reviewer').value,note:$('qa-note').value,checks});
 $('message').textContent='사람 검수 기록을 저장했습니다.';await qaLoad();
}catch(err){error(err);}};
$('qa-report').onclick=async()=>{try{
 const path=$('qa-artifact').value,r=await api('/api/jobs/'+current+'/qa/report?path='+encodeURIComponent(path));
 const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='qa-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
}catch(e){error(e);}};
