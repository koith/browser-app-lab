'use strict';
/* Screenshot-informed HUD from 2004 board.jpg / battle.jpg, NOT a recovered
 * original ROLL mesh or texture. The archived 800x600 board positions the
 * cyan/pink ROLL control over the living battlefield at roughly (400,410).
 * Both this source-positioned control and the legacy accessible button call
 * ONE existing engine roll handler; neither invents dice or player turns.
 */
(function(){
 const $=id=>document.getElementById(id);
 let source=null,observer=null;
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
  source.addEventListener('click',()=>{
   // The main game engine alone decides whose turn it is and generates
   // movement values. Dispatch no synthetic events or duplicate dice logic.
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
   evidence:'2004-board-battle-screenshot-inferred-mesh'})
 };
})();
