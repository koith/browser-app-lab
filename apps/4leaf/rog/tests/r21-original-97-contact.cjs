'use strict';
/* ACT-04 native 2D grounding exhaustive: 97 uniquely owned original OBS
 * body sprites in an actual source DMP board tile. This does NOT assert
 * the 2004 MVE 3D mesh, collision normals or camera are recovered. */
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.stack||String(e)));
 const report={engine,sourceContract:'source-native-2D-only;original-3D-pivot-unverified',observations:[]};
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_GENESIS_ACTORS__&&window.__LEAF_CHR_BODY_MAP__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const ids=await page.evaluate(()=>Object.keys(window.__LEAF_CHR_BODY_MAP__.cards)
   .filter(id=>Boolean(window.__LEAF_CHR_BODY_MAP__.resolve(id))).sort());
  assert.equal(ids.length,97,'original actor roster has exactly 97 actual full body sources');
  for(const [index,id] of ids.entries()){
   await page.evaluate(id=>{
    const T=window.__ROG_TEST__,m=T.getMatch();
    m.players[0].team=['c_'+id];m.players[0].position=1;
    T.setMatch(m);T.drawGame();
   },id);
   await page.waitForFunction(id=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    if(!pawn||pawn.dataset.chessmanId!==id||pawn.dataset.actorRig!=='original-obs-sprite')return false;
    const img=pawn.querySelector('img.leaf-chess-original-obs');
    const body=window.__LEAF_CHR_BODY_MAP__.resolve(id);
    return !!body&&!!img&&img.complete&&img.naturalWidth>0&&
      body.frames.some(f=>f.url===img.getAttribute('src'));
   },id,{timeout:14000});
   const row=await page.evaluate(id=>{
    const pawn=document.querySelector('#board-pawns .board-pawn[data-id="0"]');
    const img=pawn.querySelector('img.leaf-chess-original-obs');
    const tile=document.querySelector('#board-nodes>.tile[data-tile="1"]');
    const native=window.__LEAF_CHR_BODY_MAP__.resolve(id);
    const r=img.getBoundingClientRect(),pr=pawn.getBoundingClientRect();
    return {id,source:img.getAttribute('src'),member:native.originalMember,
     rig:pawn.dataset.actorRig,frame:pawn.dataset.actorFrame,
     sourceContactWidth:Number(pawn.dataset.sourceContactWidth),
     image:[img.naturalWidth,img.naturalHeight],
     cssContact:getComputedStyle(pawn).getPropertyValue('--leaf-native-contact-width').trim(),
     painter:Number(getComputedStyle(pawn).zIndex),tileZ:Number(tile.style.zIndex),
     tile:tile.dataset.originalArt,tileSize:tile.dataset.nativeTisSize,
     actorBox:[r.x,r.y,r.width,r.height].map(v=>+v.toFixed(1)),
     pawnBox:[pr.x,pr.y,pr.width,pr.height].map(v=>+v.toFixed(1))};
   },id);
   assert.match(row.source,/^\.\/original\/OBS\//,'only original source body for '+id);
   assert.ok(row.member.includes('.obs'),'must link to own original OBS/OBS2/OBS3 body '+id);
   assert.ok(row.sourceContactWidth>=10&&row.sourceContactWidth<=130,
    'non-fabricated source proportional footprint '+id+': '+JSON.stringify(row));
   assert.ok(row.image[0]>0&&row.image[1]>0);
   assert.ok(row.actorBox[2]>0&&row.actorBox[3]>0);
   assert.ok(row.painter>row.tileZ&&row.painter<=row.tileZ+8,
    'actor draws over own genuine source TIS but in same-depth painter order '+id);
   assert.equal(row.tileSize,'145x97');
   report.observations.push(row);
   if(index%20===0||index===ids.length-1)
    await page.screenshot({path:'leaf-r21-original-actor-contact-'+String(index).padStart(3,'0')+'.png'});
  }
  const memberSet=new Set(report.observations.map(r=>r.member));
  assert.equal(memberSet.size,97,'source CHR body must never masquerade as another card');
  assert.deepEqual(errors,[]);
  report.sourceBodyCount=ids.length;report.original3DPerspectiveVerified=false;
  fs.writeFileSync('leaf-r21-native-actor-97-foot-contact.json',JSON.stringify(report,null,2)+'\n');
  console.log('R21_NINETYSEVEN_OWN_OBS_REAL_BOARD_CONTACT_PASS',JSON.stringify({
   engine,actors:ids.length,members:memberSet.size,
   contactRange:[Math.min(...report.observations.map(r=>r.sourceContactWidth)),
    Math.max(...report.observations.map(r=>r.sourceContactWidth))],
   map:'4LEAF',nativeTile:'145x97',
   native3DSource:'UNVERIFIED',previewShots:6}));
 }finally{await browser.close()}
})().catch(e=>{console.error('R21_ACTOR_CONTACT_EXHAUSTIVE_FAIL',e.stack||e);process.exit(1)});
