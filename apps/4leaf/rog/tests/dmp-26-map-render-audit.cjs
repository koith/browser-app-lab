'use strict';
/* 26-map DMP/TIS live render audit (round 13, 2026-11-05). NO sampling:
 * every one of the 26 source maps, every rendered cell.
 * Per map, from the live Chromium DOM and the real Tiles/*.png alpha:
 *  - one live tile per DMP route cell, each art loaded at native 145x97;
 *  - start art 0024 / goal art 0018 on the first / last cell;
 *  - every tile carries the storage-flip undo (computed matrix d = -1);
 *  - opaque-pixel overlap between ALL tile pairs (alpha masks placed at
 *    their world positions), and painter depth for every touching pair:
 *    the cell nearer the camera (greater DMP y, then x) must paint above;
 *  - minimum opaque gap between consecutive route cells (reported only:
 *    the 2002 MVE projection that would fix the true spacing is missing);
 *  - pawn on start / goal / straight / turn / cross / jump cells: foot
 *    pixel (screenshot diff) vs tile centre, pawn depth above its own
 *    tile, DMP-grounded travel facing, own tile on screen after camera
 *    follow.
 * Tile crops (one per distinct art) are written for an offline
 * upright-vs-inverted pixel comparison (tools/tis-orientation-compare.py).
 * Tolerances are WEB rules (INFERRED). A PASS here is NOT a claim of
 * original 3D mesh/camera fidelity, which stays UNVERIFIED.
 * Env: LEAF_AUDIT_OUT=<json>, LEAF_AUDIT_CROPS=<dir>, LEAF_MAPS=0,5 (debug). */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const FOOT_X=16,FOOT_Y=22; // CSS px at camera scale 1 (INFERRED WEB rule)

async function openLobby(page){
 await page.goto(base);
 await page.waitForFunction(()=>window.__ROG_TEST__&&window.__LEAF_CAMERA__);
 await page.locator('[data-route="lobby"]').first().click();
 await page.locator('#lobby-create').click();
}
// Wait until the camera transform and the pawn box stop changing
// (board-world has a .13s transform transition; walks take ~1s).
async function settle(page,sel){
 let last='';
 for(let n=0;n<40;n++){
  const now=await page.evaluate(sel=>{const w=document.getElementById('board-world');const p=sel&&document.querySelector(sel);
   const r=p?p.getBoundingClientRect():{left:0,top:0};
   return getComputedStyle(w).transform+'|'+r.left.toFixed(1)+','+r.top.toFixed(1)+'|'+(p?.dataset.actorPose||'')},sel);
  if(now===last&&!/walk/.test(now))return true;last=now;await page.waitForTimeout(120);
 }
 return false;
}
async function footDiff(page,sel){
 // Diff only a window around the measured pawn, with every OTHER pawn
 // hidden: idle OBS animation of other chessmen and the animated ROLL cup
 // must not be mistaken for this pawn's foot.
 const area=await page.evaluate(sel=>{const a=document.getElementById('board-area').getBoundingClientRect(),
   p=document.querySelector(sel).getBoundingClientRect();
  for(const o of document.querySelectorAll('#board-pawns .board-pawn'))if(o!==document.querySelector(sel))o.dataset.auditHidden=o.style.visibility||'-',o.style.visibility='hidden';
  const l=Math.max(0,a.left,p.left-60),t=Math.max(0,a.top,p.top-60),r=Math.min(innerWidth,a.right,p.right+60),b=Math.min(innerHeight,a.bottom,p.bottom+60);
  return {x:l,y:t,width:Math.max(1,r-l),height:Math.max(1,b-t)}},sel);
 const a=await page.screenshot({clip:area});
 await page.evaluate(s=>{const e=document.querySelector(s);e.style.visibility='hidden'},sel);
 const b=await page.screenshot({clip:area});
 await page.evaluate(s=>{document.querySelector(s).style.visibility='';
  for(const o of document.querySelectorAll('#board-pawns .board-pawn[data-audit-hidden]')){o.style.visibility=o.dataset.auditHidden==='-'?'':o.dataset.auditHidden;delete o.dataset.auditHidden}},sel);
 const r=await page.evaluate(async([a,b])=>{
  const load=async s=>{const bm=await createImageBitmap(await (await fetch('data:image/png;base64,'+s)).blob());
   const c=new OffscreenCanvas(bm.width,bm.height),x=c.getContext('2d');x.drawImage(bm,0,0);return x.getImageData(0,0,bm.width,bm.height)};
  const A=await load(a),B=await load(b);let maxY=-1;const rows={};
  for(let y=0;y<A.height;y++)for(let x=0;x<A.width;x++){const i=(y*A.width+x)*4;
   if(Math.abs(A.data[i]-B.data[i])+Math.abs(A.data[i+1]-B.data[i+1])+Math.abs(A.data[i+2]-B.data[i+2])>60){
    if(y>maxY)maxY=y;(rows[y]||(rows[y]=[])).push(x)}}
  if(maxY<0)return null;
  // ignore a thin drop-shadow tail: take the lowest row band holding >=3 px
  let foot=maxY;while(foot>0&&(rows[foot]||[]).length<3)foot--;
  const xs=[];for(let y=foot-3;y<=foot;y++)if(rows[y])xs.push(...rows[y]);xs.sort((p,q)=>p-q);
  return {x:xs[xs.length>>1],y:foot};
 },[a.toString('base64'),b.toString('base64')]);
 return r&&{x:r.x+area.x,y:r.y+area.y};
}
function categories(route){
 const key=p=>p[0]+','+p[1],idx=new Map(route.map((p,i)=>[key(p),i]));
 const dir=(a,b)=>[Math.sign(b[0]-a[0]),Math.sign(b[1]-a[1])].join();
 const unit=(a,b)=>Math.max(Math.abs(b[0]-a[0]),Math.abs(b[1]-a[1]))===1;
 const out={start:0,goal:route.length-1};
 for(let i=1;i<route.length-1;i++){
  const d0=dir(route[i-1],route[i]),d1=dir(route[i],route[i+1]);
  if(out.straight===undefined&&d0===d1&&unit(route[i-1],route[i])&&unit(route[i],route[i+1]))out.straight=i;
  if(out.turn===undefined&&d0!==d1&&unit(route[i-1],route[i]))out.turn=i;
  if(out.jump===undefined&&!unit(route[i-1],route[i]))out.jump=i;
  if(out.cross===undefined){
   // a junction: a non-consecutive route cell is also a grid neighbour
   let n=0;for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){if(!dx&&!dy)continue;
    const j=idx.get((route[i][0]+dx)+','+(route[i][1]+dy));if(j!==undefined&&Math.abs(j-i)>1)n++}
   if(n>0)out.cross=i;
  }
 }
 return out;
}
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:800,height:600},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 const crops=process.env.LEAF_AUDIT_CROPS;if(crops)fs.mkdirSync(crops,{recursive:true});
 const report={generated:new Date().toISOString(),engine,viewport:'800x600',
  scope:'all 26 source DMP maps, every route cell; live DOM + real TIS alpha',
  tolerances:{footX:FOOT_X,footY:FOOT_Y,status:'INFERRED WEB'},
  unverified:['2002 MVE mesh elevation/camera matrix','true on-screen tile spacing (web pitch 150x100 is a calibration)'],
  maps:[]};
 const failures=[];const seenArt=new Set();
 try{
  await openLobby(page);
  let opts=(await page.$$eval('#map-select option',o=>o.map(x=>x.value))).filter(v=>v!=='__RANDOM__');
  assert.equal(opts.length,26,'26 source maps offered');
  const only=process.env.LEAF_MAPS?process.env.LEAF_MAPS.split(',').map(Number):null;
  for(const [k,map] of opts.entries()){
   if(only&&!only.includes(k))continue;
   if(k>0||only){await page.evaluate(()=>localStorage.removeItem('rog_match'));await openLobby(page)}
   await page.locator('#game-mode').selectOption('hotseat');
   await page.locator('#map-select').selectOption(map);
   await page.locator('#start-game').click();
   await page.waitForSelector('#game:not(.hidden)');
   await page.waitForFunction(()=>[...document.querySelectorAll('#board-nodes .tile')].length>0);
   await page.waitForTimeout(400);
   const board=await page.evaluate(async()=>{
    const T=window.__ROG_TEST__,m=T.getMatch(),S=window.__LEAF_CAMERA__.getState().size;
    const info=T.getSourceMaps(),srcId=(Object.entries(info).find(([id,v])=>v&&(v.name===m.map||v.title===m.map))||[])[0];
    const tiles=[...document.querySelectorAll('#board-nodes .tile')].map(t=>{
     const cs=getComputedStyle(t),mtx=new DOMMatrixReadOnly(cs.transform==='none'?undefined:cs.transform);
     return {i:Number(t.dataset.tile),x:parseFloat(t.style.left)/100*S.width,y:parseFloat(t.style.top)/100*S.height,
      dmp:[Number(t.dataset.dmpX),Number(t.dataset.dmpY)],code:Number(t.dataset.dmpCellCode),
      art:t.dataset.originalArt||null,type:t.className.replace('tile ',''),z:Number(t.style.zIndex),
      w:t.offsetWidth,h:t.offsetHeight,flipD:+mtx.d.toFixed(3)}}).sort((a,b)=>a.i-b.i);
    // real alpha of each art
    const arts={};
    for(const art of new Set(tiles.map(t=>t.art).filter(Boolean))){
     const img=new Image();img.src='./original/Tiles/'+art+'.png';
     try{await img.decode()}catch{arts[art]={ok:false};continue}
     const c=new OffscreenCanvas(img.naturalWidth,img.naturalHeight),x=c.getContext('2d');x.drawImage(img,0,0);
     const d=x.getImageData(0,0,c.width,c.height).data,mask=new Uint8Array(c.width*c.height);
     for(let p=0;p<mask.length;p++)mask[p]=d[p*4+3]>16?1:0;
     arts[art]={ok:true,w:c.width,h:c.height,mask:Array.from(mask)};
    }
    return {map:m.map,srcId,tileTypes:m.tiles,route:window.__LEAF_SOURCE_ROUTE_FOR_AUDIT__||null,tiles,arts,
     routeLen:(T.getSourceMaps()[srcId]?.cells)||null};
   });
   // source route from the static data the page itself uses
   const route=await page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();
    return [...document.querySelectorAll('#board-nodes .tile')].sort((a,b)=>a.dataset.tile-b.dataset.tile)
     .map(t=>[Number(t.dataset.dmpX),Number(t.dataset.dmpY),Number(t.dataset.dmpCellCode)])});
   const T=board.tiles,A=board.arts;
   // opaque overlap & depth over ALL pairs (bbox prefilter, then alpha)
   // Screen rendering applies scaleY(-1) about the centre, so the drawn
   // mask row r is stored row (h-1-r).
   const drawn=(t)=>{const a=A[t.art];if(!a||!a.ok)return null;return {a,l:Math.round(t.x-t.w/2),tp:Math.round(t.y-t.h/2)}};
   let overlapPairs=[],depthViolations=[],maxOverlap=0;
   for(let p=0;p<T.length;p++)for(let q=p+1;q<T.length;q++){
    const P=drawn(T[p]),Q=drawn(T[q]);if(!P||!Q)continue;
    const l=Math.max(P.l,Q.l),r=Math.min(P.l+P.a.w,Q.l+Q.a.w),t=Math.max(P.tp,Q.tp),b=Math.min(P.tp+P.a.h,Q.tp+Q.a.h);
    if(r<=l||b<=t)continue;
    let n=0;
    for(let y=t;y<b;y++)for(let x=l;x<r;x++){
     const pr=P.a.h-1-(y-P.tp),qr=Q.a.h-1-(y-Q.tp);
     if(P.a.mask[pr*P.a.w+(x-P.l)]&&Q.a.mask[qr*Q.a.w+(x-Q.l)])n++}
    if(!n)continue;
    maxOverlap=Math.max(maxOverlap,n);
    overlapPairs.push([T[p].i,T[q].i,n]);
    const front=(T[q].dmp[1]>T[p].dmp[1]||(T[q].dmp[1]===T[p].dmp[1]&&T[q].dmp[0]>T[p].dmp[0]))?q:p,back=front===p?q:p;
    if(!(T[front].z>T[back].z))depthViolations.push([T[back].i,T[front].i]);
   }
   // painter order monotone over the whole map
   const sorted=[...T].sort((a,b)=>a.dmp[1]-b.dmp[1]||a.dmp[0]-b.dmp[0]);
   let zMonotone=true;for(let s=1;s<sorted.length;s++)if(!(sorted[s].z>sorted[s-1].z))zMonotone=false;
   // min opaque gap between consecutive cells along the route (px, world)
   const gaps=[];
   for(let s=1;s<T.length;s++){
    const P=drawn(T[s-1]),Q=drawn(T[s]);if(!P||!Q)continue;
    const dx=Math.abs(T[s].x-T[s-1].x)-T[s].w,dy=Math.abs(T[s].y-T[s-1].y)-T[s].h;
    gaps.push(+Math.max(dx,dy).toFixed(1));
   }
   const startArt=T[0]?.art,goalArt=T[T.length-1]?.art;
   const cat=categories(route);
   // pawn checks
   const pawns={};
   for(const [name,idx] of Object.entries(cat)){
    if(idx===undefined){pawns[name]={present:false};continue}
    const prev=Math.max(0,idx-1);
    await page.evaluate(([prev,idx])=>{const T=window.__ROG_TEST__,m=T.getMatch();
     m.players.forEach((p,j)=>{p.position=j===m.active?prev:0});T.setMatch(m);
     const m2=T.getMatch();m2.players[m2.active].position=idx;T.setMatch(m2);
     window.__LEAF_CAMERA__.reset();},[prev,idx]);
    await page.waitForTimeout(idx===prev?150:900);
    await settle(page,await page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();return '#board-pawns .board-pawn[data-id="'+m.players[m.active].id+'"]'}));
    const g=await page.evaluate(idx=>{const m=window.__ROG_TEST__.getMatch(),a=m.players[m.active];
     const pawn=[...document.querySelectorAll('#board-pawns .board-pawn')].find(p=>p.dataset.id===String(a.id))||
      [...document.querySelectorAll('#board-pawns .board-pawn')][m.active];
     const tile=document.querySelector('#board-nodes .tile[data-tile="'+idx+'"]');
     const tr=tile.getBoundingClientRect(),area=document.getElementById('board-area').getBoundingClientRect();
     const peers=m.players.filter(p=>p.position===a.position).length;
     const pr=pawn.getBoundingClientRect();
     return {headClip:+(area.top-pr.top).toFixed(1),pawnSel:'#board-pawns .board-pawn[data-id="'+a.id+'"]',peers,
      tile:[tr.left+tr.width/2,tr.top+tr.height/2],tileOnScreen:tr.left>=area.left-1&&tr.right<=area.right+1&&tr.top>=area.top-1&&tr.bottom<=area.bottom+1,
      tileZ:Number(tile.style.zIndex),pawnZ:Number(getComputedStyle(pawn).zIndex),depthTile:pawn.dataset.depthTile,
      facing:pawn.dataset.travelFacing||null,basis:pawn.dataset.travelFacingBasis||null,
      scale:window.__LEAF_CAMERA__.getState().scale}},idx);
    const foot=await footDiff(page,g.pawnSel);
    const r=route,expect=idx===prev?null:window_facing(r[prev],r[idx]);
    const dx=foot?+(foot.x-g.tile[0]).toFixed(1):null,dy=foot?+(foot.y-g.tile[1]).toFixed(1):null;
    pawns[name]={present:true,index:idx,dmp:r[idx].slice(0,2),foot:foot&&[foot.x,foot.y],tileCentre:g.tile.map(n=>+n.toFixed(1)),
     dx,dy,tileOnScreen:g.tileOnScreen,headClipPx:g.headClip,tileZ:g.tileZ,pawnZ:g.pawnZ,depthTile:g.depthTile,
     facing:g.facing,expectedFacing:expect,basis:g.basis,
     pass:Boolean(foot)&&g.headClip<=2&&Math.abs(dx)<=FOOT_X&&Math.abs(dy)<=FOOT_Y&&g.tileOnScreen&&g.pawnZ>g.tileZ&&
      String(g.depthTile)===String(idx)&&(expect===null||g.facing===expect)};
   }
   // crops for offline orientation check: first instance of each new art
   if(crops){
    for(const t of T){
     if(!t.art||seenArt.has(t.art))continue;seenArt.add(t.art);
     const box={};await page.evaluate(i=>{const S=window.__LEAF_CAMERA__.getState();
      const tile=document.querySelector('#board-nodes .tile[data-tile="'+i+'"]');
      window.__LEAF_CAMERA__.focusRatio(parseFloat(tile.style.left)/100,parseFloat(tile.style.top)/100);
      window.__LEAF_CAMERA__.viewport(1,S.panX,S.panY);
      window.__LEAF_CAMERA__.focusRatio(parseFloat(tile.style.left)/100,parseFloat(tile.style.top)/100);
      const st=document.createElement('style');st.id='crop-hide';
      st.textContent='#board-pawns,#battle-visual,.tile-symbol,.tile small,#board-area>*:not(#board-world){visibility:hidden!important}';document.head.append(st);
      return true},t.i);
     await settle(page,null);
     Object.assign(box,await page.evaluate(i=>{const r=document.querySelector('#board-nodes .tile[data-tile="'+i+'"]').getBoundingClientRect();
      return {x:r.left,y:r.top,width:r.width,height:r.height}},t.i));
     if(box.width>0&&box.x>=0&&box.y>=0&&box.x+box.width<=800&&box.y+box.height<=600)
      await page.screenshot({path:path.join(crops,t.art+'.png'),clip:box});
     await page.evaluate(()=>document.getElementById('crop-hide')?.remove());
    }
   }
   const checks={
    tilesComplete:T.length===route.length&&T.length>0,
    artsLoaded:Object.values(A).every(a=>a.ok&&a.w===145&&a.h===97)&&T.every(t=>t.art),
    nativeSize:T.every(t=>t.w===145&&t.h===97),
    startArt:startArt==='0024',goalArt:goalArt==='0018',
    flipUndone:T.every(t=>t.flipD===-1),
    opaqueOverlapDepth:depthViolations.length===0,
    painterMonotone:zMonotone,
    pawns:Object.values(pawns).every(p=>!p.present||p.pass)};
   const rec={index:k,map:board.map,option:map,cells:T.length,arts:Object.keys(A).length,checks,
    pass:Object.values(checks).every(Boolean),
    errorMeasures:{opaqueOverlapPairs:overlapPairs.length,maxOverlapPx:maxOverlap,depthViolations,
     routeGapPx:{min:Math.min(...gaps),max:Math.max(...gaps)},startArt,goalArt,
     maxPawnFootErr:Math.max(0,...Object.values(pawns).filter(p=>p.present&&p.dx!==null).map(p=>Math.hypot(p.dx,p.dy))).toFixed(1)},
    pawnCells:pawns};
   report.maps.push(rec);
   for(const [c,ok] of Object.entries(checks))if(!ok)failures.push(k+' '+board.map+': '+c);
   console.log(k,board.map,rec.pass?'PASS':'FAIL',JSON.stringify(rec.errorMeasures),Object.entries(checks).filter(([,v])=>!v).map(([c])=>c).join(','));
  }
  report.summary={maps:report.maps.length,pass:report.maps.filter(m=>m.pass).length,
   cells:report.maps.reduce((s,m)=>s+m.cells,0),failures,pageErrors:errors};
  if(process.env.LEAF_AUDIT_OUT)fs.writeFileSync(process.env.LEAF_AUDIT_OUT,JSON.stringify(report,null,1)+'\n');
  assert.deepEqual(errors,[]);
  if(!only)assert.equal(report.maps.length,26);
  assert.deepEqual(failures,[],'map audit failures');
  console.log('DMP 26 MAP RENDER AUDIT PASS',JSON.stringify(report.summary));
 }finally{await browser.close()}
})().catch(e=>{console.error('DMP 26 MAP RENDER AUDIT FAILED',e.stack||e);process.exit(1)});
// Same rule as game.js sourceDmpTravelFacing (window.__LEAF_DMP_TRAVEL__):
// only true DMP row changes choose away/toward.
function window_facing(from,to){const dx=to[0]-from[0],dy=to[1]-from[1];
 return dy<0?'away':dy>0?'toward':dx<0?'left':dx>0?'right':'toward'}
