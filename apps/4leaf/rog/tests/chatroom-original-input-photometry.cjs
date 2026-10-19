'use strict';
/* Actual historical 2004 JPG pixel rows versus the LIVE 794x528 DOM:
 * no screenshots pasted into the UI and no invented user fixtures.
 * This test separately measures white input-bar rows in chat.jpg and
 * the live input/log/userlist positions after native source room4 opens.
 */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const photo=fs.readFileSync(path.resolve(__dirname,'../../assets/chat.jpg')).toString('base64');
  const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const errs=[];page.on('pageerror',e=>errs.push(e.message));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__&&window.__LEAF_NATIVE_SCROLLBAR__);
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
   window.__LEAF_SOCIAL__.createRoom('원작 2004 입력창 배치 사진 비교',4);
  });
  await page.waitForSelector('#rooms.classic-chat-room:not(.hidden)');
  await page.waitForFunction(()=>document.querySelector('.messenger[data-native-overlay="true"]')&&
    document.querySelector('.social-user-panel[data-native-overlay="true"]'),null,{timeout:14000});
  await page.locator('#message').fill('2004년 원본 한글 실제 입력 확인');
  await page.locator('#message').press('Enter');
  await page.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('2004년 원본 한글 실제 입력 확인'));
  const state=await page.evaluate(async base64=>{
   const reference=new Image();
   reference.src='data:image/jpeg;base64,'+base64;
   await reference.decode();
   const canvas=document.createElement('canvas');
   canvas.width=reference.naturalWidth;canvas.height=reference.naturalHeight;
   const ctx=canvas.getContext('2d',{willReadFrequently:true});
   ctx.drawImage(reference,0,0);
   const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
   const whites=[];
   for(let y=63;y<128;y++){
    let light=0;
    for(let x=22;x<397;x++){
     const i=(y*794+x)*4;
     const r=pixels[i],g=pixels[i+1],b=pixels[i+2];
     if(r>174&&g>174&&b>174&&Math.max(r,g,b)-Math.min(r,g,b)<85)light++;
    }
    whites.push({y,light});
   }
   const band=whites.filter(x=>x.light>=210);
   const frame=document.querySelector('#social-image-frame').getBoundingClientRect();
   const scale=frame.width/794;
   const measure=query=>{
    const el=document.querySelector(query),r=el.getBoundingClientRect();
    return {x:Number(((r.x-frame.x)/scale).toFixed(2)),
     y:Number(((r.y-frame.y)/scale).toFixed(2)),
     w:Number((r.width/scale).toFixed(2)),
     h:Number((r.height/scale).toFixed(2))};
   };
   const photoInput={top:Math.min(...band.map(x=>x.y)),
     bottom:Math.max(...band.map(x=>x.y)),brightRows:band.length,
     maxLight:Math.max(...whites.map(x=>x.light))};
   return {reference:[reference.naturalWidth,reference.naturalHeight],
    photoInput,live:{
     room:measure('#social-image-frame'),messenger:measure('.messenger'),
     log:measure('#chat-log'),form:measure('#chat-form'),
     input:measure('#message'),scroll:measure('#social-native-chat-scroll'),
     participants:measure('#social-peer-panel'),header:measure('#social-original-userlist')},
    sourceRoom:document.getElementById('social-image-frame').style.backgroundImage,
    actualText:document.getElementById('chat-log').textContent,
    nativeScrollbar:window.__LEAF_NATIVE_SCROLLBAR__.getState(),
    nativeUsers:document.getElementById('social-peer-list').children.length};
  },photo);
  assert.deepEqual(state.reference,[794,528],'the 2004 historical JPEG has original 794x528 source geometry');
  assert.ok(state.photoInput.brightRows>=9&&state.photoInput.maxLight>=280,
   'derive the real horizontal white input field from original 2004 JPG pixels, not guessed CSS');
  assert.ok(state.sourceRoom.includes('original/ChatRoom/room4.png'));
  assert.ok(state.actualText.includes('2004년 원본 한글 실제 입력 확인'));
  assert.equal(state.nativeUsers,1,'no fabricated historical users in the reproduction');
  assert.equal(state.live.log.w,390,'original room keeps one independently scrollable 390px native log');
  assert.equal(state.live.form.w,407,'native white real input is source 407px wide');
  assert.equal(state.live.scroll.w,16,'real original source ChatRoom scrollbar column');
  assert.ok(Math.abs(state.live.participants.x-621)<=3,
   'the real 150x38 source userlist floats at historical right-hand 621px x');
  assert.ok(Math.abs(state.live.participants.y-10)<=2,
   'the historical source userlist top is 10px');
  // Verifiable SOURCE-to-runtime geometry: in the actual archived 2004
  // JPG, the inner nearly-white pixels start at row 99; the original
  // 407x21 source sprite has 1px inner artwork padding. A CSS form at
  // source y=97 therefore paints real white field starting at y~99.
  assert.ok(Math.abs(state.live.input.y-(state.photoInput.top-1))<=2,
   'native editable input must match ACTUAL 2004 JPEG bright pixels within 2px: '+JSON.stringify(state));
  assert.ok(Math.abs(state.live.form.y-97)<=1,
   'source 407x21 ChatRoom/chatbaredit.png starts at historical y97, not old y91');
  assert.equal(state.live.log.h,97,'the original live log reaches the source form without a 6px empty strip');
  assert.equal(state.live.scroll.h,97,'native 52x40 scrollbar covers exactly the same height as the source log');
  assert.equal(state.live.messenger.h,118,'historic native dialogue plus edit occupies original 97+21px');
  assert.deepEqual(errs,[]);
  await page.screenshot({path:'leaf-2004-source-chat-input-row-registration.png'});
  console.log('HISTORIC-2004-CHAT-INPUT-PIXEL-REGISTRATION '+JSON.stringify(state));
 }finally{await browser.close()}
})().catch(e=>{console.error('HISTORIC 2004 CHAT INPUT QA FAILED',e.stack||e);process.exit(1)});
