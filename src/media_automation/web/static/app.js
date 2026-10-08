const $=id=>document.getElementById(id);
let token=location.hash.slice(1)||sessionStorage.getItem('media-token')||'';
if(token){sessionStorage.setItem('media-token',token);history.replaceState(null,'',location.pathname);}
let current=null;
const labels={needs_input:'자료 등록 대기',queued:'제작 대기',running:'제작 중',generated:'생성 완료 · 검수 필요',failed:'제작 실패',interrupted:'중단됨 · 새 작업 필요'};
const names={bulletin:'주일 주보',sunday:'주일예배',wednesday:'수요예배',friday:'금요기도회'};
async function api(path,options={}){const r=await fetch(path,{...options,headers:{Authorization:'Bearer '+token,...options.headers}});if(!r.ok){const data=await r.json();throw Error(data.error||'요청 실패');}return r;}
async function json(path,body){return (await api(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();}
function error(e){$('message').textContent=e.message;}
async function refresh(){try{const rows=await json('/api/jobs');$('jobs').replaceChildren();for(const job of rows){const b=document.createElement('button');b.textContent=`${job.date} · ${names[job.service]} · ${labels[job.state]||job.state}`;b.onclick=()=>show(job.job_id);$('jobs').append(b);}if(current)await show(current);}catch(e){error(e);}}
async function show(id){current=id;const job=await json('/api/jobs/'+id);$('detail').hidden=false;$('title').textContent=job.date+' '+names[job.service];$('state').textContent=(labels[job.state]||job.state)+(job.message?' — '+job.message:'');$('run').disabled=['queued','running','interrupted'].includes(job.state);$('inputs').replaceChildren();for(const path of job.inputs){const li=document.createElement('li');li.textContent=path;$('inputs').append(li);}$('artifacts').replaceChildren();for(const path of job.artifacts||[]){if(job.state!=='generated')continue;const b=document.createElement('button');b.textContent=path.split('/').pop();b.onclick=async()=>{try{const r=await api('/api/jobs/'+id+'/artifact?path='+encodeURIComponent(path));const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=path.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(e){error(e);}};$('artifacts').append(b);}}
$('create').onsubmit=async e=>{e.preventDefault();try{const job=await json('/api/jobs',{service:$('service').value,date:$('date').value});current=job.job_id;$('source').value='';$('path').value='';$('message').textContent='새 작업을 준비했습니다.';await refresh();}catch(e){error(e);}};
$('upload').onsubmit=async e=>{e.preventDefault();if(!current)return;try{await api('/api/jobs/'+current+'/files?path='+encodeURIComponent($('path').value),{method:'POST',body:$('file').files[0]});$('message').textContent='자료를 등록했습니다.';await refresh();}catch(e){error(e);}};
$('run').onclick=async()=>{try{await json('/api/jobs/'+current+'/run',{source:$('source').value||null});$('message').textContent='제작을 시작했습니다.';await refresh();}catch(e){error(e);}};
refresh();setInterval(refresh,3000);
