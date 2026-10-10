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
  root.SundayHwpAutofill={plan,isTableReview};
  if(typeof module!=='undefined')module.exports=root.SundayHwpAutofill;
})(typeof globalThis!=='undefined'?globalThis:this);
