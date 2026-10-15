const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'file://'+path.resolve(__dirname,'../index.html'),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_DICE_TERRAIN__);
  const visit=async map=>{
   await page.locator('[data-route="lobby"]').first().click();
   await page.locator('#lobby-create').click();
   await page.locator('#map-select').selectOption(map);
   await page.locator('#bot-count').selectOption('1');
   await page.locator('#start-game').click();
   await page.waitForSelector('#game:not(.hidden)');
   await page.waitForFunction(name=>document.querySelector('#dice-terrain-canvas')?.dataset.terrainMap===name,map,{timeout:16000});
   return page.evaluate(()=>{
    const canvas=document.getElementById('dice-terrain-canvas');
    const world=document.getElementById('board-world');
    const tiles=[...document.querySelectorAll('#board-nodes .tile')];
    const ctx=canvas.getContext('2d');
    const samples=new Set();let opaque=0,green=0,brown=0;
    for(let y=27;y<canvas.height;y+=63)for(let x=23;x<canvas.width;x+=73){
     const rgba=[...ctx.getImageData(x,y,1,1).data];
     samples.add(rgba.slice(0,3).join(','));
     if(rgba[3]===255)opaque++;
     if(rgba[1]>rgba[0]&&rgba[1]>rgba[2])green++;
     if(rgba[0]>rgba[1]&&rgba[1]>rgba[2])brown++;
    }
    const ter=window.__LEAF_DICE_TERRAIN__.getState();
    const st=getComputedStyle(canvas),rect=canvas.getBoundingClientRect();
    return {ter,dimensions:[canvas.width,canvas.height],
     samples:samples.size,opaque,green,brown,
     sourceTileCount:tiles.filter(t=>t.dataset.originalArt&&getComputedStyle(t).backgroundImage.includes('/original/Tiles/')).length,
     tileCount:tiles.length,
     canvasCount:document.querySelectorAll('#dice-terrain-canvas').length,
     pointer:st.pointerEvents,position:st.position,
     canvasParent:canvas.parentElement.id,
     boardTransform:world.style.transform,
     tileZ:Number(getComputedStyle(document.getElementById('board-nodes')).zIndex),
     terrainZ:Number(st.zIndex),pawnCount:document.querySelectorAll('#board-pawns .board-pawn').length,
     canvasRect:rect.toJSON(),game:document.querySelector('#game').getBoundingClientRect().toJSON()};
   });
  };
  const first=await visit('4LEAF');
  assert.deepEqual(first.dimensions,[1450,1120],'terrain matches fixed DMP world/camera coordinates');
  assert.equal(first.ter.map,'4LEAF','terrain belongs to exact original selected map');
  assert.equal(first.ter.source,'DMP coordinates','source route is preserved, not random placement of source tiles');
  assert.ok(first.ter.pathLength>40,'historical map route drives landscape');
  assert.ok(first.ter.trees>35&&first.ter.rocks>20,'forest landscape contains independent vegetation and boulders');
  assert.ok(first.samples>48,'real rendered varied terrain rather than old solid navy board');
  assert.ok(first.opaque>300&&first.green>10&&first.brown>5,'landscape has natural ground/rock color and opaque terrain');
  assert.equal(first.canvasCount,1,'single registered terrain renderer, no screenshot duplicates');
  assert.equal(first.canvasParent,'board-world','camera transforms actual scenery along with TIS world');
  assert.equal(first.pointer,'none','terrain does not obstruct real TIS interaction');
  assert.ok(first.tileZ>first.terrainZ,'interactive original art tiles are in front of inferred background');
  assert.equal(first.tileCount,104,'all original 4LEAF route cells still independently exist');
  assert.equal(first.sourceTileCount,first.tileCount,'all cells still render their distinct recovered TIS art');
  assert.equal(first.pawnCount,2,'actual participant game actors remain on board');
  assert.ok(first.boardTransform.includes('scale('),'source DMP landscape shares real follow-camera transform');
  await page.screenshot({path:'leaf-source-dmp-forest-world.png'});

  // The world is not a frozen image: movement pans terrain and existing live
  // tiles together; terrain construction itself stays cached for the map.
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch()?.players[0].position>0,null,{timeout:15000});
  const moving=await page.evaluate(()=>{
   const canvas=document.querySelector('#dice-terrain-canvas');
   return {count:document.querySelectorAll('#dice-terrain-canvas').length,
    seed:canvas.dataset.terrainSeed,tiles:document.querySelectorAll('#board-nodes .tile').length,
    pawns:document.querySelectorAll('#board-pawns .board-pawn').length};
  });
  assert.equal(moving.seed,String(first.ter.seed),'camera/turns reuse same map landscape without random flicker');
  assert.equal(moving.count,1,'moving original pawn never clones source terrain');
  assert.equal(moving.tiles,first.tileCount,'real board remains interactive');
  await page.locator('#exit-game').click();
  await page.locator('#modal-buttons button').filter({hasText:'나가기'}).click();
  const second=await visit('악마의 달팽이');
  assert.notEqual(second.ter.seed,first.ter.seed,'a different original DMP map renders distinct deterministic scenery');
  assert.notEqual(second.ter.map,first.ter.map);
  assert.ok(second.ter.pathLength>20&&second.tileCount>20,'second original map retains independently mapped TIS route');
  assert.equal(second.canvasCount,1,'the same functioning canvas is reused on real map switch');
  await page.screenshot({path:'leaf-source-dmp-forest-snail.png'});
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.locator('#roll-btn').isVisible(),'mobile still has real dice button');
  assert.equal(await page.locator('#dice-terrain-canvas').evaluate(el=>getComputedStyle(el).pointerEvents),'none','mobile terrain does not intercept taps');
  assert.deepEqual(errors,[],'forest landscape adds no browser script errors');
  console.log('SOURCE-GROUNDED FOREST TERRAIN PASS: 25 map-capable world, independent live original TIS, deterministic camera landscape, 2 playable scenes and mobile');
 }finally{await browser.close()}
})().catch(error=>{console.error('SOURCE FOREST TERRAIN FAIL',error.stack||error);process.exit(1)});
