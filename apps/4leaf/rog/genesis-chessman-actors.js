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
   const map={idle:[0,1,2],walk:[0,1,2,3],attack:[10,18],hurt:[18,10],victory:[25,30,0]};
   const all=native.frames||[];
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
   img.style.setProperty('--leaf-obs-left','calc(50% + '+frame.originX+'px)');
   img.style.setProperty('--leaf-obs-bottom','calc(var(--leaf-obs-ground,11.52px) - '+(frame.originY+frame.height)+'px)');
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
     img.addEventListener('error',()=>{
       if(!pawn.isConnected)return;
       pawn.dataset.obsUnavailable='true';
       pawn.dataset.actorOriginalModelRecovered='false';
       renderFrame(pawn,pawn.dataset.chessmanId,pawn.dataset.actorPose||'idle');
     });
     pawn.append(img);
   }
   pawn.dataset.actorRig='original-obs-sprite';
   pawn.dataset.actorSource='OBS/'+native.originalMember;
   pawn.dataset.actorOriginalModelRecovered='true';
   pawn.dataset.sourceAnimation='genuine-OBS-pixels';
   pawn.dataset.sourcePoseMapping='provisional';
   img.hidden=false;
   const seq=sequenceFor(native,action);
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
   sheet.hidden=true;node.dataset.actorRig='inferred-8head';
   node.dataset.sourceAnimation='unavailable';
  }
 }
 function pose(pawn,requested='idle',duration=0){
  if(!pawn)return;
  const action=VALID.includes(requested)?requested:'idle';
  clearTimeout(timeouts.get(pawn));
  pawn.dataset.actorPose=action;
  const counts=states.get(pawn)||{};
  states.set(pawn,{...counts,[action]:(counts[action]||0)+1});
  renderFrame(pawn,pawn.dataset.chessmanId,action);
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
  const pawn=[...document.querySelectorAll('#board-pawns .board-pawn')]
   .find(el=>el.dataset.id===String(id));
  if(pawn)pose(pawn,action,duration);
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
 window.__LEAF_GENESIS_ACTORS__={
  mount,pose,poseByPlayer,registerFrames,
  getState:()=>({
   originalFullBodyFramesRecovered:[...new Set([...Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}),...frames.keys()])],
   rendered:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
    playerId:p.dataset.id,chessmanId:p.dataset.chessmanId,
    pose:p.dataset.actorPose,rig:p.dataset.actorRig,
    originalRecovered:p.dataset.actorOriginalModelRecovered,
    source:p.dataset.actorSource,frame:p.dataset.actorFrame,
    poseMapping:p.dataset.sourcePoseMapping,
    counts:states.get(p)||{}
   }))
  })
 };
})();
