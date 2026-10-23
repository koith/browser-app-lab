'use strict';
/* Real Playwright run, not DOM mock: generated movement dice must visibly
 * drop from the sky, bounce multiple times, spin to the SAME face handed
 * to the game engine, THEN permit pawn movement. Supports D4 and D6 eyes.
 * Our mesh/keyframes are inferred, not source MVE/EXE frames. */
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch({
  headless:true,args:engine==='webkit'?[]:['--no-sandbox']});
 const mobile=process.env.FOURLEAF_MOBILE==='1';
 const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:900},
  isMobile:mobile,hasTouch:mobile,deviceScaleFactor:mobile?2:1,serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL='';});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||
   'file://'+path.resolve(__dirname,'../index.html'));
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__&&window.__ROG_TEST__);
  await page.locator('[data-route="lobby"]').first().click();
  await page.locator('#lobby-create').click();
  await page.locator('#game-mode').selectOption('hotseat');
  await page.locator('#bot-count').selectOption('1');
  await page.locator('#map-select').selectOption('4LEAF');
  await page.locator('#start-game').click();
  await page.waitForSelector('#game:not(.hidden)');
  const before=await page.evaluate(()=>({
   turn:window.__ROG_TEST__.getMatch().active,
   count:Number(document.querySelector('#dice-box').dataset.rollCount||0)
  }));
  assert.equal(before.turn,0);assert.equal(before.count,0);
  await page.locator('#dice-source-roll').click();
  await page.waitForFunction(()=>window.__LEAF_DICE_FALL__.getState().active===true||
    window.__LEAF_DICE_FALL__.getState().active===1,{timeout:5000});
  const mid=await page.evaluate(()=>({
   phase:document.querySelector('#leaf-dice-fall-layer')?.dataset.phase,
   faceCount:document.querySelectorAll('#leaf-dice-fall-layer .leaf-die-face').length,
   total:document.querySelectorAll('#leaf-dice-fall-layer .leaf-fall-piece').length,
   count:Number(document.querySelector('#dice-box').dataset.rollCount||0),
   disabled:document.querySelector('#roll-btn').disabled,
   overlay:getComputedStyle(document.querySelector('#leaf-dice-fall-layer')).pointerEvents,
   pos:document.querySelector('#leaf-dice-fall-layer').getBoundingClientRect().toJSON(),
   original:document.querySelectorAll('#board-nodes>.tile').length,
   // Read the live geometry of the currently playing D4/D6 stage, not
   // an offscreen CSS constant. Source MVE keyframes remain unknown.
   trajectories:[...document.querySelectorAll('#leaf-dice-fall-layer .leaf-fall-piece')].map(piece=>{
    const stage=piece.closest('.leaf-dice-fall-layer');
    const height=stage.getBoundingClientRect().height;
    const trackHeight=piece.parentElement.getBoundingClientRect().height;
    return {height,trackHeight,drop:Number(piece.dataset.webFallHeight),
     bounce:piece.dataset.webBounceHeights.split(',').map(Number),
     provenance:piece.dataset.motionProvenance};
   }),
   grounded:[...document.querySelectorAll('#leaf-dice-fall-layer .leaf-fall-track')]
    .map(track=>{
     const shadow=getComputedStyle(track,'::before');
     const piece=track.querySelector('.leaf-fall-piece');
     return {shadowProvenance:track.dataset.shadowProvenance,
      anchorPosition:getComputedStyle(track).position,
      anchorTransform:getComputedStyle(track).transform,
      shadowBackground:shadow.backgroundImage,
      shadowPosition:shadow.position,
      shadowBottom:parseFloat(shadow.bottom),
      piece:!!piece,piecePosition:piece&&getComputedStyle(piece).position,
      shadowTimeline:track.style.getPropertyValue('--leaf-dice-shadow-duration')
     };
    })
  }));
  assert.equal(mid.phase,'falling','dice genuinely start high in the sky');
  assert.ok(mid.faceCount>=6&&mid.faceCount<=24,'every independent die has six visible-world 3D faces');
  assert.equal(mid.count,0,'game dice result MUST NOT appear before bounce and landing');
  assert.equal(mid.disabled,true,'other player cannot double-roll during drop');
  assert.equal(mid.overlay,'none','physics never blocks underlying game input');
  assert.equal(mid.original,104,'104 real TIS tiles unaffected by physics overlay');
  assert.ok(mid.trajectories.length===mid.total&&mid.trajectories.every(t=>
    t.provenance==='responsive-WEB-fallback/not-original-MVE'&&
    t.drop===Math.round(Math.max(28,Math.min(260,t.height-t.trackHeight-12)))&&
    t.bounce[0]===Math.round(Math.min(66,t.drop*.26))&&
    t.bounce[1]===Math.round(Math.min(19,t.drop*.075))&&
    t.bounce[0]<t.drop&&t.bounce[1]<t.bounce[0]),
   'real D4/D6 flight must fit the live viewport and rebound progressively: '+
    JSON.stringify(mid.trajectories));
  assert.equal(mid.grounded.length,mid.total,
   'every actually falling die needs an independent floor-grounded cast shadow');
  assert.ok(mid.grounded.every(t=>t.shadowProvenance==='web-inferred-ground-contact'&&
   t.anchorPosition==='relative'&&t.anchorTransform==='none'&&t.shadowPosition==='absolute'&&
   t.shadowBottom<0&&t.shadowBackground.includes('radial-gradient')&&
   t.piece&&t.piecePosition==='absolute'&&t.shadowTimeline.endsWith('ms')),
   'during actual airborne tumble, floor-shadow must stay in untransformed stage: '+
    JSON.stringify(mid.grounded));
  await page.screenshot({path:'leaf-true-falling-dice-'+engine+(mobile?'-mobile':'')+'.png'});
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box').dataset.rollCount)>0,
   null,{timeout:14000});
  const landed=await page.evaluate(()=>({
   result:window.__LEAF_DICE_FALL__.getState(),
   match:window.__ROG_TEST__.getMatch().lastRoll,
   count:Number(document.querySelector('#dice-box').dataset.rollCount)
  }));
  assert.equal(landed.count,1,'exactly one complete genuine dice roll is awarded');
  assert.deepEqual(landed.result.last,landed.match,
   'actual gameplay result was not independently re-randomized for 3D animation');
  assert.ok(landed.match.every(x=>Number.isInteger(x)&&x>=1&&x<=6));
  await page.waitForFunction(()=>window.__ROG_TEST__.getMatch().active===1&&
   !document.querySelector('#roll-btn').disabled,null,{timeout:17000});
  await page.locator('#roll-btn').click();
  await page.waitForFunction(()=>Number(document.querySelector('#dice-box').dataset.rollCount)>=2,
   null,{timeout:14000});
  assert.equal(await page.locator('#dice-box').getAttribute('data-roll-count'),'2',
   'second real participant rolls normally after their own landing');
  // D4 used to fly with a duplicate 8px CSS shadow even though D6 and
  // the tetra both have their own anchored .leaf-fall-track::before shadow.
  // Inspect rendered geometry DURING actual D4 fall, then confirm this
  // purely visual probe never mutates the real game turn/roll count.
  await page.waitForFunction(()=>!window.__LEAF_DICE_FALL__.getState().active,
   null,{timeout:12000});
  const d4Air=await page.evaluate(()=>{
   window.__LEAF_D4_AIR_TEST__=window.__LEAF_DICE_FALL__.roll([3],{sides:4});
   const track=document.querySelector('#leaf-dice-fall-layer .leaf-fall-track');
   const piece=track.querySelector('.leaf-fall-piece[data-sides="4"]');
   return {pieceFilter:getComputedStyle(piece).filter,
    groundShadow:getComputedStyle(track,'::before').backgroundImage,
    shadowProvenance:track.dataset.shadowProvenance,
    trackTransform:getComputedStyle(track).transform,
    result:piece.dataset.result,
    source:window.__LEAF_DICE_FALL__.getState().originalFramesRecovered,
    rollCount:Number(document.querySelector('#dice-box').dataset.rollCount)};
  });
  assert.equal(d4Air.pieceFilter,'none',
   'airborne D4 must not carry a second moving WEB shadow');
  assert.ok(d4Air.groundShadow.includes('radial-gradient')&&
   d4Air.shadowProvenance==='web-inferred-ground-contact'&&
   d4Air.trackTransform==='none',
   'D4 tetra must fall over a stationary ground-contact shadow');
  assert.equal(d4Air.result,'3');
  assert.equal(d4Air.source,false,'2002 3D die source still unrecovered');
  assert.equal(d4Air.rollCount,2,'D4 visual-only probe cannot mutate gameplay');
  await page.screenshot({path:'leaf-d4-stationary-shadow-'+engine+
   (mobile?'-iphone':'')+'.png'});
  const d4End=await page.evaluate(async()=>{
   const result=await window.__LEAF_D4_AIR_TEST__;
   return {result,now:Number(document.querySelector('#dice-box').dataset.rollCount)};
  });
  assert.deepEqual(d4End.result,[3],'D4 presentation must land on supplied face');
  assert.equal(d4End.now,2,'D4 shadow test must not advance game turn');

  // Inspect ALL six eye placements and final rotations on actual DOM geometry.
  // Reduced motion skips arbitrary waiting; it must still yield precisely
  // the requested source engine values.
  await page.emulateMedia({reducedMotion:'reduce'});
  const physicallyMeasured=[];
  for(let eye=1;eye<=6;eye++){
   // Inspect the actual rotating native DOM cube WHILE rendered, before
   // the presentation promise cleans up the result layer. A data/result
   // attribute is insufficient: it could say "3" while the white cube
   // visibly paints two, four, or a row of six clustered dots.
   const proof=await page.evaluate(async eye=>{
    const pending=window.__LEAF_DICE_FALL__.roll([eye]);
    const node=document.querySelector('#leaf-dice-fall-layer .leaf-fall-cube');
    const targetFace=node?.querySelector('.leaf-die-face-'+eye);
    if(!node||!targetFace)return {missing:true};
    const pipNodes=[...targetFace.querySelectorAll('.leaf-die-eye')];
    const coords=pipNodes.map((n,index)=>({
     index,x:n.offsetLeft,y:n.offsetTop,
     shown:getComputedStyle(n).visibility==='visible'&&getComputedStyle(n).display!=='none'
    }));
    // Source screenshot's red result-1 pip is deliberately 14px vs 10px
    // black pips. Grid aligns their CENTERS, so its left/top is 2px
    // before the ordinary center cell. Compare each actual pixel position
    // to the physical row/column references with a 3px centering tolerance.
    const xs=coords.slice(0,3).map(n=>n.x);
    const ys=[coords[0],coords[3],coords[6]].map(n=>n.y);
    const layout=coords.map(n=>({...n,
     col:xs.reduce((best,x,i)=>Math.abs(x-n.x)<Math.abs(xs[best]-n.x)?i:best,0),
     row:ys.reduce((best,y,i)=>Math.abs(y-n.y)<Math.abs(ys[best]-n.y)?i:best,0),
     gridCenterErrorX:Math.abs(n.x-xs[n.index%3]),
     gridCenterErrorY:Math.abs(n.y-ys[Math.floor(n.index/3)])
    }));
    const cssCube=new DOMMatrixReadOnly(getComputedStyle(node).transform);
    const normals=[...node.querySelectorAll('.leaf-die-face')].map((face,index)=>{
     const faceMatrix=new DOMMatrixReadOnly(getComputedStyle(face).transform);
     return {eye:index+1,
      towardsCamera:Number(cssCube.multiply(faceMatrix)
       .transformPoint(new DOMPoint(0,0,1,0)).z.toFixed(3))};
    });
    const realValues=await pending;
    return {result:realValues,expected:window.__LEAF_DICE_FALL__.faces[eye],
     coordinates:layout,columns:xs.length,rows:ys.length,normals,
     originalMesh:window.__LEAF_DICE_FALL__.getState().originalFramesRecovered};
   },eye);
   assert.equal(proof.missing,undefined,'D6 must instantiate source-valued real 3D geometry');
   assert.deepEqual(proof.result,[eye]);
   assert.equal(proof.columns,3,'physical D6 columns: '+JSON.stringify(proof));
   assert.equal(proof.rows,3,'physical D6 rows: '+JSON.stringify(proof));
   assert.equal(proof.coordinates.length,9);
   assert.ok(proof.coordinates.every((n,i)=>n.col===i%3&&n.row===Math.floor(i/3)&&
      n.gridCenterErrorX<=3&&n.gridCenterErrorY<=3),
    'pip grid must preserve real 3x3 positions (hidden cells remain physically laid out): '+
    JSON.stringify(proof.coordinates));
   assert.deepEqual(proof.coordinates.filter(n=>n.shown).map(n=>n.index),proof.expected,
    'result '+eye+' must show correct geometrical eyes, not auto-packed pips');
   assert.equal(proof.normals[eye-1].towardsCamera,1,
    'actual 3D result-face normal must face front for '+eye+': '+JSON.stringify(proof.normals));
   assert.equal(proof.originalMesh,false,
    'this corrected WEB fallback is not yet an original 2002 MVE die');
   physicallyMeasured.push({eye,cells:proof.expected,
    normal:proof.normals[eye-1].towardsCamera});
  }
  // The 4-sided movement die previously kept the SAME flat polygon for
  // 1, 2, 3 and 4 and only replaced its printed numeral. Verify four real
  // independent 3D triangle faces and actual result-facing 3D orientation.
  const normalResults=[];
  for(let eye=1;eye<=4;eye++){
   const proof=await page.evaluate(async eye=>{
    const pending=window.__LEAF_DICE_FALL__.roll([eye],{sides:4});
    const die=document.querySelector('#leaf-dice-fall-layer .leaf-fall-tetra');
    if(!die)return {missing:true};
    const faces=[...die.querySelectorAll('.leaf-tetra-face')];
    const cube=new DOMMatrixReadOnly(getComputedStyle(die).transform);
    const normals=faces.map(face=>{
     const matrix=cube.multiply(
      new DOMMatrixReadOnly(getComputedStyle(face).transform));
     return Number(matrix.transformPoint(new DOMPoint(0,0,1,0)).z.toFixed(3));
    });
    const renders=faces.map(face=>({
     number:Number(face.textContent),
     display:getComputedStyle(face).display,
     backface:getComputedStyle(face).backfaceVisibility,
     originY:parseFloat(getComputedStyle(face).transformOrigin.split(' ')[1]),
     faceHeight:face.offsetHeight
    }));
    const result=await pending;
    return {result,normals,renders,
     angle:window.__LEAF_DICE_FALL__.tetraDihedralDegrees,
     target:window.__LEAF_DICE_FALL__.tetraOrientation[eye]};
   },eye);
   assert.equal(proof.missing,undefined,'D4 must instantiate a real multi-face 3D object');
   assert.deepEqual(proof.result,[eye],'actual engine result is unchanged');
   assert.equal(proof.renders.length,4);
   assert.deepEqual(proof.renders.map(f=>f.number),[1,2,3,4]);
   assert.ok(proof.renders.every(f=>f.display==='flex'&&f.backface==='hidden'),
    'all D4 physical triangular planes must exist simultaneously in 3D');
   assert.ok(proof.renders.every(f=>Math.abs(f.originY-f.faceHeight*(178/300))<.15),
    'D4 triangle pivot must be the true polygon centroid (2+88+88)/3, not the bounding-box midpoint');
   assert.ok(proof.normals[eye-1]>.995,
    'result '+eye+' actual 3D surface must face the viewer rather than switch a flat label: '+JSON.stringify(proof));
   assert.ok(proof.normals.every((z,i)=>i===eye-1||z<0),
    'remaining tetrahedral surfaces must point away from final result face');
   assert.ok(Math.abs(proof.angle-109.471)<.01);
   normalResults.push({eye,normal:proof.normals[eye-1],target:proof.target});
  }
  assert.deepEqual(errors,[],'no browser exceptions on real original game');
  console.log('4LEAF DICE FALL BOUNCE AND REAL 1-6 LANDING PASS',
   JSON.stringify({engine,mobile,first:landed.match,landings:6,d6:physicallyMeasured,d4:normalResults}));
 }finally{await browser.close()}
})().catch(e=>{console.error('DICE FALL REAL TURN FAILED',e.stack||e);process.exit(1)});
