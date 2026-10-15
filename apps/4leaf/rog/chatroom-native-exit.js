'use strict';
// ChatRoom/exitbtn.png: authentic 264×50 sprite atlas. The lower strip
// y=25..49 contains four independent 66×25 EXIT/나가기 native button states.
// Compose transparent green-keyed source frames; keep #social-back's existing
// actual navigation event rather than painting an inert screenshot.
(function(){
 function init(){
  const back=document.getElementById('social-back');
  const scene=document.getElementById('rooms');
  if(!back||!scene)return;
  const image=new Image();let attempts=0,frames=null;
  const draw=()=>{
   if(!frames)return;
   const room=scene.classList.contains('classic-chat-room');
   const pressed=back.dataset.nativePressed==='true';
   const hovering=back.matches(':hover')||back.matches(':focus-visible');
   const state=pressed?2:hovering?1:0;
   back.style.backgroundImage='url("'+frames[state]+'")';
   back.dataset.nativeFrame=String(state);
   back.dataset.nativeExitReady='true';
   // A room-only button must not masquerade as "exit" in ChatTown or map.
   back.title=room?'채팅방 나가기 · 채팅방 목록':'이전 화면으로 이동';
  };
  const load=()=>{
   if(!scene.isConnected)return;
   image.src='./original/ChatRoom/exitbtn.png'+(attempts?'?retry='+attempts+'&at='+Date.now():'');
  };
  image.onload=()=>{
   try{
    if(image.naturalWidth!==264||image.naturalHeight!==50)throw Error('unexpected original exit atlas size');
    const bitmap=document.createElement('canvas');
    bitmap.width=264;bitmap.height=50;
    const ctx=bitmap.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(image,0,0);
    const px=ctx.getImageData(0,0,264,50);
    for(let i=0;i<px.data.length;i+=4){
     if(px.data[i]<=60&&px.data[i+1]>=225&&px.data[i+2]<=70)px.data[i+3]=0;
    }
    ctx.putImageData(px,0,0);
    frames=Array.from({length:4},(_,i)=>{
     const c=document.createElement('canvas');c.width=66;c.height=25;
     c.getContext('2d').drawImage(bitmap,i*66,25,66,25,0,0,66,25);
     return c.toDataURL('image/png');
    });
    draw();
  }catch(error){back.dataset.nativeExitReady='fallback';console.warn('4LEAF native EXIT:',error.message)}
  };
  image.onerror=()=>{
   if(!scene.isConnected)return;
   if(attempts>=4){back.dataset.nativeExitReady='fallback';return}
   attempts++;setTimeout(load,Math.min(1400,180*2**attempts));
  };
  back.addEventListener('pointerenter',draw);
  back.addEventListener('pointerleave',()=>{back.dataset.nativePressed='false';draw()});
  back.addEventListener('pointerdown',()=>{back.dataset.nativePressed='true';draw()});
  back.addEventListener('pointerup',()=>{back.dataset.nativePressed='false';draw()});
  back.addEventListener('pointercancel',()=>{back.dataset.nativePressed='false';draw()});
  back.addEventListener('focus',draw);
  back.addEventListener('blur',draw);
  new MutationObserver(draw).observe(scene,{attributes:true,attributeFilter:['class']});
  load();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
 else init();
})();
