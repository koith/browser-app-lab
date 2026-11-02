'use strict';
/* 4LEAF native OBS actor bridge. 1040.obs keyframe index groups were recovered
 * from source 18-byte records. Their semantic action names and tick-to-ms
 * conversion remain UNVERIFIED; other members are not automatically mapped. */
(function(){
 const HASH='ac954b320e56b8c34ffbf1249a9905a4a53e9ac1e91c291cc398216cd8db0734';
 const ACTIONS={
  idle:{rear:[0,1,2],side:[11,12,13],front:[22,23,24]},
  walk:{rear:[3,5,6,7,8],side:[14,15,16,17,18,19],front:[25,26,27,28,29,30]},
  duel:[33,34,35,36]
 };
 let decoded=null;
 function inspectDecodedMap(raw){
  if(!raw||typeof raw!=='object'||Array.isArray(raw)||
    !raw.cards||typeof raw.cards!=='object'||Array.isArray(raw.cards))
   throw Error('Original action map must contain cards');
  let cardCount=0,actions=0,keys=0,events=0;
  for(const [cardId,card] of Object.entries(raw.cards)){
   if(!/^(?:c_)?\d{4}$/.test(cardId)||!card||typeof card!=='object'||
      !card.animations||typeof card.animations!=='object')
    throw Error('Invalid decoded card '+cardId);
   const list=Object.values(card.animations);
   if(!list.length||list.length>128)throw Error('Invalid animation count '+cardId);
   for(const a of list){
    if(!Number.isInteger(a?.ticks)||a.ticks<1||a.ticks>200000||
       !Array.isArray(a.keys)||!a.keys.length||a.keys.length>2048)
     throw Error('Invalid original OBS animation '+cardId);
    let previous=-1;
    for(const [index,key] of a.keys.entries()){
     if(!Array.isArray(key)||key.length!==2||!Number.isInteger(key[0])||
        !Number.isInteger(key[1])||key[0]<previous||key[0]<0||
        key[0]>a.ticks||key[1]<0||key[1]>65535)
      throw Error('Invalid native time/frame '+cardId+':'+index);
     previous=key[0];keys++;
    }
    if(a.events!==undefined){
     if(!Array.isArray(a.events)||a.events.length>2048)throw Error('Invalid OBS effects');
     for(const event of a.events){
      if(!Array.isArray(event)||event.length!==5||!event.every(Number.isInteger)||
         event[0]<0||event[0]>a.ticks||event[1]<0||event[2]<0||
         Math.abs(event[3])>65535||Math.abs(event[4])>65535)
       throw Error('Invalid OBS effect record');
      events++;
     }
    }
    actions++;
   }
   cardCount++;
  }
  if(!cardCount||cardCount>500)throw Error('Invalid OBS source card count');
  return Object.freeze({cardCount,actions,keys,events,
   evidence:'STRUCTURAL_ONLY/no-automatic-card-or-effect-mapping'});
 }
 function registerDecodedMap(raw){decoded=inspectDecodedMap(raw);return decoded;}
 function verified1040(native){
  return native?.sourceSHA256===HASH&&
   (native.originalMember==='1040.obs'||native.originalMember==='OBS.pak/1040.obs')&&
   native.frames?.length===37&&native.frames.every((f,i)=>
     f.index===i&&f.url==='./original/OBS/action-full/1040-'+
      String(i).padStart(2,'0')+'.png'&&/^[a-f0-9]{64}$/.test(f.sha256)&&
     [f.originX,f.originY,f.width,f.height].every(Number.isFinite));
 }
 function sequenceFor(native,action,cardId,travel,context={}){
  if(cardId!=='0040'||!verified1040(native))return null;
  const rest=context.duel?'side':context.rest==='away'?'rear':
   ['left','right'].includes(context.rest)?'side':'front';
  const facing=travel==='away'?'rear':
   ['left','right'].includes(travel)?'side':'front';
  let selected,mirror=false,label;
  if(action==='idle'){
   selected=ACTIONS.idle[rest];label='idle-'+rest;
   mirror=rest==='side'&&(context.duel?context.side==='attacker':context.rest==='right');
  }else if(action==='walk'){
   selected=ACTIONS.walk[facing];label='walk-'+facing;
   mirror=facing==='side'&&travel==='right';
  }else if(action==='attack'&&context.duel){
   selected=ACTIONS.duel;label='duel';
   mirror=context.side==='attacker';
  }else return null;
  const frames=selected.map(i=>native.frames[i]);
  frames.mirror=mirror;
  frames.loop=action!=='attack';
  frames.table='native-1040-'+label;
  frames.nativeKeyTicks=selected.map((_,i)=>i*3);
  frames.nativeEvidence='original-OBS-1040/keyframe-index-VERIFIED/action-name-INFERRED';
  frames.nativeMilliseconds='UNVERIFIED/WEB-3-tick-120ms-presentation';
  frames.nativeEffectPlayback='DISABLED/effect-identities-not-mapped';
  return frames;
 }
 window.__LEAF_NATIVE_OBS_ACTIONS__=Object.freeze({
  sequenceFor,inspectDecodedMap,registerDecodedMap,
  getState:()=>({source1040:'index-groups-and-3-tick-gap-VERIFIED',
   originalTickMilliseconds:'UNVERIFIED',decodedMap:decoded,
   otherCardAutoAssignment:false,effectPlayback:false})
 });
})();
