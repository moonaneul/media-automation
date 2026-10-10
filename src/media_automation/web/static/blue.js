(()=>{"use strict";
const $=id=>document.getElementById(id);
let token=location.hash.slice(1)||sessionStorage.getItem('media-token')||'';
if(token){sessionStorage.setItem('media-token',token);history.replaceState(null,'',location.pathname);}
let service='wednesday',page='work',tab='content',weekOffset=0,current=null,jobs=[],job=null,types=[],qa=null,previewURL=null;
const serviceNames={wednesday:'수요예배',friday:'금요기도회 Zoom',sunday:'주일예배',bulletin:'주일 주보'};
const stateNames={needs_input:'자료 준비',queued:'대기',running:'제작 중',generated:'파일 생성 · 검수 필요',failed:'제작 실패',interrupted:'중단'};
const notify=t=>{$('message').textContent=t};
async function request(url,options={}){const response=await fetch(url,{...options,headers:{Authorization:'Bearer '+token,...options.headers}});if(!response.ok){let msg='요청 실패';try{msg=(await response.json()).error||msg}catch{}throw Error(msg)}return response}
async function api(url,data){const opt=data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)};return(await request(url,opt)).json()}
function elem(tag,value,parent){const e=document.createElement(tag);if(value!=null)e.textContent=String(value);parent.append(e);return e}
function option(parent,value,label){const o=elem('option',label,parent);o.value=value}
const weekStart=()=>{const d=new Date();d.setHours(12,0,0,0);d.setDate(d.getDate()-((d.getDay()+6)%7)+7*weekOffset);return d};
const localDate=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
function serviceDate(){const d=weekStart();d.setDate(d.getDate()+{wednesday:2,friday:4,sunday:6,bulletin:6}[service]);return localDate(d)}
function pageShow(name){page=name;for(const p of ['work','library','archive','settings'])$(p+'-page').hidden=p!==name;document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===name));$('mobile-page').value=name;if(name==='archive')renderArchive()}
function tabShow(name){tab=name;for(const t of ['content','assets','result'])$(t+'-tab').hidden=t!==name;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));}
function path(){return serviceDate()}
function selectService(value){service=value;current=null;job=null;qa=null;for(const b of document.querySelectorAll('[data-service]'))b.classList.toggle('active',b.dataset.service===service);updateHeader();renderList();renderJob();tabShow('content')}
function updateHeader(){const a=weekStart(),b=new Date(a);b.setDate(b.getDate()+6);$('week-label').textContent=localDate(a)+' ~ '+localDate(b);$('service-title').textContent=serviceNames[service];$('service-date').textContent=path();$('job-status').textContent=job?stateNames[job.state]||job.state:'작업 미선택'}
function weeklyJobs(){return jobs.filter(x=>x.service===service&&x.date===path())}
function renderList(){const box=$('job-list');box.replaceChildren();const found=weeklyJobs();$('no-jobs').hidden=!!found.length;for(const x of found){const b=elem('button',x.date+' · '+(stateNames[x.state]||x.state)+' · '+x.job_id.slice(0,8),box);b.type='button';b.classList.toggle('active',x.job_id===current);b.onclick=()=>selectJob(x.job_id).catch(err)}} 
function renderArchive(){const box=$('archive-list');box.replaceChildren();for(const x of jobs){const b=elem('button',x.date+' '+serviceNames[x.service]+' · '+(stateNames[x.state]||x.state),box);b.onclick=()=>{service=x.service;pageShow('work');selectService(service);selectJob(x.job_id).catch(err)}}}
function err(error){notify(error.message||String(error))}
async function refresh(){jobs=await api('/api/jobs');if(current){try{job=await api('/api/jobs/'+current)}catch{current=null;job=null}}updateHeader();renderList();renderJob()}
async function selectJob(id){current=id;qa=null;job=await api('/api/jobs/'+id);types=await api('/api/jobs/'+id+'/input-types');renderList();renderJob();await refreshNotice();if(job.service==='bulletin')await refreshSundayChoices()}
function renderJob(){updateHeader();$('notice-panel').hidden=!job||service==='bulletin';$('bulletin-panel').hidden=!job||service!=='bulletin';$('upload-form').querySelectorAll('input,select,button').forEach(e=>e.disabled=!job);
$('input-files').replaceChildren();$('missing-items').replaceChildren();$('artifact-select').replaceChildren();$('qa-summary').textContent='검수할 제작 파일을 선택하세요';$('qa-form').hidden=true;
if(!job){$('readiness').textContent='이번 주 새 작업을 만들어주세요.';$('state-summary').textContent='미등록';$('build-help').textContent='작업을 먼저 선택하세요.';$('build').disabled=true;$('preview-build').disabled=true;$('download').disabled=true;$('qa-inspect').disabled=true;return}
const r=job.requirements||{ready:false,missing:[],checks:[]};$('readiness').textContent=r.ready?'필수 자료 1차 점검 통과 · 내용 검수 별도':'자료 준비가 더 필요합니다';for(const x of r.missing||[])elem('p','미등록: '+x,$('missing-items'));for(const x of r.checks||[])elem('p','확인: '+x,$('missing-items'));$('state-summary').textContent=stateNames[job.state]||job.state;
$('build-help').textContent=r.ready?'제작할 수 있습니다. 결과 화면과 음원은 별도 검수하세요.':'미등록·미확인 항목부터 해결해주세요.';
$('build').disabled=!r.ready||['queued','running','interrupted'].includes(job.state);
for(const x of job.inputs||[])elem('li',x,$('input-files'));
const original=$('input-kind').value;$('input-kind').replaceChildren();for(const t of types)option($('input-kind'),t.kind,t.label);if(types.some(x=>x.kind===original))$('input-kind').value=original;updateKind();
const art=job.state==='generated'?(job.artifacts||[]):[];for(const x of art)option($('artifact-select'),x,x.split('/').pop());
const enabled=art.length>0;for(const id of ['preview-build','download','qa-inspect'])$(id).disabled=!enabled;
if(enabled)statusPreview().catch(err);else{clearPreview();$('preview-help').textContent='제작된 결과 파일이 없습니다.'}}
function updateKind(){const found=types.find(x=>x.kind===$('input-kind').value);const select=$('input-slot');select.replaceChildren();$('slot-wrap').hidden=!(found&&found.slots.length);if(found)for(const slot of found.slots)option(select,slot,slot);$('input-file').accept=found?found.extensions.join(','):'';}
async function refreshNotice(){if(!job||service==='bulletin')return;const d=await api('/api/jobs/'+current+'/notice-preview');$('notice-fields').replaceChildren();$('notice-review').replaceChildren();$('notice-summary').textContent=d.available?'안내 원문 '+d.sources.length+'건 · 안내 날짜 '+(d.date_value||'미제공'):'아직 안내 원문이 없습니다.';for(const f of d.fields||[]){const v=Array.isArray(f.value)?f.value.join(', '):f.value;elem('div',f.name+' · '+f.state+(v?' · '+v:''),$('notice-fields'))}for(const c of d.checks||[])elem('div','확인: '+c,$('notice-review'));for(const x of d.review_items||[])elem('div','미인식: '+x.line,$('notice-review'));$('confirm-notice').disabled=!d.can_confirm||!d.available||job.inputs.some(x=>x.endsWith('_'+path().replaceAll('-','')+'_intake.yaml'))}
async function refreshSundayChoices(){const selected=$('sunday-job');selected.replaceChildren();for(const x of jobs.filter(x=>x.service==='sunday'&&x.date===path()&&x.state==='generated'))option(selected,x.job_id,x.date+' · '+x.job_id.slice(0,8));$('import-sunday').disabled=!selected.options.length}
function clearPreview(){if(previewURL)URL.revokeObjectURL(previewURL);previewURL=null;$('preview-display').replaceChildren()}
function activeArtifact(){return $('artifact-select').value}
async function statusPreview(){clearPreview();const p=activeArtifact();if(!p||!job)return;const st=await api('/api/jobs/'+current+'/preview/status?path='+encodeURIComponent(p));$('preview-help').textContent=st.message||'';if(st.available)await showPreview(p)}
async function showPreview(p){clearPreview();const response=await request('/api/jobs/'+current+'/preview?path='+encodeURIComponent(p));previewURL=URL.createObjectURL(await response.blob());const frame=elem('iframe',null,$('preview-display'));frame.title='PDF 미리보기';frame.src=previewURL}
async function download(url,name){const r=await request(url);const object=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=object;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(object),60000)}
async function refreshQA(){qa=null;$('qa-form').hidden=true;const p=activeArtifact();if(!p)return;const data=await api('/api/jobs/'+current+'/qa?path='+encodeURIComponent(p));renderQA(data)}
function renderQA(data){qa=data;if(!data.available){$('qa-summary').textContent=data.message||'아직 검수하지 않았습니다';$('qa-form').hidden=true;return}const s=data.automatic?.summary||{};$('qa-summary').textContent='자동 검수: 오류 '+(s.error??'?')+'건 / 확인 필요 '+(s.review??'?')+'건 · 사람 검수 '+(data.review_record_complete?'기록 완료':'미완료');$('qa-form').hidden=false;$('qa-reviewer').value=data.human?.reviewer||'';$('qa-note').value=data.human?.note||'';$('qa-checks').replaceChildren();for(const [key,label] of Object.entries(data.check_labels||{})){const wrap=elem('label',null,$('qa-checks'));wrap.append(document.createTextNode(label));const s=elem('select',null,wrap);s.dataset.check=key;for(const [v,t] of [['pending','미확인'],['checked','확인 완료'],['issue','문제 발견']])option(s,v,t);s.value=data.human?.checks?.[key]||'pending'}}
async function init(){document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>pageShow(b.dataset.page));$('mobile-page').onchange=e=>pageShow(e.target.value);document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tabShow(b.dataset.tab));document.querySelectorAll('[data-service]').forEach(b=>b.onclick=()=>selectService(b.dataset.service));document.querySelectorAll('[data-week]').forEach(b=>b.onclick=()=>{weekOffset=b.dataset.week==='0'?0:weekOffset+Number(b.dataset.week);selectService(service)});
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>tabShow('assets'));$('refresh').onclick=()=>refresh().catch(err);
$('new-job').onclick=async()=>{try{const rec=await api('/api/jobs',{service,date:path()});notify('새 작업을 만들었습니다.');await refresh();await selectJob(rec.job_id)}catch(e){err(e)}};
$('input-kind').onchange=updateKind;$('upload-form').onsubmit=async e=>{e.preventDefault();if(!current)return;const file=$('input-file').files[0];if(!file)return;const type=$('input-kind').value,slot=$('slot-wrap').hidden?'':$('input-slot').value;const q=new URLSearchParams({kind:type,filename:file.name});if(slot)q.set('slot',slot);try{await request('/api/jobs/'+current+'/typed-files?'+q,{method:'POST',body:file});notify('자료를 등록했습니다. 내용 정확성 확인은 별개입니다.');await selectJob(current)}catch(ex){err(ex)}};
$('confirm-notice').onclick=async()=>{try{await api('/api/jobs/'+current+'/confirm-notice',{});notify('안내 해석을 확정했습니다.');await selectJob(current)}catch(e){err(e)}};
$('save-bulletin-number').onclick=async()=>{try{await api('/api/jobs/'+current+'/bulletin-number',{number:$('bulletin-number').value});notify('주보 호수를 등록했습니다.');await selectJob(current)}catch(e){err(e)}};
$('import-sunday').onclick=async()=>{try{await api('/api/jobs/'+current+'/import-sunday-week',{sunday_job_id:$('sunday-job').value});notify('같은 주 주일 자료를 가져왔습니다.');await selectJob(current)}catch(e){err(e)}};
$('build').onclick=async()=>{try{await api('/api/jobs/'+current+'/run',{});notify('제작을 시작했습니다.');await refresh()}catch(e){err(e)}};
$('artifact-select').onchange=()=>{statusPreview().catch(err);refreshQA().catch(err)};
$('preview-build').onclick=async()=>{try{await api('/api/jobs/'+current+'/preview',{path:activeArtifact()});await statusPreview()}catch(e){err(e)}};
$('download').onclick=()=>{const p=activeArtifact();if(p)download('/api/jobs/'+current+'/artifact?path='+encodeURIComponent(p),p.split('/').pop()).catch(err)};
$('qa-inspect').onclick=async()=>{if(!activeArtifact())return;try{renderQA(await api('/api/jobs/'+current+'/qa/inspect',{path:activeArtifact()}));notify('구조 검사를 실행했습니다. 화면·재생은 직접 확인해 주세요.')}catch(e){err(e)}};
$('qa-form').onsubmit=async e=>{e.preventDefault();if(!qa?.available)return;const checks={};$('qa-checks').querySelectorAll('select').forEach(s=>checks[s.dataset.check]=s.value);try{renderQA(await api('/api/jobs/'+current+'/qa/confirm',{path:activeArtifact(),sha256:qa.sha256,reviewer:$('qa-reviewer').value,note:$('qa-note').value,checks}));notify('검수 상태를 저장했습니다.')}catch(ex){err(ex)}};
$('qa-report').onclick=()=>{if(activeArtifact())download('/api/jobs/'+current+'/qa/report?path='+encodeURIComponent(activeArtifact()),'inspection.json').catch(err)};
await refresh();notify('파란 화면 통합 시험판입니다. 예배별 원본 템플릿은 수정하지 않습니다.');setInterval(()=>refresh().catch(()=>{}),12000)}
init().catch(err);
})();