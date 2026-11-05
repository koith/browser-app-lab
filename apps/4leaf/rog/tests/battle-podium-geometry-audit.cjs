'use strict';
/* Battle podium geometry audit (round 13, 2026-11-05).
 * Measures, from REAL rendered pixels, for desktop 800x600 and iPhone
 * portrait / landscape:
 *  - where each fighter's lowest opaque pixel (foot) lands relative to its
 *    winBattle.spr frame-1 deck centre (source pixels [77,34] / [278,34]);
 *  - horizontal centring of each fighter on its deck;
 *  - attacker and defender use their OWN chessman body (distinct ids/src);
 *  - nothing from the surrounding UI (minimap, toolbar buttons, chat, roll
 *    cup) covers the podium decks, the fighters or the combat dice.
 * Foot pixels come from a screenshot diff (fighter visible vs hidden), so
 * transparent canvas padding cannot fake a contact.
 * The tolerance is a WEB rule: the 2002 MVE podium mesh/camera is not
 * recovered, so passing here is NOT a claim of original 3D fidelity.
 * Writes docs/evidence/round13/podium-geometry.json when LEAF_AUDIT_OUT set.
 * FOURLEAF_BROWSER=webkit runs the same audit in WebKit. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const VIEWS=[
 {name:'desktop-800x600',viewport:{width:800,height:600}},
 {name:'iphone-portrait',device:'iPhone 13'},
 {name:'iphone-landscape',device:'iPhone 13 landscape'}
];
const FOOT_TOL_Y=10, FOOT_TOL_X=14; // CSS px; WEB tolerance (INFERRED)
async function measureFoot(page,sel){
 // Screenshot the stage twice: fighter shown / fighter hidden, decode both
 // in the page with createImageBitmap and diff the pixels.
 const clip=await page.evaluate(()=>{const r=document.querySelector('#battle-visual').getBoundingClientRect();
  return {x:Math.max(0,r.left),y:Math.max(0,r.top),width:Math.min(innerWidth,r.right)-Math.max(0,r.left),height:Math.min(innerHeight,r.bottom)-Math.max(0,r.top)}});
 const freeze=async on=>page.evaluate(on=>{for(const n of document.querySelectorAll('#battle-visual *'))
  {n.style.animationPlayState=on?'paused':'';n.style.transitionDuration=on?'0s':''}},on);
 await freeze(true);
 const shown=await page.screenshot({clip,scale:'css'});
 await page.evaluate(sel=>{document.querySelector(sel).style.visibility='hidden'},sel);
 const hidden=await page.screenshot({clip,scale:'css'});
 await page.evaluate(sel=>{document.querySelector(sel).style.visibility=''},sel);
 await freeze(false);
 const res=await page.evaluate(async([a,b])=>{
  const load=async s=>{const bl=await (await fetch('data:image/png;base64,'+s)).blob();const bm=await createImageBitmap(bl);
   const c=new OffscreenCanvas(bm.width,bm.height),x=c.getContext('2d');x.drawImage(bm,0,0);return x.getImageData(0,0,bm.width,bm.height)};
  const A=await load(a),B=await load(b);let maxY=-1,minY=1e9,count=0;const rows={};
  for(let y=0;y<A.height;y++)for(let x=0;x<A.width;x++){const i=(y*A.width+x)*4;
   const d=Math.abs(A.data[i]-B.data[i])+Math.abs(A.data[i+1]-B.data[i+1])+Math.abs(A.data[i+2]-B.data[i+2]);
   if(d>60){count++;if(y>maxY)maxY=y;if(y<minY)minY=y;(rows[y]||(rows[y]=[])).push(x)}}
  if(maxY<0)return null;
  // foot = lowest rows (bottom 4px) of the fighter mask, ignoring its shadow
  const xs=[];for(let y=maxY-3;y<=maxY;y++)if(rows[y])xs.push(...rows[y]);
  xs.sort((p,q)=>p-q);
  return {footY:maxY,headY:minY,footX:xs[xs.length>>1],pixels:count};
 },[shown.toString('base64'),hidden.toString('base64')]);
 return res&&{...res,footY:res.footY+clip.y,headY:res.headY+clip.y,footX:res.footX+clip.x};
}
async function startBattle(page){
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 await page.goto(base);
 await page.waitForFunction(()=>window.__ROG_TEST__);
 await page.locator('[data-route="lobby"]').first().click();
 await page.locator('#lobby-create').click();
 await page.locator('#game-mode').selectOption('hotseat');
 await page.locator('#start-game').click();
 await page.waitForSelector('#game:not(.hidden)');
 await page.evaluate(()=>{const T=window.__ROG_TEST__,m=T.getMatch();
  m.players[0].team=['c_0056'];m.players[1].team=['c_0063'];T.drawGame();
  T.resolveBattle(m.players[0],m.players[1],false)});
 await page.waitForFunction(()=>document.querySelector('#battle-visual')?.dataset.nativeBattlePodium==='ready',null,{timeout:16000});
 // R14: the combat dice now play the original roll first; measure the
 // resting podium (dice landed, lunge/outcome finished) so moving dice are
 // not mistaken for a fighter's foot pixels.
 await page.waitForFunction(()=>{const s=document.getElementById('battle-visual');return s&&s.dataset.battleDice!=='rolling'},null,{timeout:15000}).catch(()=>{});
 await page.waitForTimeout(400);
 await page.waitForFunction(()=>[...document.querySelectorAll('#battle-visual .leaf-battle-chessman')].every(n=>n.dataset.actorPose==='idle'),null,{timeout:15000}).catch(()=>{});
 await page.waitForTimeout(300);
}
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 const out={generated:new Date().toISOString(),engine,
  method:'screenshot diff (fighter shown vs hidden) for foot pixels; elementFromPoint for occlusion',
  tolerance:{footY:FOOT_TOL_Y,footX:FOOT_TOL_X,status:'INFERRED WEB tolerance, not 2002 MVE geometry'},
  sourceDeckCentres:{attacker:[77,34],defender:[278,34],frame:'Dice/IMG.pak winBattle.spr frame 1 (355x113)'},
  views:[]};
 const failures=[];
 try{
  for(const v of VIEWS){
   const ctxOpts=v.device?{...devices[v.device]}:{viewport:v.viewport};
   if(engine!=='webkit'&&ctxOpts.defaultBrowserType)delete ctxOpts.defaultBrowserType;
   const ctx=await browser.newContext({...ctxOpts,serviceWorkers:'block'});
   const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   await startBattle(page);
   const geo=await page.evaluate(()=>{
    // The stage is pointer-events:none in play; enable hit testing on it
    // only for this measurement so elementFromPoint reports what is PAINTED
    // on top (minimap, buttons, chat) instead of falling through.
    const probe=document.createElement('style');probe.id='podium-audit-probe';
    probe.textContent='#app#app #game #battle-visual,#app#app #game #battle-visual *{pointer-events:auto!important}';
    document.head.append(probe);
    const s=document.querySelector('#battle-visual'),pod=s.querySelector('.leaf-native-winbattle-podiums');
    const r=pod.getBoundingClientRect(),ratio=355/113;
    const w=Math.min(r.width,r.height*ratio),h=w/ratio,l=r.left+(r.width-w)/2,t=r.bottom-h;
    const deck=x=>({x:l+x*w/355,y:t+34*h/113});
    const actors=[...s.querySelectorAll('.leaf-battle-chessman')].map(n=>({side:n.dataset.duelSide,
     chessman:n.dataset.chessmanId||null,body:n.dataset.chrBody||n.dataset.bodyId||null,
     fallback:Boolean(n.querySelector('.original-card-portrait-fallback'))||/fallback/.test(n.className),
     srcs:[...n.querySelectorAll('img,canvas')].map(e=>e.currentSrc||e.dataset.src||e.tagName).slice(0,2)}));
    const covered=(x,y)=>{if(x<0||y<0||x>=innerWidth||y>=innerHeight)return 'offscreen';
     const e=document.elementFromPoint(x,y);return e&&(s.contains(e)||e===s)?null:(e?(e.id?'#'+e.id:e.className||e.tagName):'none')};
    const dice=[...s.querySelectorAll('.battle-visual-die,.leaf-native-battle-die,[data-original-die]')].filter(d=>d.getBoundingClientRect().width>0)
     .map(d=>{const q=d.getBoundingClientRect();return {x:q.left+q.width/2,y:q.top+q.height/2,cover:covered(q.left+q.width/2,q.top+q.height/2)}});
    const totals=[...s.querySelectorAll('.battle-visual-total')].map(d=>{const q=d.getBoundingClientRect();return {cover:covered(q.left+q.width/2,q.top+q.height/2),rect:[q.left,q.top,q.width,q.height].map(Math.round)}});
    const deckCover={attacker:covered(l+77*w/355,t+50*h/113),defender:covered(l+278*w/355,t+50*h/113)};
    // Opaque winBattle-01 sample points (alpha checked offline): podium
    // rims, decks, both pillars down to the legs. Any UI painted over them
    // (ROLL cup, minimap tab, buttons) is a visible podium defect.
    const grid=[[40,10],[40,90],[60,70],[95,30],[95,100],[115,90],[77,70],
     [240,90],[260,100],[278,70],[296,100],[315,30],[315,100]];
    const podiumCover=grid.map(([x,y])=>({src:[x,y],cover:covered(l+x*w/355,t+y*h/113)})).filter(p=>p.cover);
    const stage=s.getBoundingClientRect();probe.remove();
    return {podium:[l,t,w,h].map(n=>+n.toFixed(1)),deck:{attacker:deck(77),defender:deck(278)},
     deckCover,podiumCover,
     stage:[stage.left,stage.top,stage.width,stage.height].map(Math.round),actors,dice,totals,
     viewport:[innerWidth,innerHeight]};
   });
   const rec={view:v.name,viewport:geo.viewport,podium:geo.podium,stage:geo.stage,actors:geo.actors,
    dice:geo.dice,totals:geo.totals,deckCover:geo.deckCover,podiumCover:geo.podiumCover,sides:{},errors};
   for(const side of ['attacker','defender']){
    const f=await measureFoot(page,'#battle-visual .leaf-battle-chessman[data-duel-side="'+side+'"]');
    const d=geo.deck[side];
    const dx=f?+(f.footX-d.x).toFixed(1):null,dy=f?+(f.footY-d.y).toFixed(1):null;
    rec.sides[side]={deck:[+d.x.toFixed(1),+d.y.toFixed(1)],foot:f&&[f.footX,f.footY],head:f&&f.headY,
     pixels:f&&f.pixels,dx,dy,
     pass:Boolean(f)&&Math.abs(dx)<=FOOT_TOL_X&&Math.abs(dy)<=FOOT_TOL_Y};
   }
   const shot=path.join(process.env.LEAF_AUDIT_SHOTS||'.', 'podium-'+v.name+'-'+engine+'.png');
   await page.screenshot({path:shot});
   rec.screenshot=path.basename(shot);
   const checks={
    footGrounded:rec.sides.attacker.pass&&rec.sides.defender.pass,
    ownBodies:geo.actors.length===2&&geo.actors.every(a=>a.chessman)&&geo.actors[0].chessman!==geo.actors[1].chessman,
    decksUncovered:!geo.deckCover.attacker&&!geo.deckCover.defender,
    podiumUncovered:geo.podiumCover.length===0,
    // combat dice sit within one podium height under the podium (battle.jpg
    // places them directly beneath the decks), never down in the HUD row.
    diceUnderPodium:geo.dice.every(d=>d.y>=geo.podium[1]&&d.y<=geo.podium[1]+geo.podium[3]*1.6),
    diceVisible:geo.dice.length>0&&geo.dice.every(d=>!d.cover),
    totalsVisible:geo.totals.every(t=>!t.cover),
    noPageErrors:errors.length===0};
   // Real flow tail: result -> board return, via the visible button.
   const btn=page.locator('.leaf-native-battle-actions button, #modal-buttons button',{hasText:'결과 확인'}).first();
   let flow={buttonHittable:false};
   try{
    await btn.waitFor({state:'visible',timeout:8000});
    flow.buttonHittable=await btn.evaluate(b=>{const r=b.getBoundingClientRect();const e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
     return (e===b||b.contains(e))&&r.top>=0&&r.bottom<=innerHeight});
    await btn.click();
    await page.waitForFunction(()=>!document.getElementById('battle-visual'),null,{timeout:8000});
    flow={...flow,...await page.evaluate(()=>{const m=window.__ROG_TEST__.getMatch();
     const pawns=[...document.querySelectorAll('#board-pawns .board-pawn')];
     const area=document.getElementById('board-area').getBoundingClientRect();
     const onTile=pawns.map(p=>{const r=p.getBoundingClientRect();return r.width>0&&r.right>area.left&&r.left<area.right&&r.bottom>area.top&&r.top<area.bottom});
     return {stageRemoved:true,pawns:pawns.length,activePawnOnScreen:onTile[m.active]??onTile.some(Boolean),positions:m.players.map(p=>p.position)}})};
   }catch(e){flow.error=String(e).slice(0,200)}
   rec.flow=flow;
   checks.resultButtonHittable=flow.buttonHittable;
   checks.boardReturn=Boolean(flow.stageRemoved&&flow.pawns>=2&&flow.activePawnOnScreen);
   rec.checks=checks;rec.pass=Object.values(checks).every(Boolean);
   out.views.push(rec);
   for(const [k,ok] of Object.entries(checks))if(!ok)failures.push(v.name+': '+k);
   await ctx.close();
  }
  if(process.env.LEAF_AUDIT_OUT)fs.writeFileSync(process.env.LEAF_AUDIT_OUT,JSON.stringify(out,null,1)+'\n');
  console.log(JSON.stringify(out.views.map(v=>({view:v.view,pass:v.pass,checks:v.checks,
   attacker:[v.sides.attacker.dx,v.sides.attacker.dy],defender:[v.sides.defender.dx,v.sides.defender.dy],
   dice:v.dice.map(d=>[Math.round(d.y),d.cover]),podium:v.podium,podiumCover:v.podiumCover}))));
  assert.deepEqual(failures,[],'podium geometry failures');
  console.log('BATTLE PODIUM GEOMETRY AUDIT PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('BATTLE PODIUM GEOMETRY AUDIT FAILED',e.stack||e);process.exit(1)});
