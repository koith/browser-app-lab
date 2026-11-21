'use strict';
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 const engine=process.env.FOURLEAF_BROWSER==='webkit'?webkit:chromium;
 const browser=await engine.launch(engine===chromium?{args:['--no-sandbox']}:{});const page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.text().startsWith('RULE01-CHECKPOINT'))console.log(m.text())});
 const watchdog=setTimeout(()=>{console.error('RULE01 overall fixture timeout');process.exit(1)},120000);
 try{
 await page.addInitScript(()=>{window.LEAF_CENTRAL_API_URL=''});
 await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
 await page.waitForFunction(()=>window.__ROG_TEST__&&window.ORIGINAL_LEAF_MAPS);
 await page.locator('[data-route="lobby"]').first().click();await page.locator('#lobby-create').click();await page.locator('#game-mode').selectOption('hotseat');await page.locator('#bot-count').selectOption('2');await page.locator('#start-game').click();await page.waitForSelector('#game:not(.hidden)');
 const proof=await page.evaluate(async()=>{
  const T=window.__ROG_TEST__,old=structuredClone(T.getMatch()),routes=window.ORIGINAL_LEAF_MAPS,typed=T.getSourceTiles(),names=T.getSourceMaps();
  const eq=(a,b,msg)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error(msg+' actual '+JSON.stringify(a)+' != '+JSON.stringify(b))};
  const random=Math.random;const deadline=(p,label)=>{let timer;return Promise.race([Promise.resolve(p),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('event blocked: '+label)),5000)})]).finally(()=>clearTimeout(timer))};
  const land=(p)=>deadline(T.resolveTile(p),map.map+':'+p.position+':'+map.tiles[p.position]);
  const fixed=async(seed,fn)=>{Math.random=()=>seed;try{return await fn()}finally{Math.random=random}};
  const original=old.players[0],cases={},seen={},warps={total:0,reciprocal:0,self:0,oneWay:0};
  let map;
  function fresh(id){
   const m=structuredClone(old);m.map=names[id].title;m.tiles=T.generateTiles(m.map);m.finished=false;m.history=[];m.attribute='NONE';
   m.players.forEach((p,i)=>{p.position=0;p.jail=0;p.ability=10;p.items=[];p.effects={...original.effects,dove:0,clover:0,spade:0};p.tileArrivalPosition=-1;p.tileArrivalOrder=0;});
   m.tileArrivalSequence=0;const live=T.getMatch();Object.assign(live,m);map=live;return live;
  }
  // Verify every real coordinate and event type against archived data first.
  for(const [id,route] of Object.entries(routes)){
   console.log('RULE01-CHECKPOINT map '+id);const m=fresh(id),source=typed[id];
   eq(m.tiles.length,route.length,'DMP length '+id);
   for(let i=0;i<route.length;i++){
    if(source)eq(m.tiles[i],source[i].type,'DMP/DMO event '+id+':'+i);
    if(source)seen[source[i].type]=(seen[source[i].type]||0)+1;
    if(route[i][3]!==10)continue;
    eq(m.tiles[i],'warp','encoded link '+id+':'+i);
    const target=route[i][5],originalDest=m.tiles[target],p=m.players[0];
    // Isolate non-warp landing effects in this routing fixture; reciprocal
    // endpoints remain real warps to exercise the actual loop bug.
    if(originalDest!=='warp')m.tiles[target]='normal';
    p.position=i;p.tileArrivalPosition=-1;m.players.slice(1).forEach(q=>q.position=target===0?1:0);m.history=[];p.ability=10;
    await fixed(.51,()=>land(p));
    eq(p.position,target,'original source link '+id+':'+i);
    eq(m.history.filter(x=>x.includes(' 워프: ')).length,i===target?0:1,'single teleport '+id+':'+i);
    eq(p.ability,10,'warp does not mint movement gauge');
    m.tiles[target]=originalDest;warps.total++;
    if(i===target)warps.self++;else if(route[target][3]===10&&route[target][5]===i)warps.reciprocal++;else warps.oneWay++;
   }
  }
  eq(warps.total,129,'all 26 source links');
  console.log('RULE01-CHECKPOINT all warp routes passed');const m=fresh('0172'),p=m.players[0];T.drawGame();m.players.slice(1).forEach(q=>q.position=0);
  function reset(type,pos=20){console.log('RULE01-CHECKPOINT '+type+' '+pos);m.tiles.fill('normal');m.tiles[0]='start';m.tiles[m.tiles.length-1]='goal';m.tiles[pos]=type;p.position=pos;p.tileArrivalPosition=-1;p.ability=10;p.items=[];p.jail=0;p.effects={...original.effects,clover:0,spade:0,dove:0};m.finished=false;m.history=[];}
  async function check(type,expected,seed=.51,pos=20){reset(type,pos);await fixed(seed,()=>land(p));for(const [k,v]of Object.entries(expected))eq(p[k],v,type+' '+k);cases[type]=(cases[type]||0)+1;}
  await check('normal',{position:20,ability:10});await check('boost',{position:23,ability:19});await check('boost4',{position:24,ability:22});
  await check('prison',{jail:3,position:20});await check('ability',{ability:35});reset('ability');p.ability=90;await land(p);eq(p.ability,100,'ability cap');
  // The four source attribute types must use their actual DMO value.
  for(const attr of ['WANDS','SWORDS','CUPS','DISKS']){const i=typed['0172'].findIndex(t=>t.attribute===attr);reset('attribute',i);await land(p);eq(m.attribute,attr,'source attribute');cases.attribute=(cases.attribute||0)+1}
  reset('chest');await fixed(.62,()=>land(p));eq(p.items.length,1,'chest grant');if(p.items.includes('odincurse'))throw Error('unreleased item');
  p.items=Array(5).fill('shoe');await land(p);eq(p.items.length,5,'full inventory cap');cases.chest=2;
  reset('blessing');await fixed(.62,()=>land(p));eq(p.items.length,5,'blessing fill');if(p.items.includes('odincurse'))throw Error('unreleased blessing');p.items=['shoe','ring'];await fixed(.62,()=>land(p));eq(p.items.length,5,'blessing preserves inventory');eq(p.items.slice(0,2),['shoe','ring'],'blessing no replacement');cases.blessing=2;
  reset('curse');p.items=['shoe','ring'];await land(p);eq(p.items,[],'curse removes inventory');cases.curse=1;
  for(const [type,range]of [['clover',[4,6]],['spade',[1,3]]]){
   reset(type);p.team=['c_0078'];await land(p);const stats=T.teamStats(p.team);const dice=await fixed(.99,()=>T.moveValues(p));const lo=stats.move===2?(type==='clover'?3:1):range[0],hi=stats.move===2?(type==='clover'?4:2):range[1];if(!dice.every(x=>x>=lo&&x<=hi))throw Error(type+' range '+dice);eq([p.effects.clover,p.effects.spade],[0,0],type+' consumed');cases[type]=1;
  }
  for(const [first,second,expected]of [[1,1,20],[3,2,17],[4,2,14],[6,1,0]]){
   reset('doa');const seq=[(first-.5)/6,(second-.5)/first];Math.random=()=>seq.length?seq.shift():.6;try{await T.resolveTile(p)}finally{Math.random=random}eq(p.position,expected,'DOA '+first+':'+second);cases.doa=(cases.doa||0)+1;
  }
  reset('random');await fixed(0,()=>land(p));eq(m.tiles[20],'chest','question tile persists');eq(p.items.length,1,'question resolves effect');cases.random=1;
  reset('joker');await fixed(0,()=>land(p));eq(m.tiles[20],'joker','joker restores visual');await fixed(.99,()=>land(p));eq(m.tiles[20],'joker','joker rerolls');eq(p.items.length,0,'joker second effect differs');cases.joker=2;
  reset('ability100');p.team=['c_0042'];p.effects.ring=99;await fixed(0,()=>land(p));eq(p.ability,100,'Soulful matching selected eye');cases.ability100=1;
  reset('ability100');const seq=Array(4).fill(0).concat([.99]);const count=Math.max(1,Math.min(4,T.teamStats(p.team).atk));let n=0;Math.random=()=>n++<count?0:.99;try{await T.resolveTile(p)}finally{Math.random=random}eq(p.ability,10,'Soulful failed eye');cases.ability100++;
  reset('start',0);m.players.slice(1).forEach(q=>q.position=1);await land(p);eq(p.position,0,'start no effect');cases.start=1;
  reset('arena');m.players.slice(1).forEach(q=>q.position=0);await land(p);eq(p.position,20,'unoccupied arena no combat');cases.arena=1;
  // Real arena incumbent selection: second roster member arrived first.
  m.players[1].position=20;m.players[1].tileArrivalPosition=20;m.players[1].tileArrivalOrder=3;m.players[2].position=20;m.players[2].tileArrivalPosition=20;m.players[2].tileArrivalOrder=2;p.position=20;p.tileArrivalPosition=-1;
  m.players[1].name='LATER';m.players[2].name='FIRST';m.players[2].effects.dove=1;await land(p);if(document.querySelector('#modal')&&!document.querySelector('#modal').classList.contains('hidden'))throw Error('first incumbent dove immunity ignored');cases.arena++;
  m.players[2].effects.dove=0;console.log('RULE01-CHECKPOINT real arena duel');window.__arenaPromise=T.resolveTile(p);
  return {warps,seen,cases,arenaPending:true};
 });
 await page.waitForFunction(()=>document.querySelector('#modal-content')?.textContent.includes('FIRST')&&document.querySelector('#modal-content')?.textContent.includes('방어합니다'),null,{timeout:15000});
 await page.locator('#modal-buttons button').filter({hasText:'결과 확인'}).click();await page.evaluate(()=>window.__arenaPromise);
 const goal=await page.evaluate(async()=>{const T=window.__ROG_TEST__,m=T.getMatch(),p=m.players[0];m.players.slice(1).forEach(q=>q.position=0);m.finished=false;p.position=m.tiles.length-1;m.tiles[p.position]='goal';m.startedAt=Date.now()-300000;await T.resolveTile(p);return {finished:m.finished,winner:m.winner};});assert.deepEqual(goal,{finished:true,winner:0});
 proof.cases.goal=1;proof.cases.arena++;assert.equal(Object.keys(proof.seen).length,19);assert.equal(Object.keys(proof.cases).length+1,19);assert.deepEqual(errors,[]);
 await page.screenshot({path:'rule01-original-event-result-'+engine.name()+'.png'});console.log('RULE-01 ORIGINAL TILE SOURCE MATRIX PASS '+JSON.stringify(proof));
 }finally{clearTimeout(watchdog);await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
