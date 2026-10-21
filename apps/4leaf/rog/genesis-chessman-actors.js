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
 const originalFor=id=>window.ORIGINAL_LEAF_OBS_FRAMES?.[id]||null;
 const poses=['idle','walk','attack','hurt','victory'];
 function sequenceFor(native,action){
   // Frame indexes are SOURCE-VERIFIED but the native 2002 action table
   // and FPS have NOT been recovered. Walk samples use the entire contiguous
   // native 0..7 run, rather than looping 4 frames while discarding real
   // source frames 4..7. Action labels and pacing remain WEB provisional.
   const map={idle:[0,1,2,3],walk:[0,1,2,3,4,5,6,7],
     attack:[10,18],hurt:[18,10],victory:[25,30,0]};
   const all=native.frames||[];
   // The exact 0..7 sequence is available for only 80 original OBS
   // characters. Repeating a clipped 0..2/0..6 subset on the other 12
   // wrongly depicts a complete walking cycle. Keep their real first
   // source frame STATIC until missing packets/action metadata are found.
   const fullSourceWalk=Array.from({length:8},(_,i)=>i)
    .every(index=>all.some(frame=>frame.index===index));
   if(action==='walk'&&!fullSourceWalk)
     return [all.find(frame=>frame.index===0)||all[0]].filter(Boolean);
   // Some genuinely decoded OBS sources have no safe frame-0 decode.
   // Expose their real pixels, but NEVER animate unrelated frames as if
   // their original idle/walk/attack semantic mapping were established.
   if(native.hasVerifiedFrameZero===false)return all.slice(0,1);
   const picks=(map[action]||[0]).map(index=>all.find(f=>f.index===index)).filter(Boolean);
   // Frame data is source-authentic; these labels are provisional until
   // the original action/direction lookup table is recovered.
   return picks.length?picks:all.slice(0,1);
 }
 function renderNativeFrame(pawn,frame){
   const img=pawn.querySelector('img.leaf-chess-original-obs');
   if(!img||!frame)return;
   if(img.getAttribute('src')!==frame.url)img.src=frame.url;
   img.style.setProperty('--leaf-obs-width',frame.width+'px');
   img.style.setProperty('--leaf-obs-height',frame.height+'px');
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
   const standing=native?.frames?.find(f=>f.index===0)||native?.frames?.[0]||frame;
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
   pawn.dataset.actorRig='original-obs-sprite';
   pawn.dataset.actorSource='OBS/'+native.originalMember;
   pawn.dataset.actorOriginalModelRecovered='true';
   pawn.dataset.sourceAnimation='genuine-OBS-pixels';
   pawn.dataset.sourceWalkCoverage=Array.from({length:8},(_,i)=>i)
    .every(index=>native.frames.some(frame=>frame.index===index))
     ?'8-of-8-original-source-indices/WEB-action-unverified'
     :'partial-original-source/static-walk-until-source-complete';
   pawn.dataset.sourcePoseMapping=native.frames.length===1||native.singleFrameStillOnly===true
     ?'unverified-single-source-frame/static-no-animation'
     :native.hasVerifiedFrameZero===false
      ?'unverified-frame-zero-missing/static-source-pose':'unverified';
   img.hidden=false;
   const seq=sequenceFor(native,action);
   // Expose EXACT SOURCE packet indexes independently from inferred labels;
   // QA can inspect what was really rendered during genuine gameplay.
   pawn.dataset.sourceFrameSequence=seq.map(frame=>frame.index).join(',');
   pawn.dataset.sourceFrameSequenceProvenance='original-OBS-indexes/WEB-action-timing-unverified';
   renderNativeFrame(pawn,seq[0]);
   const sourceSheet=pawn.querySelector('.leaf-chess-source-frame');
   if(sourceSheet)sourceSheet.hidden=true;
   if(seq.length>1&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){
     let i=0;
     const timer=setInterval(()=>{
       if(!pawn.isConnected||pawn.dataset.chessmanId!==id||pawn.dataset.actorPose!==action){
         clearInterval(timer);sourceTimers.delete(pawn);return;
       }
       i=(i+1)%seq.length;renderNativeFrame(pawn,seq[i]);
     },action==='idle'?340:action==='walk'?120:175);
     sourceTimers.set(pawn,timer);
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
   node.dataset.sourcePoseMapping='original-OBS-missing/CardData-original-portrait-only';
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
   originalFullBodyFramesRecovered:[...new Set([...Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}),...frames.keys()])],
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
