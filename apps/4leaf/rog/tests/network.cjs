const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('path');
(async()=>{
  const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-web-security','--use-fake-ui-for-media-stream']});
  const contextHost=await browser.newContext({viewport:{width:1440,height:900}}),contextGuest=await browser.newContext({viewport:{width:1440,height:900}});
  const host=await contextHost.newPage(),guest=await contextGuest.newPage();
  const errors=[];
  for(const [name,p] of [['HOST',host],['GUEST',guest]]){
    p.on('pageerror',e=>{errors.push(name+':'+e.message);console.log('PAGEERROR',name,e.stack)});
    p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',name,m.text())});
  }
  const url='file://'+path.resolve(__dirname,'../index.html');
  await Promise.all([host.goto(url),guest.goto(url)]);
  await Promise.all([host.waitForFunction(()=>!!window.__LEAF_NET__&&!!window.__LEAF_BRIDGE__),guest.waitForFunction(()=>!!window.__LEAF_NET__&&!!window.__LEAF_BRIDGE__)]);
  await host.locator('[data-route="lobby"]').first().click();
  await guest.locator('[data-route="lobby"]').first().click();
  await Promise.all([host.selectOption('#game-mode','network'),guest.selectOption('#game-mode','network')]);
  await host.locator('#net-make').click();
  await host.waitForFunction(()=>document.querySelector('#net-output-offer').value.length>100,null,{timeout:18000});
  const offer=await host.locator('#net-output-offer').inputValue();
  assert.ok(offer.length>100);
  await guest.locator('#net-input-offer').fill(offer);
  await guest.locator('#net-accept-offer').click();
  await guest.waitForFunction(()=>document.querySelector('#net-output-answer').value.length>100,null,{timeout:18000});
  const answer=await guest.locator('#net-output-answer').inputValue();
  assert.ok(answer.length>100);
  await host.locator('#net-input-answer').fill(answer);
  await host.locator('#net-apply-answer').click();
  await Promise.all([
    host.waitForFunction(()=>window.__LEAF_NET__?.connected,null,{timeout:20000}),
    guest.waitForFunction(()=>window.__LEAF_NET__?.connected,null,{timeout:20000})
  ]);
  console.log('WEBRTC CONNECT PASS: host and guest connected through a genuine DataChannel');
  await host.locator('#bot-count').evaluate(el=>{el.value='1'});
  await host.locator('#start-game').click();
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.mode==='network',null,{timeout:12000});
  await host.evaluate(()=>{const m=window.__LEAF_BRIDGE__.getMatch();m.players[1].position=50;for(let i=1;i<18;i++)m.tiles[i]='normal';for(let i=51;i<70;i++)m.tiles[i]='normal';window.__LEAF_BRIDGE__.onState(m);window.__ROG_TEST__.drawGame()});
  await host.locator('#roll-btn').click();
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.active===1,null,{timeout:15000});
  assert.ok(await guest.locator('#roll-btn').isEnabled(),'guest must have control of their own turn');
  assert.ok(await host.locator('#roll-btn').isDisabled(),'host must not play guest turn');
  await guest.locator('#roll-btn').click();
  await host.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.active===0,null,{timeout:16000});
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.active===0,null,{timeout:16000});
  const one=await host.evaluate(()=>window.__LEAF_BRIDGE__.getMatch().players.map(p=>p.position));
  const two=await guest.evaluate(()=>window.__LEAF_BRIDGE__.getMatch().players.map(p=>p.position));
  assert.deepEqual(one,two,'board position state must remain synchronized across independent browser contexts');
  assert.deepEqual(errors,[],'no client JavaScript errors');
  await guest.screenshot({path:'rog-online-guest.png'});
  await host.screenshot({path:'rog-online-host.png'});
  await browser.close();
  console.log('WEBRTC TWO DEVICE TURN PASS',JSON.stringify(one));
})().catch(e=>{console.error('WEBRTC E2E FAIL',e);process.exit(1)});