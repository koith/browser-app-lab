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
 // Decode ALL original 2002 eventRoll1.spr PNG frames BEFORE the first
 // animated roll. Without this, 55ms src swaps display missing/stale frames
 // on slow/cold network loads, even when the engine result is correct.
 const FRAME_COUNT=16,FRAME_HEIGHT=51;
 const SOURCE_BASE='./original/SourceSPR/eventRoll1-';
 const frameUrl=index=>SOURCE_BASE+String(index).padStart(2,'0')+'.png';
 const cachedFrames=new Array(FRAME_COUNT);
 let preloadPromise=null,nativeFramesReady=false;
 const nativeReady=()=>nativeFramesReady&&!!source&&source.dataset.nativeRollSource==='ready';
 function loadFrame(index){
  return new Promise((resolve,reject)=>{
   const img=new Image();
   img.onload=async()=>{
    if(img.naturalHeight!==FRAME_HEIGHT||
      img.naturalWidth<69||img.naturalWidth>91){
     reject(new Error('Unexpected original eventRoll1.spr frame '+index+
      ' '+img.naturalWidth+'x'+img.naturalHeight));return;
    }
    try{
     // A loaded resource is not necessarily decoded for immediate painting.
     // Browser support varies; once decoded, swaps hit the image cache.
     if(typeof img.decode==='function')await img.decode();
     resolve(img);
    }catch(error){reject(error)}
   };
   img.onerror=()=>reject(new Error('Missing original eventRoll1.spr frame '+index));
   img.src=frameUrl(index);
  });
 }
 function preloadOriginalFrames(){
  if(preloadPromise)return preloadPromise;
  if(source){
   source.dataset.nativeRollSource='loading';
   source.dataset.nativeRollPreloaded='0';
  }
  preloadPromise=Promise.all(
   Array.from({length:FRAME_COUNT},(_,index)=>loadFrame(index))
  ).then(frames=>{
   frames.forEach((img,index)=>{cachedFrames[index]=img});
   nativeFramesReady=true;
   if(!source?.isConnected)return false;
   source.dataset.nativeRollSource='ready';
   source.dataset.nativeRollPreloaded=String(frames.length);
   source.dataset.originalSpriteMember='Dice/IMG.pak:eventRoll1.spr';
   source.dataset.originalSpriteFrameCount=String(FRAME_COUNT);
   return true;
  }).catch(error=>{
   // The real game always remains clickable. Do not claim recovered
   // animation if one archived frame fails to load.
   nativeFramesReady=false;
   if(source?.isConnected){
    source.dataset.nativeRollSource='fallback';
    source.dataset.nativeRollPreloaded='0';
    source.dataset.nativeRollError=String(error.message||error);
   }
   return false;
  });
  return preloadPromise;
 }
 function showFrame(index){
  if(!nativeReady()||!nativeImage)return;
  const cached=cachedFrames[index];
  if(!cached||!cached.complete||!cached.naturalWidth)return;
  nativeImage.src=cached.src;
  source.dataset.sourceRollFrame=String(index);
 }
 function playOriginalRoll(){
  if(!nativeReady()||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
  if(sourceAnimation)clearInterval(sourceAnimation);
  let frame=0;
  showFrame(frame);
  source.dataset.sourceRollTriggerCount=String(
   (Number(source.dataset.sourceRollTriggerCount)||0)+1);
  source.dataset.sourceRollAnimated='true';
  sourceAnimation=setInterval(()=>{
   frame++;
   if(frame>=FRAME_COUNT){
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
  img.addEventListener('error',()=>{
   // Keep gameplay and inferred CSS accessible if the presentation element
   // fails independently of the decoded 16-frame source cache.
   nativeFramesReady=false;
   if(source?.isConnected)source.dataset.nativeRollSource='fallback';
  });
  nativeImage=img;
  source.append(img);
  img.src=frameUrl(0);
  preloadOriginalFrames();
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
  // The native 16-frame source animation must follow the ONE authoritative
  // roll engine for all inputs (visible source button, keyboard/primary HUD,
  // assistive control). Capture fires before game handlers disable the turn.
  // The source button only forwards its click to that same engine, so no
  // second animation or duplicate random dice result can be created.
  roll.addEventListener('click',()=>{
   if(!roll.disabled)playOriginalRoll();
  },{capture:true});
  source.addEventListener('click',()=>{
   if(!roll.disabled)roll.click();
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
   nativeFrameCount:nativeReady()?FRAME_COUNT:0,
   preloadedFrameCount:nativeReady()?cachedFrames.filter(Boolean).length:0,
   loadState:source?.dataset.nativeRollSource||'unmounted',
   displayedFrame:Number(source?.dataset.sourceRollFrame)||0,
   nativeTriggerCount:Number(source?.dataset.sourceRollTriggerCount)||0,
   evidence:nativeReady()?'original-2002-IMG-SPR/palette-frames':
    '2004-board-battle-screenshot-inferred-mesh'})
 };
})();
