/* Actual ChatRoom/scrollbar.png (52x40) from the 2002 4LEAF client.
 * The recovered atlas is 4 normal/hover/pressed/etc 13px columns by 40px.
 * Canvas keys original green pixels, then the native buttons scroll the
 * existing REAL #chat-log. No second transcript, fake message, proxy panel,
 * custom server or screenshot interaction overlay is introduced. */
(function(){
 'use strict';
 const $=id=>document.getElementById(id);
 let handle=null,up=null,down=null,track=null,thumb=null,log=null;
 let ready=false,source=null,drag=null;
 function update(){
  if(!handle||!log)return;
  const max=Math.max(0,log.scrollHeight-log.clientHeight);
  const tHeight=track.clientHeight||63;
  const ratio=log.scrollHeight?log.clientHeight/log.scrollHeight:1;
  const h=Math.round(Math.min(tHeight,Math.max(15,tHeight*ratio)));
  const limit=Math.max(0,tHeight-h);
  const offset=max>0?Math.round(limit*Math.max(0,log.scrollTop)/max):0;
  thumb.style.height=h+'px';thumb.style.top=offset+'px';
  track.setAttribute('aria-valuenow',String(Math.round(max?100*log.scrollTop/max:100)));
  up.disabled=log.scrollTop<1;down.disabled=log.scrollTop>=max-1;
  handle.dataset.scrollable=String(max>1);
 }
 function seek(t){
  const max=Math.max(0,log.scrollHeight-log.clientHeight);
  log.scrollTop=Math.max(0,Math.min(max,t*max));
  update();
 }
 function setup(){
  log=$('chat-log');
  const host=log?.closest('.messenger');
  if(!log||!host||handle)return;
  handle=document.createElement('div');
  handle.id='social-native-chat-scroll';handle.dataset.source='ChatRoom/scrollbar.png';
  handle.setAttribute('aria-label','원본 포리프 채팅 기록 스크롤');
  up=document.createElement('button');up.type='button';up.id='social-native-scroll-up';
  up.setAttribute('aria-label','이전 채팅 기록');up.title='위로';
  track=document.createElement('div');track.id='social-native-scroll-track';
  track.setAttribute('role','scrollbar');track.setAttribute('aria-controls','chat-log');
  track.setAttribute('aria-label','채팅 기록 위치');track.setAttribute('aria-orientation','vertical');
  track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax','100');
  thumb=document.createElement('button');thumb.type='button';thumb.id='social-native-scroll-thumb';
  thumb.setAttribute('aria-label','채팅 스크롤 손잡이');thumb.title='스크롤 손잡이';
  down=document.createElement('button');down.type='button';down.id='social-native-scroll-down';
  down.setAttribute('aria-label','다음 채팅 기록');down.title='아래로';
  track.append(thumb);handle.append(up,track,down);host.append(handle);
  up.onclick=()=>{log.scrollTop-=48;update()};
  down.onclick=()=>{log.scrollTop+=48;update()};
  track.addEventListener('pointerdown',event=>{
   if(event.target===thumb)return;
   const rect=track.getBoundingClientRect();
   const center=thumb.clientHeight/2;
   seek((event.clientY-rect.top-center)/Math.max(1,rect.height-thumb.clientHeight));
  });
  thumb.addEventListener('pointerdown',event=>{
   event.preventDefault();event.stopPropagation();
   drag={id:event.pointerId,y:event.clientY,start:Number.parseFloat(thumb.style.top)||0};
   thumb.setPointerCapture(event.pointerId);
  });
  thumb.addEventListener('pointermove',event=>{
   if(!drag||drag.id!==event.pointerId)return;
   const trackHeight=track.clientHeight,travel=Math.max(1,trackHeight-thumb.clientHeight);
   const offset=drag.start+(event.clientY-drag.y);
   seek(offset/travel);
  });
  const release=event=>{
   if(!drag||drag.id!==event.pointerId)return;
   drag=null;
   if(thumb.hasPointerCapture(event.pointerId))thumb.releasePointerCapture(event.pointerId);
  };
  thumb.addEventListener('pointerup',release);
  thumb.addEventListener('pointercancel',release);
  log.addEventListener('scroll',update,{passive:true});
  const changes=new MutationObserver(()=>requestAnimationFrame(update));
  changes.observe(log,{childList:true,subtree:true,characterData:true});
  if('ResizeObserver' in window){new ResizeObserver(update).observe(log);new ResizeObserver(update).observe(track)}
  window.addEventListener('resize',update,{passive:true});
  window.addEventListener('leaf-route-change',()=>requestAnimationFrame(update));
  loadSource();
  update();
 }
 function loadSource(){
  if(!handle)return;
  // file:// disallows pixel reads of local images. Native HTTP(S) browser QA
  // reads the source RGBA and applies the original green-key transparencies.
  if(location.protocol==='file:'){handle.dataset.ready='offline-fallback';return;}
  const img=new Image();let attempts=0;
  img.onload=()=>{
   if(!handle?.isConnected)return;
   try{
    if(img.naturalWidth!==52||img.naturalHeight!==40)throw Error('Source scrollbar has unexpected dimensions');
    const canvas=document.createElement('canvas');canvas.width=52;canvas.height=40;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(img,0,0);
    const data=ctx.getImageData(0,0,52,40);
    for(let i=0;i<data.data.length;i+=4){
     const r=data.data[i],g=data.data[i+1],b=data.data[i+2];
     if(g>220&&r<65&&b<90)data.data[i+3]=0;
    }
    ctx.putImageData(data,0,0);
    source=canvas.toDataURL('image/png');
    handle.style.setProperty('--social-scroll-asset','url("'+source+'")');
    handle.dataset.ready='true';ready=true;update();
   }catch(e){handle.dataset.ready='offline-fallback';console.warn('Original ChatRoom scrollbar key:',e.message)}
  };
  img.onerror=()=>{
   if(attempts++>=5){handle.dataset.ready='error';return}
   setTimeout(()=>{img.src='./original/ChatRoom/scrollbar.png?retry='+attempts+'&at='+Date.now()},Math.min(1600,200*2**attempts));
  };
  img.src='./original/ChatRoom/scrollbar.png';
 }
 window.__LEAF_NATIVE_SCROLLBAR__={getState:()=>({
  ready,source:'ChatRoom/scrollbar.png',
  rendered:handle?.dataset.ready||'not-mounted',
  overflow:log?Math.max(0,log.scrollHeight-log.clientHeight):0,
  position:log?.scrollTop||0,count:document.querySelectorAll('#social-native-chat-scroll').length
 }),update};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);
 else setup();
})();
