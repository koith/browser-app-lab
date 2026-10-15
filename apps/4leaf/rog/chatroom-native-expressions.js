'use strict';
/* Native source ChatRoom/expdialogbtn.png 196x267.
   Real screenshot/corpus extracted six expression labels and corresponding
   face icons. Live peer propagation uses the existing *real chat message*
   transport; it is WEB RECONSTRUCTION, not a claim about old binary packets. */
(function(){
 const URL='./original/ChatRoom/expdialogbtn.png';
 const OPTIONS=['하하','우씨','으앙','좋아','헉','기타'];
 const LINE='[표정] ';
 const SOURCE={width:196,height:267,cellWidth:66,cellHeight:22};
 const image=new Image();
 let ready=false,attempts=0,palette=null;
 function load(){
  image.src=URL+(attempts?'?retry='+attempts+'&at='+Date.now():'');
 }
 image.onload=()=>{
  if(image.naturalWidth!==SOURCE.width||image.naturalHeight!==SOURCE.height){
   console.warn('Original ChatRoom expression source dimensions changed');
   return;
  }
  ready=true;
  palette?.setAttribute('data-source-ready','true');
 };
 image.onerror=()=>{
  if(attempts>=5){palette?.setAttribute('data-source-ready','fallback');return}
  attempts++;setTimeout(load,Math.min(1600,200*2**attempts));
 };
 load();
 function trigger(){return document.querySelector('#rooms .social-exp-trigger')}
 function close(restore=false){
  const opened=palette;
  palette=null;
  opened?.remove();
  const t=trigger();
  if(t){
   t.setAttribute('aria-expanded','false');
   if(restore&&t.isConnected)t.focus({preventScroll:true});
  }
 }
 function parse(text){
  if(typeof text!=='string'||!text.startsWith(LINE))return -1;
  return OPTIONS.indexOf(text.slice(LINE.length));
 }
 function show(peer,text){
  const index=parse(text);
  if(index<0)return false;
  const layer=document.getElementById('social-avatar-layer');
  const actor=[...(layer?.querySelectorAll('.social-avatar')||[])]
   .find(node=>node.dataset.peer===String(peer));
  if(!actor)return true;
  actor.querySelector('.social-native-expression')?.remove();
  const face=document.createElement('span');
  face.className='social-native-expression';
  face.dataset.nativeExpression=OPTIONS[index];
  face.dataset.source='ChatRoom/expdialogbtn.png';
  face.setAttribute('role','img');
  face.setAttribute('aria-label','표정: '+OPTIONS[index]);
  face.style.backgroundPosition='0 '+(-index*SOURCE.cellHeight)+'px';
  if(!ready){
   face.dataset.fallback='true';
   face.textContent=OPTIONS[index];
  }
  actor.append(face);
  setTimeout(()=>{if(face.isConnected)face.remove()},4800);
  return true;
 }
 function choose(index){
  if(!Number.isInteger(index)||index<0||index>=OPTIONS.length)return;
  if(!document.querySelector('#rooms.classic-chat-room'))return;
  const phrase=LINE+OPTIONS[index];
  close(true);
  // Actual chat delivery guarantees local, BroadcastChannel, RTC and central
  // authority peers see the same user-originated event. No fabricated peers,
  // no artificial room events, no second untrusted presence writer.
  window.__LEAF_SOCIAL__?.send(phrase);
 }
 function open(){
  const t=trigger();
  if(!t||!document.querySelector('#rooms.classic-chat-room'))return;
  if(palette?.isConnected){close(true);return}
  close();
  const frame=document.querySelector('#rooms .social-image-frame.social-interior');
  if(!frame)return;
  palette=document.createElement('div');
  palette.id='social-native-expression-palette';
  palette.className='social-native-expression-palette';
  palette.dataset.source='ChatRoom/expdialogbtn.png';
  palette.dataset.sourceReady=ready?'true':'loading';
  palette.setAttribute('role','group');
  palette.setAttribute('aria-label','원본 4LEAF 표정 선택');
  for(let i=0;i<OPTIONS.length;i++){
   const button=document.createElement('button');
   button.type='button';
   button.className='social-native-expression-option';
   button.setAttribute('aria-label','표정 '+OPTIONS[i]);
   button.dataset.expression=OPTIONS[i];
   button.dataset.row=String(i);
   button.style.setProperty('--emotion-y',(-i*SOURCE.cellHeight)+'px');
   button.textContent=OPTIONS[i];
   button.addEventListener('click',()=>choose(i));
   palette.append(button);
  }
  palette.addEventListener('keydown',e=>{
   if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close(true)}
  });
  frame.append(palette);
  t.setAttribute('aria-expanded','true');
  palette.querySelector('button')?.focus({preventScroll:true});
 }
 function install(toolbar){
  if(!toolbar||toolbar.querySelector('.social-exp-trigger'))return;
  const button=document.createElement('button');
  button.type='button';button.className='social-exp-trigger';
  button.setAttribute('aria-label','원본 4LEAF 표정 열기');
  button.setAttribute('aria-controls','social-native-expression-palette');
  button.setAttribute('aria-expanded','false');
  button.title='표정 선택 · 원본 expdialogbtn';
  button.textContent='표정';
  button.addEventListener('click',open);
  toolbar.append(button);
 }
 window.__LEAF_NATIVE_EXPRESSIONS__={
  install,close,show,parse,choose,
  getState:()=>({ready,atlas:[SOURCE.width,SOURCE.height],
   options:OPTIONS.slice(),opened:Boolean(palette?.isConnected)})
 };
})();
