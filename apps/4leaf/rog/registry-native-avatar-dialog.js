'use strict';
/* Recovered Registry.pak Avatar dialog.
   avatardialog1.png / 2.png / 3.png and savaNN.png are genuine original
   components; live HTML text, controls, and real peer avatar remain separate.
   DO NOT synthesize unavailable original jobs, levels, FP or GP. */
(function(){
 const SOURCES={
  logo:{file:'avatardialog1.png',width:111,height:34},
  title:{file:'avatardialog2.png',width:168,height:23},
  info:{file:'avatardialog3.png',width:368,height:205},
  actor:{width:75,height:141}
 };
 const PREFIX='./original/Registry/';
 let currentDialog=null;
 const inside=(i,size)=>Math.max(0,Math.min(size-1,Number(i)||0));
 const path=name=>PREFIX+name+'.png';
 function resource(element,file,width,height){
  element.width=width;element.height=height;
  element.decoding='async';
  let attempts=0;
  const setSource=(next)=>{
   attempts=0;
   element.dataset.source='Registry/'+next;
   element.dataset.sourceReady='loading';
   element.src=PREFIX+next;
  };
  element.__leafSetNativeSource=setSource;
  element.addEventListener('load',()=>{
   const current=element.dataset.source;
   if(element.naturalWidth!==width||element.naturalHeight!==height){
    element.dataset.sourceReady='mismatch';
    console.warn('Original Registry avatar component has unexpected dimensions:',current);
   }else element.dataset.sourceReady='true';
  });
  element.addEventListener('error',()=>{
   const current=element.dataset.source;
   if(attempts<5){
    attempts++;
    setTimeout(()=>{
     // If the user chose a new actor meanwhile, never retry an old sprite.
     if(element.isConnected&&element.dataset.source===current)
      element.src=PREFIX+current.slice('Registry/'.length)+
       '?retry='+attempts+'&at='+Date.now();
    },Math.min(1800,200*2**attempts));
    return;
   }
   element.dataset.sourceReady='fallback';
   // The live selection stays usable after source CDN failures.
   console.warn('Original Registry component unavailable after retries:',current);
  });
  setSource(file);
  return element;
 }
 function enhance(panel,chooser,options){
  if(!panel||!chooser||!Array.isArray(options?.avatars)||
    !options.avatars.length||panel.dataset.nativeAvatarDialog)return false;
  const avatars=options.avatars;
  const buttons=[...chooser.querySelectorAll('button')];
  if(buttons.length!==avatars.length)return false;
  panel.dataset.nativeAvatarDialog='Registry/avatardialog3.png';
  panel.dataset.nativeAvatarSource='Registry/avatardialog1.png|avatardialog2.png|avatardialog3.png';
  panel.classList.add('social-native-avatar-panel');
  panel.setAttribute('role','dialog');
  panel.setAttribute('aria-label','원본 4LEAF 아바타 선택');
  chooser.classList.add('social-native-avatar-chooser');
  chooser.setAttribute('role','group');
  chooser.setAttribute('aria-label','원본 캐릭터 고르기');
  const header=document.createElement('div');
  header.className='social-native-avatar-header';
  const logo=resource(document.createElement('img'),SOURCES.logo.file,SOURCES.logo.width,SOURCES.logo.height);
  logo.alt='4LEAF';logo.className='social-native-avatar-logo';
  const title=resource(document.createElement('img'),SOURCES.title.file,SOURCES.title.width,SOURCES.title.height);
  title.alt='Select your Avatar';title.className='social-native-avatar-title';
  header.append(logo,title);
  const scene=document.createElement('div');scene.className='social-native-avatar-scene';
  scene.dataset.source='Registry/avatardialog3.png';
  const background=resource(document.createElement('img'),SOURCES.info.file,SOURCES.info.width,SOURCES.info.height);
  background.alt='';background.className='social-native-avatar-source';
  background.setAttribute('aria-hidden','true');
  const nick=document.createElement('output');nick.className='social-native-avatar-name';
  nick.textContent=String(options.nickname||'').slice(0,36);
  nick.setAttribute('aria-label','현재 실제 사용자 이름');
  const actor=resource(document.createElement('img'),
    avatars[inside(options.current,avatars.length)]+'.png',SOURCES.actor.width,SOURCES.actor.height);
  actor.className='social-native-avatar-preview';
  actor.alt='선택 중인 캐릭터';
  actor.dataset.originalAvatar=avatars[inside(options.current,avatars.length)];
  const selection=document.createElement('output');selection.className='social-native-avatar-selection';
  selection.setAttribute('aria-live','polite');selection.setAttribute('aria-label','미리보기 캐릭터 번호');
  scene.append(background,nick,actor,selection);
  const footer=document.createElement('div');footer.className='social-native-avatar-actions';
  const info=document.createElement('span');info.className='social-native-avatar-hint';
  info.textContent='원본 캐릭터를 선택하세요';
  const cancel=document.createElement('button');cancel.type='button';
  cancel.className='social-native-avatar-cancel';cancel.textContent='취소';
  cancel.setAttribute('aria-label','선택을 변경하지 않고 닫기');
  const confirm=document.createElement('button');confirm.type='button';
  confirm.className='social-native-avatar-confirm';confirm.textContent='선택';
  confirm.setAttribute('aria-label','선택한 원본 캐릭터 확정');
  footer.append(info,cancel,confirm);
  chooser.before(header,scene);chooser.after(footer);
  let selected=inside(options.current,avatars.length);
  function choose(i,focus=false){
   selected=inside(i,avatars.length);
   const name=avatars[selected];
   actor.dataset.originalAvatar=name;
   actor.__leafSetNativeSource(name+'.png');
   selection.textContent=(selected+1)+' / '+avatars.length;
   buttons.forEach((button,index)=>{
    button.classList.toggle('selected',index===selected);
    button.setAttribute('aria-pressed',String(index===selected));
    button.dataset.source=avatars[index]+'.png';
   });
   panel.dataset.selectedAvatar=name;
   if(focus)buttons[selected].focus({preventScroll:true});
  }
  buttons.forEach((button,i)=>{
   button.type='button';
   button.dataset.avatarIndex=String(i);
   button.setAttribute('aria-label','원본 캐릭터 '+(i+1)+'번 선택');
   button.onclick=()=>choose(i);
   const img=button.querySelector('img');
   if(img){img.alt='';img.setAttribute('aria-hidden','true')}
  });
  chooser.addEventListener('keydown',event=>{
   const index=buttons.indexOf(document.activeElement);
   if(index<0)return;
   let target=null;
   if(event.key==='ArrowRight')target=(index+1)%buttons.length;
   if(event.key==='ArrowLeft')target=(index+buttons.length-1)%buttons.length;
   if(event.key==='ArrowDown')target=(index+6)%buttons.length;
   if(event.key==='ArrowUp')target=(index+buttons.length-6)%buttons.length;
   if(event.key==='Home')target=0;
   if(event.key==='End')target=buttons.length-1;
   if(target!==null){event.preventDefault();choose(target,true)}
  });
  cancel.addEventListener('click',()=>options.onCancel?.());
  confirm.addEventListener('click',()=>options.onCommit?.(selected));
  panel.addEventListener('keydown',event=>{
   if(event.key==='Escape'){
    event.preventDefault();event.stopPropagation();options.onCancel?.();
   }
  });
  choose(selected);
  // Runtime state is used by interactive QA, not as a fabricated player list.
  currentDialog={panel,scene,chooser,buttons,actor,selection,getIndex:()=>selected};
  return true;
 }
 window.__LEAF_NATIVE_AVATAR_DIALOG__={
  enhance,
  getState:()=>currentDialog?.panel.isConnected?{
   open:true,source:currentDialog.panel.dataset.nativeAvatarDialog,
   selected:currentDialog.getIndex(),name:currentDialog.panel.dataset.selectedAvatar,
   candidates:currentDialog.buttons.length,
   actor:currentDialog.actor.dataset.originalAvatar
  }:{open:false}
 };
})();
