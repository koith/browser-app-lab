'use strict';
/* CardData CHR +260 -> original OBS body identity, decoded round 9.
 * This is a 98-card source-verified mapping, NOT the old "card ID = OBS ID"
 * guess. Art is promoted only when an archived source manifest matches the
 * CHR-selected member. 0156's 1222 member is missing from all source PAKs.
 * Raw decoded action names / original frame milliseconds remain unverified.
 */
(function(){
 const cards={};
 const assign=(ids,first,pak)=>{
  ids.forEach((id,i)=>{
   if(cards[id])throw Error('Duplicate CHR body id '+id);
   const member=String(first+i);
   cards[id]=Object.freeze({card:id,member,pak,originalMember:pak+'.pak/'+member+'.obs'});
  });
 };
 const seq=(a,b)=>Array.from({length:b-a+1},(_,i)=>String(a+i).padStart(4,'0'));
 assign(['0040',...seq(42,56),...seq(58,100)],1025,'OBS');
 assign(seq(125,147),1199,'OBS2');
 cards['0156']=Object.freeze({card:'0156',member:'1222',
  pak:null,originalMember:null,missing:true});
 assign(seq(157,170),1254,'OBS3');
 assign(['0171'],1276,'OBS3');
 if(Object.keys(cards).length!==98)throw Error('CHR inventory must contain 98 unique cards');
 const BY_CARD=Object.freeze(cards);
 const missingMembers=new Set([
  ...seq(1025,1039).map(String), '1041','1057','1212','1256','1222'
 ]);
 // Source member numbers (1025 etc.), not card numbers.
 const unavailable=new Set([
  ...Array.from({length:15},(_,i)=>String(1025+i)),
  '1041','1057','1212','1256','1222'
 ]);
 function assetKey(card){
  const record=BY_CARD[card];
  if(!record||record.missing)return null;
  return record.pak==='OBS'?'0'+record.member.slice(1):
   record.pak.toLowerCase()+'/'+record.member;
 }
 function resolve(card){
  const record=BY_CARD[card];
  if(!record||record.missing||unavailable.has(record.member))return null;
  const key=assetKey(card);
  let source=null;
  if(record.pak==='OBS'){
   source=window.ORIGINAL_LEAF_FULL_ACTION_FRAMES?.[key]||
    window.ORIGINAL_LEAF_EXT_ACTION_FRAMES?.[key];
  }else source=window.ORIGINAL_LEAF_OBS23_ACTORS?.[key];
  if(!source||!Array.isArray(source.frames)||!source.frames.length||
     !/^[a-f0-9]{64}$/.test(source.sourceSHA256||''))return null;
  const original=source.originalMember;
  if(record.pak==='OBS'&&original!==record.member+'.obs'&&
     original!==record.originalMember)return null;
  if(record.pak!=='OBS'&&original!==record.originalMember)return null;
  if(!source.frames.every((f,i)=>f.index===i&&
      /^[a-f0-9]{64}$/.test(f.sha256||'')&&
      typeof f.url==='string'&&
      f.url.startsWith(record.pak==='OBS'?'./original/OBS/action-full':
       './original/OBS/obs23-actors/')&&
      f.url.endsWith('.png')&&
      [f.width,f.height,f.originX,f.originY].every(Number.isFinite)))
   return null;
  return source;
 }
 function getState(){
  const records=Object.values(BY_CARD);
  const assigned=records.filter(c=>!c.missing);
  return {cards:records.length,chrBodyMembers:assigned.length,
   missingOriginalMembers:records.filter(x=>x.missing).map(x=>x.card),
   knownUnpublishedCards:assigned.filter(x=>unavailable.has(x.member)).map(x=>x.card),
   resolvedSourceCards:assigned.filter(x=>resolve(x.card)).length,
   integrity:'CHR-offset-260/round9-verified/source-manifest-member-gated',
   originalActionLabels:'INFERRED'};
 }
 window.__LEAF_CHR_BODY_MAP__=Object.freeze({
  cards:BY_CARD,lookup:card=>BY_CARD[card]||null,resolve,assetKey,getState
 });
})();
