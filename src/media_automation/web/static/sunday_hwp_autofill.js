/* Sunday HWP autofill policy: preserve existing entries and review table cells.
 * This file does not read files or mutate DOM. It plans safe field updates only.
 */
(function(root){
  'use strict';
  function isTableReview(label){
    return /^(?:이번 주|다음 주) (?:1부|2부|설거지|수요예배 기도)/.test(label) ||
      /^2부 (?:기도|봉헌기도) 담당자$/.test(label);
  }
  function normalizeDate(label){
    const m=String(label||'').match(/^\s*(\d{1,2})\s*\/\s*(\d{1,2})\s*$/);
    return m ? Number(m[1])+'/'+Number(m[2]) : null;
  }
  function plan(parsed, sourceDate, targetDate, currentFields){
    if(!parsed || typeof parsed!=='object' || !currentFields || typeof currentFields!=='object')
      throw new Error('안내문 해석 정보를 확인해주세요.');
    const date=normalizeDate(sourceDate), expected=normalizeDate(targetDate);
    const dateMismatch=!!date && date!==expected;
    const updates={}, review=[],preserved=[];
    for(const [label,field] of Object.entries(parsed)){
      if(!field || !['VALUE','NONE','UNSET'].includes(field.state))continue;
      if(isTableReview(label)){
        review.push(label);
        continue;
      }
      if(field.state==='UNSET')continue;
      const old=currentFields[label];
      if(old && old.state!=='UNSET' && (old.state!==field.state || old.value!==field.value)){
        preserved.push(label); continue;
      }
      updates[label]={state:field.state,value:field.value||''};
    }
    if(dateMismatch)return {updates:{},review,preserved,dateMismatch:true};
    return {updates,review,preserved,dateMismatch:false};
  }

  /* 목장 본문/제목 are NOT automatically the Sunday morning sermon.
   * Prepare a copy only after the operator explicitly confirms they match. */
  function planSermonCopy(fields){
    const sourceNames={'성경 본문':'목장 본문','설교 제목':'목장 제목'};
    const updates={},conflicts=[],equal=[];
    const missing=Object.entries(sourceNames).filter(([,from])=>
      fields[from]?.state!=='VALUE'||!String(fields[from].value||'').trim()
    ).map(([,from])=>from);
    if(missing.length)return {ready:false,updates:{},conflicts:[],
      message:'목장 본문과 제목이 모두 입력되어야 복사할 수 있습니다.'};
    for(const [to,from] of Object.entries(sourceNames)){
      const value=fields[from].value.trim(), existing=fields[to];
      if(existing && existing.state==='VALUE' && existing.value.trim()===value){
        equal.push(to);
      }else if(existing && existing.state && existing.state!=='UNSET'){
        conflicts.push(to);
      }else{
        updates[to]={state:'VALUE',value};
      }
    }
    return {
      ready:conflicts.length===0&&Object.keys(updates).length>0,
      updates:conflicts.length?{}:updates,
      conflicts,equal,
      message:conflicts.length?'이미 입력된 PPT 본문/설교 제목이 다릅니다. 자동으로 덮어쓰지 않습니다.':
        Object.keys(updates).length?'목장 말씀을 이번 주 주일 PPT에도 사용할지 확인해주세요.':
        '목장 본문/제목과 주일 PPT 본문/설교 제목이 이미 일치합니다.',
    };
  }
  root.SundayHwpAutofill={plan,isTableReview,planSermonCopy};
  if(typeof module!=='undefined')module.exports=root.SundayHwpAutofill;
})(typeof globalThis!=='undefined'?globalThis:this);
