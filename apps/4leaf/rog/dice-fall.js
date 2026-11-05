'use strict';
/* The user remembers 4LEAF's actual roll sequence: dice descend from above,
 * bounce more than once and only THEN reveal their faces. This recovered
 * source archive has source die sprite frames but no decoded 2002 roll
 * timing, mesh or trajectory. This renderer
 * is an explicit WEB RECONSTRUCTION of those interactions, NOT original
 * keyframe data. The underlying real game.js generates every outcome first.
 * No dice randomness, item or turn rule may be introduced here.
 */
(function(){
 const $=id=>document.getElementById(id);
 const PIPS={
  1:[4],2:[0,8],3:[0,4,8],4:[0,2,6,8],
  5:[0,2,4,6,8],6:[0,2,3,5,6,8]
 };
 const ROTATION={1:[0,0],2:[0,-90],3:[-90,0],
  4:[90,0],5:[0,90],6:[0,180]};
 // The original 2002 Dice/OBS.pak 1223.obs contains D4 sprites:
 // 0..3 are the 1..4-pip result faces (visually VERIFIED), 4..21 are
 // rotating poses. Their original timing/trajectory is still INFERRED.
 // The original D4 source PNGs are stored bottom-up, as with 1171 D6.
 const ORIGINAL_D4_MEMBER_SHA='f6f9792b1fdfa6185cfc89cb8e44be4bbdaf69b7d5cc3b792868354fc8a28f89';
 function originalD4(){
  const ui=window.ORIGINAL_LEAF_UI_FRAMES?.['1223'];
  if(!ui||ui.sourceSHA256!==ORIGINAL_D4_MEMBER_SHA||
     ui.declaredFrames!==22||ui.frames?.length!==22)return null;
  const frames=[...ui.frames].sort((a,b)=>a.index-b.index);
  // Reject a partial/mismatched source map instead of silently associating
  // an arbitrary 4-eye WEB result with a different source sprite.
  if(!frames.every((f,i)=>f.index===i&&
     f.url==='./original/OBS/ui/1223-'+String(i).padStart(3,'0')+'.png'))return null;
  return {member:'1223.obs',faces:frames.slice(0,4),tumble:frames.slice(4),
   declared:22,partial:false};
 }
 // Result-face normals use the regular tetrahedral dihedral angle
 // acos(-1/3)=109.471 degrees. This is still a WEB fallback mesh,
 // NOT original 2002 MVE geometry/keyframes.
 const TETRA_ANGLE=109.471;
 const TETRA_LAND={
  1:'rotateY(0deg) rotateZ(0deg)',
  2:'rotateY(-109.471deg) rotateZ(0deg)',
  3:'rotateY(-109.471deg) rotateZ(-120deg)',
  4:'rotateY(-109.471deg) rotateZ(-240deg)'
 };
 let active=0,last=[],lastSides=[],complete=0;
 /* ORIGINAL D6 SPRITE (2026-11-01). Dice/OBS.pak member 1171.obs was filed
  * as card 0171 "HUD-card-icon", but its frames are the game's die:
  * frames 0-5 are flat result faces showing 1..6 pips (46x49, red single
  * pip) - the same art as the dice in the archived 800x600 battle.jpg -
  * and frames 6+ are a white die tumbling in 3D (60x71). Face index =
  * pips - 1 is VERIFIED by counting pips in each frame. Only tumble frames
  * 6,7,10,18,25 were the initial partial set; now all 28 are available
  * through the extracted UI manifest. D4 1223.obs source faces have been
  * visually reviewed, but physics and frame timings remain WEB inferred. */
 const D6_MEMBER='0171';
 const D6_TUMBLE=[6,7,10,18,25];
 function originalD6(){
  // Preferred: the UI manifest (tools/extract-targeted-original-frames.py)
  // holding every decoded 1171 frame with written-run alpha. Faces 0-5 are
  // VERIFIED by pip count; tumble order = native frame order (INFERRED).
  const ui=window.ORIGINAL_LEAF_UI_FRAMES?.['1171'];
  if(ui?.frames?.length){
   const at=i=>ui.frames.find(f=>f.index===i)||null;
   const faces=[0,1,2,3,4,5].map(at);
   if(faces.every(Boolean))return {member:ui.member||'1171.obs',faces,
    tumble:ui.frames.filter(f=>f.index>=6).sort((a,b)=>a.index-b.index),
    declared:ui.declaredFrames,partial:!!ui.partial};
  }
  const member=window.ORIGINAL_LEAF_OBS_FRAMES?.[D6_MEMBER];
  if(!member?.frames)return null;
  // Legacy fallback: colour-key corrected copies of the 11 sampled frames.
  const fix=f=>f&&{...f,url:f.url.replace('/OBS/bulk/1171-','/OBS/d6-colorkey-corrected/1171-')};
  const at=i=>fix(member.frames.find(f=>f.index===i)||null);
  const faces=[0,1,2,3,4,5].map(at);
  if(!faces.every(Boolean))return null;
  return {member:member.originalMember||'1171.obs',faces,
   tumble:D6_TUMBLE.map(at).filter(Boolean),declared:28,partial:true};
 }
 // These 63 SHA1-archive-derived PNGs are correctly located but their
 // independent per-block palettes were decoded incorrectly in round 7.
 // They are kept as forensic evidence only, NOT used in live gameplay.
 // The separately verified original UI result faces remain authoritative.
 const EMBEDDED_DIE_CHAINS=Object.freeze({
  6:[['obs-1171-c0',16],['obs-1171-c1',16],['obs-1171-c2',6]],
  4:[['obs-1223-c0',9],['obs-1223-c1',16]]
 });
 function originalEmbeddedDice(sides){
  const archive=window.ORIGINAL_LEAF_EMBEDDED_DICE;
  if(!archive)return null;
  const spec=EMBEDDED_DIE_CHAINS[sides],out=[];
  if(!spec)return null;
  for(const [id,count] of spec){
   const item=archive[id];
   if(item?.originalMember!=='OBS.pak/'+(sides===6?'1171':'1223')+'.obs'||
      item.status!=='QUARANTINED/role-unknown'||
      !Number.isInteger(item.trailerOffset)||item.trailerOffset<128||
      !Array.isArray(item.frames)||item.frames.length!==count)return null;
   for(let i=0;i<count;i++){
    const f=item.frames[i];
    if(f.index!==i||f.url!=='./original/OBS/embedded/'+id+'-'+String(i).padStart(3,'0')+'.png'||
       !/^[a-f0-9]{64}$/.test(f.sha256)||!Number.isInteger(f.width)||
       !Number.isInteger(f.height)||f.width<1||f.height<1)return null;
    out.push({...f,sourceChain:id});
   }
  }
  return {frames:out,chains:spec.map(x=>x[0]),
   role:'source-OBS-pixels-VERIFIED/rolling-order-WEB-INFERRED'};
 }
 // The 7th extraction used the FIRST block's palette for independent
 // additional OBS blocks. Their coordinates are source-derived but colours
 // are wrong; a matching source PNG SHA256 does NOT establish palette
 // correctness. Do not render any of those 63 extra frames until each
 // corrected frame has been visually checked, SHA256 pinned, and explicitly
 // added to this allowlist. No runtime metadata flag can override the gate.
 // Each approved chain must supply the exact complete indexed set.
 const EMBEDDED_PALETTE_REVIEWED_SHA256=Object.freeze({});
 function playableEmbeddedDice(sides){
  const candidate=originalEmbeddedDice(sides);
  if(!candidate)return null;
  return candidate.frames.every(frame=>
   EMBEDDED_PALETTE_REVIEWED_SHA256[frame.sourceChain]?.[frame.index]===frame.sha256
  )?candidate:null;
 }
 // Warm the complete original D4 image sequence after the 1223 manifest
 // loads. Without this, first-turn 60ms frame swaps may show blank/stale
 // images on cold mobile networks. Only source assets are cached in memory;
 // neither gameplay RNG nor timing/turn state is touched.
 const d4ImageCache=new Map();
 function prefetchD4(){
  const native=originalD4();
  if(!native||typeof Image!=='function')return 0;
  for(const f of [...native.faces,...native.tumble]){
   if(d4ImageCache.has(f.url))continue;
   const img=new Image();
   d4ImageCache.set(f.url,img);
   img.src=f.url;
   if(typeof img.decode==='function')img.decode().catch(()=>{});
  }
  return d4ImageCache.size;
 }
 // D6 has 28 genuine source frames (6 audited landing faces + 22 tumble
 // packets). Fetching them at 60ms cadence without predecode can show a
 // stale/blank frame on the FIRST cold-cache turn, even though the native
 // images are present. Keep real PNGs in memory; this is not synthesized art.
 const d6ImageCache=new Map();
 function prefetchD6(){
  const native=originalD6();
  if(!native||typeof Image!=='function')return 0;
  for(const f of [...native.faces,...native.tumble]){
   if(d6ImageCache.has(f.url))continue;
   const img=new Image();
   d6ImageCache.set(f.url,img);
   img.src=f.url;
   if(typeof img.decode==='function')img.decode().catch(()=>{});
  }
  return d6ImageCache.size;
 }
 // Preload only separately colour-verified native trailer PNGs. All 63
 // current extra frames stay quarantined; the original UI art is preloaded
 // independently, so gameplay and offline fallback remain available.
 const embeddedDieCache=new Map();
 function prefetchEmbeddedDice(){
  if(typeof Image!=='function')return 0;
  for(const sides of [4,6]){
   for(const frame of playableEmbeddedDice(sides)?.frames||[]){
    if(embeddedDieCache.has(frame.url))continue;
    const img=new Image();embeddedDieCache.set(frame.url,img);
    img.src=frame.url;
    if(typeof img.decode==='function')img.decode().catch(()=>{});
   }
  }
  return embeddedDieCache.size;
 }
 // Score numerals from original UI 1167 should be decoded before first battle.
 // Separate cache preserves the original D6 (28) decoded-frame counters.
 const numeralImageCache=new Map();
 function prefetchNumerals(){
  const frames=window.ORIGINAL_LEAF_UI_FRAMES?.['1167']?.frames||[];
  if(typeof Image!=='function')return 0;
  for(const f of frames){
   if(numeralImageCache.has(f.url))continue;
   const img=new Image();numeralImageCache.set(f.url,img);img.src=f.url;
   if(typeof img.decode==='function')img.decode().catch(()=>{});
  }
  return frames.length;
 }
 /* ORIGINAL ROLL TABLES (2026-11-04). The CI data branch
  * data/4leaf-obs-blocks-20261103 decoded every extra block of 1171 (D6) and
  * 1223 (D4) with ITS OWN palette (block 0 is byte-identical to
  * original/OBS/ui) together with the members' animation tables:
  *   type-2 record = show block B frame F at tick T; type-60 = id 2125.
  * D6 slot 20 = 15 crisp rotations of block 0 (18..27, 2 ticks each),
  * slot 12 = 16 blurred-then-settling block-2 frames with id 2125 at tick 1,
  * slot 13 = 16 block-1 frames; D4 uses the same slot numbers (block 1 for
  * 12, block 2 for 13). Frames/ticks VERIFIED; using slot 20 for the fall,
  * slot 12 from the first impact (2125 = presumed impact sound) and the
  * VERIFIED pip face at rest is INFERRED. Pins: SHA-256 over the ordered
  * frame hashes of each member's imported block set; anything else stays
  * off (the round-7 'embedded' chains keep their quarantine). */
 const DICE_BLOCK_SET_SHA256=Object.freeze({
  '1171':'0999b9e0adac7799ff89d378e3717e9335b948c2d42d7659304588ba0bd8014b',
  '1223':'ed4df7a4c4aaa65f78c5ec8201b49cf1b17510958dd0804c45086170d2929f06'});
 const diceBlockVerified={};
 async function verifyDiceBlocks(){
  const all=window.ORIGINAL_LEAF_DICE_BLOCKS?.members;
  if(!all||!window.crypto?.subtle)return diceBlockVerified;
  for(const member of Object.keys(DICE_BLOCK_SET_SHA256)){
   const m=all[member];
   if(!m)continue;
   const joined=m.blocks.flatMap(b=>b.frames.map(f=>f.sha256)).join('');
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(joined));
   const hex=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
   diceBlockVerified[member]=hex===DICE_BLOCK_SET_SHA256[member];
  }
  return diceBlockVerified;
 }
 const diceBlocksReady=verifyDiceBlocks().catch(()=>diceBlockVerified);
 function originalRollTable(sides){
  const member=sides===4?'1223':'1171';
  const m=window.ORIGINAL_LEAF_DICE_BLOCKS?.members?.[member];
  const ui=window.ORIGINAL_LEAF_UI_FRAMES?.[member]?.frames;
  if(!m||!ui||diceBlockVerified[member]!==true)return null;
  if(m.originalMember!=='OBS.pak/'+member+'.obs')return null;
  const blockFrames=[ui,...m.blocks.map(b=>b.frames)];
  if(blockFrames.some((frames,b)=>frames.length!==m.blockFrames[b]))return null;
  const prefix='./original/OBS/dice-blocks/obs-'+member+'-b';
  if(!m.blocks.every(b=>b.frames.every((f,i)=>f.index===i&&
   f.url===prefix+b.block+'-'+String(i).padStart(3,'0')+'.png')))return null;
  const resolveSlot=index=>{
   const a=m.animations[index];
   if(!a||!a.keys.length)return null;
   const frames=a.keys.map(([tick,block,frame])=>{
    const f=blockFrames[block]?.[frame];
    return f&&{...f,tick,block,sourceChain:'OBS-'+member+'-b'+block};
   });
   return frames.every(Boolean)?{index,ticks:a.ticks,frames,sounds:a.sounds}:null;
  };
  const fall=resolveSlot(20),impact=resolveSlot(12);
  if(!fall||!impact)return null;
  return {member,fall,impact,
   role:'OBS-'+member+'-slots-20-12-frames-and-ticks-VERIFIED/fall-impact-role-INFERRED/ms-UNVERIFIED'};
 }
 const rollImageCache=new Map();
 function prefetchRollTables(){
  if(typeof Image!=='function')return 0;
  for(const sides of [6,4]){
   const t=originalRollTable(sides);
   for(const f of t?[...t.fall.frames,...t.impact.frames]:[]){
    if(rollImageCache.has(f.url))continue;
    const img=new Image();rollImageCache.set(f.url,img);img.src=f.url;
    if(typeof img.decode==='function')img.decode().catch(()=>{});
   }
  }
  return rollImageCache.size;
 }
 diceBlocksReady.then(prefetchRollTables);
 const prefetchOriginalDice=()=>{prefetchD4();prefetchD6();prefetchEmbeddedDice();prefetchRollTables();return prefetchNumerals()};
 const prefetchSourceDice=prefetchOriginalDice;
 if(document.readyState==='complete')prefetchSourceDice();
 else window.addEventListener('load',prefetchSourceDice,{once:true});
 const state=()=>({active:active>0,last:last.slice(),lastSides:lastSides.slice(),complete,
  source:'user-reported fall/bounce; outcome from live game engine',
  // Full original roll (all tumble frames + trajectory) is not recovered.
  originalFramesRecovered:false,
  originalD6Faces:!!originalD6(),
  originalD6TumbleFrames:originalD6()?.tumble.map(f=>f.index)||[],
  originalD6PrefetchCount:d6ImageCache.size,
  originalD6DecodedCount:[...d6ImageCache.values()]
   .filter(image=>image.complete&&image.naturalWidth>0).length,
  originalD4Art:!!originalD4(),
  originalD4TumbleFrames:originalD4()?.tumble.map(f=>f.index)||[],
  originalD4PrefetchCount:d4ImageCache.size,
  nativeEmbeddedD6Frames:originalEmbeddedDice(6)?.frames.length||0,
  nativeEmbeddedD4Frames:originalEmbeddedDice(4)?.frames.length||0,
  nativeEmbeddedPlayableD6Frames:playableEmbeddedDice(6)?.frames.length||0,
  nativeEmbeddedPlayableD4Frames:playableEmbeddedDice(4)?.frames.length||0,
  nativeEmbeddedPaletteStatus:'QUARANTINED/per-block-palette-not-yet-verified',
  nativeEmbeddedPrefetchCount:embeddedDieCache.size,
  nativeEmbeddedDecodedCount:[...embeddedDieCache.values()].filter(img=>img.complete&&img.naturalWidth>0).length,
  nativeEmbeddedRole:'source-pixel-coordinates-VERIFIED/palette-UNVERIFIED/not-live',
  originalRollTables:{d6:originalRollTable(6)?.role||null,d4:originalRollTable(4)?.role||null},
  originalRollBlockSetsVerified:{...diceBlockVerified},
  originalRollPrefetchCount:rollImageCache.size});
 function makeFace(n){
  const face=document.createElement('span');
  face.className='leaf-die-face leaf-die-face-'+n;
  face.dataset.face=String(n);
  face.setAttribute('aria-hidden','true');
  for(let i=0;i<9;i++){
   const dot=document.createElement('i');
   dot.className='leaf-die-eye'+(PIPS[n].includes(i)?' visible':'');
   face.append(dot);
  }
  return face;
 }
 function makeDie(result,index,count,sides){
  // Ground contact belongs to the board plane, NOT to the moving cube.
  // Previously a CSS drop-shadow travelled 260px up into the air with
  // every falling die. Use a stationary track shadow while the genuine
  // gameplay die model continues its independent fall/spin/bounces.
  // This remains WEB inferred lighting, not original 2002 MVE keyframes.
  const track=document.createElement('span');
  track.className='leaf-fall-track';
  track.dataset.shadowProvenance='web-inferred-ground-contact';
  const node=document.createElement('span');
  node.className='leaf-fall-piece';
  node.dataset.result=String(result);
  node.dataset.sides=String(sides);
  node.dataset.index=String(index);
  node.setAttribute('aria-hidden','true');
  const cube=document.createElement('span');
  cube.className='leaf-fall-cube';
  if(sides===4){
   cube.classList.add('leaf-fall-tetra');
   for(let n=1;n<=4;n++){
    const face=document.createElement('span');
    face.className='leaf-tetra-face leaf-tetra-face-'+n;
    face.textContent=String(n);
    face.setAttribute('aria-hidden','true');
    cube.append(face);
   }
   cube.dataset.result=String(result);
  }else{
   for(let n=1;n<=6;n++)cube.append(makeFace(n));
  }
  node.append(cube);
  const original=sides===4?originalD4():originalD6();
  const embedded=playableEmbeddedDice(sides);
  // Never replace the VERIFIED landing eyes from the established UI
  // manifest. The 63 additional frames have incorrect per-block colours;
  // only SHA256-allowlisted and independently reviewed frames may be used.
  const rollTable=original?originalRollTable(sides):null;
  const source=original&&rollTable?{...original,rollTable,tumble:rollTable.fall.frames}:
   original&&embedded?{...original,tumble:embedded.frames,nativeEmbedded:embedded}:original;
  let sprite=null;
  if(source){
   sprite=document.createElement('img');
   sprite.className=sides===4?'leaf-fall-original-d4':'leaf-fall-original-d6';
   sprite.alt='';sprite.draggable=false;
   sprite.setAttribute('aria-hidden','true');
   const first=source.tumble[0]||source.faces[result-1];
   sprite.src=first.url;
   sprite.dataset.frame=String(first.index);
   node.classList.add('leaf-fall-original');
   node.dataset.faceSource='original-OBS-'+source.member+'/face-VERIFIED-by-pip-count';
   node.dataset.tumbleSource=source.nativeEmbedded?
    'original-OBS/embedded/'+source.tumble.length+'-verified-source-pixels/WEB-sequence-INFERRED':
    'original-OBS-'+source.member+'/' +
    (source.partial?'partial-':'index-ordered-INFERRED-')+source.tumble.length+'-frames';
   node.dataset.embeddedSourceChains=source.nativeEmbedded?.chains.join(',')||'';
   if(source.rollTable){
    node.dataset.tumbleSource='original-OBS-'+source.rollTable.member+'/slot20-fall+slot12-impact';
    node.dataset.rollTableRole=source.rollTable.role;
   }
   node.dataset.nativeSourceRole='landing-faces-VERIFIED/tumble-frames-source-VERIFIED/order-and-FPS-INFERRED';
   sprite.dataset.sourceChain=first.sourceChain||'original-UI-OBS';
   // If the original PNG cannot load, show the WEB cube instead of nothing.
   sprite.addEventListener('error',()=>{
    node.classList.remove('leaf-fall-original');
    node.dataset.faceSource='web-cube-fallback/original-load-failed';
   });
   node.append(sprite);
  }else{
   node.dataset.faceSource=sides===4?'web-tetra/no-original-D4-art':'web-cube/original-missing';
  }
  track.append(node);
  return {track,node,cube,result,index,count,sides,sprite,source};
 }
 const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 async function animateDie(die,duration,instant){
  const {track,node,cube,result,index,sides,sprite,source}=die;
  const showFace=()=>{
   if(!sprite)return;
   const face=source.faces[result-1];
   sprite.src=face.url;sprite.dataset.frame=String(face.index);
   sprite.dataset.sourceChain='original-UI-OBS';
   node.dataset.originalFace=String(face.index);
  };
  // Match stationary ground-shadow opacity to the SAME presentation
  // timeline as actual fall/bounce animation, not an independent clock.
  track.style.setProperty('--leaf-dice-shadow-duration',duration+'ms');
  const [rx,ry]=sides===4?[0,0]:ROTATION[result];
  const target=sides===4?TETRA_LAND[result]:
   'rotateX('+(720+rx)+'deg) rotateY('+(1080+ry)+'deg) rotateZ(0deg)';
  // Source MVE camera/keyframes have not been recovered. The previous
  // inferred 260px spawn height put real CSS geometry outside the compact
  // iPhone stage. Keep the first drop INSIDE the actual current stage, with
  // rebound heights proportional to the available falling distance.
  // This changes PRESENTATION only; dice faces/results and game-turn awaits
  // continue to come exclusively from the authoritative match engine.
  const layerHeight=track.parentElement?.getBoundingClientRect().height||0;
  const dieHeight=track.getBoundingClientRect().height||57;
  const fallHeight=Math.round(Math.max(28,Math.min(260,layerHeight-dieHeight-12)));
  const bounceHeight=Math.round(Math.min(66,fallHeight*.26));
  const finalBounce=Math.round(Math.min(19,fallHeight*.075));
  node.dataset.webFallHeight=String(fallHeight);
  node.dataset.webBounceHeights=bounceHeight+','+finalBounce;
  node.dataset.motionProvenance='responsive-WEB-fallback/not-original-MVE';
  const physics=[
   {transform:'translate3d(0,-'+fallHeight+'px,0) scale(.76)',offset:0},
   {transform:'translate3d('+(index%2?12:-12)+'px,0,0) scale(1.08,.88)',offset:.38},
   {transform:'translate3d('+(index%2?19:-19)+'px,-'+bounceHeight+'px,0) scale(.98)',offset:.55},
   {transform:'translate3d('+(index%2?10:-10)+'px,0,0) scale(1.03,.94)',offset:.72},
   {transform:'translate3d('+(index%2?7:-7)+'px,-'+finalBounce+'px,0) scale(.99)',offset:.83},
   {transform:'translate3d(0,0,0) scale(1)',offset:1}
  ];
  const spin=sides===4?[
   {transform:'rotateX(-540deg) rotateY(390deg) rotateZ(-40deg)',offset:0},
   {transform:'rotateX(-180deg) rotateY(730deg) rotateZ(21deg)',offset:.4},
   {transform:'rotateX(35deg) rotateY(355deg) rotateZ(-11deg)',offset:.81},
   {transform:target,offset:1}
  ]:[
   {transform:'rotateX(-680deg) rotateY(510deg) rotateZ(-30deg)',offset:0},
   {transform:'rotateX(-180deg) rotateY(720deg) rotateZ(24deg)',offset:.38},
   {transform:'rotateX(370deg) rotateY(890deg) rotateZ(-10deg)',offset:.71},
   {transform:target,offset:1}
  ];
  if(instant||typeof node.animate!=='function'){
   cube.style.transform=target;
   showFace();
   return;
  }
  let tumbleTimer=0;
  const table=sprite&&source.rollTable;
  if(table){
   // Slot 20 loops until the first floor contact (physics offset .38), then
   // slot 12 plays once and holds its last frame; one WEB tick = the slot-12
   // span spread over the rebound part of the presentation.
   const impactAt=duration*.38;
   const tickMs=Math.max(8,(duration-impactAt)/table.impact.ticks);
   const t0=performance.now();let shown=-1;
   const frameAt=(slot,tick)=>{let f=slot.frames[0];
    for(const k of slot.frames){if(k.tick<=tick)f=k;else break}return f};
   const render=f=>{if(!f||shown===f.url)return;shown=f.url;
    sprite.src=f.url;sprite.dataset.frame=f.block+':'+f.index;
    sprite.dataset.sourceChain=f.sourceChain};
   node.dataset.rollTickMs=tickMs.toFixed(1)+'/WEB';
   const step=()=>{
    const t=performance.now()-t0;
    if(t<impactAt){
     node.dataset.rollPhase='fall/slot20';
     render(frameAt(table.fall,Math.floor(t/tickMs)%table.fall.ticks));
    }else{
     node.dataset.rollPhase='impact/slot12';
     render(frameAt(table.impact,Math.min(table.impact.ticks-1,Math.floor((t-impactAt)/tickMs))));
    }
   };
   step();
   tumbleTimer=setInterval(step,Math.max(16,Math.round(tickMs/2)));
  }else if(sprite&&source.tumble.length>1){
   let k=0;
   tumbleTimer=setInterval(()=>{
    k=(k+1)%source.tumble.length;
    const f=source.tumble[k];
    sprite.src=f.url;sprite.dataset.frame=String(f.index);
    sprite.dataset.sourceChain=f.sourceChain||'original-UI-OBS';
   },Math.max(60,Math.round(duration*.8/(source.tumble.length*2))));
  }
  const fall=node.animate(physics,{duration,
   easing:'linear',fill:'forwards'});
  const turn=cube.animate(spin,{duration,
   easing:'cubic-bezier(.19,.61,.33,1)',fill:'forwards'});
  try{await Promise.all([fall.finished,turn.finished]);}
  finally{
   // Make the FINAL face permanent before removing animated layer.
   cube.style.transform=target;
   if(tumbleTimer)clearInterval(tumbleTimer);
   showFace();
   fall.cancel();turn.cancel();
   node.style.transform='translate3d(0,0,0)';
  }
 }
 async function roll(results,options={}){
  const values=Array.isArray(results)?results.map(Number):[];
  const sides=Array.isArray(options.sides)?options.sides.slice():
    values.map(()=>options.sides===4?4:6);
  if(!values.length||values.length>4||sides.length!==values.length||
    sides.some(n=>n!==4&&n!==6)||
    values.some((v,i)=>!Number.isInteger(v)||v<1||v>sides[i]))
   throw new Error('Dice results must agree with D4/D6 source rules');
  if(active)throw new Error('Falling Dice presentation already running');
  const game=$('game');
  if(!game||!game.isConnected)return values.slice();
  let layer=$('leaf-dice-fall-layer');
  if(!layer){
   layer=document.createElement('div');
   layer.id='leaf-dice-fall-layer';
   layer.className='leaf-dice-fall-layer';
   layer.setAttribute('role','status');
   layer.setAttribute('aria-live','polite');
   game.append(layer);
  }
  layer.replaceChildren();
  layer.dataset.phase='falling';
  layer.setAttribute('aria-label','주사위가 하늘에서 떨어져 굴러갑니다');
  layer.dataset.count=String(values.length);
  layer.dataset.sides=sides.join(',');
  const dice=values.map((result,index)=>makeDie(result,index,values.length,sides[index]));
  for(const die of dice)layer.append(die.track);
  const instant=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches||false;
  active=1;
  try{
   await Promise.all(dice.map((die,index)=>animateDie(die,instant?0:1120+index*115,instant)));
   last=values.slice();
   lastSides=sides.slice();
   complete++;
   layer.dataset.phase='landed';
   layer.dataset.result=values.join(',');
   layer.setAttribute('aria-label','주사위 착지 결과 '+values.join(' + '));
   // Hold visible final values before the existing game HUD reveals them.
   if(!instant)await delay(210);
   layer.dataset.phase='complete';
   if(!instant)await delay(180);
   return values.slice();
  }finally{
   layer.dataset.phase='idle';
   layer.replaceChildren();
   active=0;
  }
 }
 window.__LEAF_DICE_FALL__={roll,getState:state,
  faces:PIPS,orientation:ROTATION,originalD6,originalD4,originalEmbeddedDice,playableEmbeddedDice,
  originalRollTable,diceBlocksReady,prefetchD4,prefetchD6,prefetchEmbeddedDice,prefetchNumerals,prefetchOriginalDice,
  tetraOrientation:{...TETRA_LAND},tetraDihedralDegrees:TETRA_ANGLE};
})();
