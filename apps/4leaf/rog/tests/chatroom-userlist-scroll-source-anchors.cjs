'use strict';
/* ChatRoom participant panel + chat-log scrollbar vs the 2004 screenshots.
 * Anchors below were measured by template matching the ORIGINAL sprite
 * pieces (ChatRoom/userlist.png, ChatRoom/scrollbar.png) in chat.jpg and
 * chat_ref.jpg (tools/chatroom-anchor-audit.py): VERIFIED screen anchors.
 * Every checked control stays a live DOM control (two real browser
 * participants per room, no screenshot overlay). All six source rooms.
 * FOURLEAF_BROWSER=webkit runs the same checks in WebKit. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const ANCHOR={
 panel:[620,10,163,128],header:[627,15,129,16],menu:[760,16,15,14],
 list:[628,35,143,93],
 logUp:[406,78,13,9],logDown:[406,87,13,9],logTrack:[406,19,13,56],logColumn:[406,0,16,97]
};
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:
  {args:['--no-sandbox'],ignoreDefaultArgs:['--hide-scrollbars']});
 const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const host=await context.newPage(),guest=await context.newPage();
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const errors=[],report=[];
 for(const page of [host,guest]){
  page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__,null,{timeout:15000});
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
 }
 try{
  for(let bg=0;bg<6;bg++){
   const rid=await host.evaluate(bg=>{window.__LEAF_SOCIAL__.openDirectory();
    return window.__LEAF_SOCIAL__.createRoom('원본 참여자목록 '+bg,bg,12)},bg);
   await guest.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
   await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),rid,{timeout:15000});
   await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),rid);
   await host.waitForFunction(()=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===2&&
    document.getElementById('social-peer-panel')?.dataset.nativeFrame==='userlist.png-9slice',null,{timeout:15000});
   const m=await host.evaluate(()=>{
    const frame=document.getElementById('social-image-frame').getBoundingClientRect();
    const box=sel=>{const r=document.querySelector(sel).getBoundingClientRect();
     return [r.left-frame.left,r.top-frame.top,r.width,r.height].map(v=>Math.round(v*100)/100)};
    const hit=sel=>{const el=document.querySelector(sel),r=el.getBoundingClientRect();
     const t=document.elementFromPoint(r.left+r.width/2,r.top+Math.min(r.height/2,6));
     return t===el||el.contains(t)};
    const list=document.getElementById('social-peer-list');
    return {bg:getComputedStyle(document.getElementById('social-image-frame')).backgroundImage,
     panel:box('#social-peer-panel'),header:box('#social-original-userlist'),
     menu:box('.leaf-native-userlist-menu'),list:box('#social-peer-list'),
     logUp:box('#social-native-scroll-up'),logDown:box('#social-native-scroll-down'),
     logTrack:box('#social-native-scroll-track'),logColumn:box('#social-native-chat-scroll'),
     hits:{menu:hit('.leaf-native-userlist-menu'),row:hit('#social-peer-list .social-user-row'),
      up:hit('#social-native-scroll-up'),down:hit('#social-native-scroll-down'),
      track:hit('#social-native-scroll-track'),input:hit('#message')},
     rows:[...list.querySelectorAll('.social-user-row')].map(r=>r.textContent),
     rowFont:getComputedStyle(list.querySelector('.social-user-row')).fontSize,
     listScrollbar:list.offsetWidth-list.clientWidth,
     count:document.getElementById('social-native-user-count').textContent,
     headerCanvas:[document.getElementById('social-original-userlist').width,
      document.getElementById('social-original-userlist').height],
     arrowOpacity:getComputedStyle(document.getElementById('social-native-scroll-up')).opacity,
     frameUrl:getComputedStyle(document.getElementById('social-peer-panel')).getPropertyValue('--leaf-userlist-frame').length};
   });
   assert.ok(m.bg.includes('/original/ChatRoom/room'+bg+'.png'),'room '+bg+' source backdrop');
   for(const k of Object.keys(ANCHOR))
    assert.ok(m[k].every((v,i)=>Math.abs(v-ANCHOR[k][i])<=0.5),
     'room '+bg+' '+k+' '+JSON.stringify(m[k])+' must equal source anchor '+JSON.stringify(ANCHOR[k]));
   assert.ok(Object.values(m.hits).every(Boolean),'room '+bg+' live controls are physically hittable '+JSON.stringify(m.hits));
   assert.equal(m.rows.length,2,'two real participants listed, no fabricated names');
   assert.equal(m.count,'2 명','the original chat.jpg shows a space before 명');
   assert.equal(m.rowFont,'12px');
   assert.deepEqual(m.headerCanvas,[150,38],'the decoded 150x38 source canvas is kept and cropped');
   assert.equal(m.arrowOpacity,'1','source arrows are never dimmed (atlas has no disabled cell)');
   assert.ok(m.frameUrl>100,'panel painted from the composed source 9-slice');
   if(engine==='chromium')assert.equal(m.listScrollbar,13,'live 13px source-art scrollbar column in the list');
   report.push({room:bg,ok:true});
  }
  // Composed panel pixels == source atlas pixels (corners and inner corners).
  const pixels=await host.evaluate(async()=>{
   const url=getComputedStyle(document.getElementById('social-peer-panel'))
    .getPropertyValue('--leaf-userlist-frame').trim().replace(/^url\("?|"?\)$/g,'');
   const load=src=>new Promise((ok,no)=>{const i=new Image();i.onload=()=>ok(i);i.onerror=no;i.src=src});
   const [frame,atlas]=await Promise.all([load(url),load('./original/ChatRoom/userlist.png')]);
   const read=(img,x,y,w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;
    const g=c.getContext('2d');g.drawImage(img,x,y,w,h,0,0,w,h);return [...g.getImageData(0,0,w,h).data]};
   const key=a=>{for(let i=0;i<a.length;i+=4)if(a[i+3]===0||(a[i]===0&&a[i+1]===255&&a[i+2]===0))a[i]=a[i+1]=a[i+2]=a[i+3]=0;return a};
   const same=(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i]);
   return {size:[frame.naturalWidth,frame.naturalHeight],
    outerTL:same(read(frame,0,0,6,6),key(read(atlas,0,0,6,6))),
    outerBR:same(read(frame,157,122,6,6),key(read(atlas,14,14,6,6))),
    innerTL:same(read(frame,7,23,5,5),key(read(atlas,0,21,5,5))),
    innerBR:same(read(frame,151,115,5,5),key(read(atlas,12,33,5,5)))};
  });
  assert.deepEqual(pixels,{size:[163,128],outerTL:true,outerBR:true,innerTL:true,innerBR:true},
   'composed panel corners are byte-identical source pixels '+JSON.stringify(pixels));
  // The live controls still work: '=' opens the existing invite workflow,
  // relocated log arrows still scroll the one real chat log.
  await host.locator('.leaf-native-userlist-menu').click();
  await host.waitForSelector('#social-create-offer',{timeout:5000});
  await host.locator('#social-modal .social-modal-title button[aria-label="닫기"]').click();
  await host.waitForFunction(()=>!document.getElementById('social-modal'));
  for(let i=0;i<14;i++)await host.evaluate(i=>window.__LEAF_SOCIAL__.send('원본 스크롤 확인 '+i),i);
  await host.waitForFunction(()=>{const l=document.getElementById('chat-log');return l.scrollHeight-l.clientHeight>40},null,{timeout:8000});
  const scrolled=await host.evaluate(async()=>{
   const l=document.getElementById('chat-log');l.scrollTop=l.scrollHeight;
   await new Promise(r=>setTimeout(r,50));const end=l.scrollTop;
   return end});
  await host.locator('#social-native-scroll-up').click({force:false});
  const afterUp=await host.evaluate(()=>document.getElementById('chat-log').scrollTop);
  assert.ok(afterUp<scrolled,'source up arrow at (406,78) scrolls the real log up');
  await host.locator('#social-native-scroll-down').click();
  const afterDown=await host.evaluate(()=>document.getElementById('chat-log').scrollTop);
  assert.ok(afterDown>afterUp,'source down arrow at (406,87) scrolls the real log down');
  assert.deepEqual(errors,[]);
  console.log('CHATROOM USERLIST/SCROLL SOURCE ANCHORS PASS',JSON.stringify({engine,rooms:report.length,anchors:ANCHOR,pixels}));
 }finally{await browser.close();}
})().catch(e=>{console.error('CHATROOM USERLIST/SCROLL SOURCE ANCHORS FAILED',e.stack||e);process.exit(1);});
