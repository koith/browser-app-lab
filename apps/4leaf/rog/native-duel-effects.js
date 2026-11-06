'use strict';
/* R15: the 2002 OBS source effect members, emitted by original CHR event records.
 *
 * The original 2002 installer (SHA1 86526d...) yielded 28 exact OBS member
 * byte streams and 420 SHA-verified native RGBA frames. Native CHR animation
 * events [tick, type, member, dx, dy] are real data, not fabricated effects.
 *
 * VERIFIED: member/frame pixels & own palette, originX/Y, native 18-byte
 * actor animation event (tick, type, member, offsets), CHR->body identity.
 * INFERRED: event type means visual effect, frame playback timing (40ms),
 * event offsets as scaled 2D foot-relative positions on the WEB scene.
 * UNVERIFIED: original 3D/MVE camera depth, signed coordinate transforms,
 * 2002 tick->milliseconds, intra-effect OBS animation table/loop.
 *
 * Deliberately no CSS substitutes. If original PNGs cannot decode, simply
 * omit the effect and retain the game's original dice/result calculation.
 */
(function(){
 const TICK_MS=40; // WEB tick for native source body lunge, not EXE timing
 const MAX_EVENTS=4,MAX_FRAMES=160;
 // Visually reviewed genuine effect sprites. Other CHR event member values
 // may be audio, scene triggers or unclassified actors; merely decoding an
 // OBS member is insufficient to call it a live combat visual effect.
 const REVIEWED_VISUAL_MEMBERS=new Set([
  '1096','1097','1098','1099','1101','1102','1112','1114','1118'
 ]);
 const cache=new Map();
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const afterPaint=()=>new Promise(done=>{
  if(typeof requestAnimationFrame!=='function'){done();return}
  requestAnimationFrame(()=>requestAnimationFrame(done));
 });
 const original=()=>window.ORIGINAL_LEAF_DUEL_EFFECTS||{};
 const cardOf=actor=>String(actor?.dataset?.chessmanId||'').replace(/^c_/,'');
 const isRealSource=source=>!!source &&
  source.status==='SOURCE-PIXELS-VERIFIED/ROLE-UNVERIFIED' &&
  /^[0-9a-f]{64}$/.test(source.sourceSHA256||'') &&
  Array.isArray(source.frames)&&source.frames.length>0&&
  source.frames.length<=MAX_FRAMES&&source.frames.every((f,i)=>
   f.index===i&&/^[0-9a-f]{64}$/.test(f.sha256||'')&&
   /^\.\/original\/OBS\/duel-effects\/(obs|obs2|obs3)-\d{4}-\d{3}\.png$/.test(f.url)&&
   Number.isInteger(f.width)&&f.width>0&&Number.isInteger(f.height)&&f.height>0 &&
   Number.isFinite(f.originX)&&Number.isFinite(f.originY));
 function eventsFor(card,slot=12){
  const matches=[];
  for(const [member,source] of Object.entries(original())){
   if(!isRealSource(source))continue;
   const numeric=/\/(\d{4})\.obs$/.exec(member)?.[1];
   if(!numeric||source.originalMember!==member||!REVIEWED_VISUAL_MEMBERS.has(numeric))continue;
   for(const entry of source.nativeEvents||[]){
    const [who,sourceSlot,tick,type,dx,dy]=entry;
    if(who!==card||sourceSlot!==slot||!Number.isInteger(tick)||tick<0||
      !Number.isFinite(dx)||!Number.isFinite(dy))continue;
    matches.push({member,numeric,source,tick,type,dx,dy});
   }
  }
  return matches.sort((a,b)=>a.tick-b.tick||a.numeric.localeCompare(b.numeric)).slice(0,MAX_EVENTS);
 }
 function preloadSource(source){
  return Promise.allSettled(source.frames.map(f=>{
   if(cache.has(f.url))return cache.get(f.url);
   const img=new Image();
   const done=new Promise(resolve=>{
    img.addEventListener('load',()=>resolve(img.naturalWidth>0),{once:true});
    img.addEventListener('error',()=>resolve(false),{once:true});
   });
   img.src=f.url;
   const awaited=typeof img.decode==='function'?img.decode().then(()=>true,()=>false):done;
   cache.set(f.url,awaited);
   return awaited;
  }));
 }
 function warm(card){
  const sources=[...new Set(eventsFor(String(card)).map(e=>e.source))];
  return Promise.allSettled(sources.map(preloadSource));
 }
 function scaleFor(stage){
  const css=parseFloat(stage.style.getPropertyValue('--leaf-native-podium-scale'));
  return Number.isFinite(css)&&css>0?Math.max(.28,Math.min(1.8,css)):1;
 }
 function coordinates(stage,actor,event,frame,scale){
  const base=actor.getBoundingClientRect(),canvas=stage.getBoundingClientRect();
  const mirror=actor.dataset.sourceMirror==='true';
  const sign=mirror?-1:1;
  // Native source effect positions are signed offsets around the source
  // actor origin. WEB 2D approximation only: this is NOT a restored MVE
  // world-space transform or historically proven effect-camera position.
  const x=base.left+base.width/2-canvas.left+event.dx*scale*sign;
  const y=base.bottom-canvas.top+event.dy*scale;
  return {x:x+frame.originX*scale,y:y-(frame.height-1+frame.originY)*scale,mirror};
 }
 async function render(stage,actor,event){
  if(!stage.isConnected||!actor.isConnected)return;
  const container=document.createElement('span');
  container.className='leaf-native-duel-effect';
  container.dataset.nativeMember=event.member;
  container.dataset.nativeEventType=String(event.type);
  container.dataset.nativeEventTick=String(event.tick);
  container.dataset.provenance='original-OBS-source-pixels-and-CHR-event-VERIFIED/WEB-placement-and-tick-ms-INFERRED';
  container.setAttribute('aria-hidden','true');
  const img=document.createElement('img');
  img.className='leaf-native-duel-effect-frame';
  img.alt='';img.draggable=false;img.decoding='async';
  container.append(img);stage.append(container);
  const scale=scaleFor(stage);
  const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  let framesPlayed=0;
  try{
   const frames=reduced?event.source.frames.slice(0,1):event.source.frames;
   for(const f of frames){
    if(!container.isConnected||!actor.isConnected)break;
    const valid=await cache.get(f.url);
    if(!valid){container.dataset.load='unavailable';break}
    const box=coordinates(stage,actor,event,f,scale);
    img.src=f.url;
    img.style.width=f.width*scale+'px';img.style.height=f.height*scale+'px';
    img.style.left=box.x+'px';img.style.top=box.y+'px';
    img.style.transform=box.mirror?'scaleX(-1)':'none';
    container.dataset.sourceFrame=String(f.index);
    container.dataset.load='decoded-original';
    framesPlayed++;
    stage.dataset.duelSourceEffectFrames=String((Number(stage.dataset.duelSourceEffectFrames)||0)+1);
    const start=performance.now();
    await afterPaint();
    const duration=reduced?100:TICK_MS;
    const remainder=duration-(performance.now()-start);
    if(remainder>0)await sleep(remainder);
   }
  }finally{
   container.dataset.playedFrames=String(framesPlayed);
   container.remove();
  }
 }
 function play(stage,actor,slot=12){
  if(!stage||!actor||!stage.isConnected)return {events:0,done:Promise.resolve([])};
  const card=cardOf(actor),list=eventsFor(card,slot);
  stage.dataset.duelSourceEffects=String(list.length);
  stage.dataset.duelSourceEffectEvidence=list.length?'original-event-and-pixels-VERIFIED/WEB-timing-and-placement-INFERRED':'no-original-effect-source-for-card';
  if(!list.length)return {events:0,done:Promise.resolve([])};
  // Prefetch verified source pixels before their original event ticks.
  // Safe even if the battle starts without a prior warm() call.
  for(const ev of list)preloadSource(ev.source);
  const started=performance.now();
  const done=Promise.all(list.map(async ev=>{
   const delay=Math.max(0,ev.tick*TICK_MS-(performance.now()-started));
   if(delay>0)await sleep(delay);
   if(!stage.isConnected||!actor.isConnected)return;
   return render(stage,actor,ev);
  }));
  return {events:list.length,done};
 }
 // Explicit native actor pose event, not a fragile mutation observer or
 // monkey-patched game method. Only the real slot-12 duel attacker triggers
 // this; ordinary board movement, defense, hurt and score code are untouched.
 if(typeof document.addEventListener==='function')
  document.addEventListener('leaf-native-duel-attack',event=>{
   const actor=event.target,stage=actor?.closest?.('#battle-visual');
   if(!stage||actor.dataset.duelSide!=='attacker'||
      event.detail?.slot!=='12'||stage.dataset.duelNativeFxStarted)return;
   stage.dataset.duelNativeFxStarted='true';
   play(stage,actor,12);
  });
 window.__LEAF_NATIVE_DUEL_FX__=Object.freeze({
  eventsFor,warm,play,tickMs:TICK_MS,
  source:'original 2002 OBS/CHR per-event member/frame/offset VERIFIED, meanings and WEB timing INFERRED'
 });
})();
