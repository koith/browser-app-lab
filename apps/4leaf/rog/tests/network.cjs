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
  await Promise.all([host.locator('#lobby-create').click(),guest.locator('#lobby-create').click()]);
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

  // The guest chooses an original item locally; the authoritative host applies it.
  await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    const p=m.players[1];p.items=['charge','wing'];p.ability=10;p.usedItem=false;
    p.team=['c_0087','c_0078','c_0040'];
    for(let k=51;k<90;k++)m.tiles[k]='normal';
    window.__LEAF_BRIDGE__.onState(m);window.__ROG_TEST__.drawGame();
  });
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.items?.[0]==='charge',null,{timeout:5000});
  // The original screenshot-accurate game now keeps real item buttons in a
  // drawer behind native IMG/selector.png. Click its ACTUAL on-screen
  // command: direct clicks on hidden old strips are no longer gameplay.
  assert.equal(await guest.locator('#dice-items-toggle').isVisible(),true,'guest can open native item selector');
  assert.equal(await guest.locator('#dice-items-toggle').getAttribute('aria-expanded'),'false');
  await guest.locator('#dice-items-toggle').click();
  assert.equal(await guest.locator('#dice-items-toggle').getAttribute('aria-expanded'),'true','genuine source sprite opened the actual guest inventory');
  assert.equal(await guest.locator('#my-items .item-card').count(),2,'two real authoritative guest items are in inventory');
  await guest.locator('#my-items .item-card').first().click();
  await guest.locator('#modal-buttons button').filter({hasText:'사용'}).click();
  await host.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.ability===60,null,{timeout:9000});
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.ability===60,null,{timeout:9000});
  assert.equal(await host.evaluate(()=>window.__LEAF_BRIDGE__.getMatch().players[1].items.length),1);
  console.log('WEBRTC ITEM PASS: guest uses 50-point original card; host and guest synchronized');
  await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();m.players[1].ability=100;
    window.__LEAF_BRIDGE__.onState(m);window.__ROG_TEST__.drawGame();
  });
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.ability===100,null,{timeout:5000});
  await guest.locator('#ability-btn').click();
  await guest.locator('#modal-buttons button').filter({hasText:'발동'}).click();
  await host.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.ability===0,null,{timeout:9000});
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.ability===0,null,{timeout:9000});
  console.log('WEBRTC ABILITY PASS: guest invokes Saladin ability via host-authoritative game state');

  await guest.locator('#roll-btn').click();
  await host.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.active===0,null,{timeout:16000});
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.active===0,null,{timeout:16000});
  const one=await host.evaluate(()=>window.__LEAF_BRIDGE__.getMatch().players.map(p=>p.position));
  const two=await guest.evaluate(()=>window.__LEAF_BRIDGE__.getMatch().players.map(p=>p.position));
  assert.deepEqual(one,two,'board position state must remain synchronized across independent browser contexts');

  // Host-authoritative peer duel must wait for the remote human's card choice.
  await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    m.active=1;m.players[1].usedItem=false;m.players[1].items=['change'];
    m.players[0].position=15;m.players[1].position=15;
    window.__LEAF_BRIDGE__.onState(m);window.__ROG_TEST__.drawGame();
    window.__ROG_TEST__.resolveBattle(m.players[1],m.players[0],false);
  });
  await guest.waitForFunction(()=>document.querySelector('#modal-title')?.textContent?.includes('전투 카드 선택'),null,{timeout:11000});
  assert.ok(await host.locator('#battle-visual').isVisible());
  await guest.locator('#modal-buttons button').filter({hasText:'체인지 카드'}).click();
  await host.waitForFunction(()=>!document.querySelector('#battle-visual'),null,{timeout:11000});
  await guest.waitForFunction(()=>window.__LEAF_BRIDGE__.getMatch()?.players[1]?.items?.length===0,null,{timeout:11000});
  assert.ok(await guest.locator('#modal').evaluate(el=>el.classList.contains('hidden')));
  console.log('WEBRTC BATTLE PASS: guest uses actual Change card and host resolves remote duel');
  await guest.locator('#message').fill('포리프 상대방 온라인 메시지');
  await guest.locator('#message').press('Enter');
  await host.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('포리프 상대방 온라인 메시지'),null,{timeout:6000});
  await host.locator('#message').fill('호스트 실시간 응답');
  await host.locator('#message').press('Enter');
  await guest.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('호스트 실시간 응답'),null,{timeout:6000});
  console.log('WEBRTC CHAT PASS: two-way real peer messenger messages mirrored live');

  assert.deepEqual(errors,[],'no client JavaScript errors');
  await guest.screenshot({path:'rog-online-guest.png'});
  await host.screenshot({path:'rog-online-host.png'});
  await browser.close();
  console.log('WEBRTC TWO DEVICE TURN PASS',JSON.stringify(one));
})().catch(e=>{console.error('WEBRTC E2E FAIL',e);process.exit(1)});