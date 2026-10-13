(function(root){
function cleanPerson(value){return String(value).split(/[,，\n]+/).map(v=>v.trim().replace(/\s*(?:형제|자매|목사|집사|장로|권사)(?:님)?\s*$/,'').trim()).filter(Boolean).join(', ');}
function isPerson(label){return /담당자|인도자|설거지|수요예배 기도|(?:1부|2부) (?:기도|봉헌기도)$/.test(label);}
function cleanPeople(fields){for(const [label,f]of Object.entries(fields))if(isPerson(label)&&f.state==='VALUE')f.value=cleanPerson(f.value);return fields;}
function parseFriday(raw){
 const fields={},groups=[],unknown=[],prayerGroups=[];let phase='first',topic=null,prayerGroup=null;
 const prefixes={first:'첫',word:'말씀 관련',final:'공동체·중보'};
 const field=(label,value,state='VALUE')=>{fields[label]={state,value};};
 const addGroup=(title,labels)=>{groups.push([title,labels]);return labels;};
 function finish(){if(topic){field(topic.bodyLabel,topic.body.join('\n'),topic.body.length?'VALUE':'NONE');topic=null;}}
 function song(number,title){finish();prayerGroup=null;const label='찬양 '+number;field(label,title,title?'VALUE':'UNSET');const previous=groups.at(-1);if(previous&&/^찬양 순서 \d+$/.test(previous[0]))previous[1].push(label);else addGroup('찬양 순서 '+number,[label]);}
 for(const original of raw.split(/\r?\n/)){
  const line=original.trim();if(!line)continue;
  if(/^\[금요\s*기도회\s*순서\]/.test(line)){finish();continue;}
  if(/^<.*>$/.test(line)){finish();prayerGroup=null;if(/메시지/.test(line))phase='word';else if(/마지막/.test(line))phase='final';else if(/두 곡/.test(line))phase='first';continue;}
  let m=line.match(/^(\d+)\)\s*~\s*(\d+)\)\s*$/);
  if(m){for(let n=Number(m[1]);n<=Number(m[2]);n++)song(n,'');continue;}
  m=line.match(/^(\d+)\)\s*(.*)$/);if(m){song(Number(m[1]),m[2]);continue;}
  m=line.match(/^읽을\s*말씀\s*[–—\-:：]\s*(.*)$/);if(m){finish();field('추가 말씀',m[1],m[1]?'VALUE':'NONE');const group=groups.find(g=>g[0]==='말씀');if(group)group[1].push('추가 말씀');else addGroup('말씀',['추가 말씀']);continue;}
  m=line.match(/^([가-힣]+\s*\d+\s*:\s*\d+(?:\s*[~～\-]\s*\d+)?)\s*\/\s*(.+)$/);
  if(m){finish();phase='word';prayerGroup=null;field('성경 본문',m[1]);field('설교 제목',m[2]);addGroup('말씀',['성경 본문','설교 제목']);continue;}
  m=line.match(/^(\d+)\.\s*(.+)$/);
  if(m){finish();if(!prayerGroup){const title=prefixes[phase]+' 기도';let key=title;let suffix=2;while(prayerGroups.some(g=>g.title===key))key=title+' '+suffix++;prayerGroup={title:key,prefix:key,ids:[]};prayerGroups.push(prayerGroup);addGroup(key,[]);}const id=prayerGroup.ids.length+1;prayerGroup.ids.push(id);const titleLabel=prayerGroup.prefix+' 제목 '+id,bodyLabel=prayerGroup.prefix+' 내용 '+id;field(titleLabel,m[2]);groups.at(-1)[1].push(titleLabel,bodyLabel);topic={bodyLabel,body:[]};continue;}
  if(topic){topic.body.push(line);continue;}
  unknown.push(line);
 }
 finish();
 const date=raw.match(/\[금요\s*기도회\s*순서\]\s*(\d{1,2})\/(\d{1,2})/);
 cleanPeople(fields);return {fields,groups,prayerGroups,unknown,dateLabel:date?date[1]+'/'+date[2]:null};
}

function parseWednesday(raw){
 const fields={},unknown=[];const put=(k,v,state)=>fields[k]={state:state||(v?'VALUE':'NONE'),value:v};
 for(const text of raw.split(/\r?\n/)){const line=text.trim();if(!line)continue;if(/^수요\s*예배/.test(line))continue;
 let m=line.match(/^3곡\s*찬양\s*[:：]\s*(.*)$/);if(m){put('찬양 인도자',m[1]);for(let n=1;n<=3;n++)put('시작 찬양 '+n,'','UNSET');continue;}
 m=line.match(/^말씀\s*봉독\s*[:：]\s*(.*?)\s*\/\s*(.*)$/);if(m){put('성경 본문',m[1]);put('설교 제목',m[2]);continue;}
 m=line.match(/^(기도|찬양\s*1곡|읽을\s*말씀|결단\s*찬송|폐회\s*기도)\s*[:：]\s*(.*)$/);if(m){put({'기도':'기도 담당자','찬양 1곡':'추가 찬양','읽을 말씀':'추가 말씀','결단 찬송':'결단 찬송','폐회 기도':'폐회 기도 담당자'}[m[1].replace(/\s+/g,' ').trim()],m[2]);continue;}
 if(line==='광고'){put('광고 순서','포함');continue;}unknown.push(line);
 }
 const date=raw.match(/수요\s*예배\s*\(\s*(\d+)\/(\d+)/);
 cleanPeople(fields);return {fields,unknown,dateLabel:date?Number(date[1])+'/'+Number(date[2]):null};
}
function parseBulletinCore(raw){
 const fields={},unknown=[];const put=(k,v)=>fields[k]={state:v?'VALUE':'NONE',value:v};const lines=raw.split(/\r?\n/).map(v=>v.trim()).filter(Boolean);let section=null,body=[];
 const finish=()=>{if(section&&section!=='목장')put(section,body.join('\n'));body=[];section=null;};
 for(let i=0;i<lines.length;i++){const line=lines[i];let m;const heading=line.replace(/[<>〈〉《》＜＞\[\]【】*]/g,'').replace(/\s/g,'');
 if((m=heading.match(/^교회소식$/))){finish();section='교회 소식';continue;}
 if((m=heading.match(/^(.+사역일정)$/))){finish();section='월간 사역 일정';put('월간 일정 제목',m[1]);continue;}
 if(/^목장말씀나누기$/.test(heading)){finish();section='목장';continue;}
 if(section==='목장'){m=line.match(/^<(.+?)\s*\/\s*(.+)>$/);if(m){put('목장 본문',m[1]);put('목장 제목',m[2]);continue;}m=line.match(/^(\d+)\.\s*(.*)$/);if(m){put('질문 '+m[1],m[2]);continue;}unknown.push(line);continue;}
 if(section&&/^[<〈《＜\[【]/.test(line)){finish();unknown.push(line);continue;}if(section){body.push(line);continue;}
 m=line.match(/^(?:cf\)\s*)?오후\s*예배\s*[:：]\s*(.*)$/);if(m){put('오후예배',m[1]);continue;}
 m=line.match(/^찬양\s*[:：]\s*(.*)$/);if(m){put('전달 주보 찬양 목록',m[1]);continue;}
 if(/^예배\/섬김[:：]?$/.test(heading)){let table=[];while(i+1<lines.length&&!lines[i+1].startsWith('*')&&!lines[i+1].startsWith('<')&&!/^주\s*일\s*오\s*전/.test(lines[i+1]))table.push(lines[++i]);put('전달 섬김표 원문',table.join('\n'));const compact=table.map(v=>v.replace(/\s/g,''));const a=compact.indexOf('이번주'),b=compact.indexOf('다음주');let valid=true;
 for(const [start,end,key]of [[a,b,'이번 주 섬김'],[b,table.length,'다음 주 섬김']]){if(start<0||end<=start){valid=false;continue;}const rows=table.slice(start+1,end),clean=rows.map(v=>v.replace(/\s/g,''));const one=clean.indexOf('1부'),two=clean.indexOf('2부');const first=rows.slice(one+1,two),second=rows.slice(two+1);if(one!==0||first.length!==4||second.length!==2){valid=false;continue;}put(key,'1부 기도: '+first[0]+'\n1부 봉헌기도: '+first[1]+'\n2부 기도: '+second[0]+'\n2부 봉헌기도: '+second[1]+'\n설거지: '+first[2]+'\n수요예배 기도: '+first[3]);if(key==='이번 주 섬김'){put('1부 예배 순서·담당자','기도: '+first[0]+' / 봉헌기도: '+first[1]);put('2부 기도 담당자',second[0]);put('2부 봉헌기도 담당자',second[1]);}}
 unknown.push(valid?'섬김표의 담당자를 자동 배정했습니다. 병합된 설거지·수요 기도 칸은 첨부 원본과 확인하세요.':'섬김표 구조가 달라 자동 배정하지 못했습니다. 원문을 확인하고 각 담당자를 입력하세요.');continue;}
 m=line.match(/^\*설교\s*중\s*읽을\s*말씀\s*[☞:：–—-]?\s*(.*)$/);if(m){put('추가 말씀',m[1]);continue;}
 m=line.match(/^\*1면\s*[–—-]\s*(.*)$/);if(m){put('표지 변경 사항',m[1]);continue;}
 if(line==='*'){unknown.push('이름 없는 빈 항목은 자동으로 배정하지 않았습니다.');continue;}
 if(/^\d{1,2}\/\d{1,2}$/.test(line)||/^주보\s+/.test(line))continue;unknown.push(line);
 }finish();const date=lines.find(v=>/^\d{1,2}\/\d{1,2}$/.test(v));
 cleanPeople(fields);return {fields,unknown,dateLabel:date||null};
}

function parseBulletin(raw){
 const lines=raw.split(/\r?\n/).map(v=>v.trim()).filter(Boolean);const fields={},remaining=[],reference=[];let order=false,block=null,values=[],fixed=false,otherMeetings=false,meetingLines=[];
 const normalize=v=>v.replace(/\s/g,'');
 const labels={'인도:':'주일 인도자','경배와찬양':'찬양 인도 담당자','예배로의부르심':'예배로의 부르심 담당자','찬송':'별도 찬송','기도':'기도','환영':'환영 담당자','교회소식':'광고 담당자','봉헌찬송':'봉헌 찬송','봉헌기도':'봉헌기도','성경봉독':'성경 본문','말씀선포':'설교 제목','결단찬송':'결단 찬송','폐회기도':'폐회 기도 담당자'};
 const put=(k,v)=>fields[k]={state:v?'VALUE':'NONE',value:v};
 function finish(){if(!block)return;const v=values.filter(x=>!/^[-─━–—]+$/.test(x));if(block==='기도'||block==='봉헌기도'||block==='찬양 인도 담당자'){let part=null;for(const line of v){const m=line.match(/^([12])\s*부\s*(.*)$/);if(m){part=m[1];if(m[2])put(part+'부 '+(block==='기도'?'기도 담당자':block==='봉헌기도'?'봉헌기도 담당자':'찬양 인도자'),m[2]);}else if(part)put(part+'부 '+(block==='기도'?'기도 담당자':block==='봉헌기도'?'봉헌기도 담당자':'찬양 인도자'),line);else put(block,line);}}else {const content=['별도 찬송','봉헌 찬송','결단 찬송','성경 본문','설교 제목'].includes(block)?v[0]||'':v.join('\n');put(block,content);}block=null;values=[];}
 for(const line of lines){const n=normalize(line);
 if(n==='오전예배순서'){order=true;continue;}
 if(order&&(n.includes('예배/섬김')||line.startsWith('*'))){finish();order=false;}
 if(order){if(labels[n]){finish();block=labels[n];continue;}if(block)values.push(line);else if(!/^[-─]+$/.test(line))remaining.push(line);continue;}
 if(n==='주일오전'){otherMeetings=true;}if(otherMeetings){if(/목장말씀나누기/.test(n)){otherMeetings=false;const afternoon=meetingLines.findIndex(v=>/^주\s*일\s*오\s*후$/.test(v));if(afternoon>=0){const after=meetingLines.slice(afternoon+1);const candidates=after.filter(v=>!/^\(/.test(v)&&!/^수\s*요\s*예\s*배/.test(v)&&!/^[-─]+$/.test(v));const topic=candidates.find(v=>/생명의\s*삶/.test(v));if(topic)put('오후예배',topic);}reference.push(meetingLines.join('\n'));}else{meetingLines.push(line);continue;}}if(/^\*\s*헌금/.test(line)){reference.push(line);continue;}if(n.includes('예배/모임안내')){fixed=true;reference.push(line);continue;}
 if(fixed){reference.push(line);continue;}
 remaining.push(line);
 }finish();const result=parseBulletinCore(remaining.join('\n'));Object.assign(result.fields,fields);
 if(reference.length)result.reference=reference.join('\n');delete result.fields['헌금 안내'];delete result.fields['기타 예배·모임 안내'];
 if(fields['주일 인도자'])result.fields['1부 예배 순서·담당자']={state:'VALUE',value:Object.entries(fields).filter(([k])=>/^1부|주일 인도자/.test(k)).map(([k,v])=>k+': '+v.value).join('\n')};
 for(const [key,prefix]of [['이번 주 섬김','이번 주'],['다음 주 섬김','다음 주']]){const text=result.fields[key]?.value;if(text)for(const line of text.split('\n')){const m=line.match(/^(.+?):\s*(.*)$/);if(!m)continue;const name=m[1]==='수요예배 기도'?'수요예배 기도':m[1];const label=prefix==='이번 주'&&/^2부 (기도|봉헌기도)$/.test(name)?name+' 담당자':prefix+' '+name;if(!result.fields[label])result.fields[label]={state:m[2]?'VALUE':'NONE',value:m[2]};}delete result.fields[key];}delete result.fields['전달 섬김표 원문'];delete result.fields['1부 예배 순서·담당자'];
 result.songList=result.fields['전달 주보 찬양 목록']?.value||'';delete result.fields['전달 주보 찬양 목록'];cleanPeople(result.fields);return result;
}
root.NoticeParser={parseFriday,parseWednesday,parseBulletin,cleanPerson,isPerson};if(typeof module!=='undefined')module.exports=root.NoticeParser;
})(typeof globalThis!=='undefined'?globalThis:this);
