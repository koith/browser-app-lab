'use strict';
// Decode real 4LEAF TIS sprites, not a screenshot or invented tile geometry.
// Original external chroma mattes: 0000 pink, 0015 red. Only contiguous
// border matte should disappear; live event art and DMP remain untouched.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
const vm=require('node:vm');
const fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync(path.resolve(__dirname,'../dice-native-tis-alpha.js'),'utf8');
 new vm.Script(source,{filename:'dice-native-tis-alpha.js'});
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  const url=process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html');
  await page.goto(url);
  await page.waitForFunction(()=>window.__LEAF_TIS_ALPHA__&&window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const originalPath=await page.evaluate(()=>{
   const game=window.__ROG_TEST__.getMatch();
   return {map:game.map,tiles:game.tiles.length,
    dmp:[...document.querySelectorAll('#board-nodes .tile')].map(el=>[
     el.dataset.dmpX,el.dataset.dmpY,el.dataset.dmpCellCode,
     el.dataset.originalArt,el.style.zIndex
    ])};
  });
  assert.equal(originalPath.tiles,104,'true original DMP map still has 104 cells');
  assert.equal(originalPath.dmp.length,104,'each real TIS tile remains a playable DOM entity');

  if(url.startsWith('file:')){
   // file:// canvas reads are prohibited in Chromium, even though the exact
   // source PNG itself decodes. The fallback must NOT crash offline access.
   await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes .tile')]
    .every(el=>el.dataset.tisAlpha==='ready'||el.dataset.tisAlpha==='fallback'),
    null,{timeout:20000});
   assert.equal(await page.locator('#board-nodes .tile').count(),104);
   assert.ok((await page.locator('#board-nodes .tile[data-tis-alpha="fallback"]').count())>0,
    'offline file:// fallback should retain actual source art and gameplay on canvas security error');
   await page.locator('#roll-btn').click();
   await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>0,
    null,{timeout:13000});
   assert.deepEqual(errors,[],'file:// fallback has no unhandled page errors');
   console.log('NATIVE TIS KEY FILE FALLBACK PASS');
   return;
  }
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes .tile')]
   .every(el=>el.dataset.tisAlpha==='ready'||el.dataset.tisAlpha==='fallback'),
   null,{timeout:20000});
  const imageSample=await page.evaluate(async()=>{
   const decode=async url=>{
    const image=new Image();image.src=url;await image.decode();
    const canvas=document.createElement('canvas');
    canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(image,0,0);
    return {shape:[canvas.width,canvas.height],
     pixels:ctx.getImageData(0,0,canvas.width,canvas.height).data};
   };
   const probes=[];
   // Six independently archived matte palettes: pink, red, green,
   // navy, mauve and yellow. A universal red-color filter would be wrong.
   for(const id of ['0000','0015','0006','0011','0028','0046']){
    const source=await decode('./original/Tiles/'+id+'.png');
    const processed=await window.__LEAF_TIS_ALPHA__.prepare(id);
    const masked=await decode(processed.url);
    const point=(p,x,y)=>[...p.slice((y*145+x)*4,(y*145+x)*4+4)];
    probes.push({
     id,shape:source.shape,native:processed.native,
     cornerBefore:point(source.pixels,0,0),cornerAfter:point(masked.pixels,0,0),
     otherCorner:point(masked.pixels,144,96),
     centerBefore:point(source.pixels,72,48),centerAfter:point(masked.pixels,72,48),
     removed:processed.removed,pixels:processed.pixels,
     preserved:processed.alreadyTransparent,
     encoded:processed.url.startsWith('data:image/png'),
     clip:processed.clip,source:processed.source
    });
   }
   const nodes=[...document.querySelectorAll('#board-nodes .tile')];
   const chroma=nodes.map(node=>{
    const style=getComputedStyle(node);
    return {
     source:node.dataset.originalArt,
     alpha:node.dataset.tisAlpha,
     original:node.dataset.tisAlphaSource,
     removed:Number(node.dataset.tisChromaRemoved),
     preserved:node.dataset.tisSourcePreserved,
     bitmap:style.backgroundImage,
     clip:style.clipPath,
     native:[node.offsetWidth,node.offsetHeight],
     depth:node.style.zIndex,
     clickable:typeof node.onclick==='function'
    };
   });
   return {probes,chroma};
  });
  for(const item of imageSample.probes){
   assert.deepEqual(item.shape,[145,97],'unmodified recovered TIS file is 145x97');
   assert.deepEqual(item.native,[145,97]);
   assert.equal(item.cornerAfter[3],0,'actual external source matte is transparent at corner');
   assert.equal(item.otherCorner[3],0,'outer matte also cleared at lower opposite corner');
   // All six recovered source images may already have true transparent
   // outer pixels. Zero removed is correct, not an alpha-restoration failure.
   assert.ok(item.removed>=0&&item.removed<item.pixels*.65,
    'only opaque exterior matte is removed, never native art: '+JSON.stringify(item));
   if(item.removed===0){
    assert.equal(item.preserved,true,'preserve source bytes when PNG already keyed');
    assert.equal(item.encoded,false,'do not make a redundant data URL');
   }else assert.equal(item.encoded,true);
   assert.deepEqual(item.centerAfter,item.centerBefore,
    'the exact central RGB symbol and its alpha must survive untouched');
   assert.ok(item.clip?.startsWith('polygon(')&&item.clip.split('%').length>40,
    'pointer polygon comes from individual source PNG alpha silhouette');
   assert.equal(item.source,'Tiles/'+item.id+'.png');
  }
  // Compare actual alpha, never judge the key solely from RGB displayed
  // by a PNG viewer (fully transparent corners can carry arbitrary RGB).
  assert.ok(imageSample.probes.every(p=>p.cornerAfter[3]===0));
  assert.equal(imageSample.chroma.length,104);
  assert.ok(imageSample.chroma.every(t=>t.alpha==='ready'),
   'all 104 source tiles are decoded and composited by the live original atlas');
  assert.ok(imageSample.chroma.every(t=>t.original==='Tiles/'+t.source+'.png'&&
   (t.removed===0?
     t.preserved==='true'&&t.bitmap.includes('/original/Tiles/'+t.source+'.png'):
     t.bitmap.includes('data:image/png'))),
   'real DMP tiles preserve pre-keyed originals and only reencode actual opaque mattes');
  assert.ok(imageSample.chroma.every(t=>t.clip.startsWith('polygon(')&&
   t.clip.split('%').length>40),
   'real per-TIS alpha silhouette replaces a one-size-fits-all invented hexagon');
  assert.ok(imageSample.chroma.every(t=>t.clickable&&
   t.native[0]===145&&t.native[1]===97),
   'source tile hitboxes remain independently interactive at original logical dimensions');
  assert.deepEqual(imageSample.chroma.map(t=>t.depth),
   originalPath.dmp.map(c=>c[4]),'original DMP foreground painter order preserved');
  await page.screenshot({path:'leaf-original-tis-source-transparent-platforms.png'});
  // Recreating a live round should reuse original decoded assets, not trigger
  // another 104 downloads nor lose source click geometry.
  await page.evaluate(()=>{
   document.getElementById('board-nodes').dataset.renderKey='';
   window.__ROG_TEST__.drawGame();
  });
  await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes .tile')]
   .every(el=>el.dataset.tisAlpha==='ready'),null,{timeout:10000});
  assert.equal(await page.locator('#board-nodes .tile').count(),104);
  const cached=await page.evaluate(()=>window.__LEAF_TIS_ALPHA__.getState());
  assert.deepEqual(cached.native,[145,97]);
  assert.ok(cached.cached.length>=5&&cached.cached.length<104,
   'decoded source bitmaps are cached per authentic image, not per recreated tile');
  await page.evaluate(()=>window.__LEAF_CAMERA__.zoom(.35));
  const tileAfterZoom=await page.locator('#board-nodes .tile').first().evaluate(el=>({
   size:[el.offsetWidth,el.offsetHeight],
   mask:el.dataset.tisAlpha,
   pointer:getComputedStyle(el).clipPath
  }));
  assert.deepEqual(tileAfterZoom.size,[145,97],'camera zoom preserves original source pixels');
  assert.equal(tileAfterZoom.mask,'ready');
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().players[0].position>0,
   null,{timeout:13000});
  assert.equal(await page.locator('#board-pawns .board-pawn').count(),2,
   'actual game still shows only the two genuine hotseat player pieces');
  await page.setViewportSize({width:390,height:844});
  assert.deepEqual(await page.locator('#board-nodes .tile').first().evaluate(el=>[
   el.offsetWidth,el.offsetHeight]),[145,97]);
  await page.screenshot({path:'leaf-original-tis-transparent-mobile.png'});
  assert.deepEqual(errors,[],'no browser exceptions during source keying or real dice turn');
  console.log('GENESIS SOURCE TIS MATTE REMOVAL PASS',JSON.stringify({
   samples:imageSample.probes,sourceTiles:imageSample.chroma.length,cached:cached.cached.length
  }).slice(0,3500));
 }finally{await browser.close()}
})().catch(e=>{console.error('GENESIS SOURCE TIS MATTE FAIL',e.stack||e);process.exit(1)});
