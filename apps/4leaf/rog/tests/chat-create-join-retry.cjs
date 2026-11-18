'use strict';
/* P0-CHAT: genuine browser owner-dialog regression.
 * Remote CREATE ACK + failed JOIN must not silently create another local
 * room or re-POST CREATE. A user retry enters the already-created room.
 */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const failures=[];
 page.on('pageerror',error=>failures.push(String(error)));
 const room={id:'acknowledged-server-room-777',name:'재시도 온라인 방',
  region:'north',district:'샤이닝 브리즈',capacity:4,background:2,
  locked:false,preset:false,occupants:0,created:Date.now(),isOwner:true};
 let createPosts=0,joinPosts=0;
 await page.route('https://chat-ack.test/**',async route=>{
  const req=route.request(),pathname=new URL(req.url()).pathname;
  const headers={'access-control-allow-origin':'*',
   'access-control-allow-methods':'GET,POST,OPTIONS',
   'access-control-allow-headers':'authorization,content-type,accept'};
  const respond=(status,data)=>route.fulfill({status,contentType:'application/json',
   headers,body:JSON.stringify(data)});
  if(req.method()==='OPTIONS')return route.fulfill({status:204,headers,body:''});
  if(pathname==='/api/session')
   return respond(201,{token:'a'.repeat(64),id:'created-user',room:null});
  if(pathname==='/api/rooms'&&req.method()==='GET')
   return respond(200,{rooms:createPosts?[room]:[]});
  if(pathname==='/api/snapshot')
   return respond(200,{roomId:joinPosts>=2?room.id:null,nextSequence:0,messages:[],peers:[]});
  if(pathname==='/api/rooms'&&req.method()==='POST'){
   createPosts++;
   await new Promise(resolve=>setTimeout(resolve,250));
   return respond(201,{room});
  }
  if(pathname==='/api/rooms/'+room.id+'/join'){
   joinPosts++;
   if(joinPosts===1)return respond(503,{error:'temporary room join failure'});
   return respond(200,{room,joined:true});
  }
  return respond(200,{});
 });
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='https://chat-ack.test'});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().centralReady,
   null,{timeout:15000});
  await page.evaluate(()=>{
   window.__LEAF_SOCIAL__.openRegion('north');
   window.__ROG_TEST__.go('rooms');
  });
  await page.locator('.social-district-hotspot').nth(3).click();
  await page.locator('#social-new-room').click();
  await page.locator('#social-modal [name="name"]').fill(room.name);
  await page.locator('#social-modal [name="capacity"]').selectOption('4');
  await page.evaluate(()=>{
   const form=document.querySelector('#social-modal form');
   form.requestSubmit();form.requestSubmit();
  });
  await page.waitForFunction(()=>document.querySelector('#social-modal form')?.dataset.serverCreatedRoom===
   'acknowledged-server-room-777'&&!document.querySelector('#social-modal button[type="submit"]')?.disabled,
   null,{timeout:15000});
  assert.equal(await page.locator('#social-modal form').getAttribute('data-lifecycle'),'v2-room-domain',
   'real CREATE form must use isolated V2 room transaction module');
  assert.equal(await page.locator('#social-create-error').isVisible(),true,
   'JOIN failure remains visible in the source owner dialog');
  assert.equal(createPosts,1,'double submit must not create a duplicate online room');
  assert.equal(joinPosts,1,'initial JOIN should be attempted once');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory',
   'failed JOIN must not claim room entry');
  assert.equal(await page.locator('#social-modal button[type="submit"]').textContent(),
   '생성된 방에 다시 입장','owner can retry the existing room');
  await page.locator('#social-modal button[type="submit"]').click();
  await page.waitForFunction(()=>window.__LEAF_SOCIAL__?.getState().roomId===
   'acknowledged-server-room-777'&&window.__LEAF_CENTRAL_CHAT__?.joinedId===
   'acknowledged-server-room-777',null,{timeout:15000});
  const state=await page.evaluate(()=>window.__LEAF_SOCIAL__.getState());
  assert.equal(state.offlineRoom,false,'JOIN retry must enter genuine central room');
  assert.equal(createPosts,1,'JOIN retry cannot POST /api/rooms again');
  assert.equal(joinPosts,2);
  assert.deepEqual(failures,[]);
  console.log('P0_CHAT_CREATE_JOIN_RETRY_PASS',JSON.stringify({
   engine:engine.name(),created:createPosts,joins:joinPosts,
   remoteRoomId:state.roomId,offlineRoom:state.offlineRoom}));
 }finally{await browser.close()}
})().catch(e=>{console.error('P0_CHAT_CREATE_JOIN_RETRY_FAIL',e.stack||e);process.exit(1)});
