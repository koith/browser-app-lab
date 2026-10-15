'use strict';
// Region/regionback.png with TOWN SELECT is a Genesis World dice channel menu.
// WorldMap north/south Haiacan are entirely separate ChatTown destinations.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1120,height:820}});
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(base);
  await page.waitForFunction(()=>window.__LEAF_WORLD__&&window.__LEAF_LOBBY__&&window.__LEAF_SOCIAL__&&window.__ROG_TEST__);
  await page.locator('[data-region="north"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'north Haiacan must be chat');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'north');
  assert.ok((await page.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('ChatTown/northback.png'));
  assert.equal(await page.locator('#dice-channels:not(.hidden)').count(),0,'no dice channel art within northern ChatTown');
  await page.locator('[data-route="sky"]').first().click();
  await page.locator('[data-region="south"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'south Haiacan must be chat');
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south');
  assert.ok((await page.locator('#social-image-frame').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('ChatTown/southback.png'));
  await page.locator('[data-route="sky"]').first().click();

  await page.locator('[data-region="dice"]').click();
  assert.ok(await page.locator('#dice-channels:not(.hidden)').isVisible(),'dice island alone opens TOWN SELECT');
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28,'seven original dice channels with four seats each');
  assert.equal(await page.locator('#rooms:not(.hidden)').count(),0,'dice channel screen is not ChatTown');
  assert.ok((await page.locator('#dice-channel-stage').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('Region/regionback.png'));
  await page.locator('#dice-channels [data-channel="ispin:3"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().channel),'ispin:3');
  assert.equal(await page.evaluate(()=>window.__LEAF_LOBBY__.getState().region),'genesis','dice channels have no Haiacan chat region');
  assert.ok(await page.locator('#lobby:not(.hidden)').isVisible());
  // Native client 0.9 installation resources: ROOM SELECT Map PAK (794x404),
  // not the unrelated distorted 800x540 Gif/d1lobby mockup.
  await page.waitForFunction(()=>window.__LEAF_DICE_NATIVE__?.getState().scale>0);
  const nativeSelect=await page.evaluate(()=>{
   const stage=document.getElementById('dice-native-stage');
   return {...window.__LEAF_DICE_NATIVE__.getState(),
    background:getComputedStyle(stage).backgroundImage,
    create:stage.querySelector('#lobby-create')?.getBoundingClientRect().width,
    join:stage.querySelector('#lobby-join')?.getBoundingClientRect().width};
  });
  assert.equal(nativeSelect.source,'Map/mapback.png');
  assert.deepEqual([nativeSelect.width,nativeSelect.height],[794,404]);
  assert.ok(nativeSelect.background.includes('original/Map/mapback.png'),
   'original 794x404 Map ROOM SELECT background is used');
  assert.ok(Math.abs(nativeSelect.actualStageWidth/nativeSelect.actualStageHeight-794/404)<.001,
   'native room selector scales uniformly, no non-native stretching');
  assert.ok(nativeSelect.actualStageWidth<=nativeSelect.availableWidth+2
         &&nativeSelect.actualStageHeight<=nativeSelect.availableHeight+2,
   'room selector is fully visible rather than cropped');
  assert.ok(nativeSelect.create>35&&nativeSelect.join>35,
   'native CREATE/JOIN image hotspots are interactive');
  // Original Map/mapbutton.png is an 880×210 source atlas. Its real first
  // CREATE/JOIN frames match the unchanged Map/mapback.png pixels at
  // (28,317) and (334,312), not approximated screenshot placements.
  await page.waitForFunction(()=>window.__LEAF_DICE_MAP_BUTTONS__?.getState().loaded==='true'
   &&window.__LEAF_DICE_MAP_BUTTONS__?.getState().list==='true',null,{timeout:16000});
  const originalMapButtons=await page.evaluate(async()=>{
   const state=window.__LEAF_DICE_MAP_BUTTONS__.getState();
   const makeImage=async(path)=>{const img=new Image();img.src=path;await img.decode();return img};
   const [atlas,back]=await Promise.all([
    makeImage('./original/Map/mapbutton.png'),makeImage('./original/Map/mapback.png')
   ]);
   const ctx=(img)=>{const c=document.createElement('canvas');c.width=img.width;c.height=img.height;
    const g=c.getContext('2d',{willReadFrequently:true});g.drawImage(img,0,0);return g};
   const pixels=ctx(atlas).getImageData(0,0,atlas.width,atlas.height).data;
   const backdrop=ctx(back).getImageData(0,0,back.width,back.height).data;
   const match=state.buttons.map(b=>{
    let total=0,n=0;
    const sourceY=b.id==='lobby-create'?63:136;
    for(let y=0;y<b.h;y+=2)for(let x=0;x<b.w;x+=2){
     const p=((sourceY+y)*atlas.width+x)*4;
     const r=pixels[p],g=pixels[p+1],blue=pixels[p+2];
     if(r<=60&&g>=225&&blue<=70)continue;
     const q=((b.y+y)*back.width+b.x+x)*4;
     for(let k=0;k<3;k++){total+=Math.abs(pixels[p+k]-backdrop[q+k]);n++}
    }
    return {...b,meanError:total/n,compared:n};
   });
   const frame=getComputedStyle(document.getElementById('dice-native-stage')).getPropertyValue('--native-map-row');
   return {source:[atlas.naturalWidth,atlas.naturalHeight],
    listFrame:frame.includes('data:image/png;base64,'),match};
  });
  assert.deepEqual(originalMapButtons.source,[880,210],'actual source map button atlas is loaded');
  assert.deepEqual(originalMapButtons.match.map(({x,y,w,h})=>[x,y,w,h]),[
   [28,317,220,72],[334,312,183,72]
  ],'both original CREATE/JOIN hitboxes align to Map/mapback source pixels');
  assert.ok(originalMapButtons.match.every(b=>b.meanError<23&&b.compared>3000),
   'original button frame pixels correlate with native mapback: '+JSON.stringify(originalMapButtons.match));
  assert.ok(originalMapButtons.listFrame,'real 402×23 maplist row frames are composed from source');
  assert.equal(await page.locator('#lobby-join .dice-original-map-button-art').getAttribute('data-frame'),'3',
   'empty room list draws original disabled JOIN state, not a fake text button');
  await page.locator('#lobby-create').hover();
  const nativeHover=await page.locator('#lobby-create .dice-original-map-button-art').evaluate(canvas=>{
   const data=canvas.getContext('2d',{willReadFrequently:true})
    .getImageData(0,0,canvas.width,canvas.height).data;
   let opaque=0,leakedGreen=0;
   for(let i=0;i<data.length;i+=4){
    if(data[i+3]<120)continue;
    opaque++;
    if(data[i]<=60&&data[i+1]>=225&&data[i+2]<=70)leakedGreen++;
   }
   return {frame:canvas.dataset.frame,opaque,leakedGreen};
  });
  assert.equal(nativeHover.frame,'1','hover selects actual second CREATE sprite frame');
  assert.ok(nativeHover.opaque>1000,'native hover frame contains real source bitmap pixels');
  assert.equal(nativeHover.leakedGreen,0,'original chroma green does not obscure mapback');

  const sourceRoomInfo=await page.locator('#lobby-room-info>div').evaluateAll(els=>els.map(el=>({
   field:el.dataset.field,x:parseFloat(getComputedStyle(el).left),
   y:parseFloat(getComputedStyle(el).top),width:parseFloat(getComputedStyle(el).width)
  })));
  assert.deepEqual(sourceRoomInfo.filter(x=>['방제','방장','인원','MAP','소환수치','방식','상태'].includes(x.field)),[
   {field:'방제',x:502,y:180,width:264},
   {field:'방장',x:502,y:202,width:125},
   {field:'인원',x:677,y:202,width:95},
   {field:'MAP',x:502,y:226,width:125},
   {field:'소환수치',x:693,y:226,width:78},
   {field:'방식',x:514,y:249,width:102},
   {field:'상태',x:677,y:249,width:92}
  ],'dynamic ROOM INFO values inhabit separate original 794x404 bitmap cells, not a 7-row fake scroll pane');
  assert.equal(await page.locator('#lobby-room-info>div[data-field="방식"]').isVisible(),false,
   'do not paint non-native local game mode over source STYLE toggle artwork');
  assert.equal(await page.locator('#lobby-room-info>div[data-field="상태"]').isVisible(),false,
   'do not paint internal server status over original PUBLIC/PRIVATE artwork');
  await page.screenshot({path:'leaf-dice-native-map-select.png'});
  await page.locator('#lobby-create').click();
  assert.ok(await page.locator('#dice-lobby-scene.config-open').isVisible());
  assert.ok((await page.locator('#dice-native-stage').evaluate(el=>getComputedStyle(el).backgroundImage))
   .includes('original/Room/roomback.png'),'original READY and CHESSMAN INFO are drawn from Room/roomback.png');
  assert.ok(await page.locator('#lobby-players .lobby-seat').count()===8,'native PLAYER panel displays eight distinct seats');
  assert.equal(await page.locator('#dice-team-picker').getAttribute('aria-expanded'),'false');
  await page.locator('#dice-team-picker').click();
  assert.ok(await page.locator('#dice-room-config .team-select').isVisible(),
   'native SELECT hotspot opens real interactive chessman controls');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#dice-team-picker').getAttribute('aria-expanded'),'false',
   'chessman panel closes without concealing recovered client art');
  await page.screenshot({path:'leaf-dice-native-ready-room.png'});
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  assert.deepEqual(await page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();return [m.diceRegion,m.diceChannel]}),['genesis','ispin:3'],'saved game carries actual dice channel');
  await page.evaluate(()=>window.__ROG_TEST__.go('sky'));
  await page.locator('[data-region="south"]').click();
  assert.ok(await page.locator('#rooms:not(.hidden)').isVisible(),'playing dice does not rewire Haiacan chat');
  await page.locator('[data-route="sky"]').first().click();
  await page.locator('[data-region="dice"]').click();
  await page.locator('#dice-channels [data-channel="benya:4"]').click();
  assert.deepEqual(await page.evaluate(()=>{const s=window.__LEAF_LOBBY__.getState();return [s.region,s.channel]}),['genesis','benya:4']);
  assert.equal(await page.locator('#lobby-room-list .lobby-room-row').count(),0,'a saved Ispin match does not leak into Benya channel');
  assert.ok(await page.locator('#lobby-room-list .lobby-room-empty').isVisible(),'other dice channel correctly has an empty lobby');

  // Retain chat logs saved by earlier incorrect region/channel mixing.
  await page.evaluate(()=>{
   const oldScope='town:north:ispin:2',key='leaf_social_log_'+encodeURIComponent(oldScope);
   localStorage.setItem(key,JSON.stringify([{id:'legacy-dice-chat-key-test',scope:oldScope,
    text:'보존되어야 할 이전 채팅 기록',user:'기존사용자',sender:'old-tab',time:Date.now()-50000}]));
  });
  await page.reload();
  await page.waitForFunction(()=>window.__LEAF_LOBBY__&&window.__LEAF_SOCIAL__);
  assert.deepEqual(await page.evaluate(()=>{const s=window.__LEAF_LOBBY__.getState();return [s.region,s.channel]}),['genesis','benya:4'],'dice channel persists independent of chat region');
  await page.locator('[data-region="north"]').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().view),'town');
  assert.ok((await page.locator('#chat-log').textContent()).includes('보존되어야 할 이전 채팅 기록'),'old misclassified chat history is preserved');
  assert.ok(await page.evaluate(()=>localStorage.getItem('leaf_social_log_'+encodeURIComponent('town:north:ispin:2'))!==null),'original saved chat keys not destroyed');
  await page.locator('#social-chat-south').click();
  assert.equal(await page.evaluate(()=>window.__LEAF_SOCIAL__.getState().region),'south');
  assert.equal(await page.locator('.dice-channel-hotspot').count(),28,'ChatTown navigation never alters Genesis channel selector');
  await page.screenshot({path:'leaf-dice-channel-chat-independent.png'});
  assert.deepEqual(errors,[],'no browser exceptions');
  console.log('GENESIS DICE TOWN SELECT PASS: WorldMap Haiacan→ChatTown, dice→28 channel slots, saved match isolation and history');
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS DICE TOWN SELECT FAILED',e.stack||e);process.exit(1)});
