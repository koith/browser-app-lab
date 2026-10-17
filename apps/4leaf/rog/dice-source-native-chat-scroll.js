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
  for(const direction of ['up','down']){
   const b=document.createElement('button');
   b.type='button';
   b.className='leaf-dice-chat-scroll';
   b.dataset.direction=direction;
   b.dataset.originalSource='IMG/scrollButton.bmp';
   b.setAttribute('aria-label',direction==='up'?'주잔 채팅 이전 메시지':'주잔 채팅 다음 메시지');
   b.title=direction==='up'?'이전 대화':'다음 대화';
   b.addEventListener('click',()=>{
    const move=Math.max(20,Math.round(log.clientHeight*.65));
    log.scrollTop+=(direction==='up'?-move:move);
    refresh();
   });
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
    visible:!!host.closest('#app.app-classic-dice')
   })
  };
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);
 else install();
})();
