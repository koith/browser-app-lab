const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const url='http://127.0.0.1:8765/';
 const ctx1=await browser.newContext(),ctx2=await browser.newContext();
 await Promise.all([ctx1.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';}),
                    ctx2.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';})]);
 const host=await ctx1.newPage(),guest=await ctx2.newPage(),errors=[];
 for(const [name,p] of [['HOST',host],['GUEST',guest]])p.on('pageerror',e=>{errors.push(name+':'+e.message);console.error(e.stack)});
 await Promise.all([host.goto(url),guest.goto(url)]);
 for(const p of [host,guest]){await p.waitForFunction(()=>!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__);await p.evaluate(()=>{window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')});await p.locator('.social-district-hotspot').nth(3).click()}
 const room=await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('하이아칸 원격 채팅',2));
 await host.locator('#social-invite').click();await guest.locator('#social-invite').click();
 await host.locator('#social-create-offer').click();
 await host.waitForFunction(()=>document.querySelector('#social-output-offer')?.value.length>150,null,{timeout:17000});
 const offer=await host.locator('#social-output-offer').inputValue();
 await guest.locator('#social-input-offer').fill(offer);
 await guest.locator('#social-make-answer').click();
 await guest.waitForFunction(()=>document.querySelector('#social-output-answer')?.value.length>150,null,{timeout:17000});
 await host.locator('#social-input-answer').fill(await guest.locator('#social-output-answer').inputValue());
 await host.locator('#social-apply-answer').click();
 await Promise.all([host.waitForFunction(()=>document.querySelector('#social-connect-state')?.textContent.includes('연결 성공'),null,{timeout:20000}),guest.waitForFunction(()=>document.querySelector('#social-connect-state')?.textContent.includes('연결 성공'),null,{timeout:20000})]);
 console.log('P2P SOCIAL CONNECTION PASS');
 await host.locator('.social-modal-title button').click();await guest.locator('.social-modal-title button').click();
 await guest.waitForFunction(room=>window.__LEAF_SOCIAL__.getState().roomId===room,room,{timeout:10000});
 await Promise.all([host.waitForFunction(()=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===2,null,{timeout:10000}),guest.waitForFunction(()=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===2,null,{timeout:10000})]);
 const seats=await host.locator('#social-avatar-layer .social-avatar').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y}}));
 assert.ok(Math.abs(seats[0].x-seats[1].x)>25||Math.abs(seats[0].y-seats[1].y)>25,'original room chat characters must not overlap each other');
 await guest.locator('#message').fill('원격 기기 쌍방향 채팅');await guest.locator('#message').press('Enter');
 await host.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('원격 기기 쌍방향 채팅'),null,{timeout:9000});
 await host.locator('#message').fill('호스트 응답 도착');await host.locator('#message').press('Enter');
 await guest.waitForFunction(()=>document.querySelector('#chat-log')?.textContent.includes('호스트 응답 도착'),null,{timeout:9000});
 assert.deepEqual(errors,[]);
 await host.screenshot({path:'leaf-p2p-host.png'});await guest.screenshot({path:'leaf-p2p-guest.png'});
 await browser.close();
 console.log('SOCIAL WEBRTC TWO-WAY CHAT PASS');
})().catch(e=>{console.error('SOCIAL WEBRTC FAILED',e.stack||e);process.exit(1)});