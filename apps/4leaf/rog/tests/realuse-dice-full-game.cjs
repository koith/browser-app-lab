'use strict';
/* WorldMap -> lobby -> CREATE -> original READY -> whole match -> GAME OVER.
 * Only UI click/fill/select; __ROG_TEST__ read-only for progress. */
const assert=require('node:assert/strict');
const {chromium,webkit,devices}=require('playwright');
const base=process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/';
const VIEWS=[['desktop-1280',{viewport:{width:1280,height:850}}],
 ['desktop-800x600',{viewport:{width:800,height:600}}],
 ['iphone-portrait','iPhone 13'],['iphone-landscape','iPhone 13 landscape']];
const only=process.env.LEAF_VIEWS?process.env.LEAF_VIEWS.split(','):null;
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?'webkit':'chromium';
 const browser=await (engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--no-sandbox']});
 try{
  for(const [name,spec] of VIEWS){
   if(only&&!only.includes(name))continue;
   const opts=typeof spec==='string'?{...devices[spec]}:spec;
   if(engine!=='webkit')delete opts.defaultBrowserType;
   const ctx=await browser.newContext({...opts,serviceWorkers:'block'});
   const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
   await page.goto(base);
   const hit=sel=>page.evaluate(sel=>{
    const e=document.querySelector(sel);if(!e||e.hidden)return false;
    const r=e.getBoundingClientRect();
    if(!(r.width>4&&r.height>4)||r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth)return false;
    const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
    return t===e||e.contains(t);
   },sel);
   await page.getByRole('button',{name:/주사위의 잔영/}).first().click();
   await page.waitForFunction(()=>{
    const l=document.getElementById('lobby');
    return l&&!l.classList.contains('hidden')&&l.getBoundingClientRect().height>100;
   },null,{timeout:10000});
   assert.ok(await hit('#lobby-create'),name+' CREATE is visible');
   await page.locator('#lobby-create').click();
   await page.locator('#map-select').waitFor({state:'attached'});
   await page.locator('#map-select').selectOption({index:2});
   await page.locator('#point-limit').selectOption({label:'8 POINT'}).catch(()=>{});
   await page.waitForTimeout(400);
   let how='original READY';
   if(await hit('#start-game'))await page.locator('#start-game').click();
   else{
    assert.ok(await hit('#dice-room-start-shortcut'),name+' start must be reachable without panning');
    how='phone shortcut';await page.locator('#dice-room-start-shortcut').click();
   }
   await page.waitForFunction(()=>!document.getElementById('game').classList.contains('hidden'),null,{timeout:10000});
   const state=()=>page.evaluate(()=>{
    const m=window.__ROG_TEST__.getMatch();
    return {round:m.round,active:m.active,finished:Boolean(m.finished||m.winner>=0),
     pos:m.players.map(p=>p.position)};
   });
   const t0=Date.now();let last='',lastChange=Date.now(),clicks=0;const rounds=new Set();
   for(;;){
    const s=await state(),key=JSON.stringify(s);
    if(key!==last){last=key;lastChange=Date.now();rounds.add(s.round)}
    if(s.finished)break;
    if(Date.now()-lastChange>=45000){
     const diagnosis=await page.evaluate(()=>{
      const els=[...document.querySelectorAll('button')].map(e=>{
       const r=e.getBoundingClientRect(),st=getComputedStyle(e),t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
       return {id:e.id,text:(e.textContent||'').trim().slice(0,65),
        disabled:e.disabled,display:st.display,visibility:st.visibility,
        inside:r.width>0&&r.height>0&&r.left>=0&&r.top>=0&&
         r.right<=innerWidth&&r.bottom<=innerHeight,
        hit:t===e||e.contains(t)};
      }).filter(x=>/roll|turn|continue|exit|battle|ability|modal|result|confirm|주사위|확인|굴리기|진행/.test(x.id+' '+x.text));
      const m=document.getElementById('modal');
      return {viewport:[innerWidth,innerHeight],fit:window.__LEAF_PHONE_FIT__?.getState?.(),
       modal:{hidden:m?.classList.contains('hidden'),text:(m?.textContent||'').slice(0,500)},
       controls:els,match:window.__ROG_TEST__?.getMatch?.()};
     });
     console.error('REALUSE FULL GAME STALL DIAGNOSTIC',JSON.stringify({key,diagnosis}).slice(0,9000));
     throw new Error(name+' match stuck at '+key);
    }
    assert.ok(Date.now()-t0<200000,name+' match did not finish within 200 seconds');
    const target=await page.evaluate(()=>{
     const ok=e=>{
      if(e.disabled)return false;
      const r=e.getBoundingClientRect(),c=getComputedStyle(e);
      if(!(r.width>4&&r.height>4&&c.visibility!=='hidden'&&c.display!=='none'&&c.pointerEvents!=='none'))return false;
      if(r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth)return false;
      const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
      return t===e||e.contains(t);
     };
     const pt=e=>{const r=e.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]};
     const modal=[...document.querySelectorAll('#modal-buttons button,.leaf-native-battle-actions button')].filter(ok);
     const confirm=modal.find(b=>/결과 확인/.test(b.textContent))
      ||modal.find(b=>/확인/.test(b.textContent))||modal[0];
     if(confirm)return pt(confirm);
     const roll=document.getElementById('roll-btn');
     return roll&&ok(roll)?pt(roll):null;
    });
    if(target){await page.mouse.click(target[0],target[1]);clicks++}
    await page.waitForTimeout(350);
   }
   await page.waitForFunction(()=>{
    const m=document.getElementById('modal');
    return m&&!m.classList.contains('hidden')&&/게임 종료|결과/.test(m.textContent||'');
   },null,{timeout:10000});
   assert.ok(rounds.size>=3,name+' a full game must advance several rounds');
   assert.deepEqual(errors,[]);
   console.log(name,JSON.stringify({start:how,seconds:Math.round((Date.now()-t0)/1000),
    clicks,rounds:rounds.size,final:JSON.parse(last).pos}));
   await ctx.close();
  }
  console.log('REALUSE FULL GAME PASS',engine);
 }finally{await browser.close()}
})().catch(e=>{console.error('REALUSE FULL GAME FAILED',e.stack||e);process.exit(1)});
