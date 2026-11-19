'use strict';
/* Regression: HTTP 503 AFTER authoritative CREATE commit must not spawn an
 * independent local room. Retry keeps the exact request ID and enters
 * the original server room by clicking the real owner dialog. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',error=>errors.push(String(error)));
 const room={id:'already-durable-551',name:'응답 잃은 원작방',
  region:'north',district:'샤이닝 브리즈',capacity:4,background:2,
  locked:false,preset:false,occupants:0,created:Date.now(),isOwner:true};
 let attempts=0,joins=0;
 const sent=[];
 await page.route('https://lost-create.test/**',async route=>{
  const req=route.request(),pathname=new URL(req.url()).pathname;
  const headers={'access-control-allow-origin':'*',
   'access-control-allow-methods':'GET,POST,OPTIONS',
   'access-control-allow-headers':'authorization,content-type,accept'};
  const respond=(status,data)=>route.fulfill({status,contentType:'application/json',
   headers,body:JSON.stringify(data)});
  if(req.method()==='OPTIONS')return route.fulfill({status:204,headers,body:''});
  if(pathname==='/api/session')return respond(201,{token:'c'.repeat(64),id:'room-owner',room:null});
  if(pathname==='/api/rooms'&&req.method()==='GET')
   return respond(200,{rooms:attempts?[room]:[]});
  if(pathname==='/api/snapshot')
   return respond(200,{roomId:joins?room.id:null,nextSequence:0,entries:[],peers:[]});
  if(pathname==='/api/rooms'&&req.method()==='POST'){
   attempts++;sent.push(req.postDataJSON());
   // The first request was committed by server. Only its ACK disappeared.
   if(attempts===1)return respond(503,{error:'upstream ACK lost after commit'});
   return respond(200,{room,replayed:true});
  }
  if(pathname==='/api/rooms/'+room.id+'/join'){
   joins++;return respond(200,{room,joined:true});
  }
  return respond(200,{});
 });
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='https://lost-create.test'});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().centralReady,null,{timeout:15000});
  await page.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});
  await page.locator('.social-district-hotspot').nth(3).click();
  await page.locator('#social-new-room').click();
  await page.locator('#social-modal [name="name"]').fill(room.name);
  await page.locator('#social-modal [name="capacity"]').selectOption('4');
  await page.locator('#social-modal form').evaluate(form=>form.requestSubmit());
  await page.waitForFunction(()=>document.querySelector('#social-create-error:not([hidden])')?.textContent.includes('동일 요청'),null,{timeout:15000});
  assert.equal(attempts,1);
  assert.equal(joins,0);
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory',
   'ambiguous online CREATE must not silently enter a fake local room');
  assert.equal(await page.locator('#social-modal form').getAttribute('data-server-created-room'),null);
  await page.locator('#social-modal button[type="submit"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().roomId==='already-durable-551'&&
   window.__LEAF_CENTRAL_CHAT__?.joinedId==='already-durable-551',null,{timeout:15000});
  assert.equal(attempts,2);assert.equal(joins,1);
  assert.ok(/^[0-9a-f-]{32,36}$/i.test(sent[0].createRequestId));
  assert.deepEqual(sent[0],sent[1],'retry must keep same logical room ID and payload');
  const state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(state.offlineRoom,false);
  assert.deepEqual(errors,[]);
  console.log('P0_CHAT_LOST_CREATE_ACK_REPLAY_REAL_BROWSER_PASS',
   JSON.stringify({attempts,joins,roomId:state.roomId,offline:false}));
 }finally{await browser.close()}
})().catch(error=>{console.error('P0_CHAT_LOST_CREATE_ACK_REPLAY_FAIL',error.stack||error);process.exit(1)});
