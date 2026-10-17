'use strict';
/* The original 2002 client has native Genesis OBS animation pixels.
 * Real, individually restored source frames appear for recovered cards
 * (currently 0042 and 0045). Unrecovered characters still use the clearly
 * identified web proxy; NEVER substitute ChatTown Registry/sava avatars.
 * Source frame values are genuine; pose-to-frame attribution and horizontal
 * run registration remain PROVISIONAL pending native EXE action-table decode.
 */
(function(){
 'use strict';
 const VALID=['idle','walk','attack','hurt','victory'];
 const frames=new Map(),timeouts=new WeakMap(),states=new WeakMap();
 const sourceTimers=new WeakMap();
 const sourceId=p=>String(p?.team?.[0]||'').replace(/^c_/,'');
 const recovered=id=>window.ORIGINAL_LEAF_OBS_FRAMES?.[id]||null;
 const sequenceFor=(source,action)=>{
  const frames=source?.frames||[];
  const byIndex=id=>frames.find(frame=>frame.index===id);
  // Existing recovered 2002 source poses: the ORIGINAL bitmap frames are
  // authentic; action labels here are only provisional until animation
  // group direction/action metadata is fully decoded.
  const chosen=(action==='idle'?[0,1,2]:
   action==='walk'?[0,1,2,3]:
   action==='attack'?[10,18]:
   action==='hurt'?[18,10]:
   action==='victory'?[25,30,0]:[0]).map(byIndex).filter(Boolean);
  return chosen.length?chosen:[frames[0]].filter(Boolean);
 };
 function showSourceFrame(pawn,frame){
  const image=pawn.querySelector('img.leaf-chess-original-obs');
  if(!image||!frame||pawn.dataset.actorRig!=='original-obs-sprite')return;
  if(image.getAttribute('src')!==frame.url)image.src=frame.url;
  image.style.width=frame.width+'px';
  image.style.height=frame.height+'px';
  image.style.left='calc(50% + '+frame.originX+'px)';
  // Frame origins are relative to the world tile center, NOT to the fake
  // figure's 112px tall CSS box. Pawn root (height124, transform -88%) is
  // anchored 14.88px below tile origin; preserve native world pixel sizes.
  image.style.bottom=(14.88-frame.originY-frame.height)+'px';
  pawn.dataset.actorFrame=String(frame.index);
 }
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
  clearInterval(sourceTimers.get(node));
  sourceTimers.delete(node);
  const original=recovered(src);
  if(original?.frames?.length){
   let image=node.querySelector('img.leaf-chess-original-obs');
   if(!image){
    image=document.createElement('img');
    image.className='leaf-chess-original-obs';image.alt='';
    image.draggable=false;image.setAttribute('aria-hidden','true');
    node.append(image);
   }
   node.dataset.actorRig='original-obs-sprite';
   node.dataset.actorSource='OBS/'+original.originalMember;
   node.dataset.actorOriginalModelRecovered='true';
   node.dataset.sourceAnimation='genuine-bitmap-pose-map-inferred';
   node.dataset.sourcePoseMapping='unverified';
   image.hidden=false;
   const seq=sequenceFor(original,action);
   showSourceFrame(node,seq[0]);
   if(seq.length>1&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){
    let frame=0;
    const timer=setInterval(()=>{
     if(!node.isConnected||node.dataset.actorPose!==action||
       node.dataset.chessmanId!==src){
      clearInterval(timer);sourceTimers.delete(node);return;
     }
     frame=(frame+1)%seq.length;showSourceFrame(node,seq[frame]);
    },action==='walk'?120:action==='idle'?340:155);
    sourceTimers.set(node,timer);
   }
   const sheet=node.querySelector('.leaf-chess-source-frame');
   if(sheet)sheet.hidden=true;
   return;
  }
  const originalImage=node.querySelector('img.leaf-chess-original-obs');
  if(originalImage)originalImage.hidden=true;
  delete node.dataset.actorFrame;
  node.dataset.sourcePoseMapping='unavailable';
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
   pawn.dataset.actorSource=recovered(src)?'OBS/'+recovered(src).originalMember:'CardData';
   pawn.dataset.actorOriginalModelRecovered=String(!!recovered(src));
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
 }
 window.__LEAF_GENESIS_ACTORS__={
  mount,pose,poseByPlayer,registerFrames,
  getState:()=>({
   originalFullBodyFramesRecovered:[...new Set([
    ...Object.keys(window.ORIGINAL_LEAF_OBS_FRAMES||{}),...frames.keys()
   ])],
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
