'use strict';
/* Baseline / regression capture of live ChatRoom against archived 794x528
 * February 2004 source photos. No screenshot is ever injected in gameplay.
 * Never introduce fictional room users for visual similarity.
 */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:800},
  deviceScaleFactor:1,serviceWorkers:'block'});
 const errors=[],missing=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()===404&&r.url().includes('/original/'))missing.push(r.url())});
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_SOCIAL__,null,{timeout:12000});
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('원작 화면 시각 검증',4,12);
  });
  await page.waitForSelector('#rooms.classic-chat-room #social-image-frame.social-interior');
  await page.waitForFunction(()=>{
   const c=document.querySelector('#social-image-frame');
   return c&&getComputedStyle(c).backgroundImage.includes('room4.png')
    &&document.querySelector('.social-avatar.self img')?.naturalWidth===75;
  },null,{timeout:15000});
  await page.waitForTimeout(420);
  const audit=await page.evaluate(()=>{
   const r=selector=>{const el=document.querySelector(selector);if(!el)return null;
    const b=el.getBoundingClientRect(),css=getComputedStyle(el);
    return {x:Math.round(b.x),y:Math.round(b.y),
     w:Math.round(b.width),h:Math.round(b.height),
     display:css.display,position:css.position,zIndex:css.zIndex,
     transform:css.transform,
     background:css.backgroundImage.slice(0,140)};
   };
   return {app:r('#app'),rooms:r('#rooms'),layout:r('#rooms .social-layout'),
    header:r('#rooms .social-header'),stage:r('#social-stage'),
    frame:r('#social-image-frame'),userPanel:r('#social-peer-panel'),
    messenger:r('#rooms .messenger'),chatLog:r('#chat-log'),chatForm:r('#chat-form'),
    avatar:r('.social-avatar.self'),actorArt:r('.social-avatar.self img'),
    furniture:r('.social-room-foreground'),
    toolbar:r('#rooms .social-header-tools'),
    actualOccupants:document.querySelectorAll('.social-avatar').length,
    frameArt:document.querySelector('#social-image-frame').style.backgroundImage,
    nativeLayer:document.querySelector('.social-room-foreground')?.dataset.ready
   };
  });
  console.log('SOURCE_ROOM_LIVE_GEOMETRY '+JSON.stringify(audit));
  assert.equal(audit.actualOccupants,1,'do not fake historical 10 people');
  assert.ok(audit.frameArt.includes('room4.png'));
  assert.deepEqual(missing,[]);
  assert.deepEqual(errors,[]);
  const shot=await page.locator('#app').screenshot({type:'jpeg',quality:79,animations:'disabled'});
  console.log('SOURCE_ROOM_LIVE_JPEG_BASE64 '+shot.toString('base64'));
  console.log('SOURCE_ROOM_END');
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE ROOM VISUAL FAILED',e.stack||e);process.exit(1)});
