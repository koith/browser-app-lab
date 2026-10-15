'use strict';
/* Original 4LEAF ChatRoom/ownerdialog.png is a 338x282 atlas, NOT an entire
   screen capture. The 309x126 top-left region is the room owner's original
   UI backdrop; lower strips contain source-drawn OK and Cancel buttons.
   Composite the original PNG pieces with real live HTML inputs and the
   existing secure room creation handler. No decorative fake inputs. */
(function(){
 const SOURCE='./original/ChatRoom/ownerdialog.png';
 const ATLAS={width:338,height:282,form:{x:0,y:0,w:309,h:126},
  ok:{x:0,y:234,w:62,h:23},cancel:{x:0,y:258,w:62,h:23}};
 const forms=new Set();
 const image=new Image();
 let attempts=0,buffer=null,loading=false,ready=false;
 function decode(){
  if(image.naturalWidth!==ATLAS.width||image.naturalHeight!==ATLAS.height)
   throw new Error('Unexpected native ChatRoom owner dialogue atlas dimensions');
  const canvas=document.createElement('canvas');
  canvas.width=ATLAS.width;canvas.height=ATLAS.height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  ctx.drawImage(image,0,0);
  const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
  // The recovered atlas uses saturated green for transparency, independent
  // from the source text, white editable fields and blue window backdrop.
  for(let i=0;i<pixels.data.length;i+=4){
   const r=pixels.data[i],g=pixels.data[i+1],b=pixels.data[i+2];
   if(g>=225&&r<=65&&b<=85&&g>r*1.7&&g>b*1.7)pixels.data[i+3]=0;
  }
  ctx.putImageData(pixels,0,0);
  return canvas;
 }
 function sourceSlice(part){
  const output=document.createElement('canvas');
  output.width=part.w;output.height=part.h;
  output.getContext('2d').drawImage(buffer,part.x,part.y,part.w,part.h,0,0,part.w,part.h);
  return output;
 }
 function paint(form){
  if(!ready||!form.isConnected||form.dataset.nativeOwnerReady==='true')return;
  const backdrop=form.querySelector('.social-owner-source-backdrop');
  const sprite=sourceSlice(ATLAS.form);
  backdrop.width=sprite.width;backdrop.height=sprite.height;
  backdrop.getContext('2d').drawImage(sprite,0,0);
  backdrop.dataset.source='ChatRoom/ownerdialog.png';
  const ok=sourceSlice(ATLAS.ok).toDataURL('image/png');
  const cancel=sourceSlice(ATLAS.cancel).toDataURL('image/png');
  form.style.setProperty('--owner-source-ok','url("'+ok+'")');
  form.style.setProperty('--owner-source-cancel','url("'+cancel+'")');
  form.dataset.nativeOwnerSource='ChatRoom/ownerdialog.png';
  form.dataset.nativeOwnerAtlas='338x282';
  form.dataset.nativeOwnerReady='true';
  form.querySelector('[name="name"]')?.removeAttribute('placeholder');
 }
 function load(){
  if(loading||ready)return;
  loading=true;
  image.src=SOURCE+(attempts?'?retry='+attempts+'&at='+Date.now():'');
 }
 image.onload=()=>{
  loading=false;
  try{
   buffer=decode();ready=true;
   for(const form of forms)paint(form);
   forms.clear();
  }catch(err){
   console.warn('Native room creation dialog could not be decoded; keeping working HTML form:',err.message);
   for(const form of forms)form.dataset.nativeOwnerReady='fallback';
   forms.clear();
  }
 };
 image.onerror=()=>{
  loading=false;
  if(attempts<5){
   attempts++;
   setTimeout(load,Math.min(1800,200*2**attempts));
  }else{
   for(const form of forms)form.dataset.nativeOwnerReady='fallback';
   forms.clear();
   console.warn('Original ChatRoom room-creation dialog unavailable; HTML form remains usable');
  }
 };
 function enhance(form){
  if(!form||form.dataset.nativeOwnerEnhanced)return;
  form.dataset.nativeOwnerEnhanced='true';
  form.classList.add('social-native-owner-form');
  form.dataset.nativeOwnerReady='loading';
  const art=document.createElement('canvas');
  art.className='social-owner-source-backdrop';art.width=309;art.height=126;
  art.setAttribute('aria-hidden','true');
  form.prepend(art);
  for(const name of ['name','capacity','background','password']){
   const field=form.querySelector('[name="'+name+'"]');
   if(!field)continue;
   field.parentElement.dataset.ownerField=name;
   field.setAttribute('aria-label',({name:'채팅방 제목',capacity:'채팅방 정원',
    background:'채팅방 배경',password:'비공개 방 비밀번호'})[name]);
  }
  // '공개/비공개' and '비밀번호' are printed in the source atlas. Preserve
  // actual meaning: private requires 6+ characters. Public clears the
  // password so no room is inadvertently advertised as public yet locked.
  const privacy=document.createElement('fieldset');
  privacy.className='social-owner-privacy';
  privacy.setAttribute('aria-label','방 공개 여부');
  privacy.innerHTML='<label><input type="radio" name="visibility" value="public" checked>공개</label>'+
   '<label><input type="radio" name="visibility" value="private">비공개</label>';
  const password=form.querySelector('[name="password"]');
  const visibility=()=>form.querySelector('[name="visibility"]:checked')?.value;
  const togglePrivate=()=>{
   const priv=visibility()==='private';
   if(password){
    password.required=priv;
    if(!priv)password.value='';
    password.setCustomValidity('');
   }
  };
  privacy.addEventListener('change',togglePrivate);
  password?.addEventListener('input',()=>{
   password.setCustomValidity('');
   if(password.value&&visibility()!=='private'){
    const radio=privacy.querySelector('[value="private"]');
    radio.checked=true;togglePrivate();
   }
  });
  const capacity=form.querySelector('[name="capacity"]')?.parentElement;
  capacity?.after(privacy);
  const originalSubmit=form.querySelector('button[type="submit"]');
  if(originalSubmit){
   originalSubmit.classList.add('social-owner-native-submit');
   originalSubmit.setAttribute('aria-label','원본 창: 채팅방 만들기');
   const cancel=document.createElement('button');
   cancel.type='button';cancel.className='social-owner-native-cancel';
   cancel.textContent='취소';cancel.setAttribute('aria-label','원본 창: 개설 취소');
   cancel.addEventListener('click',()=>document.querySelector('#social-modal .social-modal-title button')?.click());
   originalSubmit.after(cancel);
  }
  form.addEventListener('keydown',event=>{
   if(event.key!=='Escape')return;
   event.preventDefault();event.stopPropagation();
   document.querySelector('#social-modal .social-modal-title button')?.click();
  });
  if(ready)paint(form);else{forms.add(form);load()}
 }
 window.__LEAF_NATIVE_OWNER_DIALOG__={enhance,getState:()=>({
  ready,dimensions:[ATLAS.width,ATLAS.height],registered:forms.size
 })};
})();
