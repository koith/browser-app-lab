'use strict';
/* Genuine 2002 4LEAF Dice/IMG.pak eventRoll1.spr, source 16-frame ROLL orb.
 * All native transparent palette pixels were losslessly decoded to PNG with
 * the original 640-stride video-buffer codec. Source frame0 is 69x51, closely
 * corresponding to the 2004 (x400,y410) control captured in board.jpg.
 * The prior CSS orb remains ONLY a failed-image/offline-resource fallback.
 * This is a UI sprite animation, NOT yet the original tumbling-dice mesh.
 * Real movement results come exclusively from the game's normal handler.
 */
(function(){
 const $=id=>document.getElementById(id);
 let source=null,observer=null,nativeImage=null,sourceAnimation=null;
 const SOURCE_BASE='./original/SourceSPR/eventRoll1-';
 const frameUrl=index=>SOURCE_BASE+String(index).padStart(2,'0')+'.png';
 const nativeReady=()=>!!source&&source.dataset.nativeRollSource==='ready';
 function showFrame(index){
  if(!nativeReady()||!nativeImage)return;
  nativeImage.src=frameUrl(index);
  source.dataset.sourceRollFrame=String(index);
 }
 function playOriginalRoll(){
  if(!nativeReady()||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
  if(sourceAnimation)clearInterval(sourceAnimation);
  let frame=0;
  showFrame(frame);
  source.dataset.sourceRollAnimated='true';
  sourceAnimation=setInterval(()=>{
   frame++;
   if(frame>=16){
    clearInterval(sourceAnimation);
    sourceAnimation=null;
    showFrame(0);
    source.dataset.sourceRollAnimated='false';
    return;
   }
   showFrame(frame);
  },55);
 }
 function installOriginalImage(){
  if(source.querySelector('.dice-original-roll-spr'))return;
  const img=document.createElement('img');
  img.className='dice-original-roll-spr';
  img.alt='';img.draggable=false;
  img.setAttribute('aria-hidden','true');
  img.decoding='async';
  img.addEventListener('load',()=>{
   if(!source?.isConnected)return;
   if(img.naturalHeight!==51||img.naturalWidth<69||img.naturalWidth>91){
    source.dataset.nativeRollSource='fallback';return;
   }
   source.dataset.nativeRollSource='ready';
   source.dataset.originalSpriteMember='Dice/IMG.pak:eventRoll1.spr';
   source.dataset.originalSpriteFrameCount='16';
  });
  img.addEventListener('error',()=>{
   // A failed asset never hides the interactive legacy fallback.
   if(source?.isConnected)source.dataset.nativeRollSource='fallback';
  });
  nativeImage=img;
  source.append(img);
  img.src=frameUrl(0);
 }
 function sync(){
  const roll=$('roll-btn'),game=$('game');
  if(!source||!roll||!game)return;
  source.disabled=roll.disabled;
  source.setAttribute('aria-disabled',String(roll.disabled));
  source.setAttribute('aria-label',roll.getAttribute('aria-label')||'주사위 굴리기');
  source.title=roll.title||'주사위 굴리기';
  source.dataset.rollCount=String(Number($('dice-box')?.dataset.rollCount)||0);
  source.dataset.busy=String(roll.disabled);
 }
 function init(){
  const game=$('game'),roll=$('roll-btn'),dice=$('dice-box');
  if(!game||!roll||!dice)return;
  source=$('dice-source-roll');
  if(!source){
   source=document.createElement('button');
   source.id='dice-source-roll';
   source.className='dice-source-roll';
   source.type='button';
   source.dataset.evidence='2004-board-battle-screenshot-inferred-mesh';
   const orb=document.createElement('span');
   orb.className='dice-source-roll-orb';
   orb.setAttribute('aria-hidden','true');
   const text=document.createElement('span');
   text.className='dice-source-roll-label';
   text.setAttribute('aria-hidden','true');
   text.textContent='ROLL';
   source.append(orb,text);
   game.append(source);
  }
  installOriginalImage();
  source.addEventListener('click',()=>{
   // The main game engine alone decides whose turn it is and generates
   // movement values. Dispatch no synthetic events or duplicate dice logic.
   if(!roll.disabled){
    playOriginalRoll();
    roll.click();
   }
   sync();
  });
  observer?.disconnect();
  observer=new MutationObserver(sync);
  observer.observe(roll,{attributes:true,attributeFilter:['disabled','aria-label','title']});
  observer.observe(dice,{attributes:true,attributeFilter:['data-roll-count']});
  sync();
 }
 if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',init,{once:true});
 else init();
 window.__LEAF_SOURCE_ROLL__={
  sync,
  getState:()=>({mounted:!!source,isReady:!!source&&!source.disabled,
   rollCount:Number(source?.dataset.rollCount)||0,
   originalSource:nativeReady()?'Dice/IMG.pak:eventRoll1.spr':null,
   nativeFrameCount:nativeReady()?16:0,
   displayedFrame:Number(source?.dataset.sourceRollFrame)||0,
   evidence:nativeReady()?'original-2002-IMG-SPR/palette-frames':
    '2004-board-battle-screenshot-inferred-mesh'})
 };
})();
