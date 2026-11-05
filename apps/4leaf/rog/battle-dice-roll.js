'use strict';
/* R14-B (2026-11-05): original D6 roll inside the battle podium.
 * Before: every combat die was painted as its FINAL face the moment the
 * podium appeared, the totals were already shown and the attacker lunged at
 * t=0 — the dice never fell. Now each live combat die plays the original
 * Dice/OBS.pak 1171 tables that the board roll already uses:
 *   slot 20 (15 keys / 30 ticks, block 0 frames 18-27)  -> fall/tumble
 *   slot 12 (16 keys / 32 ticks, block 2 frames 0-15)   -> impact/settle
 *   final face = UI frame (value-1)                      -> VERIFIED by pips
 * Pixels, frame order and tick spans: VERIFIED (18-byte OBS records via
 * dice-fall.js originalRollTable). Slot roles fall/impact: INFERRED.
 * Tick length, drop height and the dice -> totals -> lunge -> outcome order:
 * INFERRED / WEB (2002 MVE camera and EXE timing are not recovered).
 * Each frame is placed by its OWN OBS origin around the 46x49 face anchor.
 * Results come only from the match engine; this module changes presentation.
 */
(function(){
 const FACE={w:46,h:49,ax:23,ay:24};
 const TICK_MS=22;            // WEB: (30+32 ticks) x 22ms ~= 1.4s, close to the 1.1-1.6s board roll
 const FALL_LOOPS=1;          // slot 20 plays once before floor contact
 const reduce=()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches||false;
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 function place(img,frame,scale){
  img.src=frame.url;
  img.style.setProperty('width',frame.width*scale+'px','important');
  img.style.setProperty('height',frame.height*scale+'px','important');
  // displayed anchor after the storage flip is row (h-1+originY)
  img.style.setProperty('left',(FACE.ax+Number(frame.originX))*scale+'px','important');
  img.style.setProperty('top',(FACE.ay-(frame.height-1+Number(frame.originY)))*scale+'px','important');
 }
 function clear(img){for(const p of ['width','height','left','top'])img.style.removeProperty(p)}
 async function rollOne(die,table,faces,delay,state){
  const img=die.querySelector('img.battle-die-original');
  const value=Number(die.dataset.eye);
  const face=faces?.[value-1];
  if(!img||!face)return;
  const scale=(die.getBoundingClientRect().width||FACE.w)/FACE.w;
  const keys=[...table.fall.frames.map(f=>({f,t:f.tick,slot:20}))];
  const fallTicks=table.fall.ticks*FALL_LOOPS;
  const all=[];
  for(let l=0;l<FALL_LOOPS;l++)for(const k of keys)all.push({...k,t:k.t+l*table.fall.ticks});
  for(const f of table.impact.frames)all.push({f,t:fallTicks+f.tick,slot:12});
  const total=fallTicks+table.impact.ticks;
  die.dataset.battleRoll='falling';
  die.dataset.rollSource='original-OBS-1171-slot20+slot12/frames-ticks-VERIFIED/roles-INFERRED/'+TICK_MS+'ms-tick-WEB';
  die.dataset.rollFrames=String(all.length);
  // WEB drop: from above the die row onto it, two small rebounds after the
  // impact key; heights scale with the die (the MVE camera is not recovered).
  const drop=Math.round(90*scale),b1=Math.round(16*scale),b2=Math.round(6*scale);
  const fallMs=fallTicks*TICK_MS,totalMs=total*TICK_MS;
  const at=fallMs/totalMs;
  const anim=typeof die.animate==='function'?die.animate([
   // 'translate' (not 'transform'): the podium CSS pins transform with
   // !important, which would silently override an animated transform.
   {translate:'0 -'+drop+'px',offset:0},
   {translate:'0 0',offset:at},
   {translate:'0 -'+b1+'px',offset:at+(1-at)*.25},
   {translate:'0 0',offset:at+(1-at)*.5},
   {translate:'0 -'+b2+'px',offset:at+(1-at)*.65},
   {translate:'0 0',offset:at+(1-at)*.8},
   {translate:'0 0',offset:1}],
   {duration:totalMs,delay,easing:'linear',fill:'backwards'}):null;
  if(delay){place(img,all[0].f,scale);die.dataset.rollFrame='20:'+all[0].f.block+':'+all[0].f.index;await sleep(delay)}
  const t0=performance.now();let shown=null;
  while(die.isConnected&&!state.cancelled){
   const tick=Math.floor((performance.now()-t0)/TICK_MS);
   if(tick>=total)break;
   let k=all[0];for(const x of all){if(x.t<=tick)k=x;else break}
   if(k!==shown){shown=k;place(img,k.f,scale);
    die.dataset.battleRoll=k.slot===20?'falling':'impact';
    die.dataset.rollFrame=k.slot+':'+k.f.block+':'+k.f.index}
   await sleep(Math.max(12,TICK_MS/2));
  }
  anim?.cancel();
  clear(img);img.src=face.url;
  die.dataset.rollFrame='face:'+face.index;
  die.dataset.battleRoll='landed';
 }
 async function play(stage){
  if(!stage||stage.dataset.battleDice)return;
  const fall=window.__LEAF_DICE_FALL__;
  const table=fall?.originalRollTable?.(6);
  const faces=fall?.originalD6?.()?.faces;
  const dice=[...stage.querySelectorAll('.battle-visual-die.battle-die-has-original')];
  const totals=[...stage.querySelectorAll('.battle-visual-total')];
  if(!table||!faces||!dice.length||reduce()){
   stage.dataset.battleDice=table?'instant':'original-roll-table-unavailable/static-faces';
   stage.dataset.battlePhase='scored';
   return;
  }
  const state={cancelled:false};
  stage.dataset.battleDice='rolling';stage.dataset.battlePhase='dice';
  for(const t of totals)t.dataset.battleHidden='true';
  // attacker dice first, then defender, 70ms stagger per die (WEB)
  await Promise.all(dice.map((d,i)=>rollOne(d,table,faces,i*70,state)));
  if(!stage.isConnected)return;
  stage.dataset.battleDice='landed';stage.dataset.battlePhase='scored';
  for(const t of totals)delete t.dataset.battleHidden;
 }
 // Cancel a running roll if the stage is removed (result confirmed early).
 window.__LEAF_BATTLE_DICE_ROLL__={play,tickMs:TICK_MS,
  provenance:'OBS 1171 slot20+slot12 frames/ticks VERIFIED; roles, tick ms, drop, order INFERRED'};
})();
