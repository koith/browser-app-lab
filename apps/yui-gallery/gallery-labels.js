(function(root){
 'use strict';
 function describe(a){
  const title=String(a.title||''),explicit=typeof a.publisher==='string'?a.publisher.trim():'';
  let publisher=explicit||({'cn-wantuzhi-everyday':'Yo-U'}[a.id]||'');
  const brands=[[/sweetbox|\bSWTB\b/i,'SWEETBOX'],[/artgravia|\bAG\.\s*663\b/i,'ArtGravia'],[/milkybomb/i,'MilkyBomb'],[/\bYo[-_ ]?U\b/i,'Yo-U'],[/pussylet/i,'PUSSYLET'],[/movie fantasy|\[(?:M|H)\.F\]/i,'MOVIE FANTASY']];
  if(!publisher)publisher=brands.find(([pattern])=>pattern.test(title))?.[1]||'';
  if(!publisher){
   let host='';try{host=new URL(a.source||'').hostname}catch{}
   if(host==='ctee.kr')publisher='크티';
   else if(host==='bcutrank.com'||host==='bcut.maximkorea.net')publisher='B컷';
   else if(/MOVIE FANTASY/i.test(a.site||''))publisher='MOVIE FANTASY';
  }
  const processing=(title+' '+String(a.quality||'')).replace(/[_-]/g,' ');
  const ai=a.ai_enhanced===true||/\bAI\s*(?:enhanc\w*|보정)/i.test(processing);
  const original=a.publisher_original_verified===true&&!ai;
  return {publisher:publisher||'미확인',kind:ai?'ai':original?'original':'web',
   edition:ai?'AI 보정판':original?'원본':'웹판',
   detail:ai?'AI 보정 판본':original?'발행사 원본으로 확인된 파일':'발행사 원본으로 확인되지 않은 출처 웹판'};
 }
 const api={describe};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.YuiLabels=api;
})(globalThis);
