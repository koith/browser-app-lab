'use strict';
/* 4LEAF ChatRoom screen module (P0-CHAT, 2026-11-19).
 *
 * One owner for what the 794x528 original room SHOWS about its participants:
 *  - chat log lines   "닉네임 : 내용"  and presence lines "- 닉네임 님이 나갔습니다. -"
 *  - speech balloons  built from ChatRoom/talkbox.png, laid out as in the 2004
 *                     captures (apps/4leaf/assets/chat.jpg, chat_ref.jpg)
 * Transport, room model, seats and the live DOM controls stay in social-chat.js.
 *
 * Original evidence (VERIFIED from the two 794x528 captures):
 *  - log lines read  "fallenstar : [루] 그런데 ..."  -> name, " : ", text; no time stamp;
 *  - a leave line reads "- 하멜론 님이 나갔습니다. -";
 *  - a balloon is a white rounded box whose TOP carries the speaker's own blue
 *    name tag; the text sits below the tag; the box ends at the speaker's head
 *    ("I에헤야디야" 193..240 over a head at ~255; "아르티웬" two lines);
 *  - balloons are drawn over the whole scene and stay inside the 794px room.
 * INFERRED: the join line wording ("님이 들어왔습니다"), the 5 s balloon life,
 * the 160px wrap width and a 1.5 s grace period in which the occupants already in
 * a room are taken as the starting list (no join lines for them).
 */
(function(){
 const ROOM_W=794,ROOM_H=528;
 const WRAP=160,PAD_X=8,PAD_TOP=5,PAD_BOTTOM=7,GAP=2,LIFE=5000,GRACE=1500;
 const $=id=>document.getElementById(id);

 // ---- ChatRoom/talkbox.png (47x100): 9-slice body x0..24,y0..23 + 12x15 tail at x25,y0.
 const atlas=new Image();atlas.decoding='async';
 let source=null,tries=0;const waiting=new Set();
 function loadAtlas(){atlas.src='./original/ChatRoom/talkbox.png'+(tries?'?retry='+tries:'')}
 atlas.onload=()=>{
  if(atlas.naturalWidth!==47||atlas.naturalHeight!==100)return;
  const c=document.createElement('canvas');c.width=47;c.height=100;
  const x=c.getContext('2d',{willReadFrequently:true});x.drawImage(atlas,0,0);
  let px;try{px=x.getImageData(0,0,47,100)}catch{waiting.clear();return}
  for(let i=0;i<px.data.length;i+=4){const r=px.data[i],g=px.data[i+1],b=px.data[i+2];
   if((r>=245&&g<=20&&b<=20)||(r===0&&g===255&&b===0))px.data[i+3]=0}
  x.putImageData(px,0,0);source=c;
  for(const b of waiting)if(b.isConnected)paint(b);waiting.clear();
 };
 atlas.onerror=()=>{if(tries<5){tries++;setTimeout(loadAtlas,200*2**tries)}};
 loadAtlas();

 function paint(bubble){
  const canvas=bubble.querySelector('canvas.native-talkbox-canvas');
  if(!canvas)return;
  if(!source){waiting.add(bubble);return}
  const w=Math.round(parseFloat(bubble.style.width)),h=Math.round(parseFloat(bubble.style.height));
  const tail=bubble.dataset.tail==='true'?14:0;
  const ratio=Math.min(3,Math.max(1,window.devicePixelRatio||1));
  canvas.width=Math.ceil(w*ratio);canvas.height=Math.ceil((h+tail)*ratio);
  canvas.style.width=w+'px';canvas.style.height=(h+tail)+'px';
  const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.imageSmoothingEnabled=false;
  ctx.clearRect(0,0,w,h+tail);
  const d=(sx,sy,sw,sh,x,y,ww,hh)=>ctx.drawImage(source,sx,sy,sw,sh,x,y,ww,hh);
  const L=9,R=10,T=9,B=9,mx=Math.max(1,w-L-R),my=Math.max(1,h-T-B);
  d(0,0,9,9,0,0,L,T);d(10,0,4,9,L,0,mx,T);d(15,0,10,9,w-R,0,R,T);
  d(0,10,9,4,0,T,L,my);d(10,10,4,4,L,T,mx,my);d(15,10,10,4,w-R,T,R,my);
  d(0,15,9,9,0,h-B,L,B);d(10,15,4,9,L,h-B,mx,B);d(15,15,10,9,w-R,h-B,R,B);
  if(tail){const tx=Math.max(4,Math.min(w-16,Number(bubble.dataset.tailX)-6));d(25,0,12,15,tx,h-1,12,15)}
  bubble.dataset.nativeTalkboxReady='true';
  bubble.dataset.nativeSource='ChatRoom/talkbox.png';
  bubble.dataset.nativeWidth=String(w);bubble.dataset.nativeHeight=String(h);
 }

 // ---- balloons ------------------------------------------------------------
 const frame=()=>$('social-image-frame');
 function speechLayer(){
  const layer=$('social-avatar-layer');if(!layer)return null;
  let s=layer.querySelector(':scope>.leaf-speech-layer');
  if(!s){s=document.createElement('div');s.className='leaf-speech-layer';s.setAttribute('aria-live','polite');layer.append(s)}
  return s;
 }
 const toRoom=(r,fr,k)=>({l:(r.left-fr.left)/k,t:(r.top-fr.top)/k,w:r.width/k,h:r.height/k});
 function place(bubble){
  const f=frame();if(!f||!bubble.isConnected)return;
  const node=[...f.querySelectorAll('#social-avatar-layer .social-avatar')].find(n=>n.dataset.peer===bubble.dataset.peer);
  if(!node){bubble.remove();return}
  const fr=f.getBoundingClientRect();const k=fr.width/ROOM_W||1;
  const tag=node.querySelector('.social-avatar-name');
  const img=node.querySelector('img');
  const ir=toRoom(img.getBoundingClientRect(),fr,k);
  // Use the tag's home position above the avatar: the web collision layout
  // (chatroom-native-panels.js) may have pushed it sideways, but in the
  // captures the balloon and its tag sit straight above the speaker.
  const tr=toRoom(tag.getBoundingClientRect(),fr,k);
  const [sx,sy]=String(tag.dataset.tagShift||'0,0').split(',').map(Number);
  tr.l-=sx||0;tr.t-=sy||0;
  const text=bubble.querySelector('.native-talkbox-text');
  // measure the natural one-line width, then wrap at WRAP px (room units)
  const probe=text.cloneNode(true);
  Object.assign(probe.style,{position:'absolute',visibility:'hidden',whiteSpace:'nowrap',width:'auto',maxWidth:'none',left:'0',top:'0'});
  bubble.append(probe);const natural=probe.getBoundingClientRect().width/k;probe.remove();
  const tw=Math.min(WRAP,Math.ceil(natural)+1);
  text.style.maxWidth='none';text.style.width=tw+'px';
  const th=Math.ceil(text.getBoundingClientRect().height/k);
  const w=Math.max(48,Math.max(tw,Math.ceil(tr.w))+PAD_X*2);
  const h=PAD_TOP+Math.ceil(tr.h)+GAP+th+PAD_BOTTOM;
  const cx=ir.l+ir.w/2;tr.l=cx-tr.w/2;
  let left=Math.round(Math.max(2,Math.min(ROOM_W-2-w,cx-w/2)));
  let top=Math.round(Math.max(0,tr.t-PAD_TOP));
  // The body reaches the head: the 75x141 Registry canvas has ~13px of
  // transparent rows above the hair (measured on the source PNGs).
  const head=ir.t+13;
  bubble.dataset.tail=String(top+h+6<head);
  bubble.dataset.tailX=String(Math.round(cx-left));
  Object.assign(bubble.style,{left:left+'px',top:top+'px',width:w+'px',height:h+'px'});
  text.style.left=Math.round((w-tw)/2)+'px';
  text.style.top=(PAD_TOP+Math.ceil(tr.h)+GAP)+'px';
  // the speaker's own tag rides on the balloon top, like the capture
  const label=bubble.querySelector('.leaf-speech-tag');
  label.textContent=tag.textContent;
  label.style.left=Math.round(tr.l-left)+'px';label.style.top=Math.round(tr.t-top)+'px';
  label.style.width=Math.ceil(tr.w)+'px';label.style.height=Math.ceil(tr.h)+'px';
  const cs=getComputedStyle(tag);
  for(const p of ['font','color','background','borderTop','borderRight','borderBottom','borderLeft','borderRadius','textShadow','lineHeight','letterSpacing','boxShadow','textAlign','paddingLeft','paddingRight'])label.style[p]=cs[p];
  tag.style.visibility='hidden';bubble.__tag=tag;
  bubble.style.visibility='';
  paint(bubble);
 }
 function placeAll(){for(const b of document.querySelectorAll('#social-avatar-layer .leaf-speech-layer>.social-speech'))place(b)}
 let raf=0;const schedule=()=>{if(!raf)raf=requestAnimationFrame(()=>{raf=0;placeAll();mountRoster();roster?.sync?.()})};
 function say(peer,text){
  const layer=speechLayer();if(!layer)return false;
  for(const old of layer.querySelectorAll('.social-speech'))if(old.dataset.peer===String(peer)){old.remove();if(old.__tag)old.__tag.style.visibility=''}
  const bubble=document.createElement('div');
  bubble.className='social-speech native-talkbox-applied';bubble.dataset.peer=String(peer);
  bubble.setAttribute('role','status');bubble.style.visibility='hidden';
  const canvas=document.createElement('canvas');canvas.className='native-talkbox-canvas';
  canvas.setAttribute('aria-hidden','true');canvas.dataset.source='ChatRoom/talkbox.png';
  const label=document.createElement('span');label.className='leaf-speech-tag';label.setAttribute('aria-hidden','true');
  const body=document.createElement('span');body.className='native-talkbox-text';body.textContent=String(text);
  bubble.append(canvas,label,body);layer.append(bubble);
  place(bubble);
  setTimeout(()=>{if(bubble.isConnected)bubble.remove();if(bubble.__tag)bubble.__tag.style.visibility=''},LIFE);
  return true;
 }

 // ---- chat log lines ------------------------------------------------------
 function messageLine(m){
  const el=document.createElement('div');el.className='social-chat-message';
  const name=document.createElement('b');name.textContent=String(m.user);
  const msg=document.createElement('span');msg.textContent=' : '+String(m.text);
  el.append(name,msg);
  if(m.time)el.dataset.time=String(m.time);
  return el;
 }
 function noticeLine(text){
  const el=document.createElement('div');el.className='social-system-line leaf-presence-line';
  el.textContent='- '+text+' -';return el;
 }
 function append(line){
  const log=$('chat-log');if(!log)return;
  if(window.__LEAF_CHAT_APPEND__)return window.__LEAF_CHAT_APPEND__(log,line,110);
  const follow=log.scrollHeight-log.clientHeight-log.scrollTop<=3;
  log.append(line);if(follow)log.scrollTop=log.scrollHeight;
  window.__LEAF_NATIVE_SCROLLBAR__?.update?.();
 }

 // ---- presence (join / leave lines) ---------------------------------------
 let presenceRoom=null,presenceSince=0,settled=false,serverSeen=false,known=new Map();
 function occupants(roomId,people,opts={}){
  const now=Date.now();
  const next=new Map(people.map(p=>[String(p.id),String(p.nick)]));
  if(roomId!==presenceRoom){presenceRoom=roomId;presenceSince=now;settled=false;serverSeen=false;known=next;return}
  // Baseline = the room as found: no join lines for people already inside.
  // Central rooms: the first server snapshot of this room is authoritative
  // (local self-only rosters before it are not). Offline/BroadcastChannel
  // rooms have no snapshot, so they settle after GRACE.
  if(opts.central)return; // only an authoritative snapshot can announce online membership changes
  if(!settled){
   if(now-presenceSince>GRACE){settled=true;known=next;return}
   known=next;return;
  }
  for(const [id,nick] of next)if(!known.has(id))append(noticeLine(nick+' 님이 들어왔습니다.'));
  for(const [id,nick] of known)if(!next.has(id))append(noticeLine(nick+' 님이 나갔습니다.'));
  known=next;
 }
 function beginRoom(roomId,people){
  presenceRoom=roomId;presenceSince=Date.now();settled=true;serverSeen=true;
  known=new Map(people.map(p=>[String(p.id),String(p.nick)]));
 }
 function serverRoster(roomId,people){
  if(!Array.isArray(people))return;
  if(roomId!==presenceRoom||!settled){beginRoom(roomId,people);return}
  const next=new Map(people.map(p=>[String(p.id),String(p.nick)]));
  for(const [id,nick] of next)if(!known.has(id))append(noticeLine(nick+' 님이 들어왔습니다.'));
  for(const [id,nick] of known)if(!next.has(id))append(noticeLine(nick+' 님이 나갔습니다.'));
  known=next;serverSeen=true;
 }
 function leftRoom(){presenceRoom=null;settled=false;serverSeen=false;known=new Map()}

 // keep balloons on their tags when tags/avatars move or the room rescales
 /* Roster scrollbar. chat.jpg (VERIFIED): with 10 participants the
    roster shows 5 rows and a scroll column at x758..771 — thin track from
    y~35, white pill thumb, up/down cells stacked at the bottom (y110/119) —
    the same ChatRoom/scrollbar.png cells as the log column. The thumb uses
    atlas rows 19..34 only (rows 35..39 hold are black key/shadow pixels that do
    not appear in chat.jpg) - INFERRED. */
 let roster=null;
 function mountRoster(){
  const panel=$('social-peer-panel'),list=$('social-peer-list');
  if(!panel||!list||roster?.isConnected)return;
  roster=document.createElement('div');roster.id='leaf-roster-scroll';roster.setAttribute('aria-hidden','true');
  roster.innerHTML='<div id="leaf-roster-scroll-track"><div id="leaf-roster-scroll-thumb"></div></div>'+
   '<button type="button" id="leaf-roster-scroll-up" tabindex="-1" aria-label="위로"></button>'+
   '<button type="button" id="leaf-roster-scroll-down" tabindex="-1" aria-label="아래로"></button>';
  panel.appendChild(roster);
  const track=roster.firstChild,thumb=track.firstChild,ROW=16;
  const sync=()=>{
   const over=list.scrollHeight-list.clientHeight;roster.dataset.overflow=over>1?'true':'false';
   const th=16,room=Math.max(0,track.clientHeight-th);
   thumb.style.top=Math.round(over>0?room*list.scrollTop/over:0)+'px';
  };
  list.addEventListener('scroll',sync,{passive:true});
  roster.querySelector('#leaf-roster-scroll-up').onclick=()=>{list.scrollTop-=ROW;sync()};
  roster.querySelector('#leaf-roster-scroll-down').onclick=()=>{list.scrollTop+=ROW;sync()};
  track.addEventListener('pointerdown',e=>{
   const r=track.getBoundingClientRect(),over=list.scrollHeight-list.clientHeight;
   const move=ev=>{list.scrollTop=over*Math.min(1,Math.max(0,(ev.clientY-r.top-8)/Math.max(1,r.height-16)));sync()};
   move(e);track.setPointerCapture?.(e.pointerId);
   track.onpointermove=ev=>{if(ev.buttons)move(ev)};
  });
  new MutationObserver(sync).observe(list,{childList:true});
  roster.sync=sync;sync();
 }
 function watch(){
  mountRoster();
  const panels=window.__LEAF_NATIVE_ROOM_PANELS__;
  if(panels&&!panels.__screenWrapped){
   const original=panels.layoutTags;
   panels.layoutTags=function(){const r=original.apply(this,arguments);schedule();return r};
   panels.__screenWrapped=true;
  }
  const rooms=$('rooms');
  if(rooms)new MutationObserver(records=>{
   // ignore our own writes to balloons / hidden tags
   if(records.some(r=>!r.target.closest?.('.leaf-speech-layer,#leaf-roster-scroll')&&!(r.target.classList?.contains('social-avatar-name')&&r.attributeName==='style')))schedule();
  }).observe(rooms,{subtree:true,attributes:true,attributeFilter:['style','class'],childList:true});
  window.addEventListener('resize',schedule,{passive:true});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',watch);else watch();

 window.__LEAF_CHATROOM_SCREEN__={say,messageLine,noticeLine,occupants,beginRoom,serverRoster,leftRoom,placeAll,
  getState:()=>({ready:Boolean(source),room:presenceRoom,known:[...known.values()],
   balloons:document.querySelectorAll('#social-avatar-layer .leaf-speech-layer>.social-speech').length})};
 // compatibility for callers/tests that read the former talkbox module
 window.__LEAF_NATIVE_TALKBOX__={apply(){},getState:()=>({ready:Boolean(source),width:source?.width||0,height:source?.height||0,waiting:waiting.size})};
})();
