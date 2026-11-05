'use strict';
/* R14-D: six permanent-room ChatRoom concurrency QA (2026-11-05).
 * Real browser participants (one page each, shared BroadcastChannel/storage
 * transport exactly as two tabs of the public game). For each of the 6 rooms:
 *  1. five guests join SIMULTANEOUSLY -> every page agrees on one seat per
 *     occupant, no two occupants share a seat, counts and rosters agree;
 *  2. duplicate nickname: a sixth guest uses an existing nickname -> both
 *     remain listed and seated (no merge, no eviction);
 *  3. message burst: three senders x 15 messages concurrently -> every page
 *     receives all 45 exactly once, in each sender's order;
 *  4. chat log follows the newest line after the burst;
 *  5. EXIT by a real click frees the seat on every page; re-entry reseats;
 *  6. room switch: a guest moves to the next room; the old room drops them;
 *  7. reconnect: a guest reloads; its stale avatar leaves the host view.
 * Seat/tag geometry rules stay in chatroom-residual-original-qa.cjs.
 * FOURLEAF_BROWSER=webkit runs the same checks. LEAF_ROOMS=0,3 for debug. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium,webkit}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const NAMES=['겔드','일루드','kh-jh516','택틱스마스터','율카아','러브히키','fallenstar'];
async function open(context,name,errors,i){
 const page=await context.newPage();
 page.on('pageerror',e=>errors.push(i+': '+e));
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 await page.goto(base);
 await page.waitForFunction(()=>window.__LEAF_SOCIAL__&&window.__ROG_TEST__,null,{timeout:20000});
 await page.evaluate(name=>{document.getElementById('profile-name').textContent=name;
  window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')},name);
 return page;
}
const view=page=>page.evaluate(()=>({
 seats:[...document.querySelectorAll('#social-avatar-layer .social-avatar')].map(a=>({seat:a.dataset.seat,
  name:a.querySelector('.social-avatar-name')?.textContent||''})).sort((x,y)=>x.seat-y.seat),
 roster:[...document.querySelectorAll('#social-peer-list .social-user-row b')].map(b=>b.textContent).sort(),
 count:document.getElementById('social-native-user-count')?.textContent||'',
 roomId:window.__LEAF_SOCIAL__.getState().roomId}));
async function join(page,rid){
 await page.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
 await page.waitForFunction(id=>window.__LEAF_SOCIAL__.getState().rooms.some(r=>r.id===id),rid,{timeout:15000});
 await page.evaluate(id=>window.__LEAF_SOCIAL__.joinRoom(id),rid);
}
async function waitCount(page,n,timeout=25000){
 await page.waitForFunction(n=>document.querySelectorAll('#social-avatar-layer .social-avatar').length===n,n,{timeout});
 await page.waitForTimeout(200);
}
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1280,height:850},serviceWorkers:'block'});
 const errors=[],report={engine,generated:new Date().toISOString(),rooms:[]};
 const only=process.env.LEAF_ROOMS?process.env.LEAF_ROOMS.split(',').map(Number):null;
 try{
  const pages=[];
  for(let i=0;i<7;i++)pages.push(await open(context,i===6?NAMES[1]:NAMES[i],errors,i)); // page 6 duplicates '일루드'
  const host=pages[0];
  for(let bg=0;bg<6;bg++){
   if(only&&!only.includes(bg))continue;
   const rec={room:bg};
   const rid=await host.evaluate(bg=>{window.__LEAF_SOCIAL__.openDirectory();
    return window.__LEAF_SOCIAL__.createRoom('R14 동시성 '+bg,bg,12)},bg);
   // 1. simultaneous joins
   await Promise.all(pages.slice(1,6).map(p=>join(p,rid)));
   for(const p of pages.slice(0,6))await waitCount(p,6);
   const views=await Promise.all(pages.slice(0,6).map(view));
   const ref=JSON.stringify(views[0].seats);
   rec.seats=views[0].seats;
   assert.equal(new Set(views[0].seats.map(s=>s.seat)).size,6,'room'+bg+' distinct seats after simultaneous join');
   views.forEach((v,i)=>{assert.equal(JSON.stringify(v.seats),ref,'room'+bg+' page '+i+' agrees on seat map');
    assert.equal(v.count,'6 명');assert.deepEqual(v.roster,[...NAMES.slice(0,6)].sort())});
   // 2. duplicate nickname
   await join(pages[6],rid);
   for(const p of [host,pages[1],pages[6]])await waitCount(p,7);
   const dup=await view(host);
   assert.equal(dup.roster.filter(n=>n===NAMES[1]).length,2,'room'+bg+' both "'+NAMES[1]+'" listed');
   assert.equal(new Set(dup.seats.map(s=>s.seat)).size,7,'room'+bg+' duplicate name still gets its own seat');
   assert.equal(dup.count,'7 명');
   // 3. message burst
   const stamp=Date.now()+'-'+bg;
   const senders=[1,3,6];
   await Promise.all(senders.map(async si=>{const box=pages[si].locator('#message');
    for(let k=0;k<15;k++){await box.fill('b'+stamp+'-'+si+'-'+String(k).padStart(2,'0'));await box.press('Enter')}}));
   const got=[];
   for(const [i,p] of pages.entries()){
    await p.waitForFunction(st=>(document.getElementById('chat-log').textContent.match(new RegExp('b'+st+'-\\d-\\d\\d','g'))||[]).length>=45,
     stamp,{timeout:15000}).catch(()=>{});
    const lines=await p.evaluate(st=>document.getElementById('chat-log').textContent.match(new RegExp('b'+st+'-\\d-\\d\\d','g'))||[],stamp);
    const per={};for(const l of lines){const [,s,k]=l.split('-').slice(-3);(per[s]||(per[s]=[])).push(Number(k))}
    got.push({page:i,total:lines.length,unique:new Set(lines).size,
     ordered:Object.values(per).every(a=>a.every((v,j)=>j===0||v>a[j-1]))});
   }
   rec.burst=got;
   for(const g of got){assert.equal(g.unique,45,'room'+bg+' page '+g.page+' received all 45 ('+g.unique+')');
    assert.equal(g.total,45,'room'+bg+' page '+g.page+' no duplicates');assert.ok(g.ordered,'room'+bg+' per-sender order')}
   // 4. log follows newest line
   const scroll=await host.evaluate(()=>{const l=document.getElementById('chat-log');return {gap:l.scrollHeight-l.clientHeight-l.scrollTop,overflow:l.scrollHeight>l.clientHeight}});
   rec.logScroll=scroll;
   if(scroll.overflow)assert.ok(scroll.gap<=24,'room'+bg+' chat log scrolled to newest ('+scroll.gap+'px)');
   // 5. EXIT by click and re-entry
   const g=pages[2];
   await g.locator('#social-back').click();
   await g.waitForFunction(()=>window.__LEAF_SOCIAL__.getState().view==='directory',null,{timeout:8000});
   await waitCount(host,6);
   const afterExit=await view(host);
   assert.ok(!afterExit.roster.includes(NAMES[2]),'room'+bg+' EXIT removes the roster row');
   await join(g,rid);await waitCount(host,7);await waitCount(g,7);
   const re=await view(host);
   assert.equal(new Set(re.seats.map(s=>s.seat)).size,7,'room'+bg+' re-entry gets a free seat');
   // 6. room switch to a second room
   const rid2=await pages[5].evaluate(bg=>{window.__LEAF_SOCIAL__.openDirectory();
    return window.__LEAF_SOCIAL__.createRoom('R14 이동 '+bg,(bg+1)%6,12)},bg);
   await waitCount(host,6);
   await join(pages[4],rid2);
   await waitCount(host,5);await waitCount(pages[5],2);
   const sw=await view(host);
   assert.ok(!sw.roster.includes(NAMES[4])&&!sw.roster.includes(NAMES[5]),'room'+bg+' movers left the old room');
   // 7. reconnect: reload one guest; host must drop the stale occupant
   const t0=Date.now();
   await pages[3].reload();
   await pages[3].waitForFunction(()=>window.__LEAF_SOCIAL__,null,{timeout:20000});
   await waitCount(host,4,30000);
   rec.staleDropMs=Date.now()-t0;
   await pages[3].evaluate(n=>{document.getElementById('profile-name').textContent=n;
    window.__LEAF_SOCIAL__.openRegion('north');window.__ROG_TEST__.go('rooms')},NAMES[3]);
   // everyone back to the directory for the next room
   for(const p of pages.slice(1)){await p.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory())}
   await host.evaluate(()=>window.__LEAF_SOCIAL__.openDirectory());
   report.rooms.push(rec);
   console.log('room',bg,'ok',JSON.stringify({staleDropMs:rec.staleDropMs,logScroll:rec.logScroll}));
  }
  report.pageErrors=errors;
  if(process.env.LEAF_AUDIT_OUT)fs.writeFileSync(process.env.LEAF_AUDIT_OUT,JSON.stringify(report,null,1)+'\n');
  assert.deepEqual(errors,[]);
  console.log('R14 CHATROOM CONCURRENCY PASS',engine,report.rooms.length);
 }finally{await browser.close()}
})().catch(e=>{console.error('R14 CHATROOM CONCURRENCY FAILED',e.stack||e);process.exit(1)});
