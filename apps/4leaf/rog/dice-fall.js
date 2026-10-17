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
 let active=0,last=[],complete=0;
 const state=()=>({active:active>0,last:last.slice(),complete,
  source:'user-reported fall/bounce; outcome from live game engine',
  originalFramesRecovered:false});
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
 function makeDie(result,index,count){
  const node=document.createElement('span');
  node.className='leaf-fall-piece';
  node.dataset.result=String(result);
  node.dataset.index=String(index);
  node.setAttribute('aria-hidden','true');
  const cube=document.createElement('span');
  cube.className='leaf-fall-cube';
  for(let n=1;n<=6;n++)cube.append(makeFace(n));
  node.append(cube);
  return {node,cube,result,index,count};
 }
 const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 async function animateDie(die,duration,instant){
  const {node,cube,result,index}=die;
  const [rx,ry]=ROTATION[result];
  const target='rotateX('+(720+rx)+'deg) rotateY('+(1080+ry)+'deg) rotateZ(0deg)';
  const physics=[
   {transform:'translate3d(0,-260px,0) scale(.76)',offset:0},
   {transform:'translate3d('+(index%2?12:-12)+'px,0,0) scale(1.08,.88)',offset:.38},
   {transform:'translate3d('+(index%2?19:-19)+'px,-66px,0) scale(.98)',offset:.55},
   {transform:'translate3d('+(index%2?10:-10)+'px,0,0) scale(1.03,.94)',offset:.72},
   {transform:'translate3d('+(index%2?7:-7)+'px,-19px,0) scale(.99)',offset:.83},
   {transform:'translate3d(0,0,0) scale(1)',offset:1}
  ];
  const spin=[
   {transform:'rotateX(-680deg) rotateY(510deg) rotateZ(-30deg)',offset:0},
   {transform:'rotateX(-180deg) rotateY(720deg) rotateZ(24deg)',offset:.38},
   {transform:'rotateX(370deg) rotateY(890deg) rotateZ(-10deg)',offset:.71},
   {transform:target,offset:1}
  ];
  if(instant||typeof node.animate!=='function'){
   cube.style.transform=target;
   return;
  }
  const fall=node.animate(physics,{duration,
   easing:'linear',fill:'forwards'});
  const turn=cube.animate(spin,{duration,
   easing:'cubic-bezier(.19,.61,.33,1)',fill:'forwards'});
  try{await Promise.all([fall.finished,turn.finished]);}
  finally{
   // Make the FINAL face permanent before removing animated layer.
   cube.style.transform=target;
   fall.cancel();turn.cancel();
   node.style.transform='translate3d(0,0,0)';
  }
 }
 async function roll(results){
  const values=Array.isArray(results)?results.map(Number):[];
  if(!values.length||values.length>4||
   values.some(v=>!Number.isInteger(v)||v<1||v>6))
   throw new Error('Falling Dice requires 1..4 genuine D4/D6 eyes');
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
  const dice=values.map((result,index)=>makeDie(result,index,values.length));
  for(const die of dice)layer.append(die.node);
  const instant=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches||false;
  active=1;
  try{
   await Promise.all(dice.map((die,index)=>animateDie(die,instant?0:1120+index*115,instant)));
   last=values.slice();
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
  faces:PIPS,orientation:ROTATION};
})();
