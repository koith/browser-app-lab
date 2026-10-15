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
 function sync(){
  remember();
  const frame=$('social-image-frame');
  if(!active()||mobile()||!frame||!messenger||!roster){restore();return}
  if(messenger.parentElement!==frame)frame.append(messenger);
  if(roster.parentElement!==frame)frame.append(roster);
  messenger.dataset.nativeOverlay='true';
  roster.dataset.nativeOverlay='true';
 }
 function start(){
  remember();
  window.addEventListener('resize',sync,{passive:true});
  window.addEventListener('leaf-route-change',sync);
  sync();
 }
 window.__LEAF_NATIVE_ROOM_PANELS__={
  beforeRender:restore,
  afterRender:sync,
  sync,
  getState:()=>({
   inRoom:active(),
   overlay:messenger?.dataset.nativeOverlay==='true',
   messengerParent:messenger?.parentElement?.id||null,
   rosterParent:roster?.parentElement?.id||null,
   messageFormCount:document.querySelectorAll('#chat-form').length,
   rosterCount:document.querySelectorAll('#social-peer-list').length
  })
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);
 else start();
})();
