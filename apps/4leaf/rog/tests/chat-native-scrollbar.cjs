const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 // Inspect actual HTTP or public Pages local ChatRoom UI. Central
 // admission remains independently covered by central-browser.cjs.
 await context.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__LEAF_NATIVE_ROOM_PANELS__&&window.__LEAF_NATIVE_SCROLLBAR__);
  assert.equal(await page.locator('#social-native-chat-scroll').count(),1,'only one real persistent chat transcript scrollbar exists');
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('원본 대화창 스크롤 검증',4);
  });
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden)');
  await page.waitForFunction(()=>window.__LEAF_NATIVE_ROOM_PANELS__.getState().overlay===true);
  await page.waitForFunction(()=>window.__LEAF_NATIVE_SCROLLBAR__.getState().ready===true,null,{timeout:14000});
  const source=await page.evaluate(async()=>{
   const src=new Image();src.src='./original/ChatRoom/scrollbar.png';await src.decode();
   const control=document.getElementById('social-native-chat-scroll');
   const up=document.getElementById('social-native-scroll-up');
   const down=document.getElementById('social-native-scroll-down');
   const track=document.getElementById('social-native-scroll-track');
   const sourceCanvas=document.createElement('canvas');sourceCanvas.width=src.naturalWidth;sourceCanvas.height=src.naturalHeight;
   const ctx=sourceCanvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(src,0,0);
   const p=ctx.getImageData(0,0,src.naturalWidth,src.naturalHeight).data;
   let keyed=0,nonKey=0;for(let i=0;i<p.length;i+=4){if(p[i+1]>220&&p[i]<65&&p[i+2]<90)keyed++;else if(p[i+3]>0)nonKey++}
   return {dimensions:[src.naturalWidth,src.naturalHeight],keyed,nonKey,
    rendered:control.dataset.ready,
    inMessenger:control.parentElement.classList.contains('messenger'),
    parentFrame:control.parentElement.parentElement.id,
    computed:getComputedStyle(control).display,
    size:[parseFloat(getComputedStyle(up).width),parseFloat(getComputedStyle(down).width)],
    art:getComputedStyle(up).backgroundImage,
    role:track.getAttribute('role'),controls:track.getAttribute('aria-controls'),
    count:document.querySelectorAll('#chat-log').length};
  });
  console.log('SOURCE 52x40 PIXEL DIAGNOSTICS',JSON.stringify(source));
  assert.deepEqual(source.dimensions,[52,40],'source ChatRoom native scrollbar sprite is 52x40');
  assert.ok(source.keyed>30&&source.nonKey>50,'native bright-green key and real visible artwork both exist in source');
  assert.equal(source.rendered,'true','source PNG was decoded and chroma keyed rather than displayed as neon green');
  assert.equal(source.parentFrame,'social-image-frame','actual scrollbar moves with existing original room chat pane');
  assert.equal(source.count,1,'no fake secondary transcript replaces the native original room chat');
  assert.equal(source.computed,'flex','original 13px vertical scrollbar appears beside actual conversation');
  assert.deepEqual(source.size,[13,13],'both native sprites have original 13px column width');
  assert.ok(source.art.includes('data:image/png;base64,'),'original source pixels are actually painted with keyed native canvas data');
  assert.equal(source.role,'scrollbar','source decoration has accessible real scrollbar semantics');
  assert.equal(source.controls,'chat-log');

  for(let i=0;i<29;i++)await page.evaluate(i=>window.__LEAF_SOCIAL__.send('원작 채팅 스크롤 실제 전송 '+String(i).padStart(2,'0')),i);
  await page.waitForFunction(()=>window.__LEAF_NATIVE_SCROLLBAR__?.getState().overflow>150,null,{timeout:14000});
  const log=page.locator('#chat-log');
  await log.evaluate(el=>{el.scrollTop=el.scrollHeight});
  await page.waitForFunction(()=>Number(document.getElementById('social-native-scroll-track')?.getAttribute('aria-valuenow'))>=99);
  const bottom=await log.evaluate(el=>el.scrollTop);
  assert.ok(bottom>150,'genuine chat transcript has overflow after actual sent messages');
  await page.locator('#social-native-scroll-up').click();
  const lifted=await log.evaluate(el=>el.scrollTop);
  assert.ok(lifted<bottom-30,'source UP button scrolls the same real chat messages to older history');
  await page.locator('#social-native-scroll-down').click();
  const returned=await log.evaluate(el=>el.scrollTop);
  assert.ok(returned>lifted+30,'source DOWN button returns toward latest real chat messages');
  await page.locator('#social-native-scroll-track').click({position:{x:5,y:5}});
  const top=await log.evaluate(el=>el.scrollTop);
  assert.ok(top<returned-30,'native original track clicks seek the real scroll position');
  const thumb=page.locator('#social-native-scroll-thumb');
  const t=await thumb.boundingBox();
  await page.mouse.move(t.x+t.width/2,t.y+t.height/2);
  await page.mouse.down();
  await page.mouse.move(t.x+t.width/2,t.y+t.height/2+25,{steps:6});
  await page.mouse.up();
  const dragged=await log.evaluate(el=>el.scrollTop);
  assert.ok(dragged>top,'source scrollbar thumb can be dragged using real pointer events');
  const native=await page.locator('#social-native-chat-scroll').evaluate(el=>({
   track:el.querySelector('#social-native-scroll-track').getAttribute('aria-valuenow'),
   thumbHeight:parseFloat(getComputedStyle(el.querySelector('#social-native-scroll-thumb')).height),
   up:el.querySelector('#social-native-scroll-up').disabled,
   source:getComputedStyle(el.querySelector('#social-native-scroll-thumb')).backgroundImage,
   count:document.querySelectorAll('#social-native-chat-scroll').length
  }));
  assert.ok(Number(native.track)>=0&&Number(native.track)<=100,'scroll thumb retains correct accessible value');
  assert.ok(native.thumbHeight>=15&&native.thumbHeight<60,'source thumb size reflects real transcript ratio');
  assert.ok(native.source.includes('data:image/png;base64,'),'real 52x40 bitmap also decorates draggable thumb');
  assert.equal(native.count,1);
  await page.screenshot({path:'leaf-chatroom-original-52x40-live-scrollbar.png'});
  await page.locator('#social-back').click();
  assert.equal(await page.locator('#social-native-chat-scroll').count(),1,'changing rooms preserves one real transcript scrollbar and its bindings');
  assert.equal(await page.locator('#social-native-chat-scroll').evaluate(el=>getComputedStyle(el).display),'none','scroll chrome never appears over original ChatTown');
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('모바일 원본 스크롤 유지 검증',4));
  assert.equal(await page.locator('#social-native-chat-scroll').evaluate(el=>getComputedStyle(el).display),'none','mobile uses full-height native readable log instead of tiny 13px source controls');
  assert.ok(await page.locator('#message').isVisible(),'the actual keyboard input remains usable on mobile');
  assert.deepEqual(errors,[],'native source decoration adds no JS exceptions');
  console.log('SOURCE 52x40 CHAT SCROLLBAR PASS: genuine keyed archive, real room log, arrow/track/drag, no transcript clone, mobile');
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE CHAT SCROLL FAILED',e.stack||e);process.exit(1)});
