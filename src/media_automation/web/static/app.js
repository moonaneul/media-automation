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

const fieldLabels={
 opening_song_1:'시작 찬양 1',opening_song_2:'시작 찬양 2',opening_song_3:'시작 찬양 3',
 separate_hymn:'별도 찬송',second_service_prayer:'2부 기도',church_news:'교회 소식',
 offering_hymn:'봉헌 찬송',second_service_offering_prayer:'2부 봉헌기도',
 special_song:'특송',sermon_title:'설교 제목',scripture:'성경 본문',
 additional_scripture:'추가 말씀',decision_hymn:'결단 찬송',prayer:'기도',
 additional_song:'추가 찬양',first_prayer:'첫 기도 제목',song_after_prayer:'기도 후 찬양',
 response_song:'응답 찬양',word_prayer:'말씀 기도',intercession_song:'중보 찬양',
 community_prayer:'공동체 기도',personal_prayer:'개인 기도'
};
const inputStatus={
 VALUE:{icon:'✓',label:'입력됨',tone:'provided'},
 NONE:{icon:'—',label:'이번 주 없음',tone:'none'},
 UNSET:{icon:'○',label:'미제공',tone:'missing'}
};
function statusRow(parent,name,code,label){
 const row=item(parent,'li','');
 row.className='input-status-row';row.dataset.status=code;
 const left=item(row,'span',name);left.className='input-status-name';
 const right=item(row,'span',label);right.className='input-status-text';
}
function renderReadiness(r){
 const box=$('readiness');box.replaceChildren();
 const present=r.present||[],missing=r.missing||[],checks=r.checks||[],fields=r.fields||[];
 const total=present.length+missing.length;
 const summary=item(box,'p',r.ready?'✓ 제작 전 기초 확인 통과':'제작 전 확인이 필요해요');
 summary.className='readiness-summary';summary.dataset.status=r.ready?'provided':'missing';
 if(total)item(box,'p',`자료 ${present.length}/${total}개 등록 · 미제공 ${missing.length}개 · 내용 확인 ${checks.length}건`).className='hint';
 const list=item(box,'ul','');list.className='input-status-list';
 for(const name of present)statusRow(list,name,'provided','✓ 등록됨');
 for(const name of missing)statusRow(list,name,'missing','○ 미제공');
 for(const message of checks)statusRow(list,message,'review','! 확인 필요');
 if(!total&&!checks.length)item(box,'p',r.note||'');
 const fieldsArea=$('field-states');fieldsArea.replaceChildren();
 if(fields.length){
  const details=item(fieldsArea,'details','');
  const caption=item(details,'summary','이번 주 안내 항목 상태 보기');caption.className='status-details-toggle';
  const entries=item(details,'ul','');entries.className='input-status-list';
  for(const field of fields){
   const spec=inputStatus[field.state]||inputStatus.UNSET;
   statusRow(entries,fieldLabels[field.name]||field.name,spec.tone,`${spec.icon} ${spec.label}`);
  }
 }
}
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
 const r=job.requirements;renderReadiness(r);
 $('run').disabled=!r.ready||['queued','running','interrupted'].includes(job.state);
 $('run-help').textContent=r.ready?'제작기가 추가 내용 검증에 실패하면 성공 결과는 노출되지 않습니다.':'필수 입력과 미확인 항목이 해결되기 전에는 실행할 수 없습니다.';
 await generatedPreviewSelect(job,changed);
 $('artifacts').replaceChildren();for(const path of job.artifacts||[]){if(job.state!=='generated')continue;const b=item($('artifacts'),'button',path.split('/').pop());b.onclick=async()=>{try{const resp=await api('/api/jobs/'+id+'/artifact?path='+encodeURIComponent(path));const url=URL.createObjectURL(await resp.blob());const a=document.createElement('a');a.href=url;a.download=path.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){error(e);}};}
}
$('create').onsubmit=async e=>{e.preventDefault();try{const job=await json('/api/jobs',{service:$('service').value,date:$('date').value});current=null;$('message').textContent='새 작업을 준비했습니다.';await show(job.job_id);await refresh();$('detail').scrollIntoView({behavior:'smooth',block:'start'});}catch(e){error(e);}};
$('upload').onsubmit=async e=>{e.preventDefault();if(!current)return;const file=$('file').files[0],kind=$('input-kind').value,slot=$('slot-wrap').hidden?'':$('input-slot').value;if(!file)return;
 try{const query=new URLSearchParams({kind,filename:file.name});if(slot)query.set('slot',slot);await api('/api/jobs/'+current+'/typed-files?'+query,{method:'POST',body:file});$('message').textContent='입력 파일을 등록했습니다. 내용 검증은 별개입니다.';await refresh();}catch(e){error(e);}};
$('number-form').onsubmit=async e=>{e.preventDefault();try{await json('/api/jobs/'+current+'/bulletin-number',{number:$('bulletin-number').value});$('message').textContent='명시적으로 확인한 호수를 등록했습니다.';await refresh();}catch(e){error(e);}};
$('run').onclick=async()=>{try{await json('/api/jobs/'+current+'/run',{});$('message').textContent='제작을 시작했습니다.';await refresh();}catch(e){error(e);}};
refresh();setInterval(refresh,5000);

$('confirm-notice').onclick=async()=>{if(!current)return;try{await json('/api/jobs/'+current+'/confirm-notice',{});$('message').textContent='검토한 이번 주 안내를 해석 YAML로 저장했습니다. 추가 자료와 제작 검수는 별도로 필요합니다.';await refresh();}catch(e){error(e);}};

$('import-sunday').onsubmit=async e=>{e.preventDefault();if(!current)return;try{await json('/api/jobs/'+current+'/import-sunday-week',{sunday_job_id:$('source-sunday-job').value});$('message').textContent='이번 주 주일 작업의 공통 입력 3개를 명시적으로 가져왔습니다. 주보 원문과의 교차검수는 제작기에서 별도로 합니다.';await refresh();}catch(e){error(e);}};



let generatedPreviewURL=null, generatedPreviewKey=null, existingPreviewURL=null;
function releasePreview(id,oldUrl){
 if(oldUrl)URL.revokeObjectURL(oldUrl);
 $(id).replaceChildren();
}
async function showPdfFrame(endpoint, target, source){
 const response=await api(endpoint);
 const url=URL.createObjectURL(await response.blob());
 const frame=document.createElement('iframe');
 frame.title=source+' PDF 미리보기';frame.src=url;frame.loading='lazy';
 $(target).replaceChildren(frame);
 return url;
}
async function generatedPreviewSelect(job,changed){
 const select=$('preview-artifact');
 const paths=job.state==='generated'?(job.artifacts||[]):[];
 const previous=select.value;select.replaceChildren();
 for(const path of paths){
  const opt=document.createElement('option');opt.value=path;opt.textContent=path.split('/').pop();select.append(opt);
 }
 if(paths.includes(previous))select.value=previous;
 const available=paths.length>0;
 $('preview-empty').hidden=available;select.disabled=!available;
 $('preview-build').disabled=!available;
 if(!available){
   generatedPreviewKey=null;
   releasePreview('preview-display',generatedPreviewURL);generatedPreviewURL=null;
   $('preview-help').textContent='';return;
 }
 const key=job.job_id+'|'+select.value;
 if(changed||key!==generatedPreviewKey){
  generatedPreviewKey=key;
  await generatedPreviewShow();
 }
}
async function generatedPreviewShow(){
 releasePreview('preview-display',generatedPreviewURL);generatedPreviewURL=null;
 if(!current||!$('preview-artifact').value)return;
 const path=$('preview-artifact').value;
 const result=await json('/api/jobs/'+current+'/preview/status?path='+encodeURIComponent(path));
 $('preview-help').textContent=result.message||'';
 $('preview-build').hidden=!!result.available;
 $('preview-build').disabled=!!result.available;
 if(result.available)generatedPreviewURL=await showPdfFrame(
  '/api/jobs/'+current+'/preview?path='+encodeURIComponent(path),
  'preview-display','제작 결과'
 );
}
$('preview-artifact').onchange=()=>{generatedPreviewKey=current+'|'+$('preview-artifact').value;generatedPreviewShow().catch(error);};
$('preview-build').onclick=async()=>{
 try{await json('/api/jobs/'+current+'/preview',{path:$('preview-artifact').value});await generatedPreviewShow();}
 catch(e){error(e);}
};

$('existing-upload').onsubmit=async event=>{
 event.preventDefault();
 const file=$('existing-file').files[0];
 if(!file)return;
 const button=event.submitter;
 if(button)button.disabled=true;
 releasePreview('existing-preview',existingPreviewURL);existingPreviewURL=null;
 $('existing-preview-help').textContent='미리보기를 준비하는 중입니다. 큰 PPTX는 잠시 걸릴 수 있어요.';
 try{
  const query=new URLSearchParams({filename:file.name});
  const response=await api('/api/preview-once?'+query,{method:'POST',body:file});
  existingPreviewURL=URL.createObjectURL(await response.blob());
  const frame=document.createElement('iframe');
  frame.title=file.name+' 미리보기';
  frame.src=existingPreviewURL;frame.loading='lazy';
  $('existing-preview').append(frame);
  $('existing-preview-help').textContent='현재 선택한 파일만 표시하고 있어요. 서버에 목록이나 복사본을 보관하지 않습니다.';
 }catch(e){
  $('existing-preview-help').textContent='미리보기를 열지 못했어요. 파일 또는 PowerPoint 변환 상태를 확인해주세요.';
  error(e);
 }finally{
  if(button)button.disabled=false;
 }
};
