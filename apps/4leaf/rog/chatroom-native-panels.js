/* Original ChatRoom/room0..5.png are 794x528 backdrops.
 * Archived actual session screenshot: chat_ref.jpg/chat.jpg shows a 407px
 * chat window floating at (about 16,0) and the real participant list at
 * upper-right, BOTH inside the scene; neither shrinks the room artwork.
 *
 * Move the real, already interactive messenger/form and the real occupancy
 * list into the 794x528 original-scene DOM rather than duplicating them or
 * painting a dead screenshot. On narrow screens return them to the normal
 * layout so the keyboard and participant chooser remain usable.
 */
(function(){
 'use strict';
 const $=id=>document.getElementById(id);
 let originalMessengerParent=null;
 let originalRosterParent=null;
 let messenger=null,roster=null;
 const mobile=()=>window.matchMedia('(max-width:650px)').matches;
 const active=()=>Boolean($('rooms')?.classList.contains('classic-chat-room')&&
  !$('rooms')?.classList.contains('hidden'));
 function remember(){
  messenger||=document.querySelector('#main > .messenger');
  roster||=document.querySelector('#rooms .social-user-panel');
  if(messenger&&!originalMessengerParent)originalMessengerParent=messenger.parentElement;
  if(roster&&!originalRosterParent)originalRosterParent=roster.parentElement;
 }
 function restore(){
  remember();
  // Required BEFORE social-chat.js frame.replaceChildren(): otherwise the
  // current frame would destroy the moved input/form and its event handlers.
  if(messenger&&originalMessengerParent&&messenger.parentElement!==originalMessengerParent)
   originalMessengerParent.append(messenger);
  if(roster&&originalRosterParent&&roster.parentElement!==originalRosterParent)
   originalRosterParent.append(roster);
  messenger?.removeAttribute('data-native-overlay');
  roster?.removeAttribute('data-native-overlay');
 }
 /* ChatRoom/userlist.png (150x38) is a green-separated SLICE ATLAS, not one
  * header picture: outer 9-slice (0..19,0..19; 6px corners), header strip
  * (21..149,0..15), inner list 9-slice (0..16,21..37; 5px corners) and two
  * 15x14 round buttons (=, updown) at y21. Template matching each piece in
  * the 2004 screenshots chat.jpg AND chat_ref.jpg (same pixels in both):
  *   outer TL corner (620,10), outer BR corner (777,132) -> 163x128 panel
  *   header strip (627,15), '=' button (760,16)
  *   inner TL corner (627,33), inner BR corner (771,124) -> 149x97 list
  * These offsets are VERIFIED anchors of the original screen. The panel is
  * composed from the source pixels here; the list stays a live DOM list. */
 const PANEL={x:620,y:10,w:163,h:128,
  header:{x:7,y:5},menu:{x:140,y:6,w:15,h:14},inner:{x:7,y:23,w:149,h:97}};
 let frameUrl=null,framePending=false;
 const isKey=(d,i)=>d[i+3]===0||(d[i]===0&&d[i+1]===255&&d[i+2]===0);
 function nineSlice(ctx,src,sx,sy,c,e,dx,dy,dw,dh){
  // c = corner size, e = edge segment length in the atlas (separated by 1px key)
  const xs=[sx,sx+c+1,sx+c+1+e+1],ys=[sy,sy+c+1,sy+c+1+e+1];
  const ws=[c,e,c],hs=[c,e,c];
  const dxs=[dx,dx+c,dx+dw-c],dys=[dy,dy+c,dy+dh-c];
  const dws=[c,dw-2*c,c],dhs=[c,dh-2*c,c];
  for(let r=0;r<3;r++)for(let q=0;q<3;q++)
   ctx.drawImage(src,xs[q],ys[r],ws[q],hs[r],dxs[q],dys[r],dws[q],dhs[r]);
 }
 function composeFrame(){
  if(frameUrl||framePending||location.protocol==='file:')return;
  framePending=true;
  const img=new Image();
  img.onload=()=>{
   try{
    const key=document.createElement('canvas');
    key.width=img.naturalWidth;key.height=img.naturalHeight;
    const k=key.getContext('2d',{willReadFrequently:true});
    k.drawImage(img,0,0);
    const data=k.getImageData(0,0,key.width,key.height);
    for(let i=0;i<data.data.length;i+=4)if(isKey(data.data,i))data.data[i+3]=0;
    k.putImageData(data,0,0);
    const out=document.createElement('canvas');out.width=PANEL.w;out.height=PANEL.h;
    const ctx=out.getContext('2d');ctx.imageSmoothingEnabled=false;
    nineSlice(ctx,key,0,0,6,6,0,0,PANEL.w,PANEL.h);
    nineSlice(ctx,key,0,21,5,5,PANEL.inner.x,PANEL.inner.y,PANEL.inner.w,PANEL.inner.h);
    frameUrl=out.toDataURL('image/png');
    apply();
   }catch{if(roster)roster.dataset.nativeFrame='fallback'}
  };
  img.onerror=()=>{framePending=false;if(roster)roster.dataset.nativeFrame='error'};
  img.src='./original/ChatRoom/userlist.png';
 }
 function menuButton(){
  let button=roster.querySelector('.leaf-native-userlist-menu');
  if(button)return button;
  button=document.createElement('button');
  button.type='button';button.className='leaf-native-userlist-menu';
  button.dataset.source='ChatRoom/userlist.png#33,21,15,14';
  button.setAttribute('aria-label','참여자목록 메뉴 · 다른 기기 연결');
  button.title='다른 기기 연결';
  // The '=' glyph is the source panel's own button; it opens the existing
  // real invite workflow (#social-invite), no new feature is invented.
  button.addEventListener('click',event=>{
   event.stopPropagation();
   document.getElementById('social-invite')?.click();
  });
  roster.querySelector('.social-user-titlebar')?.append(button);
  return button;
 }
 function apply(){
  if(!roster||roster.dataset.nativeOverlay!=='true')return;
  menuButton();
  if(frameUrl){
   roster.style.setProperty('--leaf-userlist-frame','url("'+frameUrl+'")');
   roster.dataset.nativeFrame='userlist.png-9slice';
  }else composeFrame();
 }
 function sync(){
  remember();
  const frame=$('social-image-frame');
  if(!active()||mobile()||!frame||!messenger||!roster){restore();return}
  if(messenger.parentElement!==frame)frame.append(messenger);
  if(roster.parentElement!==frame)frame.append(roster);
  messenger.dataset.nativeOverlay='true';
  roster.dataset.nativeOverlay='true';
  apply();
 }

 /* Original toolbar belongs to MainFrame/title outside 794x528 photo.
  * Move the EXISTING live controls to preserve event handlers/permissions. */
 const CHROME_QUERY='(min-width:801px) and (min-height:640px)';
 const chromeFits=()=>window.matchMedia(CHROME_QUERY).matches;
 function chromeHost(){
  const title=document.querySelector('#app>.titlebar');
  if(!title)return null;
  let host=title.querySelector('.leaf-room-mainframe-tools');
  if(!host){
   host=document.createElement('div');host.className='leaf-room-mainframe-tools';
   const grip=document.createElement('span');grip.className='leaf-room-toolbar-grip';
   grip.setAttribute('aria-hidden','true');grip.dataset.source='MainFrame/toolbarmove.png';
   host.append(grip);title.append(host);
  }
  return host;
 }
 function homeChrome(){
  const host=document.querySelector('#app>.titlebar .leaf-room-mainframe-tools');
  if(!host)return;
  const bar=host.querySelector('.social-classic-toolbar');
  if(bar)$('rooms')?.querySelector('.social-header')?.append(bar);
  const close=host.querySelector('#social-close-room');
  if(close)$('rooms')?.querySelector('.social-header-tools')?.prepend(close);
  document.documentElement.classList.remove('leaf-room-mainframe');
 }
 function placeChrome(){
  if(!active()||!chromeFits()){homeChrome();return}
  const host=chromeHost();if(!host)return;
  const bar=$('rooms')?.querySelector('.social-classic-toolbar');
  if(bar&&bar.parentElement!==host)host.append(bar);
  if(bar){delete bar.dataset.webPositionInferred;bar.dataset.nativeHost='MainFrame/title'}
  const close=$('social-close-room');
  if(close&&close.parentElement!==host)host.append(close);
  document.documentElement.classList.add('leaf-room-mainframe');
 }
 /* The original photograph anchors nickname labels above the 141px
  * Registry canvas. Collision offsets remain INFERRED, deterministic and
  * constrained to the source room bounds; not client-decoded positions. */
 const TAG_GAP=2;
 const TAG_STEPS=[[0,0],[-16,0],[16,0],[-32,0],[32,0],[-48,0],[48,0],
  [0,-18],[-24,-18],[24,-18],[-48,-18],[48,-18],[0,-36],[-32,-36],[32,-36]];
 let tagFrame=0;
 function layoutTags(){
  tagFrame=0;
  const frame=$('social-image-frame');
  if(!active()||!frame)return;
  const fr=frame.getBoundingClientRect();
  if(fr.width<1)return;
  const scale=fr.width/794;
  const figures=[...frame.querySelectorAll('#social-avatar-layer .social-avatar')]
   .map(el=>({el,tag:el.querySelector('.social-avatar-name'),
    y:parseFloat(el.style.top)||0,x:parseFloat(el.style.left)||0}))
   .filter(f=>f.tag)
   .sort((a,b)=>b.y-a.y||a.x-b.x);
  const placed=[];
  for(const f of figures){
   f.tag.style.setProperty('--leaf-tag-dx','0px');
   f.tag.style.setProperty('--leaf-tag-dy','0px');
   const r=f.tag.getBoundingClientRect();
   const base={l:(r.left-fr.left)/scale,t:(r.top-fr.top)/scale,w:r.width/scale,h:r.height/scale};
   let chosen=TAG_STEPS[0];
   for(const step of TAG_STEPS){
    const c={l:base.l+step[0],t:base.t+step[1],w:base.w,h:base.h};
    if(c.l<0||c.l+c.w>794||c.t<0)continue;
    const collides=placed.some(p=>c.l<p.l+p.w+TAG_GAP&&p.l<c.l+c.w+TAG_GAP&&
     c.t<p.t+p.h+TAG_GAP&&p.t<c.t+c.h+TAG_GAP);
    if(!collides){chosen=step;break}
   }
   f.tag.style.setProperty('--leaf-tag-dx',chosen[0]+'px');
   f.tag.style.setProperty('--leaf-tag-dy',chosen[1]+'px');
   f.tag.dataset.tagShift=chosen.join(',');
   placed.push({l:base.l+chosen[0],t:base.t+chosen[1],w:base.w,h:base.h});
  }
 }
 const scheduleTags=()=>{if(!tagFrame)tagFrame=requestAnimationFrame(layoutTags)};
 let tagObserver=null;
 function watchTags(){
  const frame=$('social-image-frame');
  if(!frame||tagObserver)return;
  // Exclude our own tag style writes to avoid observer/requestAnimationFrame loop.
  tagObserver=new MutationObserver(records=>{
   if(records.some(r=>!(r.type==='attributes'&&r.target.classList?.contains('social-avatar-name'))))
    scheduleTags();
  });
  tagObserver.observe(frame,{childList:true,subtree:true,
   attributes:true,attributeFilter:['style'],characterData:true});
 }
 function before(){homeChrome();restore()}
 function after(){sync();placeChrome();watchTags();scheduleTags()}
 function start(){
  remember();
  window.addEventListener('resize',()=>{
   sync();requestAnimationFrame(()=>{placeChrome();scheduleTags()})
  },{passive:true});
  window.addEventListener('leaf-route-change',()=>{sync();placeChrome()});
  sync();placeChrome();watchTags();
 }
 window.__LEAF_NATIVE_ROOM_PANELS__={
  beforeRender:before,
  afterRender:after,
  sync,layoutTags,
  getState:()=>({
   inRoom:active(),
   overlay:messenger?.dataset.nativeOverlay==='true',
   messengerParent:messenger?.parentElement?.id||null,
   rosterParent:roster?.parentElement?.id||null,
   messageFormCount:document.querySelectorAll('#chat-form').length,
   rosterCount:document.querySelectorAll('#social-peer-list').length,
   userlistFrame:roster?.dataset.nativeFrame||'pending',
   toolbarHost:$('rooms')?.querySelector('.social-classic-toolbar')?.closest('.leaf-room-mainframe-tools')?'MainFrame/title':
    $('rooms')?.querySelector('.social-classic-toolbar')?.parentElement?.id||'header',
   userlistAnchors:PANEL
  })
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);
 else start();
})();
