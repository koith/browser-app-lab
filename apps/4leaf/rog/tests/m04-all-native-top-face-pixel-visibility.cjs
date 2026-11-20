'use strict';
/* M04: quantitative native RGBA top-face exposure of every rendered TIS cell
 * in 26 original DMP maps. Source original 145×97 PNG is displayed scaleY(-1).
 * The 2004 battle.jpg reference supports 105×80 odd-q projection; the historic
 * MVE camera, terrain parallax and native mesh are not inferred from pixels. */
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
(async()=>{
 const browser=await engine.launch({headless:true,args:engine===chromium?['--no-sandbox']:[]});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_MAPS&&window.__LEAF_TIS_ALPHA__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const result=await page.evaluate(async()=>{
   const game=window.__ROG_TEST__,refs=window.ORIGINAL_LEAF_MAPS,info=game.getSourceMaps();
   const before=game.getMatch(),log=[],W=145,H=97;
   const source=new Map();
   const alpha=async id=>{
    if(!source.has(id))source.set(id,await window.__LEAF_TIS_ALPHA__.prepare(id));
    return source.get(id).alpha;
   };
   const pixel=(a,x,y)=>x>=0&&x<W&&y>=0&&y<H?a[(H-1-y)*W+x]:0;
   for(const [id,meta] of Object.entries(info)){
    const route=refs[id],tiles=game.generateTiles(meta.title);
    if(!route||tiles.length!==route.length)throw Error('DMP source missing '+id);
    game.setMatch({...before,map:meta.title,tiles,active:0,round:1,finished:false,
      players:before.players.map(p=>({...p,position:0}))});
    const nodes=[...document.querySelectorAll('#board-nodes>.tile')];
    if(nodes.length!==route.length)throw Error('Rendered source tiles missing '+id);
    const rows=nodes.map((node,i)=>{
     const x=Number(node.dataset.dmpX),y=Number(node.dataset.dmpY);
     const art=node.dataset.originalArt;
     const z=Number(node.style.zIndex);
     if(x!==route[i][0]||y!==route[i][1]||!art||
       z!==(2*y+(x&1))*256*8+x*8)
       throw Error('Wrong source coordinates, art or painter depth '+id+'/'+i);
     if(node.offsetWidth!==W||node.offsetHeight!==H)
       throw Error('Wrong original 145x97 pixel dimensions '+id+'/'+i);
     return {index:i,x:x*105,y:y*80+(x&1?40:0),art,z};
    });
    await Promise.all([...new Set(rows.map(r=>r.art))].map(alpha));
    let visible=0,min=1,mostCovered=null,centerMisses=0;
    for(const a of rows){
     const own=source.get(a.art).alpha;
     const nearer=rows.filter(b=>b!==a&&b.z>a.z&&
      b.x<a.x+W&&a.x<b.x+W&&b.y<a.y+H&&a.y<b.y+H);
     let full=0,exposed=0,center=0;
     for(let y=8;y<=79;y++)for(let x=10;x<W-10;x++){
      if(pixel(own,x,y)<128)continue;
      full++;
      if(x>=64&&x<=80&&y>=34&&y<=60)center++;
      const absX=a.x+x,absY=a.y+y;
      if(!nearer.some(b=>pixel(source.get(b.art).alpha,absX-b.x,absY-b.y)>=128))
       exposed++;
     }
     if(full<200||center<3)throw Error('Native top-face alpha absent '+id+'/'+a.index);
     const ratio=exposed/full;visible++;
     if(ratio<min){min=ratio;mostCovered={map:id,index:a.index,art:a.art,ratio:+ratio.toFixed(4),full,exposed,nearer:nearer.length}}
     if(ratio<.70)centerMisses++;
    }
    log.push({map:id,tiles:rows.length,visible,minTopFaceExposure:+min.toFixed(4),mostCovered,unsafeBelow70Percent:centerMisses});
   }
   game.setMatch(before);
   return {maps:log,checked:visible,sourceTypes:source.size,
    cells:log.reduce((n,r)=>n+r.tiles,0),unsafe:log.reduce((n,r)=>n+r.unsafeBelow70Percent,0),
    worst:log.reduce((m,r)=>r.minTopFaceExposure<m.minTopFaceExposure?r:m,log[0])};
  });
  assert.equal(result.maps.length,26);
  assert.equal(result.cells,1920,'M04 all source DMP cells');
  assert.ok(result.sourceTypes>=25,'source TIS alpha variants');
  assert.equal(result.unsafe,0,'native platform top faces must not be substantially hidden');
  assert.deepEqual(errors,[]);
  console.log('M04 ORIGINAL 1920 TOP-FACE PIXEL VISIBILITY PASS '+JSON.stringify({
   browser:engine.name(),maps:result.maps.length,cells:result.cells,sourceTypes:result.sourceTypes,
   unsafe:result.unsafe,worst:result.worst}));
 }finally{await browser.close()}
})().catch(e=>{console.error('M04 TOP-FACE PIXEL AUDIT FAILED',e.stack||e);process.exit(1)});
