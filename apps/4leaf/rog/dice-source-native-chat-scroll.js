'use strict';
/* Genuine Dice/IMG/scrollButton.bmp 80x16: five 16x16 native arrow
 * states. The user clicks real DOM buttons and scrolls the ACTUAL shared
 * chat transcript; no fake online guests, simulated messages or screenshots.
 * ChatTown has a DIFFERENT native scrollbar and remains untouched.
 */
(function(){
 function install(){
  const host=document.querySelector('.messenger');
  const log=document.getElementById('chat-log');
  if(!host||!log||host.querySelector('.leaf-dice-chat-scroll'))return;
  const buttons={};
  // Original IMG/scrollButton.bmp supplies the genuine 16px arrow art.
  // Physical press-and-hold and keyboard history paging are reversible
  // WEB interaction reconstructions, not recovered 2002 input timing.
  // Operate on ONE shared actual transcript; never manufacture messages.
  let holdDelay=null,holdRepeat=null;
  const stopHolding=()=>{
   if(holdDelay!==null){clearTimeout(holdDelay);holdDelay=null;}
   if(holdRepeat!==null){clearInterval(holdRepeat);holdRepeat=null;}
   delete host.dataset.nativeScrollHeld;
  };
  const move=(direction,scale=0.65)=>{
   const step=Math.max(20,Math.round(log.clientHeight*scale));
   log.scrollTop+=direction==='up'?-step:step;
   refresh();
  };
  const startHolding=(button,direction,event)=>{
   if(event.button!==0||button.disabled)return;
   stopHolding();
   host.dataset.nativeScrollHeld=direction;
   holdDelay=setTimeout(()=>{
    if(button.disabled){stopHolding();return;}
    move(direction);
    holdRepeat=setInterval(()=>{
     if(button.disabled||!host.closest('#app.app-classic-dice')){
      stopHolding();return;
     }
     move(direction,0.45);
    },95);
   },330);
  };
  // The chat log itself is a genuine scrollable UI: permit focus and
  // keyboard history navigation without moving the game's DMP camera.
  log.tabIndex=0;
  log.setAttribute('aria-label','원본 주사위의 잔영 채팅 기록. Page Up/Down, Home/End로 탐색');
  log.addEventListener('keydown',event=>{
   let target=null;
   if(event.key==='PageUp')target='up';
   else if(event.key==='PageDown')target='down';
   else if(event.key==='Home')target='home';
   else if(event.key==='End')target='end';
   if(!target)return;
   event.preventDefault();
   if(target==='home')log.scrollTop=0;
   else if(target==='end')log.scrollTop=log.scrollHeight;
   else move(target,0.85);
   refresh();
  });
  window.addEventListener('blur',stopHolding);
  document.addEventListener('visibilitychange',()=>{
   if(document.hidden)stopHolding();
  });
  window.addEventListener('leaf-route-change',stopHolding);
  for(const direction of ['up','down']){
   const b=document.createElement('button');
   b.type='button';
   b.className='leaf-dice-chat-scroll';
   b.dataset.direction=direction;
   b.dataset.originalSource='IMG/scrollButton.bmp';
   b.setAttribute('aria-label',direction==='up'?'주잔 채팅 이전 메시지':'주잔 채팅 다음 메시지');
   b.title=direction==='up'?'이전 대화':'다음 대화';
   b.addEventListener('click',()=>{
    move(direction);
   });
   b.addEventListener('pointerdown',event=>startHolding(b,direction,event));
   b.addEventListener('pointerup',stopHolding);
   b.addEventListener('pointercancel',stopHolding);
   b.addEventListener('pointerleave',stopHolding);
   b.addEventListener('blur',stopHolding);
   host.append(b);
   buttons[direction]=b;
  }
  const refresh=()=>{
   const top=log.scrollTop;
   const limit=Math.max(0,log.scrollHeight-log.clientHeight);
   buttons.up.disabled=top<=1;
   buttons.down.disabled=top>=limit-1;
   host.dataset.nativeDiceScroll='IMG/scrollButton.bmp';
  };
  log.addEventListener('scroll',refresh,{passive:true});
  if(typeof ResizeObserver==='function')new ResizeObserver(refresh).observe(log);
  if(typeof MutationObserver==='function')new MutationObserver(refresh)
   .observe(log,{childList:true,subtree:true,characterData:true});
  refresh();
  window.__LEAF_NATIVE_DICE_CHAT_SCROLL__={
   refresh,getState:()=>({
    source:'Dice/IMG/scrollButton.bmp',
    upEnabled:!buttons.up.disabled,downEnabled:!buttons.down.disabled,
    scrollTop:log.scrollTop,scrollHeight:log.scrollHeight,
    activeHeldDirection:host.dataset.nativeScrollHeld||null,
    keyboardHistoryEnabled:log.tabIndex===0,
    visible:!!host.closest('#app.app-classic-dice')
   })
  };
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);
 else install();
})();
