'use strict';
/* Per-CHESSMAN source identity and turn-linked animation controller.
 * For recovered 2002 OBS members, use actual full-body indexed PNG pixels.
 * Remaining characters keep a labeled CSS proxy while extraction continues. A ChatTown Registry/sava
 * standee must NEVER impersonate the original Dice chessman.
 * This articulated eight-head WEB PROXY is inferred, not original art.
 * registerFrames connects actual recovered animation sources once obtained.
 */
(function(){
 'use strict';
 const VALID=['idle','walk','attack','hurt','victory'];
 const frames=new Map(),timeouts=new WeakMap(),states=new WeakMap();
 const sourceTimers=new WeakMap();
 // A source OBS PAK member is NOT necessarily a playable full-body actor.
 // Pixel audit against the SHA-verified 2002 source, 2026-10-24:
 // 1096/1097/1098/1100 are spell glows; 1125/1128 visual particles;
 // 1133/1134 HUD symbols/logo, 1136-1139 overlay FX;
 // 1141/1142/1145/1146/1147 atmospheric objects/weapon box/bomb;
 // 1159-1167 are particles/weapons/roll numeral; 1170 tiny icon.
 // Older code displayed these original *effect* frames as "chessmen",
 // producing unreadable objects even if it picked a face-forward packet.
 // Preserve all original OBS bytes; route ONLY visually audited effects
 // to the honest native CardData fallback until a real actor is recovered.
 const NON_ACTOR_OBS=Object.freeze({
  '0096':'spell-orb','0097':'spell-ray','0098':'light-effect',
  '0100':'lightning',
  '0125':'particle','0128':'particle',
  '0133':'ability-icon','0134':'DiceAttack-logo',
  '0136':'ring-effect','0137':'hex-overlay','0138':'impact-star',
  '0139':'ground-ring','0141':'smoke','0142':'leaf-symbol',
  '0145':'aura','0146':'bomb-visual','0147':'prop-box',
  '0159':'impact-star','0160':'sword-effect','0161':'fire-ring',
  '0163':'magic-burst','0164':'magic-orb','0165':'glow',
  '0167':'die-result-numeral','0170':'HUD-icon',
  '0099':'spell-ring',
  '0127':'dark-ring',
  '0130':'aura-ring',
  '0131':'cloth-effect',
  '0135':'particle-spray',
  '0140':'projectile-flash',
  '0143':'smoke-fragments',
  '0144':'spark-fragments',
  '0156':'particle-spray',
  '0158':'pointer-hand',
  '0162':'magic-globe',
  '0169':'pumpkin-prop',
  '0171':'HUD-card-icon'
 });
 const originalFor=id=>Object.hasOwn(NON_ACTOR_OBS,id)?null:
  window.ORIGINAL_LEAF_OBS_FRAMES?.[id]||null;
 const poses=['idle','walk','attack','hurt','victory'];
 // VISUALLY COMPARED against recovered original pixels, 2026-10-24.
 // Sample frame 0 is NOT a front-facing pose: original 1040/1042/1043/
 // 1044/1046/1048/1061/1064 silhouettes show their backs/side at 0.
 // Native PNGs were FLIP_TOP_BOTTOM on extraction and get scaleY(-1) in
 // dice-original-obs.css; this is genuine source pixel direction, NOT a
 // horizontally mirrored or web-generated character.
 const AUDITED_FRONT_SOURCE=Object.freeze({
  '0040':25,'0042':25,'0043':25,'0044':25,
  '0045':18,'0046':25,'0048':25,'0049':25,
  '0051':25,'0052':25,'0053':25,'0054':25,'0055':25,
  '0056':25,'0058':25,'0059':25,'0060':25,'0061':25,
  '0062':25,'0064':25
 });
 function frontFacingSource(native,id){
  const available=native?.frames||[];
  const approved=AUDITED_FRONT_SOURCE[id];
  const verified=available.find(f=>f.index===approved);
  if(verified)return {frame:verified,
    evidence:'visual-original-OBS-reviewed/front/'+id+'-'+approved};
  // In 60/90 bulk source models the same 25th native VIDEO packet offers
  // a likely camera-facing silhouette. It has NOT been manually verified
  // for every chessman. Use its genuine pixels in idle and keep the
  // uncertainty visible in the DOM/ledger rather than asserting 2002 FPS.
  const candidate=available.find(f=>f.index===25);
  if(candidate)return {frame:candidate,
    evidence:'source-family-frame25/front-candidate/PER-ID-UNVERIFIED'};
  return {frame:available.find(f=>f.index===0)||available[0]||null,
    evidence:'source-front-unavailable/NO-VERIFIED-DIRECTION'};
 }
 // Verified source pixels: 1040/1042/1043 frames 25 and 30 were
 // individually inspected in their native 640-stride PNGs: both are
 // camera-facing full-body silhouettes (not 0..7 rear/side turns).
 // This is a front-preserving WEB movement mapping; original direction
 // lookup and playback FPS remain unknown.
 const REVIEWED_FRONT_MOTION=Object.freeze({
  '0040':[25,30],'0042':[25,30],'0043':[25,30]
 });
 function sequenceFor(native,action,id){
  const all=native.frames||[];
  const at=index=>all.find(f=>f.index===index)||null;
  const facing=frontFacingSource(native,id);
  const front=facing.frame;
  const approved=Object.hasOwn(AUDITED_FRONT_SOURCE,id)&&
   facing.evidence.startsWith('visual-original-OBS-reviewed/');
  const movement=REVIEWED_FRONT_MOTION[id]?.map(at).filter(Boolean)||[];
  if(action==='idle')return front?[front]:[];
  if(approved){
   // Do not display verified BACK/SIDE 0..7 during an ordinary forward
   // movement, attack recovery or victory. One static authentic FRONT is
   // more truthful than a rapidly pirouetting chessman.
   if(action==='walk')return movement.length===2
    ?[movement[0],movement[1],movement[0],movement[1]]
    :front?[front]:[];
   if(action==='victory')return movement.length===2
    ?[movement[0],movement[1],movement[0]]
    :front?[front]:[];
   if(action==='attack'&&['0040','0042','0043'].includes(id)&&at(18))
    return [front,at(18),front];
   // Original directional action-table does not confirm any other attack,
   // hit or defeat packet; preserve verified standing identity.
   return front?[front]:[];
  }
  // Other genuine frames are source-verified but directional attribution
  // remains unverified. A missing 0..7 packet is NOT a full walk animation.
  const fullWalk=Array.from({length:8},(_,i)=>at(i)).every(Boolean);
  if(native.hasVerifiedFrameZero===false)return all.slice(0,1);
  if(action==='walk'&&!fullWalk)return front?[front]:all.slice(0,1);
  const map={walk:[0,1,2,3,4,5,6,7],
   attack:[10,18],hurt:[18,10],victory:[25,30,0]};
  const picks=(map[action]||[0]).map(at).filter(Boolean);
  return picks.length?picks:(front?[front]:all.slice(0,1));
 }
 function renderNativeFrame(pawn,frame){
   const img=pawn.querySelector('img.leaf-chess-original-obs');
   if(!img||!frame)return;
   if(img.getAttribute('src')!==frame.url)img.src=frame.url;
   img.style.setProperty('--leaf-obs-width',frame.width+'px');
   img.style.setProperty('--leaf-obs-height',frame.height+'px');
   // The former WEB contact ellipse was always 36px, even for original
   // 12px-to-239px wide chessmen. Derive its conservative visible footprint
   // from EACH actual source frame's verified width, without fabricating
   // pixels/meshes. This is an INFERRED shadow, NOT archived EXE lighting.
   const contactWidth=Math.max(18,Math.min(84,Math.round(frame.width*.72)));
   pawn.style.setProperty('--leaf-native-contact-width',contactWidth+'px');
   pawn.dataset.sourceContactFootprint='inferred-shadow-width/from-original-OBS-frame';
   pawn.dataset.sourceContactWidth=String(contactWidth);
   // Native OBS signed image origins are often negative. Build a valid
   // single-operator CSS calc rather than 'calc(50% + -17px)' which browsers
   // can discard, silently placing authentic models on the wrong platform.
   const horizontal=Number(frame.originX)||0;
   img.style.setProperty('--leaf-obs-left',
    'calc(50% '+(horizontal<0?'-':'+')+' '+Math.abs(horizontal)+'px)');
   // The native OBS y origin is relative to that actor's own animation
   // canvas, not a globally shared foot plane. Directly subtracting the
   // source bottom offsets caused two characters standing on the SAME
   // recovered TIS cell to have visibly different shoe heights (8/23px).
   // Normalize only the per-character reference pivot to the shared
   // DMP tile top. Preserve every source frame's relative origin motion.
   // Absolute foot pivot is inferred; original frame metadata remains intact.
   const native=originalFor(pawn.dataset.chessmanId);
   const standing=frontFacingSource(native,pawn.dataset.chessmanId).frame||frame;
   const sourceFoot=(frame.originY+frame.height);
   const standingFoot=(standing.originY+standing.height);
   const relativeSourceOffset=sourceFoot-standingFoot;
   img.style.setProperty('--leaf-obs-bottom',
    'calc(var(--leaf-obs-ground,14.88px) '+
      (relativeSourceOffset<0?'+':'-')+' '+Math.abs(relativeSourceOffset)+'px)');
   pawn.dataset.sourceFrameNativeOrigin=frame.originX+','+frame.originY;
   pawn.dataset.sourceFrameNativeSize=frame.width+'x'+frame.height;
   pawn.dataset.sourceFootOffset=String(relativeSourceOffset);
   pawn.dataset.sourceGrounding='inferred-shared-foot-plane/native-relative-frames';
   pawn.dataset.actorFrame=String(frame.index);
 }
 function useOriginalFrame(pawn,id,action){
   const previous=sourceTimers.get(pawn);
   if(previous)clearInterval(previous);
   sourceTimers.delete(pawn);
   const native=originalFor(id);
   if(!native?.frames?.length||pawn.dataset.obsUnavailable==='true'){
     const previousImage=pawn.querySelector('img.leaf-chess-original-obs');
     if(previousImage)previousImage.hidden=true;
     return false;
   }
   let img=pawn.querySelector('img.leaf-chess-original-obs');
   if(!img){
     img=document.createElement('img');img.className='leaf-chess-original-obs';
     img.alt='';img.draggable=false;img.setAttribute('aria-hidden','true');
     // A sleeping/offline source host can reject a real OBS PNG once.
     // Do NOT permanently replace a recovered Genesis full-body with a card
     // simply because its first network request failed. Retry ONLY the same
     // original source URL; never synthesize a body or an action frame.
     img.addEventListener('load',()=>{
       img.dataset.obsRetryCount='0';
       delete img.dataset.obsRetryFor;
       img.hidden=false;
       pawn.dataset.actorSourceLoad='ready';
     });
     img.addEventListener('error',()=>{
       if(!pawn.isConnected)return;
       const source=String(img.getAttribute('src')||'').split('?')[0];
       if(!source.startsWith('./original/OBS/')||!source.endsWith('.png')){
         pawn.dataset.obsUnavailable='true';
         pawn.dataset.actorOriginalModelRecovered='false';
         pawn.dataset.actorSourceLoad='unavailable';
         renderFrame(pawn,pawn.dataset.chessmanId,pawn.dataset.actorPose||'idle');
         return;
       }
       const attempt=img.dataset.obsRetryFor===source?
         Number(img.dataset.obsRetryCount||0)+1:1;
       img.dataset.obsRetryFor=source;
       img.dataset.obsRetryCount=String(attempt);
       if(attempt<=3){
         const member=pawn.dataset.chessmanId;
         pawn.dataset.actorSourceLoad='retrying-original-OBS';
         img.hidden=true;
         setTimeout(()=>{
           if(!pawn.isConnected||!img.isConnected||
             pawn.dataset.chessmanId!==member||pawn.dataset.obsUnavailable==='true')return;
           if(String(img.getAttribute('src')||'').split('?')[0]!==source)return;
           img.src=source+'?native_obs_retry='+attempt+'&at='+Date.now();
         },Math.min(750,120*2**(attempt-1)));
         return;
       }
       pawn.dataset.obsUnavailable='true';
       pawn.dataset.actorOriginalModelRecovered='false';
       pawn.dataset.actorSourceLoad='unavailable';
       renderFrame(pawn,pawn.dataset.chessmanId,pawn.dataset.actorPose||'idle');
     });
     pawn.append(img);
   }
   const fallback=pawn.querySelector('.leaf-chess-original-card-fallback');
   if(fallback)fallback.hidden=true;
   delete pawn.dataset.originalObsMemberRole;
   pawn.dataset.actorRig='original-obs-sprite';
   pawn.dataset.actorSource='OBS/'+native.originalMember;
   pawn.dataset.actorOriginalModelRecovered='true';
   pawn.dataset.sourceAnimation='genuine-OBS-pixels';
   const auditedMovement=REVIEWED_FRONT_MOTION[id]||null;
   pawn.dataset.sourceFrontWalkVerified=String(Boolean(auditedMovement&&
    auditedMovement.every(index=>native.frames.some(f=>f.index===index))));
   pawn.dataset.sourceWalkCoverage=pawn.dataset.sourceFrontWalkVerified==='true'
    ?'front-pair-25-30/source-verified/WEB-action-unverified'
    :Object.hasOwn(AUDITED_FRONT_SOURCE,id)
     ?'front-only/source-verified/WEB-action-unverified'
     :Array.from({length:8},(_,i)=>i)
      .every(index=>native.frames.some(frame=>frame.index===index))
       ?'8-of-8-original-source-indices/WEB-action-unverified'
       :'partial-original-source/static-walk-until-source-complete';
   pawn.dataset.sourcePoseMapping=native.frames.length===1||native.singleFrameStillOnly===true
     ?'unverified-single-source-frame/static-no-animation'
     :native.hasVerifiedFrameZero===false
      ?'unverified-frame-zero-missing/static-source-pose':'unverified';
   img.hidden=false;
   const facing=frontFacingSource(native,id);
   pawn.dataset.sourceFacingFrame=facing.frame?String(facing.frame.index):'none';
   pawn.dataset.sourceFacingEvidence=facing.evidence;
   pawn.dataset.sourceDirection='front-source-candidate/not-EXE-direction-table';
   const seq=sequenceFor(native,action,id);
   // Expose EXACT SOURCE packet indexes independently from inferred labels;
   // QA can inspect what was really rendered during genuine gameplay.
   pawn.dataset.sourceFrameSequence=seq.map(frame=>frame.index).join(',');
   pawn.dataset.sourceActionEvidence=Object.hasOwn(AUDITED_FRONT_SOURCE,id)
    ?(pawn.dataset.sourceFrontWalkVerified==='true'
       ?'front-source-pair/visual-reviewed; WEB-movement-and-FPS-inferred'
       :'front-source-static/visual-reviewed; native-action-table-unknown')
    :'source-packets/orientation-and-2002-action-unverified';
   pawn.dataset.sourceFrameSequenceProvenance='original-OBS-indexes/WEB-action-timing-unverified';
   renderNativeFrame(pawn,seq[0]);
   const sourceSheet=pawn.querySelector('.leaf-chess-source-frame');
   if(sourceSheet)sourceSheet.hidden=true;
   // Idle and contiguous walking cycles repeat; attacks, impacts and
   // victory are ONE-SHOT events. Repeating their provisional [10,18] etc.
   // forever made a struck character oscillate between attack/hurt frames
   // while no actual new gameplay action had occurred. Original OBS bytes
   // remain untouched; action-to-source-index/FPS remains UNVERIFIED.
   const loops=action==='walk';
   pawn.dataset.sourcePlaybackMode=loops?'loop/WEB-motion-inferred'
    :'one-shot/WEB-action-unverified';
   pawn.dataset.sourcePlaybackComplete='false';
   if(seq.length>1&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){
     let i=0;
     const timer=setInterval(()=>{
       if(!pawn.isConnected||pawn.dataset.chessmanId!==id||pawn.dataset.actorPose!==action){
         clearInterval(timer);sourceTimers.delete(pawn);return;
       }
       i++;
       if(i>=seq.length){
         if(!loops){
           clearInterval(timer);sourceTimers.delete(pawn);
           pawn.dataset.sourcePlaybackComplete='true';
           return;
         }
         i=0;
       }
       renderNativeFrame(pawn,seq[i]);
     },action==='idle'?340:action==='walk'?120:175);
     sourceTimers.set(pawn,timer);
   }else if(!loops){
     pawn.dataset.sourcePlaybackComplete='true';
   }
   return true;
 }

 const sourceId=p=>String(p?.team?.[0]||'').replace(/^c_/,'');
 function add(parent,name){
  const n=document.createElement('span');n.className=name;
  n.setAttribute('aria-hidden','true');parent.append(n);return n;
 }
 function createRig(pawn){
  const a=add(pawn,'leaf-chess-actor');
  add(a,'leaf-chess-cape');add(a,'leaf-chess-torso');
  const head=add(a,'leaf-chess-head');
  const image=document.createElement('img');
  image.className='leaf-chess-portrait';image.alt='';image.draggable=false;head.append(image);
  add(a,'leaf-chess-arm leaf-chess-left');add(a,'leaf-chess-arm leaf-chess-right');
  add(a,'leaf-chess-leg leaf-chess-left');add(a,'leaf-chess-leg leaf-chess-right');
  add(a,'leaf-chess-weapon');add(a,'leaf-chess-contact');
  const sheet=add(a,'leaf-chess-source-frame');sheet.hidden=true;
  return a;
 }
 function renderFrame(node,src,action){
  if(useOriginalFrame(node,src,action))return;
  const sheet=node.querySelector('.leaf-chess-source-frame');
  if(!sheet)return;
  const f=frames.get(src)?.[action];
  if(f){
   sheet.hidden=false;
   sheet.style.backgroundImage='url("'+f.url+'")';
   sheet.style.backgroundSize=f.width*f.count+'px '+f.height+'px';
   sheet.style.width=f.width+'px';sheet.style.height=f.height+'px';
   sheet.style.setProperty('--leaf-frame-size',f.width+'px');
   sheet.style.setProperty('--leaf-frame-count',String(f.count));
   sheet.style.setProperty('--leaf-frames-duration',f.duration+'ms');
   node.dataset.actorRig='source-animation';
   node.dataset.sourceAnimation=action;
  }else{
   sheet.hidden=true;
   // No actual Dice/OBS.pak body exists for this card yet. Do NOT show
   // an enormous invented eight-head grey stickman as if it were 4LEAF.
   // The recovered CardData/chm_NN portrait is the only character-specific
   // authentic artwork available. Display that small archival portrait
   // honestly, while keeping the source identity and gameplay untouched.
   let portrait=node.querySelector('.leaf-chess-original-card-fallback');
   if(!portrait){
    portrait=document.createElement('img');
    portrait.className='leaf-chess-original-card-fallback';
    portrait.alt='';portrait.draggable=false;
    portrait.setAttribute('aria-hidden','true');
    node.append(portrait);
   }
   const source=node.querySelector('.leaf-chess-portrait')?.getAttribute('src');
   if(source&&portrait.getAttribute('src')!==source)portrait.src=source;
   portrait.hidden=false;
   node.dataset.actorRig='original-card-portrait-fallback';
   node.dataset.actorSource='CardData (OBS full-body not recovered)';
   node.dataset.actorOriginalModelRecovered='false';
   node.dataset.sourceAnimation='unavailable';
   node.dataset.sourcePoseMapping=Object.hasOwn(NON_ACTOR_OBS,src)
    ?'OBS-member-is-non-character-effect/CardData-fallback'
    :'original-OBS-missing/CardData-original-portrait-only';
   node.dataset.originalObsMemberRole=NON_ACTOR_OBS[src]||'missing-full-body';
  }
 }
 function pose(pawn,requested='idle',duration=0){
  if(!pawn)return;
  const action=VALID.includes(requested)?requested:'idle';
  // A real roll advances its pawn every ~60ms. If each step restarts the
  // 120ms native-source frame clock, gameplay can NEVER show frame 2..7
  // although manual QA plays all eight. Continue the SAME source walk
  // across successive DMP cell transitions; keep the original OBS pixels.
  const continueSourceWalk=action==='walk'&&pawn.dataset.actorPose==='walk'&&
   pawn.dataset.actorRig==='original-obs-sprite'&&
   pawn.dataset.sourceWalkCoverage?.startsWith('8-of-8-');
  clearTimeout(timeouts.get(pawn));
  if(!continueSourceWalk){
   pawn.dataset.actorPose=action;
   const counts=states.get(pawn)||{};
   states.set(pawn,{...counts,[action]:(counts[action]||0)+1});
   renderFrame(pawn,pawn.dataset.chessmanId,action);
  }
  pawn.dataset.walkSourceClock=continueSourceWalk
   ?'continuous-across-real-DMP-steps/WEB-120ms':
    action==='walk'?'new-source-sequence/WEB-120ms':'inactive';
  if(duration>0&&action!=='idle'){
   const token=setTimeout(()=>{
    if(pawn.isConnected&&pawn.dataset.actorPose===action)pose(pawn,'idle',0);
   },duration);
   timeouts.set(pawn,token);
  }
 }
 function mount(pawn,player,portrait){
  if(!pawn||!player)return null;
  const src=sourceId(player);
  let rig=pawn.querySelector('.leaf-chess-actor');
  if(!rig)rig=createRig(pawn);
  const image=rig.querySelector('img.leaf-chess-portrait');
  if(pawn.dataset.chessmanId!==src||!image.getAttribute('src')){
   pawn.dataset.chessmanId=src;
   delete pawn.dataset.obsUnavailable;
   pawn.dataset.actorSource=originalFor(src)?'OBS/'+originalFor(src).originalMember:'CardData';
   pawn.dataset.actorOriginalModelRecovered=String(!!originalFor(src));
   const num=Number(src.replace(/\D/g,''))||0;
   pawn.style.setProperty('--chess-armor-hue',String((num*19)%360)+'deg');
   image.src=portrait;
   image.onerror=()=>{image.hidden=true};
   image.onload=()=>{image.hidden=false};
   pose(pawn,'idle',0);
  }
  return rig;
 }
 function poseByPlayer(id,action,duration){
  // Both native game-board and duel podium render independently mounted OBS
  // actors. Propagate one *real player* action to both renderers, never to an
  // opponent or a keeper without an original Genesis identity.
  for(const pawn of document.querySelectorAll(
    '#board-pawns .board-pawn, #battle-visual .leaf-battle-chessman')){
    if(pawn.dataset.id===String(id))pose(pawn,action,duration);
  }
 }
 function registerFrames(chessmanId,poses){
  if(!/^\d{4}$/.test(chessmanId))throw new Error('Source chessman ID required');
  const entries={};
  for(const action of VALID){
   const p=poses?.[action];
   if(!p)continue;
   if(typeof p.url!=='string'||!/^\.\/original\//.test(p.url)||
     ![p.width,p.height,p.count,p.duration].every(Number.isFinite)||
     p.width<=0||p.height<=0||p.count<1||p.duration<=0)
    throw new Error('Invalid recovered chessman animation sheet');
   entries[action]={url:p.url,width:p.width,height:p.height,
    count:p.count,duration:p.duration};
  }
  frames.set(chessmanId,entries);
  // Late-loaded verified source sheets must replace already visible web
  // proxies immediately, on the game board AND the battle podium.
  for(const pawn of document.querySelectorAll(
    '#board-pawns .board-pawn, #battle-visual .leaf-battle-chessman')){
    if(pawn.dataset.chessmanId!==chessmanId)continue;
    renderFrame(pawn,chessmanId,pawn.dataset.actorPose||'idle');
    pawn.dataset.actorOriginalAnimationRegistered=String(Boolean(Object.keys(entries).length));
  }
 }
 // When an offline PWA regains connectivity, give the known authentic
 // source another chance. Keep source-missing 34 models on their truthful
 // CardData-only fallback; there is no original OBS URL to retry.
 const recoverAvailableOriginals=()=>{
   for(const pawn of document.querySelectorAll(
     '#board-pawns .board-pawn, #battle-visual .leaf-battle-chessman')){
     if(pawn.dataset.obsUnavailable!=='true'||!originalFor(pawn.dataset.chessmanId))continue;
     delete pawn.dataset.obsUnavailable;
     const img=pawn.querySelector('img.leaf-chess-original-obs');
     if(img){img.dataset.obsRetryCount='0';delete img.dataset.obsRetryFor;}
     pawn.dataset.actorSourceLoad='retry-after-online';
     renderFrame(pawn,pawn.dataset.chessmanId,pawn.dataset.actorPose||'idle');
   }
 };
 window.addEventListener('online',recoverAvailableOriginals);
 window.__LEAF_GENESIS_ACTORS__={
  mount,pose,poseByPlayer,registerFrames,recoverAvailableOriginals,
  getState:()=>({
   originalFullBodyFramesRecovered:[...new Set([...Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}),...frames.keys()])].filter(id=>!Object.hasOwn(NON_ACTOR_OBS,id)),
   nativeObsEffectMembers:{...NON_ACTOR_OBS},
   originalFrontVisualAudited:{...AUDITED_FRONT_SOURCE},
   rendered:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
    playerId:p.dataset.id,chessmanId:p.dataset.chessmanId,
    pose:p.dataset.actorPose,rig:p.dataset.actorRig,
    originalRecovered:p.dataset.actorOriginalModelRecovered,
    source:p.dataset.actorSource,frame:p.dataset.actorFrame,
    poseMapping:p.dataset.sourcePoseMapping,sourceLoad:p.dataset.actorSourceLoad||'unknown',
    counts:states.get(p)||{}
   }))
  })
 };
})();
