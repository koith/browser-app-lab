const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('path');
(async()=>{
 const url=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const a=await browser.newContext({viewport:{width:1280,height:800}});
 const host=await a.newPage(),guest=await a.newPage(); // same browser storage partition: actual peer tabs
 const errors=[],missingAssets=[];
 for(const [who,page] of [['host',host],['guest',guest]]){
   page.on('pageerror',e=>{errors.push(who+': '+e.stack);console.error('PAGE ERROR',who,e.stack)});
   page.on('console',m=>{if(m.type()==='error')console.log('PAGE LOG ERROR',who,m.text())});
   page.on('response',res=>{if(res.status()===404){console.log('RESOURCE 404',who,res.url());if(/\/original\//.test(res.url()))missingAssets.push(who+': '+res.url())}});
 }
 await Promise.all([host.goto(url),guest.goto(url)]);
 await Promise.all([
  host.waitForFunction(()=>!!window.__LEAF_WORLD__&&!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000}),
  guest.waitForFunction(()=>!!window.__LEAF_WORLD__&&!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000})
 ]);
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'original WorldMap first');
 // The original ChatRoom/header is a separate source sprite, not decorative
 // text. It must load from PAK, key out transparent green and remain legible.
 await host.waitForFunction(()=>document.querySelector('#social-original-userlist')?.dataset.ready==='true',null,{timeout:12000});
 const originalListHeader=await host.evaluate(()=>{
  const c=document.getElementById('social-original-userlist');
  const data=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let transparent=0,visible=0,leakedGreen=0;
  for(let i=0;i<data.length;i+=4){
   if(data[i+3]===0)transparent++;else{
    visible++;if(data[i+1]>220&&data[i]<65&&data[i+2]<90)leakedGreen++;
   }
  }
  return {width:c.width,height:c.height,transparent,visible,leakedGreen};
 });
 assert.deepEqual([originalListHeader.width,originalListHeader.height],[150,38],'original userlist bitmap dimensions');
 assert.ok(originalListHeader.transparent>200&&originalListHeader.visible>200,'userlist is properly keyed but source artwork preserved');
 assert.equal(originalListHeader.leakedGreen,0,'no chroma-key green in visible userlist pixels');

 assert.equal(await host.locator('#leaf-world-stage .world-backdrop').getAttribute('src'),'./original/WorldMap/worldmapback.png');
 assert.equal(await host.locator('#leaf-world-stage .world-sprite').count(),6,'six genuine four-frame region sprites');
 assert.equal(await host.locator('#leaf-world-stage .world-location').count(),6,'six active world regions');
 // Every source location must have a visible resting sprite without requiring hover.
 await host.waitForFunction(()=>[...document.querySelectorAll('#leaf-world-stage .world-sprite')].every(c=>{
   try{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
     for(let i=3;i<d.length;i+=4)if(d[i]>0)return true;
   }catch{}return false;
 }),null,{timeout:12000});
 await host.locator('[data-region="street"]').hover();
 await host.locator('#world-zoom-in').hover();
 assert.ok(await host.evaluate(()=>[...document.querySelectorAll('#leaf-world-stage .world-sprite')].every(c=>{
   const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
   for(let i=3;i<d.length;i+=4)if(d[i])return true;
   return false;
 })),'all original locations remain rendered after pointer leaves');
 await host.screenshot({path:'leaf-original-world.png',fullPage:true});
 await host.locator('[data-region="street"]').click();
 assert.ok(await host.locator('#city:not(.hidden) #street-viewport').isVisible(),'original Keltica MainStreet opens from the real map');
 assert.equal(await host.locator('#street-track .street-artwork').getAttribute('src'),'./original/MainStreet/back.png');
 // The original MainStreet scene was assembled from back.png plus SEVEN
 // original per-business sprites. Pixel compositing must remove their green
 // chroma key, and building buttons must remain interactive.
 await host.waitForFunction(()=>{
  const tiles=[...document.querySelectorAll('.street-building-art')];
  return tiles.length===7&&tiles.every(c=>c.dataset.ready==='true');
 },null,{timeout:16000});
 const streetArtwork=await host.evaluate(()=>[...document.querySelectorAll('.street-building-art')].map(c=>{
  const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let transparent=0,painted=0,greenLeak=0;
  for(let i=0;i<d.length;i+=4){
   if(d[i+3]===0)transparent++;
   else{painted++;if(d[i+1]>205&&d[i]<92&&d[i+2]<100&&d[i+1]>d[i]*1.65&&d[i+1]>d[i+2]*1.55)greenLeak++}
  }
  return {file:c.dataset.source,w:c.width,h:c.height,painted,transparent,greenLeak};
 }));
 assert.deepEqual(streetArtwork.map(x=>x.file),['dress','event','card','hair','accessory','dandymodern','office'],'all seven actual MainStreet source buildings, not proxy illustrations');
 assert.ok(streetArtwork.every(x=>x.painted>200&&x.transparent>100),'every native shop sprite contains artwork and transparent green key');
 assert.ok(streetArtwork.every(x=>x.greenLeak===0),'no unreplaced source bright green regions');
 assert.deepEqual(streetArtwork.map(x=>[x.w,x.h]),[[230,196],[190,229],[183,266],[199,178],[152,136],[212,222],[215,238]],'pixel dimensions agree with extracted PAK manifest');
 assert.equal(await host.locator('[data-street="magic"]').getAttribute('aria-label'),'매직카덴 · 카드샵','original card shop identification');
 await host.locator('[data-street="magic"]').evaluate(el=>el.click());
 assert.ok(await host.locator('#shop:not(.hidden)').isVisible(),'native MainStreet card building enters working Magic Carden shop');
 await host.evaluate(()=>window.__ROG_TEST__.go('city'));
 assert.ok(await host.locator('#city:not(.hidden)').isVisible(),'shop to MainStreet return route works');

 const sx1=await host.evaluate(()=>window.__LEAF_STREET__.getState().x);
 await host.locator('#street-right').click();
 const sx2=await host.evaluate(()=>window.__LEAF_STREET__.getState().x);
 assert.ok(sx2>sx1,'street pans right across 1938px original source artwork');
 await host.locator('#street-left').click();
 await host.waitForTimeout(350);
 console.log('STREET GEOMETRY',JSON.stringify(await host.evaluate(()=>{
   const info=id=>{const el=document.getElementById(id);if(!el)return null;const rect=el.getBoundingClientRect();return {x:Math.round(rect.x),y:Math.round(rect.y),width:Math.round(rect.width),height:Math.round(rect.height),transform:getComputedStyle(el).transform}};
   return {viewport:info('street-viewport'),track:info('street-track'),state:window.__LEAF_STREET__.getState()}
 })));
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

 // Region/regionback.png says TOWN SELECT, but it is a DICE channel menu.
 // Both Haiacan entries must enter this scene and NEVER switch the ChatTown.
 await host.locator('[data-region="north"]').click();
 assert.ok(await host.locator('#dice-channels:not(.hidden)').isVisible(),'north Haiacan opens dice channel select');
 assert.ok(await host.locator('#rooms.hidden').count()===1,'native TOWN SELECT does not open a chat room');
 assert.equal(await host.locator('#dice-channels .dice-channel-hotspot').count(),28,'seven original dice channel rows x 4 numbered slots');
 assert.ok((await host.locator('#dice-channel-stage').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('Region/regionback.png'),'native dice Region background is drawn');
 assert.equal(await host.locator('#dice-channels [data-channel="tichiel:4"]').getAttribute('aria-label'),'주사위의 잔영 · Tichiel 4번 채널');
 await host.screenshot({path:'leaf-original-town-select-dice.png'});
 await host.locator('#dice-channels [data-channel="ispin:1"]').click();
 assert.ok(await host.locator('#lobby:not(.hidden)').isVisible(),'dice channel opens Genesis World room select, NOT chat town');
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:1','north dice channel choice is saved');
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().region),'north');
 assert.ok((await host.locator('#lobby .scene-banner').textContent()).includes('Ispin 1채널'),'lobby identifies the selected dice channel');
 await host.locator('[data-route="sky"]').first().click();
 await host.locator('[data-region="south"]').click();
 assert.ok(await host.locator('#dice-channels:not(.hidden)').isVisible(),'south Haiacan opens the SAME dice channel selection art');
 assert.equal(await host.locator('#dice-channels .dice-channel-hotspot').count(),28);
 await host.locator('#dice-channels [data-channel="tichiel:2"]').click();
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().region),'south','south region remains associated with dice channel');
 assert.equal(await host.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'tichiel:2');
 assert.ok(await host.locator('#lobby:not(.hidden)').isVisible(),'south dice channel goes to the dice room list');
 await host.locator('#lobby-channel-change').click();
 assert.ok(await host.locator('#dice-channels:not(.hidden)').isVisible(),'dice room list supports changing the native dice channel');
 await host.locator('#dice-channel-back').click();
 assert.ok(await host.locator('#sky:not(.hidden)').isVisible(),'channel back goes to world map');
 // The two chat-town art files are a SEPARATE feature, reached via the
 // main 4LEAF chat tab (not through the dice TOWN SELECT).
 await host.evaluate(()=>{
  window.__LEAF_SOCIAL__.openRegion('north');
  window.__ROG_TEST__.go('rooms');
 });
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
 assert.equal(await host.locator('.social-district-hotspot').count(),8,'original north ChatTown eight signs');
 assert.equal(await host.locator('.social-district-hotspot').nth(2).getAttribute('aria-label'),'퓨어 시티 채팅 지역');
 await host.locator('.social-district-hotspot').nth(2).click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().district),'퓨어 시티');
 await host.locator('#social-back').click();
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('northback.png'));
 await host.screenshot({path:'leaf-original-north-chat-town.png'});
 await host.locator('#social-chat-south').click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south','chat region switch stays within the actual chat module');
 assert.equal(await host.locator('.social-district-hotspot').count(),8);
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('southback.png'));
 await host.screenshot({path:'leaf-original-south-chat-town.png'});
 await host.locator('#social-chat-north').click();
 await host.locator('.social-district-hotspot').nth(3).click();
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory');
 assert.equal(await host.locator('.social-directory-row').count(),0,'chat catalogue has no invented template-based rooms');
 assert.ok(await host.locator('.social-directory-empty').isVisible(),'chat town can create rooms independently of dice channel');
 await host.locator('#social-new-room').click();
 assert.equal(await host.locator('#social-modal [name="background"] option').count(),6,'six source ChatRoom backgrounds remain selectable');
 await host.locator('#social-modal .social-modal-title button').click();
 await host.screenshot({path:'leaf-original-room-directory.png'});
 const roomId=await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원작 채팅 테스트',3));
 assert.ok(roomId.length>=10,'new real room id');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('room3.png'));
 assert.equal(await host.locator('.social-avatar').count(),1,'zero fabricated NPC users');
 assert.equal(await host.locator('.social-original-tool').count(),6,'six working source-art toolbar actions');
 assert.equal(await host.locator('#social-close-room').count(),1,'owner can close room from the window chrome');
 assert.equal(await host.locator('.social-interior-controls').count(),0,'no artificial blue control buttons cover original scene');
 await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
 assert.ok(await host.locator('.social-avatar-chooser').isVisible(),'authentic toolbar avatar icon opens working character picker');
 await host.locator('.social-modal-title button').click();
 // The native client shipped a MainFrame toolbar icon sprite sheet.
 // Do not substitute generic emoji controls: the icon crop and functional
 // actions must be present in the real room.
 assert.equal(await host.locator('.social-classic-toolbar .social-original-tool').count(),6,'recovered native ChatRoom toolbar controls are visible');
 assert.equal(await host.locator('.social-original-tool').first().evaluate(e=>getComputedStyle(e).backgroundImage.includes('original/MainFrame/toolbarbtn.png')),true,'original 120x270 sprite sheet is used');
 assert.equal(await host.locator('.social-original-tool[aria-label="월드맵으로 돌아가기"]').evaluate(e=>getComputedStyle(e).backgroundPositionY),'-240px','the correct original exit sprite row is used');
 assert.ok(await host.locator('.social-classic-toolbar').isVisible(),'toolbar has a visible second header row');
 await host.locator('.social-original-tool[aria-label="아바타 선택"]').click();
 assert.ok(await host.locator('#social-modal .social-avatar-chooser').isVisible(),'original avatar button opens the chooser');
 await host.locator('#social-modal .social-modal-title button').click();

 // Original ChatRoom.pak contains an independent red-key foreground table
 // for room3; it must sit between the rear and front avatar seats.
 await host.waitForFunction(()=>document.querySelector('.social-room-foreground')?.dataset.ready==='true',null,{timeout:16000});
 const depth=await host.evaluate(()=>{
  const c=document.querySelector('.social-room-foreground');
  const p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let visible=0,redLeak=0,transparent=0;
  for(let i=0;i<p.length;i+=4){
   if(p[i+3]>0){visible++;if(p[i]>242&&p[i+1]<18&&p[i+2]<18)redLeak++}else transparent++;
  }
  const me=document.querySelector('.social-avatar.self');
  return {source:c.dataset.source,visible,redLeak,transparent,avatarZ:Number(me.style.zIndex),foregroundZ:Number(c.style.zIndex),room:document.querySelector('#social-image-frame').style.backgroundImage};
 });
 assert.equal(depth.source,'room3t','room3 original furniture sprite was loaded');
 assert.ok(depth.visible>500,'table pixels are painted');
 assert.ok(depth.transparent>500,'original bitmap red chroma key is transparent');
 assert.equal(depth.redLeak,0,'no red chroma-key fringe remains');
 assert.ok(depth.room.includes('room3.png'),'native room backdrop and independent furniture are composited');
 assert.equal(await host.locator('#social-image-frame .social-room-title').count(),0,'no invented room title banner over native art');
 const avatarAlpha=await host.evaluate(async()=>{
  const img=document.querySelector('.social-avatar.self img');
  await img.decode();const c=document.createElement('canvas');
  c.width=img.naturalWidth;c.height=img.naturalHeight;
  const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
  const d=ctx.getImageData(0,0,c.width,c.height).data;
  return {cornerAlpha:d[3],corner:[d[0],d[1],d[2]],width:c.width,height:c.height};
 });
 console.log('ORIGINAL REGISTRY AVATAR ALPHA',JSON.stringify(avatarAlpha));
 assert.equal(avatarAlpha.width,75,'original Registry sprites use 75px source width');
 assert.equal(avatarAlpha.height,141,'original Registry sprites use 141px source height');
 assert.equal(avatarAlpha.cornerAlpha,0,'avatar background is transparent, not chroma-green');
 assert.equal(await host.locator('.social-avatar.self img').evaluate(el=>getComputedStyle(el).width),'75px','rendered avatar retains native 75px frame width');
 const stage=host.locator('.social-interior');
 const frontBack=async(x,y)=>{
  await stage.evaluate((el,coords)=>{
   const box=el.getBoundingClientRect();
   el.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:box.left+box.width*coords.x/100,clientY:box.top+box.height*coords.y/100}));
  },{x,y});
  return await host.locator('.social-avatar.self').evaluate(el=>({seat:Number(el.dataset.seat),z:Number(el.style.zIndex),transition:getComputedStyle(el).transitionDuration}));
 };
 const behind=await frontBack(38,72);
 assert.ok(behind.z<depth.foregroundZ,'rear chair is hidden behind original tabletop');
 assert.equal(behind.transition,'0s','rear-seat change has no walking animation');
 const inFront=await frontBack(24,94);
 assert.ok(inFront.z>depth.foregroundZ,'front chair is drawn in front of original tabletop');
 assert.notEqual(inFront.seat,behind.seat,'front and rear clicks choose different native scene anchors');

 await host.screenshot({path:'leaf-original-chat-room.png'});

 await guest.evaluate(()=>{
  window.__LEAF_SOCIAL__.openRegion('north');
  window.__ROG_TEST__.go('rooms');
 });
 assert.equal(await guest.locator('.social-district-hotspot').count(),8,'second browser chat access does not require a dice channel');
 await guest.locator('.social-district-hotspot').nth(3).click();
 await guest.waitForFunction(id=>document.querySelector('.social-directory-row[data-room="'+id+'"]'),roomId,{timeout:6500});
 await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),roomId);
 await Promise.all([
  host.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:7000}),
  guest.waitForFunction(()=>document.querySelectorAll('.social-avatar').length===2,null,{timeout:7000})
 ]);
 assert.equal(await host.locator('#social-online-count').textContent(),'2명');
 assert.ok(await host.locator('#social-original-userlist').isVisible(),'original participant list header remains visible during real chat');
 assert.equal(await guest.locator('#social-online-count').textContent(),'2명');
 await host.locator('#message').fill('원본 하이아칸 실시간 채팅 테스트');
 await host.locator('#message').press('Enter');
 await guest.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('원본 하이아칸 실시간 채팅 테스트'),null,{timeout:7000});
 assert.ok(await guest.locator('.social-speech').count()>=1,'real speech bubble above sender avatar');
 await guest.locator('#message').fill('두 번째 브라우저의 실제 응답');
 await guest.locator('#message').press('Enter');
 await host.waitForFunction(()=>document.querySelector('#chat-log').textContent.includes('두 번째 브라우저의 실제 응답'),null,{timeout:7000});
 // Clicking a standing area must snap instantly to a discrete slot, without walking interpolation.
 const before=await guest.locator('.social-avatar.self').evaluate(el=>({left:el.style.left,top:el.style.top}));
 // A legitimate random spawn can ALREADY occupy the previously hard-coded
 // target. Try distinct actual standing areas to avoid false failures.
 let immediate;
 for(const [x,y] of [[78,68],[20,93],[58,79]]){
  immediate=await guest.locator('.social-interior').evaluate((frame,point)=>{
   const rect=frame.getBoundingClientRect();
   frame.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left+rect.width*point.x/100,clientY:rect.top+rect.height*point.y/100}));
   const el=frame.querySelector('.social-avatar.self');
   return {left:el.style.left,top:el.style.top,transition:getComputedStyle(el).transitionDuration,seat:el.dataset.seat};
  },{x,y});
  if(immediate.left!==before.left||immediate.top!==before.top)break;
 }
 assert.notDeepEqual({left:immediate.left,top:immediate.top},before,'click changes the occupied slot without requiring a different random spawn');
 assert.equal(immediate.transition,'0s','local avatar teleports without CSS interpolation');
 assert.ok(Number.isInteger(Number(immediate.seat)),'avatar is assigned a discrete seat');
 await host.waitForFunction(pos=>[...document.querySelectorAll('.social-avatar')].some(el=>el.style.left===pos.left&&el.style.top===pos.top),{left:immediate.left,top:immediate.top},{timeout:7000});
 assert.equal(await host.locator('.social-avatar').first().evaluate(el=>getComputedStyle(el).transitionDuration),'0s','remote avatar also teleports without interpolation');
 await host.screenshot({path:'leaf-two-live-chat-users.png'});
 // Each recovered roomXt foreground is selected by the actual room's
 // background style, not by a fabricated public-room number.
 await host.locator('#social-back').click();
 for(const [background,source] of [[5,'room5t'],[4,'room4t']]){
  await host.evaluate(bg=>window.__LEAF_SOCIAL__.createRoom('원본 배경 '+bg+' 테스트',bg),background);
  await host.waitForFunction(expected=>document.querySelector('.social-room-foreground')?.dataset.source===expected&&document.querySelector('.social-room-foreground')?.dataset.ready==='true',source,{timeout:16000});
  assert.equal(await host.locator('.social-room-foreground').count(),1,'one genuine foreground per room');
  await host.screenshot({path:'leaf-original-'+source+'.png'});
  await host.locator('#social-back').click();
 }
 await host.evaluate(()=>window.__LEAF_SOCIAL__.createRoom('원본 서재 배경 검증',2));
 assert.equal(await host.locator('.social-room-foreground').count(),0,'room2 has no fabricated overlay sprite');

 // Native archive has six distinct room bitmaps. In particular room0 must
 // not silently become room2 when the browser converts the string "0".
 await host.locator('#social-back').click();
 await host.locator('#social-new-room').click();
 await host.locator('#social-modal [name="name"]').fill('숲속 광장 2인 채팅');
 await host.locator('#social-modal [name="background"]').selectOption('0');
 await host.locator('#social-modal [name="capacity"]').selectOption('2');
 await host.locator('#social-modal button[type="submit"]').click();
 const limitedRoom=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId);
 assert.ok(limitedRoom,'two-person room created through real UI');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().rooms.find(r=>r.id===window.__LEAF_SOCIAL__.getState().roomId)?.background),0,'original room0 selected without Number(0) fallback error');
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().rooms.find(r=>r.id===window.__LEAF_SOCIAL__.getState().roomId)?.capacity),2,'special two-person room carries a persisted capacity');
 assert.ok((await host.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('room0.png'));
 assert.equal(await host.locator('.social-room-foreground').count(),0,'original room0 has no invented foreground table');
 await guest.locator('#social-back').click();
 await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),limitedRoom,{timeout:8000});
 await guest.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),limitedRoom);
 await host.waitForFunction(()=>document.querySelector('#social-online-count')?.textContent==='2명',null,{timeout:8000});
 // Third actual tab must observe 2/2 in the directory and be refused.
 const third=await a.newPage();
 third.on('pageerror',e=>errors.push('third: '+e.stack));
 await third.goto(url);
 await third.waitForFunction(()=>!!window.__LEAF_SOCIAL__&&!!window.__ROG_TEST__,null,{timeout:8000});
 await third.evaluate(()=>{
  window.__LEAF_SOCIAL__.openRegion('north');
  window.__ROG_TEST__.go('rooms');
 });
 await third.locator('.social-district-hotspot').nth(3).click();
 await third.waitForFunction(id=>{
   const row=[...document.querySelectorAll('.social-directory-row')].find(x=>x.dataset.room===id);
   return row?.querySelector('.social-room-users')?.textContent==='2/2명';
 },limitedRoom,{timeout:8000});
 assert.ok(await third.locator('.social-directory-row.social-room-full').count()>0,'full room is marked in the directory');
 await third.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),limitedRoom);
 assert.ok(await third.locator('#social-modal').isVisible(),'third participant is shown a full-room warning');
 assert.equal(await third.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'directory','third participant cannot enter a two-person room');
 await third.locator('.social-modal-title button').click();
 await third.close();
 await host.screenshot({path:'leaf-original-room0-two-person.png'});
 // Leaving a room for the shop must vacate it; returning restores presence.
 await host.locator('[data-route="shop"]').first().click();
 await guest.waitForFunction(()=>document.querySelector('#social-online-count')?.textContent==='1명',null,{timeout:8000});
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().scope),'away:shop','shop visitors no longer count as chat occupants');
 await host.locator('[data-route="rooms"]').first().click();
 await guest.waitForFunction(()=>document.querySelector('#social-online-count')?.textContent==='2명',null,{timeout:8000});
 assert.equal(await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().roomId),limitedRoom,'return from shop preserves the current chat room');
 // Both tabs use the same visible Guest nickname: the guest must not acquire
 // the host's room-owner privileges from this coincidental display-name match.
 assert.equal(await guest.locator('#social-close-room').count(),0,'same nickname cannot impersonate room owner');
 assert.equal(await host.locator('#social-close-room').count(),1,'true room owner retains controls');
 const owned=await host.evaluate(()=>window.__LEAF_SOCIAL__.getState().rooms.find(r=>r.id===window.__LEAF_SOCIAL__.getState().roomId));
 assert.ok(owned.ownerId&&owned.capacity===2,'owner identity and participant limit travel with the room');
 await host.locator('#social-close-room').click();
 await guest.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().view==='directory'&&!window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),limitedRoom,{timeout:8000});
 assert.equal(await guest.locator('.social-directory-row[data-room="'+limitedRoom+'"]').count(),0,'closed room disappears from other browser');


 await guest.setViewportSize({width:390,height:844});
 await guest.screenshot({path:'leaf-chat-mobile.png'});
 assert.ok(await guest.locator('#message').isVisible(),'mobile chat input');
 assert.ok(await guest.locator('#social-back').isVisible(),'mobile navigation');
 assert.deepEqual(errors,[],'no JS exceptions');
 assert.deepEqual(missingAssets,[],'all requested original art assets load without 404');
 await browser.close();
 console.log('4LEAF WORLD + CHAT PASS: original map, north/south boards, 6 interiors, real room creation, two users, cross-tab messages and speech bubbles, mobile');
})().catch(e=>{console.error('WORLD+CHAT E2E FAILED',e.stack||e);process.exit(1)});