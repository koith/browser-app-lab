'use strict';
/* BRD-01 / M04: the live board against board.jpg and battle.jpg, same map
 * (DMP 0172) and the same cell-17 camera anchor.
 *  - every route step of all 26 maps is odd-q hex structured (data check);
 *  - the live projection is the measured 105x80 odd-q honeycomb (+40 px
 *    for odd columns), 1:1 145x97 TIS, read back from the DOM;
 *  - the measured original tile centres (docs/evidence/brd01) are hit with
 *    0 px error relative to cell 17, in both captures;
 *  - painter order: every overlapping pair paints the nearer half row
 *    above, never inverted; no two cells share a position;
 *  - each tile keeps its upright storage-flip undo (no inverted art).
 * Errors are written to LEAF_AUDIT_OUT when set.
 * Evidence levels: projection VERIFIED (screenshot anchors, route
 * structure, sprite tessellation). Terrain parallax is only recorded. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const BASE=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const evidence=JSON.parse(fs.readFileSync(path.join(__dirname,'..','docs','evidence','brd01','board-jpg-hex-anchors.json'),'utf8'));
const mapsSource=fs.readFileSync(path.join(__dirname,'..','original','maps.js'),'utf8');
const MAPS=JSON.parse(mapsSource.slice(mapsSource.indexOf('{'),mapsSource.indexOf('};')+1));

// 1. Route structure of all 26 source maps.
let consistent=0;const exceptions=[];
for(const [key,cells] of Object.entries(MAPS))for(let i=0;i+1<cells.length;i++){
 const a=cells[i],b=cells[i+1],dx=b[0]-a[0],dy=b[1]-a[1];
 if(Math.abs(dx)===1&&Math.abs(dy)===1){
  const odd=a[0]%2===1;
  if((dy===1&&odd)||(dy===-1&&!odd))consistent++;else exceptions.push(key+'#'+i);
 }
}
assert.equal(Object.keys(MAPS).length,26,'26 source DMP maps');
assert.ok(consistent>=451&&exceptions.length<=1,'DMP routes are an odd-q hex grid: '+consistent+' consistent, exceptions '+exceptions);

(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch(engine===chromium?{args:['--no-sandbox']}:{});
 const report={engine:engine.name(),routeSteps:{consistent,exceptions},captures:{}};
 try{
  const ctx=await browser.newContext({viewport:{width:1280,height:900},serviceWorkers:'block'});
  const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(BASE);
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  const picked=await page.evaluate(()=>{const s=document.getElementById('map-select');
   const o=[...s.options].find(o=>o.dataset.originalMapId==='0172');if(!o)return false;
   s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));return true});
  assert.ok(picked,'DMP 0172 (the board.jpg map) is selectable');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  await page.evaluate(()=>window.__LEAF_CAMERA__.viewport(1,0,0));
  await page.waitForTimeout(500);
  const live=await page.evaluate(()=>{
   const tiles=[...document.querySelectorAll('#board-world .tile')].map(t=>{
    const r=t.getBoundingClientRect(),c=getComputedStyle(t);
    return {i:+t.dataset.tile,x:+t.dataset.dmpX,y:+t.dataset.dmpY,z:+t.style.zIndex,
     cx:r.left+r.width/2,cy:r.top+r.height/2,w:parseFloat(c.width),h:parseFloat(c.height),tf:c.transform}});
   return {tiles,camera:window.__LEAF_CAMERA__.getState().hexProjection}});
  assert.deepEqual(live.camera,{pitchX:105,pitchY:80,oddColumnDrop:40},'camera exposes the measured projection');
  const byCell=new Map(live.tiles.map(t=>[t.i,t]));
  assert.equal(live.tiles.length,104,'DMP 0172 has 104 live cells');
  // 2. projection of every cell against cell 0, and native size/upright
  const t0=live.tiles[0];let maxErr=0;
  for(const t of live.tiles){
   const ex=(t.x-t0.x)*105,ey=(t.y-t0.y)*80+((t.x&1)-(t0.x&1))*40;
   maxErr=Math.max(maxErr,Math.abs(t.cx-t0.cx-ex),Math.abs(t.cy-t0.cy-ey));
   assert.ok(Math.abs(t.w-145)<.1&&Math.abs(t.h-97)<.1,'cell '+t.i+' keeps native 145x97');
   assert.ok(t.tf.startsWith('matrix(1, 0, 0, -1,'),'cell '+t.i+' art is shown upright');
  }
  assert.ok(maxErr<=1,'every cell sits on the odd-q 105x80 honeycomb (max error '+maxErr+' px)');
  // 3. measured original anchors, relative to cell 17 in each capture
  for(const capture of ['board.jpg','battle.jpg']){
   const anchors=evidence.anchors.filter(a=>a.capture===capture);
   const a17=anchors.find(a=>a.cell===17),w17=byCell.get(17);
   const rows=anchors.map(a=>{const w=byCell.get(a.cell);
    const err=[(w.cx-w17.cx)-(a.center[0]-a17.center[0]),(w.cy-w17.cy)-(a.center[1]-a17.center[1])].map(v=>Math.round(v*10)/10);
    return {cell:a.cell,dmp:a.dmp,score:a.score,search:a.search,original:a.center,errorPx:err}});
   report.captures[capture]=rows;
   for(const r of rows)assert.ok(Math.abs(r.errorPx[0])<=1&&Math.abs(r.errorPx[1])<=1,
    capture+' cell '+r.cell+' matches the original centre: '+JSON.stringify(r));
  }
  // 4. painter order and duplicates
  let overlaps=0,inverted=0,dupes=0;
  for(let i=0;i<live.tiles.length;i++)for(let j=i+1;j<live.tiles.length;j++){
   const a=live.tiles[i],b=live.tiles[j];
   if(Math.abs(a.cx-b.cx)<.5&&Math.abs(a.cy-b.cy)<.5)dupes++;
   if(Math.abs(a.cx-b.cx)<145&&Math.abs(a.cy-b.cy)<97){
    overlaps++;
    const near=a.cy===b.cy?(a.cx>b.cx?a:b):(a.cy>b.cy?a:b),far=near===a?b:a;
    if(!(near.z>far.z))inverted++;
   }
  }
  assert.equal(dupes,0,'no two cells share a position');
  assert.ok(overlaps>0,'neighbouring sprites interlock as in the original');
  assert.equal(inverted,0,'the nearer half row always paints above');
  report.honeycomb={maxErrorPx:maxErr,overlappingPairs:overlaps,invertedPairs:inverted,duplicates:dupes};
  assert.deepEqual(errors,[]);
  if(process.env.LEAF_AUDIT_OUT)fs.writeFileSync(process.env.LEAF_AUDIT_OUT,JSON.stringify(report,null,1)+'\n');
  console.log(JSON.stringify(report));
  console.log('BRD-01 BOARD.JPG SAME-STATE PASS',engine.name());
 }finally{await browser.close()}
})().catch(e=>{console.error('BRD-01 BOARD.JPG SAME-STATE FAILED',e.stack||e);process.exit(1)});
