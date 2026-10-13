(function(root){
function numberForDate(dateText){
 const match=/^(\d{4})-(\d{2})-(\d{2})$/.exec(dateText);if(!match)return null;
 const year=Number(match[1]),month=Number(match[2]),day=Number(match[3]);
 const date=new Date(Date.UTC(year,month-1,day));
 if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day||date.getUTCDay()!==0||year!==2026)return null;
 const first=new Date(Date.UTC(year,0,1));first.setUTCDate(1+(7-first.getUTCDay())%7);
 const issue=1+Math.round((date-first)/(7*86400000));return issue>0?'13-'+issue:null;
}
root.BulletinNumber={numberForDate};if(typeof module!=='undefined')module.exports=root.BulletinNumber;
})(typeof globalThis!=='undefined'?globalThis:this);
