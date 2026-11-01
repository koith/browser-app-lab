'use strict';
/* The user remembers 4LEAF's actual roll sequence: dice descend from above,
 * bounce more than once and only THEN reveal their faces. This recovered
 * source archive has no original die animation mesh/frames. This renderer
 * is an explicit WEB RECONSTRUCTION of those interactions, NOT original
 * keyframe data. The underlying real game.js generates every outcome first.
 * No dice randomness, item or turn rule may be introduced here.
 */
(function(){
 const $=id=>document.getElementById(id);
 const PIPS={
  1:[4],2:[0,8],3:[0,4,8],4:[0,2,6,8],
  5:[0,2,4,6,8],6:[0,2,3,5,6,8]
 };
 const ROTATION={1:[0,0],2:[0,-90],3:[-90,0],
  4:[90,0],5:[0,90],6:[0,180]};
 // Result-face normals use the regular tetrahedral dihedral angle
 // acos(-1/3)=109.471 degrees. This is still a WEB fallback mesh,
 // NOT original 2002 MVE geometry/keyframes.
 const TETRA_ANGLE=109.471;
 const TETRA_LAND={
  1:'rotateY(0deg) rotateZ(0deg)',
  2:'rotateY(-109.471deg) rotateZ(0deg)',
  3:'rotateY(-109.471deg) rotateZ(-120deg)',
  4:'rotateY(-109.471deg) rotateZ(-240deg)'
 };
 let active=0,last=[],lastSides=[],complete=0;
 /* ORIGINAL D6 SPRITE (2026-11-01). Dice/OBS.pak member 1171.obs was filed
  * as card 0171 "HUD-card-icon", but its frames are the game's die:
  * frames 0-5 are flat result faces showing 1..6 pips (46x49, red single
  * pip) - the same art as the dice in the archived 800x600 battle.jpg -
  * and frames 6+ are a white die tumbling in 3D (60x71). Face index =
  * pips - 1 is VERIFIED by counting pips in each frame. Only tumble frames
  * 6,7,10,18,25 are extracted so far (28 declared), so the tumble below is
  * a PARTIAL original sequence, and the drop height/bounce path is still
  * the WEB reconstruction. No D4 art has been found; D4 keeps the WEB mesh. */
 const D6_MEMBER='0171';
 const D6_TUMBLE=[6,7,10,18,25];
 function originalD6(){
  // Preferred: the UI manifest (tools/extract-targeted-original-frames.py)
  // holding every decoded 1171 frame with written-run alpha. Faces 0-5 are
  // VERIFIED by pip count; tumble order = native frame order (INFERRED).
  const ui=window.ORIGINAL_LEAF_UI_FRAMES?.['1171'];
  if(ui?.frames?.length){
   const at=i=>ui.frames.find(f=>f.index===i)||null;
   const faces=[0,1,2,3,4,5].map(at);
   if(faces.every(Boolean))return {member:ui.member||'1171.obs',faces,
    tumble:ui.frames.filter(f=>f.index>=6).sort((a,b)=>a.index-b.index),
    declared:ui.declaredFrames,partial:!!ui.partial};
  }
  const member=window.ORIGINAL_LEAF_OBS_FRAMES?.[D6_MEMBER];
  if(!member?.frames)return null;
  // Legacy fallback: colour-key corrected copies of the 11 sampled frames.
  const fix=f=>f&&{...f,url:f.url.replace('/OBS/bulk/1171-','/OBS/d6-colorkey-corrected/1171-')};
  const at=i=>fix(member.frames.find(f=>f.index===i)||null);
  const faces=[0,1,2,3,4,5].map(at);
  if(!faces.every(Boolean))return null;
  return {member:member.originalMember||'1171.obs',faces,
   tumble:D6_TUMBLE.map(at).filter(Boolean),declared:28,partial:true};
 }
 const state=()=>({active:active>0,last:last.slice(),lastSides:lastSides.slice(),complete,
  source:'user-reported fall/bounce; outcome from live game engine',
  // Full original roll (all tumble frames + trajectory) is not recovered.
  originalFramesRecovered:false,
  originalD6Faces:!!originalD6(),
  originalD6TumbleFrames:originalD6()?.tumble.map(f=>f.index)||[],
  originalD4Art:false});
 function makeFace(n){
  const face=document.createElement('span');
  face.className='leaf-die-face leaf-die-face-'+n;
  face.dataset.face=String(n);
  face.setAttribute('aria-hidden','true');
  for(let i=0;i<9;i++){
   const dot=document.createElement('i');
   dot.className='leaf-die-eye'+(PIPS[n].includes(i)?' visible':'');
   face.append(dot);
  }
  return face;
 }
 function makeDie(result,index,count,sides){
  // Ground contact belongs to the board plane, NOT to the moving cube.
  // Previously a CSS drop-shadow travelled 260px up into the air with
  // every falling die. Use a stationary track shadow while the genuine
  // gameplay die model continues its independent fall/spin/bounces.
  // This remains WEB inferred lighting, not original 2002 MVE keyframes.
  const track=document.createElement('span');
  track.className='leaf-fall-track';
  track.dataset.shadowProvenance='web-inferred-ground-contact';
  const node=document.createElement('span');
  node.className='leaf-fall-piece';
  node.dataset.result=String(result);
  node.dataset.sides=String(sides);
  node.dataset.index=String(index);
  node.setAttribute('aria-hidden','true');
  const cube=document.createElement('span');
  cube.className='leaf-fall-cube';
  if(sides===4){
   cube.classList.add('leaf-fall-tetra');
   for(let n=1;n<=4;n++){
    const face=document.createElement('span');
    face.className='leaf-tetra-face leaf-tetra-face-'+n;
    face.textContent=String(n);
    face.setAttribute('aria-hidden','true');
    cube.append(face);
   }
   cube.dataset.result=String(result);
  }else{
   for(let n=1;n<=6;n++)cube.append(makeFace(n));
  }
  node.append(cube);
  const source=sides===6?originalD6():null;
  let sprite=null;
  if(source){
   sprite=document.createElement('img');
   sprite.className='leaf-fall-original-d6';
   sprite.alt='';sprite.draggable=false;
   sprite.setAttribute('aria-hidden','true');
   const first=source.tumble[0]||source.faces[result-1];
   sprite.src=first.url;
   sprite.dataset.frame=String(first.index);
   node.classList.add('leaf-fall-original');
   node.dataset.faceSource='original-OBS-'+source.member+'/face-VERIFIED-by-pip-count';
   node.dataset.tumbleSource='original-OBS-'+source.member+'/partial-'+source.tumble.length+'-frames';
   // If the original PNG cannot load, show the WEB cube instead of nothing.
   sprite.addEventListener('error',()=>{
    node.classList.remove('leaf-fall-original');
    node.dataset.faceSource='web-cube-fallback/original-load-failed';
   });
   node.append(sprite);
  }else{
   node.dataset.faceSource=sides===4?'web-tetra/no-original-D4-art':'web-cube/original-missing';
  }
  track.append(node);
  return {track,node,cube,result,index,count,sides,sprite,source};
 }
 const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 async function animateDie(die,duration,instant){
  const {track,node,cube,result,index,sides,sprite,source}=die;
  const showFace=()=>{
   if(!sprite)return;
   const face=source.faces[result-1];
   sprite.src=face.url;sprite.dataset.frame=String(face.index);
   node.dataset.originalFace=String(face.index);
  };
  // Match stationary ground-shadow opacity to the SAME presentation
  // timeline as actual fall/bounce animation, not an independent clock.
  track.style.setProperty('--leaf-dice-shadow-duration',duration+'ms');
  const [rx,ry]=sides===4?[0,0]:ROTATION[result];
  const target=sides===4?TETRA_LAND[result]:
   'rotateX('+(720+rx)+'deg) rotateY('+(1080+ry)+'deg) rotateZ(0deg)';
  // Source MVE camera/keyframes have not been recovered. The previous
  // inferred 260px spawn height put real CSS geometry outside the compact
  // iPhone stage. Keep the first drop INSIDE the actual current stage, with
  // rebound heights proportional to the available falling distance.
  // This changes PRESENTATION only; dice faces/results and game-turn awaits
  // continue to come exclusively from the authoritative match engine.
  const layerHeight=track.parentElement?.getBoundingClientRect().height||0;
  const dieHeight=track.getBoundingClientRect().height||57;
  const fallHeight=Math.round(Math.max(28,Math.min(260,layerHeight-dieHeight-12)));
  const bounceHeight=Math.round(Math.min(66,fallHeight*.26));
  const finalBounce=Math.round(Math.min(19,fallHeight*.075));
  node.dataset.webFallHeight=String(fallHeight);
  node.dataset.webBounceHeights=bounceHeight+','+finalBounce;
  node.dataset.motionProvenance='responsive-WEB-fallback/not-original-MVE';
  const physics=[
   {transform:'translate3d(0,-'+fallHeight+'px,0) scale(.76)',offset:0},
   {transform:'translate3d('+(index%2?12:-12)+'px,0,0) scale(1.08,.88)',offset:.38},
   {transform:'translate3d('+(index%2?19:-19)+'px,-'+bounceHeight+'px,0) scale(.98)',offset:.55},
   {transform:'translate3d('+(index%2?10:-10)+'px,0,0) scale(1.03,.94)',offset:.72},
   {transform:'translate3d('+(index%2?7:-7)+'px,-'+finalBounce+'px,0) scale(.99)',offset:.83},
   {transform:'translate3d(0,0,0) scale(1)',offset:1}
  ];
  const spin=sides===4?[
   {transform:'rotateX(-540deg) rotateY(390deg) rotateZ(-40deg)',offset:0},
   {transform:'rotateX(-180deg) rotateY(730deg) rotateZ(21deg)',offset:.4},
   {transform:'rotateX(35deg) rotateY(355deg) rotateZ(-11deg)',offset:.81},
   {transform:target,offset:1}
  ]:[
   {transform:'rotateX(-680deg) rotateY(510deg) rotateZ(-30deg)',offset:0},
   {transform:'rotateX(-180deg) rotateY(720deg) rotateZ(24deg)',offset:.38},
   {transform:'rotateX(370deg) rotateY(890deg) rotateZ(-10deg)',offset:.71},
   {transform:target,offset:1}
  ];
  if(instant||typeof node.animate!=='function'){
   cube.style.transform=target;
   showFace();
   return;
  }
  let tumbleTimer=0;
  if(sprite&&source.tumble.length>1){
   let k=0;
   tumbleTimer=setInterval(()=>{
    k=(k+1)%source.tumble.length;
    const f=source.tumble[k];
    sprite.src=f.url;sprite.dataset.frame=String(f.index);
   },Math.max(60,Math.round(duration*.8/(source.tumble.length*2))));
  }
  const fall=node.animate(physics,{duration,
   easing:'linear',fill:'forwards'});
  const turn=cube.animate(spin,{duration,
   easing:'cubic-bezier(.19,.61,.33,1)',fill:'forwards'});
  try{await Promise.all([fall.finished,turn.finished]);}
  finally{
   // Make the FINAL face permanent before removing animated layer.
   cube.style.transform=target;
   if(tumbleTimer)clearInterval(tumbleTimer);
   showFace();
   fall.cancel();turn.cancel();
   node.style.transform='translate3d(0,0,0)';
  }
 }
 async function roll(results,options={}){
  const values=Array.isArray(results)?results.map(Number):[];
  const sides=Array.isArray(options.sides)?options.sides.slice():
    values.map(()=>options.sides===4?4:6);
  if(!values.length||values.length>4||sides.length!==values.length||
    sides.some(n=>n!==4&&n!==6)||
    values.some((v,i)=>!Number.isInteger(v)||v<1||v>sides[i]))
   throw new Error('Dice results must agree with D4/D6 source rules');
  if(active)throw new Error('Falling Dice presentation already running');
  const game=$('game');
  if(!game||!game.isConnected)return values.slice();
  let layer=$('leaf-dice-fall-layer');
  if(!layer){
   layer=document.createElement('div');
   layer.id='leaf-dice-fall-layer';
   layer.className='leaf-dice-fall-layer';
   layer.setAttribute('role','status');
   layer.setAttribute('aria-live','polite');
   game.append(layer);
  }
  layer.replaceChildren();
  layer.dataset.phase='falling';
  layer.setAttribute('aria-label','주사위가 하늘에서 떨어져 굴러갑니다');
  layer.dataset.count=String(values.length);
  layer.dataset.sides=sides.join(',');
  const dice=values.map((result,index)=>makeDie(result,index,values.length,sides[index]));
  for(const die of dice)layer.append(die.track);
  const instant=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches||false;
  active=1;
  try{
   await Promise.all(dice.map((die,index)=>animateDie(die,instant?0:1120+index*115,instant)));
   last=values.slice();
   lastSides=sides.slice();
   complete++;
   layer.dataset.phase='landed';
   layer.dataset.result=values.join(',');
   layer.setAttribute('aria-label','주사위 착지 결과 '+values.join(' + '));
   // Hold visible final values before the existing game HUD reveals them.
   if(!instant)await delay(210);
   layer.dataset.phase='complete';
   if(!instant)await delay(180);
   return values.slice();
  }finally{
   layer.dataset.phase='idle';
   layer.replaceChildren();
   active=0;
  }
 }
 window.__LEAF_DICE_FALL__={roll,getState:state,
  faces:PIPS,orientation:ROTATION,originalD6,
  tetraOrientation:{...TETRA_LAND},tetraDihedralDegrees:TETRA_ANGLE};
})();
