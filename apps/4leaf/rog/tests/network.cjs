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

  // Actual two-Chromium-browser reconnect: keep the match and exchange a fresh
  // host/guest SDP pair after leaving the original game screen. This exercises
  // the same visible lobby controls used when the previous WebRTC link dies.
  const beforeReconnect=await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return {map:m.map,round:m.round,active:m.active,positions:m.players.map(p=>p.position)};
  });
  for(const page of [host,guest]){
    await page.locator('#exit-game').click();
    await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
    await page.waitForSelector('#lobby:not(.hidden)');
    // Re-open the visible original lobby creation panel before choosing mode.
    await page.locator('#lobby-create').click();
    // Leaving a room resets the lobby to its ordinary local-game selector.
    // Re-select network mode through the real visible control before inviting.
    await page.locator('#game-mode').selectOption('network');
    await page.waitForSelector('#net-panel:not(.hidden)');
  }
  await host.locator('#net-make').click();
  await host.waitForFunction(()=>document.querySelector('#net-output-offer').value.length>100);
  const secondOffer=await host.locator('#net-output-offer').inputValue();
  await guest.locator('#net-input-offer').fill(secondOffer);
  await guest.locator('#net-accept-offer').click();
  await guest.waitForFunction(()=>document.querySelector('#net-output-answer').value.length>100);
  const secondAnswer=await guest.locator('#net-output-answer').inputValue();
  await host.locator('#net-input-answer').fill(secondAnswer);
  await host.locator('#net-apply-answer').click();
  await Promise.all([
    host.waitForFunction(()=>window.__LEAF_NET__?.connected,null,{timeout:20000}),
    guest.waitForFunction(()=>window.__LEAF_NET__?.connected,null,{timeout:20000})
  ]);
  // The authoritative host sends the running match on the new channel.
  await guest.waitForFunction(()=>document.querySelector('#game:not(.hidden)')!==null);
  await guest.waitForFunction(expected=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return m?.mode==='network'&&m.map===expected.map&&m.round===expected.round&&
      m.active===expected.active&&
      JSON.stringify(m.players.map(p=>p.position))===JSON.stringify(expected.positions);
  },beforeReconnect);
  await host.locator('#resume-game').click();
  await host.waitForSelector('#game:not(.hidden)');
  await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    m.active=0;m.players[0].position=0;m.players[1].position=50;
    m.players[0].jail=0;m.players[0].ability=0;m.players[0].effects={};
    for(let i=1;i<=40;i++)m.tiles[i]='normal';
    for(let i=51;i<=70;i++)m.tiles[i]='normal';
    window.__LEAF_BRIDGE__.onState(m);
    window.__ROG_TEST__.drawGame();
  });
  await host.locator('#roll-btn').click();
  await guest.waitForFunction(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return m?.active===1&&m.players[0].position>0&&window.__LEAF_NET__?.connected;
  },null,{timeout:20000});
  assert.equal(await host.locator('#roll-btn').isDisabled(),true,
    'reconnected host must not roll during the guest turn');
  console.log('WEBRTC REAL TWO-BROWSER RECONNECT PASS: same match and authoritative turn');

  // A disabled button is not an authorization check. Invoking the underlying
  // exported game handler must not allow the host to roll for the guest.
  const snapshot=()=>host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return {active:m.active,round:m.round,positions:m.players.map(p=>p.position),
      history:m.history?.length??0};
  });
  const beforeForeignTurn=await snapshot();
  assert.equal(beforeForeignTurn.active,1,'the reconnected guest currently owns the turn');
  await host.evaluate(()=>window.__ROG_TEST__.takeTurn());
  assert.deepEqual(await snapshot(),beforeForeignTurn,
    'host cannot mutate guest turn through a stale or direct JS roll handler');

  // RULE-03: actual connected RTCDataChannel must ignore guest-forged state.
  // The subsequent chat message is a real ordered-channel barrier; this is
  // not a stub of net.onmessage or a timeout-based absence assertion.
  const beforeForgery=await snapshot();
  const injected=await guest.evaluate(()=>{
    const fake=structuredClone(window.__LEAF_BRIDGE__.getMatch());
    fake.players[0].position=999;fake.active=0;fake.history=['INJECTED_FAKE_GUEST_STATE'];
    return [window.__LEAF_NET__.send({type:'state',match:fake}),
      window.__LEAF_NET__.send({type:'chat',who:'guest',text:'STATE_FORGERY_BARRIER_712'})];
  });
  assert.deepEqual(injected,[true,true],'real guest RTC writes reached host channel');
  await host.waitForFunction(()=>document.querySelector('#chat-log')
    ?.textContent.includes('STATE_FORGERY_BARRIER_712'),null,{timeout:10000});
  assert.deepEqual(await snapshot(),beforeForgery,
    'a peer-originated state packet cannot override the authoritative host match');

  // Put the real guest in a guaranteed source-normal DMP corridor, then fire
  // TWO legitimate roll commands through the same connected RTCDataChannel.
  // busy/remoteAct must gate the second; one pair of dice, one move, one turn
  // result must be identically persisted by both browser clients.
  await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    m.active=1;m.players[1].position=50;m.players[1].jail=0;
    m.players[1].effects={};m.players[1].items=[];
    for(let i=51;i<=70&&i<m.tiles.length-1;i++)m.tiles[i]='normal';
    window.__LEAF_BRIDGE__.onState(m);window.__ROG_TEST__.drawGame();
  });
  await guest.waitForFunction(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return m?.active===1&&m.players[1].position===50;
  },null,{timeout:10000});
  const beforeDouble=await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return {turn:m.active,rolls:m.history.filter(x=>x.includes('이동 주사위')).length};
  });
  assert.equal(beforeDouble.turn,1);
  const doubleSent=await guest.evaluate(()=>[
    window.__LEAF_NET__.send({type:'command',action:'roll'}),
    window.__LEAF_NET__.send({type:'command',action:'roll'})
  ]);
  assert.deepEqual(doubleSent,[true,true],'two commands delivered over real RTC channel');
  await host.waitForFunction(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return m?.active===0&&m.players[1].position>50;
  },null,{timeout:20000});
  const afterDouble=await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return {active:m.active,round:m.round,positions:m.players.map(p=>p.position),
      dice:m.lastRoll,history:m.history,
      rolls:m.history.filter(x=>x.includes('이동 주사위')).length};
  });
  assert.equal(afterDouble.rolls,beforeDouble.rolls+1,
    'two guest roll commands must produce exactly ONE source dice movement');
  await guest.waitForFunction(expected=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    return m?.active===expected.active&&m.round===expected.round&&
      JSON.stringify(m.players.map(p=>p.position))===JSON.stringify(expected.positions)&&
      JSON.stringify(m.lastRoll)===JSON.stringify(expected.dice)&&
      JSON.stringify(m.history)===JSON.stringify(expected.history);
  },afterDouble,{timeout:12000});
  console.log('WEBRTC RULE03 DOUBLE_ROLL_FORGED_STATE_AND_EXACT_SYNC_PASS',
    JSON.stringify({historyRollDelta:afterDouble.rolls-beforeDouble.rolls,
      positions:afterDouble.positions,lastRoll:afterDouble.dice,
      guestAndHostIdentical:true,forgedGuestStateBlocked:true}));

  // Losing connectivity while it is the host's turn must both disable the
  // visible button and protect the authoritative match state from mutation.
  await host.evaluate(()=>{
    const m=window.__LEAF_BRIDGE__.getMatch();
    m.active=0;
    window.__LEAF_NET__.connected=false;
    window.__ROG_TEST__.drawGame();
  });
  assert.equal(await host.locator('#roll-btn').isDisabled(),true,
    'the host dice button is disabled when WebRTC becomes disconnected');
  const beforeOfflineTurn=await snapshot();
  await host.evaluate(()=>window.__ROG_TEST__.takeTurn());
  assert.deepEqual(await snapshot(),beforeOfflineTurn,
    'disconnected WebRTC host may not roll or advance the authoritative match');
  // A malformed or stale signaling role must never implicitly become guest.
  await host.evaluate(()=>{
    window.__LEAF_NET__.connected=true;
    window.__LEAF_NET__.role='unknown';
    window.__LEAF_BRIDGE__.getMatch().active=1;
    window.__ROG_TEST__.drawGame();
  });
  assert.equal(await host.locator('#roll-btn').isDisabled(),true,
    'unknown WebRTC role never inherits a guest turn');
  const beforeUnknownRole=await snapshot();
  await host.evaluate(()=>window.__ROG_TEST__.takeTurn());
  assert.deepEqual(await snapshot(),beforeUnknownRole,
    'unknown WebRTC role cannot mutate the authoritative match');
  console.log('WEBRTC TURN AUTHORIZATION PASS: guest-only, disconnected-host, unknown-role state unchanged');

  assert.deepEqual(errors,[],'no client JavaScript errors');
  await guest.screenshot({path:'rog-online-guest.png'});
  await host.screenshot({path:'rog-online-host.png'});
  await browser.close();
  console.log('WEBRTC TWO DEVICE TURN PASS',JSON.stringify(one));
})().catch(e=>{console.error('WEBRTC E2E FAIL',e);process.exit(1)});