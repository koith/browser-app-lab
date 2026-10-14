const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('path');
(async()=>{
 const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const a=await browser.newContext({viewport:{width:1280,height:800}});
 const host=await a.newPage(),guest=await a.newPage(); // same browser storage partition: actual peer tabs
 const errors=[];
 for(const [who,page] of [['host',host],['guest',guest]]){
   page.on('pageerror',e=>{errors.push(who+': '+e.stack);console.error('PAGE ERROR',who,e.stack)});
   page.on('console',m=>{if(m.type()==='error')console.log('PAGE LOG ERROR',who,m.text())});
   page.on('response',res=>{if(res.status()===404)console.log('RESOURCE 404',who,res.url())});
 }
 await Promise.all([host.goto(url),guest.goto(url)]);
 await Promise.all([
  host.waitForFunction(()=>!!window.__LEAF_WORLD__&&!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000}),
  guest.waitForFunction(()=>!!window.__LEAF_WORLD__&&!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000})
 ]);
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'original WorldMap first');
 assert.equal(await host.locator('#leaf-world-stage .world-backdrop').getAttribute('src'),'./original/WorldMap/worldmapback.png');
 assert.equal(await host.locator('#leaf-world-stage .world-sprite').count(),6,'six genuine four-frame region sprites');
 assert.equal(await host.locator('#leaf-world-stage .world-location').count(),6,'six active world regions');
 await host.screenshot({path:'leaf-original-world.png',fullPage:true});
 await host.locator('[data-region="street"]').click();
 assert.ok(await host.locator('#city:not(.hidden) #street-viewport').isVisible(),'original Keltica MainStreet opens from the real map');
 assert.equal(await host.locator('#street-track .street-artwork').getAttribute('src'),'./original/MainStreet/back.png');
 const sx1=await host.evaluate(()=>window.__LEAF_STREET__.getState().x);
 await host.locator('#street-right').click();
 const sx2=await host.evaluate(()=>window.__LEAF_STREET__.getState().x);
 assert.ok(sx2>sx1,'street pans right across 1938px original source artwork');
 await host.locator('#street-left').click();
 await host.screenshot({path:'leaf-original-mainstreet.png'});
 await host.locator('#street-back').click();
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'street returns to WorldMap');

 // The original Recordable/Knight noticeboard must be a real working location.
 await host.locator('[data-region="knights"]').click();
 await host.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='board',null,{timeout:5000});
 assert.ok(await host.locator('.recordable-board').isVisible(),'recordable board opens');
 await host.locator('#recordable-create').click();
 await host.locator('.recordable-compose [name="title"]').fill('원작 포리프 기사단 게시글');
 await host.locator('.recordable-compose [name="body"]').fill('실제 게시글 보존과 다른 탭 공유 기능 확인');
 await host.locator('.recordable-compose button[type="submit"]').click();
 assert.equal(await host.locator('#recordable-rows .recordable-row').count(),1);
 await guest.locator('[data-region="knights"]').click();
 await guest.waitForFunction(()=>document.querySelector('#recordable-rows')?.textContent.includes('원작 포리프 기사단 게시글'),null,{timeout:5000});
 await guest.locator('#recordable-rows .recordable-row').first().click();
 assert.ok((await guest.locator('.recordable-article').textContent()).includes('실제 게시글 보존'));
 await guest.locator('.social-modal-title button').click();
 await host.screenshot({path:'leaf-original-recordable-board.png'});
 await host.locator('#social-back').click();
 await guest.locator('#social-back').click();

 await host.locator('[data-region="north"]').click();
 await host.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().region==='north'&&document.querySelector('#rooms:not(.hidden)'),null,{timeout:5000});
 assert.equal(await host.locator('.social-district-hotspot').count(),8,'original northern ChatTown eight signs');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('northback.png'));
 await host.screenshot({path:'leaf-original-north-town.png'});
 // Confirm distinct historic southern region also works, before returning north.
 await host.locator('#social-back').click();
 await host.locator('[data-region="south"]').click();
 assert.equal(await host.locator('.social-district-hotspot').count(),8);
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('southback.png'));
 await host.screenshot({path:'leaf-original-south-town.png'});
 await host.locator('#social-back').click();
 await host.locator('[data-region="north"]').click();
 await host.locator('.social-district-hotspot').nth(3).click();
 assert.equal((await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().view)),'directory');
 assert.equal(await host.locator('.social-directory-row').count(),6,'six original interior templates');
 await host.screenshot({path:'leaf-original-room-directory.png'});
 const roomId=await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원작 채팅 테스트',3));
 assert.ok(roomId.length>=10,'new real room id');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('room3.png'));
 assert.equal(await host.locator('.social-avatar').count(),1,'zero fabricated NPC users');
 await host.screenshot({path:'leaf-original-chat-room.png'});
 await guest.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms');});
 await guest.locator('.social-district-hotspot').nth(3).click();
 await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),roomId,{timeout:6500});
 await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),roomId);
 await Promise.all([
  host.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:7000}),
  guest.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:7000})
 ]);
 assert.equal(await host.locator('#social-online-count').textContent(),'2명');
 assert.equal(await guest.locator('#social-online-count').textContent(),'2명');
 await host.locator('#message').fill('원본 하이아칸 실시간 채팅 테스트');
 await host.locator('#message').press('Enter');
 await guest.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('원본 하이아칸 실시간 채팅 테스트'),null,{timeout:7000});
 assert.ok(await guest.locator('.social-speech').count()>=1,'real speech bubble above sender avatar');
 await guest.locator('#message').fill('두 번째 브라우저의 실제 응답');
 await guest.locator('#message').press('Enter');
 await host.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('두 번째 브라우저의 실제 응답'),null,{timeout:7000});
 await guest.locator('.social-interior').click({position:{x:620,y:365}});
 await host.waitForFunction(()=>[...document.querySelectorAll('.social-avatar')].some(x=>x.dataset.peer!==window.__LEAF_SOCIAL__.getState().people[0]?.id&&parseFloat(x.style.left)>60),null,{timeout:6500}).catch(async()=>{
    const count=await host.locator('.social-avatar').count();
    assert.equal(count,2,'remote avatar remains present after room movement');
 });
 await host.screenshot({path:'leaf-two-live-chat-users.png'});
 await guest.setViewportSize({width:390,height:844});
 await guest.screenshot({path:'leaf-chat-mobile.png'});
 assert.ok(await guest.locator('#message').isVisible(),'mobile chat input');
 assert.ok(await guest.locator('#social-back').isVisible(),'mobile navigation');
 assert.deepEqual(errors,[],'no JS exceptions');
 await browser.close();
 console.log('4LEAF WORLD + CHAT PASS: original map, north/south boards, 6 interiors, real room creation, two users, cross-tab messages and speech bubbles, mobile');
})().catch(e=>{console.error('WORLD+CHAT E2E FAILED',e.stack||e);process.exit(1)});