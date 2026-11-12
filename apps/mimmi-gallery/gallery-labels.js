(function(root){
 'use strict';
 // Use recorded work/publisher attribution, not repost-host branding.
 function describe(a){
  const title=String(a.title||''),id=String(a.id||'');
  const explicit=typeof a.publisher==='string'?a.publisher.trim():'';
  let publisher=explicit;
  if(!publisher){
   if(/\bDJAWA\b/i.test(title)||/^djawa-/.test(id)||/^pixibb-auto-djawa-photo-/.test(id))
    publisher='DJAWA';
   else if(/cream[\s-]*soda/i.test(title)||/^creamsoda-/.test(id))
    publisher='CreamSoda';
   else if(/art[\s-]*gravia/i.test(title)||/^artgravia-/.test(id))
    publisher='ArtGravia';
   else if(/^mimmi-indie-/.test(id)||/^(?:독립\s*화보|개인\s*촬영)/.test(title))
    publisher='독립 화보';
  }
  const processing=(title+' '+String(a.quality||'')).replace(/[_-]/g,' ');
  const ai=a.ai_enhanced===true||/\bAI\s*(?:enhanc\w*|보정)/i.test(processing);
  const original=a.publisher_original_verified===true&&!ai;
  return {publisher:publisher||'미확인',
   kind:ai?'ai':original?'original':'web',
   edition:ai?'AI 보정판':original?'원본':'웹판',
   detail:ai?'AI 보정 판본':original?'발행사 원본으로 확인된 파일':'발행사 원본으로 확인되지 않은 출처 웹판'};
 }
 function coverTitle(a){
  const original=String(a.title||'');
  const publisher=describe(a).publisher;
  const aliases={
   DJAWA:['DJAWA Photo','DJAWA'],
   CreamSoda:['CreamSoda','CREAMSODA','Cream Soda'],
   ArtGravia:['ArtGravia','ARTGRAVIA'],
   '독립 화보':['독립 화보']
  };
  let title=original;
  for(const token of aliases[publisher]||[]){
   // All publisher tokens here are fixed alphanumerics/spaces; no regex metacharacters.
   title=title.replace(new RegExp('\\[\\s*'+token+'\\s*\\]','gi'),' ');
   title=title.replace(new RegExp('(^|[\\s·—–|:])'+token+'(?=$|[\\s·—–|:]|Vol\\.?|\\d)','gi'),'$1');
  }
  if(describe(a).kind==='ai')
   title=title.replace(/\[\s*AI\s+Enhanced\s*\]|\(\s*AI\s*보정(?:본|판)?\s*\)/gi,' ');
  title=title.replace(/\(\s*\d+\s*photos?(?:\s*\+\s*\d+\s*videos?)?\s*\)/gi,' ')
             .replace(/\s+Sexy Girl\s*$/i,' ')
             .replace(/\[\s*\]/g,'')
             .replace(/\s+/g,' ')
             .replace(/^[\s·—–|:\-]+|[\s·—–|:\-]+$/g,'').trim();
  return title||original;
 }
 const api={describe,coverTitle};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 root.MimmiLabels=api;
})(globalThis);
