'use strict';
/* Per-CHESSMAN source identity and turn-linked animation controller.
 * For recovered 2002 OBS members, use actual full-body indexed PNG pixels.
 * Remaining characters keep a labeled CSS proxy while extraction continues. A ChatTown Registry/sava
 * standee must NEVER impersonate the original Dice chessman.
 * This articulated eight-head WEB PROXY is inferred, not original art.
 * registerFrames connects actual recovered animation sources once obtained.
 */
(function(){
 'use strict';
 const VALID=['idle','walk','attack','hurt','victory'];
 const frames=new Map(),timeouts=new WeakMap(),states=new WeakMap();
 const sourceTimers=new WeakMap();
 // A source OBS PAK member is NOT necessarily a playable full-body actor.
 // Pixel audit against the SHA-verified 2002 source, 2026-10-24:
 // 1096/1097/1098/1100 are spell glows; 1125/1128 visual particles;
 // 1133/1134 HUD symbols/logo, 1136-1139 overlay FX;
 // 1141/1142/1145/1146/1147 atmospheric objects/weapon box/bomb;
 // 1159-1167 are particles/weapons/roll numeral; 1170 tiny icon.
 // Older code displayed these original *effect* frames as "chessmen",
 // producing unreadable objects even if it picked a face-forward packet.
 // Preserve all original OBS bytes; route ONLY visually audited effects
 // to the honest native CardData fallback until a real actor is recovered.
 const NON_ACTOR_OBS=Object.freeze({
  '0096':'spell-orb','0097':'spell-ray','0098':'light-effect',
  '0100':'lightning',
  '0125':'particle','0128':'particle',
  '0133':'ability-icon','0134':'DiceAttack-logo',
  '0136':'ring-effect','0137':'hex-overlay','0138':'impact-star',
  '0139':'ground-ring','0141':'smoke','0142':'leaf-symbol',
  '0145':'aura','0146':'bomb-visual','0147':'prop-box',
  '0159':'impact-star','0160':'sword-effect','0161':'fire-ring',
  '0163':'magic-burst','0164':'magic-orb','0165':'glow',
  '0167':'die-result-numeral','0170':'HUD-icon',
  '0099':'spell-ring',
  '0127':'dark-ring',
  '0130':'aura-ring',
  '0131':'cloth-effect',
  '0135':'particle-spray',
  '0140':'projectile-flash',
  '0143':'smoke-fragments',
  '0144':'spark-fragments',
  '0156':'particle-spray',
  '0158':'pointer-hand',
  '0162':'magic-globe',
  '0169':'pumpkin-prop',
  '0171':'HUD-card-icon'
 });
 // CHR source reference +260, not inferred 0NNN->1NNN mapping.
 const originalFor=id=>window.__LEAF_CHR_BODY_MAP__?.resolve(id)||null;
 const bodyVisualId=id=>window.__LEAF_CHR_BODY_MAP__?.assetKey(id)||'';
 const poses=['idle','walk','attack','hurt','victory'];
 // VISUALLY COMPARED against recovered original pixels, 2026-10-24.
 // Sample frame 0 is NOT a front-facing pose: original 1040/1042/1043/
 // 1044/1046/1048/1061/1064 silhouettes show their backs/side at 0.
 // Native PNGs were FLIP_TOP_BOTTOM on extraction and get scaleY(-1) in
 // dice-original-obs.css; this is genuine source pixel direction, NOT a
 // horizontally mirrored or web-generated character.
 const AUDITED_FRONT_SOURCE=Object.freeze({
  '0040':25,'0042':25,'0043':25,'0044':25,
  '0045':18,'0046':25,'0048':25,'0049':25,
  '0051':25,'0052':25,'0053':25,'0054':25,'0055':25,
  '0056':25,'0058':25,'0059':25,'0060':25,'0061':25,
  '0062':25,'0064':25,
  // 2026-11-01 front-silhouette review: frame25 AND frame30 of 22 more
  // 37-frame members viewed upright at 2x beside frame0. 25/30 are camera-
  // facing bodies with changed limb poses, 0 is the back (same pattern as
  // above). Front silhouette only; action/FPS UNVERIFIED. Excluded:
  // 0086/0088 (non-humanoid facing not confidently distinguished).
  // 2026-11-02 independent 0 and 25..30 original PNG review: 1067 (orange
  // winged), 1068 (dark winged), 1074 (sword + cape) each has a full
  // consistently camera-facing six-image body cycle, distinct from frame0.
  // Source frame orientation is VISUALLY reviewed, but real EXE action
  // assignment, direction turn rules and FPS remain UNVERIFIED.
  '0067':25,'0068':25,'0074':25,
  '0047':25,'0050':25,'0063':25,'0065':25,'0066':25,'0069':25,
  '0070':25,'0071':25,'0072':25,'0073':25,'0075':25,'0076':25,
  '0077':25,'0078':25,'0079':25,'0080':25,'0081':25,'0082':25,
  '0083':25,'0084':25,'0085':25,'0166':25,
  // Genuine 1088 golem 37-frame sheet reviewed, EXE labels unverified.
  '0088':25
 });
 /* Direction/action evidence, 2026-11-01 (INFERRED, not an EXE table).
  * In every reviewed 37-frame member the sampled indices show the SAME
  * layout: 0-2 rear three-quarter, 3-7 rear view with alternating legs,
  * 10 rear weapon raise, 18 front three-quarter strike/cast, 25-30 front
  * view with alternating legs. Frames 8,9,11-17,19-24,31-36 are not in the
  * repository, so the full table is still unknown.
  * REVIEWED_BACK_WALK: 3..7 viewed at 2x per member and confirmed as a rear
  *   body with alternating legs. Excluded: 0042 (only 3 extracted), 0058
  *   (3-7 are diagonal sword poses), 0069/0079 (rear not distinguishable),
  *   0084/0085 (non-humanoid), 0045 (front is 18).
  * REVIEWED_FRONT_ATTACK: frame 18 is a front three-quarter strike or cast
  *   that differs from the standing front. Excluded 0045 (18 is its idle
  *   front), 0084/0085 (non-humanoid). */
 const REVIEWED_BACK_WALK=Object.freeze(new Set([
  '0040','0043','0044','0046','0047','0048','0049','0050','0051',
  '0052','0053','0054','0055','0056','0059','0060','0061','0062',
  '0063','0064','0065','0066','0070','0071','0072','0073','0075',
  '0076','0077','0078','0080','0081','0082','0083','0166'
 ]));
 const REVIEWED_FRONT_ATTACK=Object.freeze(new Set([
  '0040','0042','0043','0044','0046','0048','0049','0051','0052',
  '0053','0054','0055','0056','0058','0059','0060','0061','0062',
  '0064','0047','0050','0063','0065','0066','0069','0070','0071',
  '0072','0073','0075','0076','0077','0078','0079','0080','0081',
  '0082','0083','0166'
 ]));
 const BACK_WALK_INDICES=[3,4,5,6,7];
 // Original left-profile silhouettes (frames 14..17) were individually
 // inspected in the full 37-frame contact sheets of 1040/1046/1078.
 // The source PIXELS and facing are verified; their mapping to live
 // horizontal DMP motion and playback period are still INFERRED.
 const LEFT_PROFILE_SOURCE=Object.freeze(new Set(['0040','0046','0078']));
 const LEFT_PROFILE_WALK_INDICES=[14,15,16,17];
 // The same full 37-frame sheets show source wind-up, weapon-strike and
 // follow-through silhouettes at 31,33,35 in these three actors. Their
 // classification as battle ATTACK and WEB 175ms frame period are INFERRED.
 // Keep the older reviewed frame18 path for all other source characters.
 const FULL_SOURCE_ATTACK=Object.freeze(new Set(['0040','0046','0078']));
 const FULL_SOURCE_ATTACK_INDICES=[25,31,33,35,25];
 /* ACTION_TABLE_37: INFERRED repeating 37-frame OBS layout for 41 human actors.
  * 2002 executable's action timing / direction map remains UNVERIFIED.
  * 0084,0085,0086,0088 use nonhumanoid layouts and stay on legacy path. */
 const ACTION_TABLE_37=Object.freeze({
  idle:{rear:[0,1,2],side:[11,12,13],front:[22,23,24]},
  walk:{rear:[3,4,5,6,7,8],side:[14,15,16,17,18,19],front:[25,26,27,28,29,30]},
  strike:{rear:[9,10],side:[20,21],front:[31,32]},
  duel:[33,34,35,36]
 });
 const EXT_STRUCTURAL_37=Object.freeze(new Set(['0042']));
 const STRUCTURAL_37=Object.freeze(new Set([
  '0040','0043','0044','0046','0047','0048','0049','0050','0051','0052',
  '0053','0054','0055','0056','0058','0059','0060','0061','0062','0063',
  '0064','0065','0066','0067','0068','0069','0070','0071','0072','0073',
  '0074','0075','0076','0077','0078','0079','0080','0081','0082','0083',
  '0088','0166'
 ]));
 function frontFacingSource(native,id){
  const available=native?.frames||[];
  const approved=AUDITED_FRONT_SOURCE[id];
  const verified=available.find(f=>f.index===approved);
  if(verified)return {frame:verified,
    evidence:'visual-original-OBS-reviewed/front/'+id+'-'+approved};
  // In 60/90 bulk source models the same 25th native VIDEO packet offers
  // a likely camera-facing silhouette. It has NOT been manually verified
  // for every chessman. Use its genuine pixels in idle and keep the
  // uncertainty visible in the DOM/ledger rather than asserting 2002 FPS.
  const candidate=available.find(f=>f.index===25);
  if(candidate)return {frame:candidate,
    evidence:'source-family-frame25/front-candidate/PER-ID-UNVERIFIED'};
  return {frame:available.find(f=>f.index===0)||available[0]||null,
    evidence:'source-front-unavailable/NO-VERIFIED-DIRECTION'};
 }
 // Verified source pixels: 1040/1042/1043 frames 25 and 30 were
 // individually inspected in their native 640-stride PNGs: both are
 // camera-facing full-body silhouettes (not 0..7 rear/side turns).
 // This is a front-preserving WEB movement mapping; original direction
 // lookup and playback FPS remain unknown.
 const REVIEWED_FRONT_MOTION=Object.freeze({
  // 19 specific actual 2002 OBS.pak source members. Their frame25 and
  // frame30 PNGs were individually viewed in original paletted form and
  // retain the already-audited front-facing body silhouette with changed
  // arm/leg/cloth poses. Native 2002 action table / frame timing UNKNOWN;
  // sequenceFor's 25-30 loop is a WEB playback reconstruction, NOT a
  // recovered original lookup. Never map 0045 (only front 18 confirmed)
  // or any visually unaudited source/effect member.
  '0040':[25,30], '0042':[25,30], '0043':[25,30],
  '0044':[25,30], '0046':[25,30], '0048':[25,30],
  '0049':[25,30], '0051':[25,30], '0052':[25,30],
  '0053':[25,30], '0054':[25,30], '0055':[25,30],
  '0056':[25,30], '0058':[25,30], '0059':[25,30],
  '0060':[25,30], '0061':[25,30], '0062':[25,30],
  '0064':[25,30],
  // 2026-11-02: 0067/0068/0074 native packets 25..30 inspected each,
  // front silhouettes remain consistent while original limbs/capes move.
  '0067':[25,30],'0068':[25,30],'0074':[25,30],
  // 2026-11-01: same 25/30 front-pose check for the 22 members above.
  '0047':[25,30],'0050':[25,30],'0063':[25,30],'0065':[25,30],'0066':[25,30],
  '0069':[25,30],'0070':[25,30],'0071':[25,30],'0072':[25,30],'0073':[25,30],
  '0075':[25,30],'0076':[25,30],'0077':[25,30],'0078':[25,30],'0079':[25,30],
  '0080':[25,30],'0081':[25,30],'0082':[25,30],'0083':[25,30],'0084':[25,30],
  '0085':[25,30],'0166':[25,30],
  '0088':[25,30]
 });
 function sequenceFor(native,action,id,travel,context={}){
  const all=native.frames||[];
  const at=index=>all.find(f=>f.index===index)||null;
  const facing=frontFacingSource(native,id);
  const front=facing.frame;
  const approved=Object.hasOwn(AUDITED_FRONT_SOURCE,id)&&
   facing.evidence.startsWith('visual-original-OBS-reviewed/');
  const movement=REVIEWED_FRONT_MOTION[id]?.map(at).filter(Boolean)||[];
  // Authenticated native PNGs 25..30 were independently reviewed on
  // 2026-11-01. These six source pixels contain a frontal moving pose cycle.
  // Sequence timing and its assignment to WEB walk are inferred, not an
  // authenticated 2002 EXE action table. Never promote missing indices.
  const fullFrontCycle=REVIEWED_FRONT_MOTION[id]
    ?[25,26,27,28,29,30].map(at).filter(Boolean):[];
  if(approved&&(STRUCTURAL_37.has(id)||EXT_STRUCTURAL_37.has(id))&&all.length===37&&action==='idle'){
   // Last real direction sets the 37-frame source stance block. Both
   // historical action label and 340ms timing are INFERRED, not EXE data.
   const rest=context.duel?'side':context.rest==='away'?'rear'
    :(context.rest==='left'||context.rest==='right')?'side':'front';
   const block=ACTION_TABLE_37.idle[rest].map(at);
   if(block.every(Boolean)){
    const out=[block[0],block[1],block[2],block[1]];
    out.mirror=context.duel?context.side==='attacker':rest==='side'&&context.rest==='right';
    out.table='idle-'+rest;out.loop=true;return out;
   }
  }
  if(action==='idle')return front?[front]:[];
  if(approved&&(STRUCTURAL_37.has(id)||EXT_STRUCTURAL_37.has(id))&&all.length===37){
   const pick=list=>{const out=list.map(at);return out.every(Boolean)?out:null};
   if(action==='walk'){
    const dir=travel==='away'?'rear':(travel==='left'||travel==='right')?'side':'front';
    const out=pick(ACTION_TABLE_37.walk[dir]);
    if(out){out.mirror=dir==='side'&&travel==='right';out.table='walk-'+dir;return out}
   }
   if(context.duel&&(action==='hurt'||action==='victory')){
    // No original hurt/victory source frames yet: hold an opponent-facing
    // side stance and mark the inferred substitute explicitly.
    const block=pick(ACTION_TABLE_37.idle.side);
    if(block){
     const out=action==='hurt'?[block[0]]:[block[0],block[1],block[2],block[1]];
     out.mirror=context.side==='attacker';out.table='duel-'+action+'-holds-side-stance';
     return out;
    }
   }
   if(action==='attack'){
    if(context.duel){
     // Side-facing native source lunge; attacker on the left mirrors toward defender.
     const out=pick([11,...ACTION_TABLE_37.duel,11]);
     if(out){out.mirror=context.side==='attacker';out.table='duel-33-36';return out}
    }
    const [windup,hit]=ACTION_TABLE_37.strike.front;
    const out=pick([25,windup,hit,hit,25]);
    if(out){out.table='strike-front-31-32';return out}
   }
  }
  if(approved){
   // Do not display verified BACK/SIDE 0..7 during an ordinary forward
   // movement, attack recovery or victory. One static authentic FRONT is
   // more truthful than a rapidly pirouetting chessman.
   // Moving AWAY from the camera (up the screen) shows the reviewed rear
   // walk 3..7 instead of a front body sliding backwards. INFERRED.
   if(action==='walk'&&travel==='left'&&LEFT_PROFILE_SOURCE.has(id)){
    const side=LEFT_PROFILE_WALK_INDICES.map(at);
    if(side.every(Boolean))return side;
   }
   if(action==='walk'&&travel==='away'&&REVIEWED_BACK_WALK.has(id)){
    const back=BACK_WALK_INDICES.map(at);
    if(back.every(Boolean))return back;
   }
   if(action==='walk')return fullFrontCycle.length===6
    ?fullFrontCycle
    :movement.length===2
     ?[movement[0],movement[1],movement[0],movement[1]]
     :front?[front]:[];
   if(action==='victory')return movement.length===2
    ?[movement[0],movement[1],movement[0]]
    :front?[front]:[];
   if(action==='attack'&&FULL_SOURCE_ATTACK.has(id)){
    const reviewed=FULL_SOURCE_ATTACK_INDICES.map(at);
    if(reviewed.every(Boolean))return reviewed;
   }
   if(action==='attack'&&REVIEWED_FRONT_ATTACK.has(id)&&at(18))
    return [front,at(18),at(18),front];
   // Original directional action-table does not confirm any other attack,
   // hit or defeat packet; preserve verified standing identity.
   return front?[front]:[];
  }
  // Other genuine frames are source-verified but directional attribution
  // remains unverified. A missing 0..7 packet is NOT a full walk animation.
  const fullWalk=Array.from({length:8},(_,i)=>at(i)).every(Boolean);
  if(native.hasVerifiedFrameZero===false)return all.slice(0,1);
  if(action==='walk'&&!fullWalk)return front?[front]:all.slice(0,1);
  const map={walk:[0,1,2,3,4,5,6,7],
   attack:[10,18],hurt:[18,10],victory:[25,30,0]};
  const picks=(map[action]||[0]).map(at).filter(Boolean);
  return picks.length?picks:(front?[front]:all.slice(0,1));
 }
 function renderNativeFrame(pawn,frame){
   const img=pawn.querySelector('img.leaf-chess-original-obs');
   if(!img||!frame)return;
   if(img.getAttribute('src')!==frame.url)img.src=frame.url;
   img.style.setProperty('--leaf-obs-width',frame.width+'px');
   img.style.setProperty('--leaf-obs-height',frame.height+'px');
   // The former WEB contact ellipse was always 36px, even for original
   // 12px-to-239px wide chessmen. Derive its conservative visible footprint
   // from EACH actual source frame's verified width, without fabricating
   // pixels/meshes. This is an INFERRED shadow, NOT archived EXE lighting.
   const contactWidth=Math.max(18,Math.min(84,Math.round(frame.width*.72)));
   pawn.style.setProperty('--leaf-native-contact-width',contactWidth+'px');
   pawn.dataset.sourceContactFootprint='inferred-shadow-width/from-original-OBS-frame';
   pawn.dataset.sourceContactWidth=String(contactWidth);
   // Native OBS signed image origins are often negative. Build a valid
   // single-operator CSS calc rather than 'calc(50% + -17px)' which browsers
   // can discard, silently placing authentic models on the wrong platform.
   // Mirror source anchor rather than altering source PNG bytes.
   const mirrored=pawn.dataset.sourceMirror==='true';
   const horizontal=mirrored
    ?-((Number(frame.originX)||0)+(Number(frame.width)||0))
    :Number(frame.originX)||0;
   img.style.setProperty('--leaf-obs-left',
    'calc(50% '+(horizontal<0?'-':'+')+' '+Math.abs(horizontal)+'px)');
   // The native OBS y origin is relative to that actor's own animation
   // canvas, not a globally shared foot plane. Directly subtracting the
   // source bottom offsets caused two characters standing on the SAME
   // recovered TIS cell to have visibly different shoe heights (8/23px).
   // Normalize only the per-character reference pivot to the shared
   // DMP tile top. Preserve every source frame's relative origin motion.
   // Absolute foot pivot is inferred; original frame metadata remains intact.
   const native=originalFor(pawn.dataset.chessmanId);
   const standing=window.__LEAF_NATIVE_CARD_ACTIONS__?.frontFrame(native,pawn.dataset.chessmanId)||
    frontFacingSource(native,bodyVisualId(pawn.dataset.chessmanId)).frame||frame;
   const sourceFoot=(frame.originY+frame.height);
   const standingFoot=(standing.originY+standing.height);
   const relativeSourceOffset=sourceFoot-standingFoot;
   img.style.setProperty('--leaf-obs-bottom',
    'calc(var(--leaf-obs-ground,14.88px) '+
      (relativeSourceOffset<0?'+':'-')+' '+Math.abs(relativeSourceOffset)+'px)');
   pawn.dataset.sourceFrameNativeOrigin=frame.originX+','+frame.originY;
   pawn.dataset.sourceFrameNativeSize=frame.width+'x'+frame.height;
   pawn.dataset.sourceFootOffset=String(relativeSourceOffset);
   pawn.dataset.sourceGrounding='inferred-shared-foot-plane/native-relative-frames';
   pawn.dataset.actorFrame=String(frame.index);
 }
 function useOriginalFrame(pawn,id,action){
   const previous=sourceTimers.get(pawn);
   if(previous)clearInterval(previous);
   sourceTimers.delete(pawn);
   // If an on-demand full-source asset is not cached offline, keep using
   // the already shipped original partial OBS sprites rather than dropping
   // the player's full-body Genesis chessman to a card.
   const native=originalFor(id);
   if(!native?.frames?.length||pawn.dataset.obsUnavailable==='true'){
     const previousImage=pawn.querySelector('img.leaf-chess-original-obs');
     if(previousImage)previousImage.hidden=true;
     return false;
   }
   let img=pawn.querySelector('img.leaf-chess-original-obs');
   if(!img){
     img=document.createElement('img');img.className='leaf-chess-original-obs';
     img.alt='';img.draggable=false;img.setAttribute('aria-hidden','true');
     // A sleeping/offline source host can reject a real OBS PNG once.
     // Do NOT permanently replace a recovered Genesis full-body with a card
     // simply because its first network request failed. Retry ONLY the same
     // original source URL; never synthesize a body or an action frame.
     img.addEventListener('load',()=>{
       img.dataset.obsRetryCount='0';
       delete img.dataset.obsRetryFor;
       if(['/original/OBS/action-full/','/original/OBS/action-full-ext/'].some(dir=>
         (img.getAttribute('src')||'').includes(dir)))
        delete pawn.dataset.fullFrameErrors;
       img.hidden=false;
       pawn.dataset.actorSourceLoad=pawn.dataset.sourceFullUnavailable==='true'
        ?'ready-legacy-original-OBS': 'ready';
     });
     img.addEventListener('error',()=>{
       if(!pawn.isConnected)return;
       const source=String(img.getAttribute('src')||'').split('?')[0];
       if(!source.startsWith('./original/OBS/')||!source.endsWith('.png')){
         pawn.dataset.obsUnavailable='true';
         pawn.dataset.actorOriginalModelRecovered='false';
         pawn.dataset.actorSourceLoad='unavailable';
         renderFrame(pawn,pawn.dataset.chessmanId,pawn.dataset.actorPose||'idle');
         return;
       }
       // Looping idle changes source URL before per-file retries finish.
       const fullErrors=(source.startsWith('./original/OBS/action-full/')||
         source.startsWith('./original/OBS/action-full-ext/'))
        ?Number(pawn.dataset.fullFrameErrors||0)+1:0;
       if(fullErrors)pawn.dataset.fullFrameErrors=String(fullErrors);
       const attempt=fullErrors>3?4:img.dataset.obsRetryFor===source?
         Number(img.dataset.obsRetryCount||0)+1:1;
       img.dataset.obsRetryFor=source;
       img.dataset.obsRetryCount=String(attempt);
       if(attempt<=3){
         const member=pawn.dataset.chessmanId;
         pawn.dataset.actorSourceLoad='retrying-original-OBS';
         img.hidden=true;
         setTimeout(()=>{
           if(!pawn.isConnected||!img.isConnected||
             pawn.dataset.chessmanId!==member||pawn.dataset.obsUnavailable==='true')return;
           if(String(img.getAttribute('src')||'').split('?')[0]!==source)return;
           img.src=source+'?native_obs_retry='+attempt+'&at='+Date.now();
         },Math.min(750,120*2**(attempt-1)));
         return;
       }
       // The 1,665 new full-frame source PNGs are loaded on demand.
       // If one is not cached offline (or a CDN fetch repeatedly fails),
       // retain the earlier source-verified bulk/front-reviewed OBS packets.
       // Do not generate fake pixels or retry a missing full file forever.
       const id=pawn.dataset.chessmanId;
       const legacy=null /* never show another card-number-matched actor */;
       if((source.startsWith('./original/OBS/action-full/')||
            source.startsWith('./original/OBS/action-full-ext/'))&&
          pawn.dataset.sourceFullUnavailable!=='true'&&
          legacy?.frames?.length){
         pawn.dataset.sourceFullUnavailable='true';
         delete pawn.dataset.fullFrameErrors;
         pawn.dataset.actorSourceLoad='falling-back-to-legacy-original-OBS';
         delete img.dataset.obsRetryCount;
         delete img.dataset.obsRetryFor;
         renderFrame(pawn,id,pawn.dataset.actorPose||'idle');
         return;
       }
       pawn.dataset.obsUnavailable='true';
       pawn.dataset.actorOriginalModelRecovered='false';
       pawn.dataset.actorSourceLoad='unavailable';
       renderFrame(pawn,id,pawn.dataset.actorPose||'idle');
     });
     pawn.append(img);
   }
   const fallback=pawn.querySelector('.leaf-chess-original-card-fallback');
   if(fallback)fallback.hidden=true;
   delete pawn.dataset.originalObsMemberRole;
   pawn.dataset.actorRig='original-obs-sprite';
   pawn.dataset.actorSource='Original-CHR-body/'+native.originalMember;
   pawn.dataset.actorOriginalModelRecovered='true';
   pawn.dataset.sourceAnimation='genuine-OBS-pixels';
   const auditedMovement=REVIEWED_FRONT_MOTION[bodyVisualId(id)]||null;
   pawn.dataset.sourceFrontWalkVerified=String(Boolean(auditedMovement&&
    auditedMovement.every(index=>native.frames.some(f=>f.index===index))));
   pawn.dataset.sourceWalkCoverage=pawn.dataset.sourceFrontWalkVerified==='true'
    ?'front-pair-25-30/source-verified/WEB-action-unverified'
    :Object.hasOwn(AUDITED_FRONT_SOURCE,bodyVisualId(id))
     ?'front-only/source-verified/WEB-action-unverified'
     :Array.from({length:8},(_,i)=>i)
      .every(index=>native.frames.some(frame=>frame.index===index))
       ?'8-of-8-original-source-indices/WEB-action-unverified'
       :'partial-original-source/static-walk-until-source-complete';
   pawn.dataset.sourcePoseMapping=native.frames.length===1||native.singleFrameStillOnly===true
     ?'unverified-single-source-frame/static-no-animation'
     :native.hasVerifiedFrameZero===false
      ?'unverified-frame-zero-missing/static-source-pose':'unverified';
   img.hidden=false;
   const sourceNativeFront=window.__LEAF_NATIVE_CARD_ACTIONS__?.frontFrame(native,id);
   const facing=sourceNativeFront?{frame:sourceNativeFront,evidence:'CHR-native-front-keys/role-INFERRED'}:
    frontFacingSource(native,bodyVisualId(id));
   pawn.dataset.sourceFacingFrame=facing.frame?String(facing.frame.index):'none';
   pawn.dataset.sourceFacingEvidence=facing.evidence;
   pawn.dataset.sourceDirection='front-source-candidate/not-EXE-direction-table';
   const travel=action==='walk'?(pawn.dataset.travelFacing||'toward'):'toward';
   const duel=pawn.classList.contains('leaf-battle-chessman');
   const duelSide=pawn.dataset.duelSide||
    (pawn.closest('.battle-visual-side')?.classList.contains('attacker')?'attacker':'defender');
   const context={duel,side:duelSide,rest:pawn.dataset.travelFacing||'toward'};
   const nativeSeq=window.__LEAF_NATIVE_CARD_ACTIONS__?.sequenceFor(native,id,action,travel,context);
   const seq=nativeSeq||sequenceFor(native,action,bodyVisualId(id),travel,context);
   pawn.dataset.sourceMirror=seq.mirror?'true':'false';
   pawn.dataset.sourceActionTable=nativeSeq
    ?seq.table+'/original-index-VERIFIED/action-label-INFERRED'
    :seq.table?seq.table+'/structural-37/INFERRED':'legacy';
   pawn.dataset.sourceNativeKeyTicks=nativeSeq?seq.nativeKeyTicks.join(','):'';
   pawn.dataset.sourceKeyframeProvenance=nativeSeq?seq.nativeEvidence:'WEB-structural-guess';
   pawn.dataset.sourceNativeMilliseconds=nativeSeq?seq.nativeMilliseconds:'';
   pawn.dataset.sourceNativeEffects=nativeSeq?seq.nativeEffects:'';
   pawn.dataset.actorWalkFacing=action==='walk'?travel:'';
   pawn.dataset.sourceTravelFacing=action==='walk'&&travel==='left'&&
     seq.length&&seq[0].index===LEFT_PROFILE_WALK_INDICES[0]
    ?'left-profile-14-17/visual-reviewed/WEB-direction-timing-INFERRED'
    :action==='walk'&&travel==='away'&&
      seq.length&&seq[0].index===BACK_WALK_INDICES[0]
     ?'rear-walk-3-7/visual-reviewed/INFERRED'
     :action==='walk'?'front/INFERRED':'n/a';
   pawn.dataset.sourceAttackEvidence=action==='attack'&&FULL_SOURCE_ATTACK.has(id)&&
     seq.length===FULL_SOURCE_ATTACK_INDICES.length&&seq[1].index===31
    ?'original-full-attack-31-33-35/visual-reviewed/WEB-action-FPS-INFERRED'
    :action==='attack'&&REVIEWED_FRONT_ATTACK.has(id)
     ?'front-three-quarter-18/visual-reviewed/INFERRED':'n/a';
   if(action==='walk'&&travel==='left'&&seq.length===4&&seq[0].index===14)
    pawn.dataset.sourceDirection='left-profile-source-14-17/2002-EXE-direction-unverified';
   if(seq.table&&!nativeSeq){
    if(action==='walk')pawn.dataset.sourceTravelFacing=seq.table+(seq.mirror?'-mirrored':'')+'/structural-37/INFERRED';
    if(action==='attack')pawn.dataset.sourceAttackEvidence=seq.table+(seq.mirror?'-mirrored':'')+'/structural-37/INFERRED';
    if(action==='idle')pawn.dataset.sourceIdleFacing=seq.table+(seq.mirror?'-mirrored':'')+'/structural-37/INFERRED';
    if(action==='hurt'||action==='victory')pawn.dataset.sourceOutcomeEvidence=seq.table+'/no-source-'+action+'-frame/UNVERIFIED';
    pawn.dataset.sourceDirection=(seq.table.split('-')[1]||'front')+(seq.mirror?'-mirrored':'')+'/structural-37/EXE-table-unverified';
   }
   if(nativeSeq){
    pawn.dataset.sourceDirection=seq.table+'/source-index-VERIFIED/semantic-role-INFERRED';
    if(action==='walk')pawn.dataset.sourceTravelFacing=pawn.dataset.sourceDirection;
    if(action==='idle')pawn.dataset.sourceIdleFacing=pawn.dataset.sourceDirection;
    pawn.dataset.sourceFrontWalkVerified=String(action==='walk'&&seq.length>1);
    pawn.dataset.sourceWalkCoverage='native-CHR-OBS-indices/2002-ms-UNVERIFIED';
    if(action==='attack')pawn.dataset.sourceAttackEvidence=seq.table+(seq.mirror?'-mirrored':'')+'/'+seq.nativeEvidence;
    if(action==='hurt'||action==='victory')pawn.dataset.sourceOutcomeEvidence=seq.table+'/'+seq.nativeEvidence;
    pawn.dataset.sourceNativeSlot=seq.nativeSlot||'';
   }
   // Original one-shot length (exact tick span x WEB tick ms) so a pose
   // timer never cuts an original animation short. ms mapping UNVERIFIED.
   pawn.dataset.sourceNativeDurationMs=nativeSeq&&Number.isFinite(seq.nativeDurationMs)
    ?String(seq.nativeDurationMs):'';
   // Expose EXACT SOURCE packet indexes independently from inferred labels;
   // QA can inspect what was really rendered during genuine gameplay.
   pawn.dataset.sourceFrameSequence=seq.map(frame=>frame.index).join(',');
   pawn.dataset.sourceFrontCycleCoverage=REVIEWED_FRONT_MOTION[bodyVisualId(id)]&&
     [25,26,27,28,29,30].every(index=>native.frames.some(f=>f.index===index))
       ?'six-original-pixel-frames/WEB-walk-timing-inferred'
       :'partial-2002-source-front-cycle';
   pawn.dataset.sourceActionEvidence=Object.hasOwn(AUDITED_FRONT_SOURCE,bodyVisualId(id))
    ?(pawn.dataset.sourceFrontWalkVerified==='true'
       ?'front-source-pair/visual-reviewed; WEB-movement-and-FPS-inferred'
       :'front-source-static/visual-reviewed; native-action-table-unknown')
    :'source-packets/orientation-and-2002-action-unverified';
   pawn.dataset.sourceFrameSequenceProvenance=nativeSeq?seq.nativeEvidence:'original-OBS-indexes/WEB-action-timing-unverified';
   renderNativeFrame(pawn,seq[0]);
   const sourceSheet=pawn.querySelector('.leaf-chess-source-frame');
   if(sourceSheet)sourceSheet.hidden=true;
   // Idle and contiguous walking cycles repeat; attacks, impacts and
   // victory are ONE-SHOT events. Repeating their provisional [10,18] etc.
   // forever made a struck character oscillate between attack/hurt frames
   // while no actual new gameplay action had occurred. Original OBS bytes
   // remain untouched; action-to-source-index/FPS remains UNVERIFIED.
   const loops=action==='walk'||seq.loop===true;
   pawn.dataset.sourcePlaybackMode=nativeSeq
    ?(loops?'loop':'one-shot')+'/OBS-source-index-VERIFIED/WEB-ms-INFERRED'
    :loops?'loop/WEB-motion-inferred':'one-shot/WEB-action-unverified';
   pawn.dataset.sourcePlaybackComplete='false';
   if(seq.length>1&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){
     let i=0;
     // Original tick tables are played against the clock so a busy main
     // thread drops steps instead of stretching the original tick span.
     const clocked=Number.isFinite(seq.intervalMs),t0=performance.now();
     const timer=setInterval(()=>{
       if(!pawn.isConnected||pawn.dataset.chessmanId!==id||pawn.dataset.actorPose!==action){
         clearInterval(timer);sourceTimers.delete(pawn);return;
       }
       const next=clocked?Math.floor((performance.now()-t0)/seq.intervalMs):i+1;
       if(next===i)return;
       i=loops&&clocked?next%seq.length:next;
       if(i>=seq.length){
         if(!loops){
           if(clocked)renderNativeFrame(pawn,seq[seq.length-1]);
           clearInterval(timer);sourceTimers.delete(pawn);
           pawn.dataset.sourcePlaybackComplete='true';
           return;
         }
         i=0;
       }
       renderNativeFrame(pawn,seq[i]);
     },Number.isFinite(seq.intervalMs)?seq.intervalMs:action==='idle'?340:action==='walk'?120:175);
     sourceTimers.set(pawn,timer);
   }else if(!loops){
     pawn.dataset.sourcePlaybackComplete='true';
   }
   return true;
 }

 const sourceId=p=>String(p?.team?.[0]||'').replace(/^c_/,'');
 function add(parent,name){
  const n=document.createElement('span');n.className=name;
  n.setAttribute('aria-hidden','true');parent.append(n);return n;
 }
 function createRig(pawn){
  const a=add(pawn,'leaf-chess-actor');
  add(a,'leaf-chess-cape');add(a,'leaf-chess-torso');
  const head=add(a,'leaf-chess-head');
  const image=document.createElement('img');
  image.className='leaf-chess-portrait';image.alt='';image.draggable=false;head.append(image);
  add(a,'leaf-chess-arm leaf-chess-left');add(a,'leaf-chess-arm leaf-chess-right');
  add(a,'leaf-chess-leg leaf-chess-left');add(a,'leaf-chess-leg leaf-chess-right');
  add(a,'leaf-chess-weapon');add(a,'leaf-chess-contact');
  const sheet=add(a,'leaf-chess-source-frame');sheet.hidden=true;
  return a;
 }
 function renderFrame(node,src,action){
  if(useOriginalFrame(node,src,action))return;
  const sheet=node.querySelector('.leaf-chess-source-frame');
  if(!sheet)return;
  const f=frames.get(src)?.[action];
  if(f){
   sheet.hidden=false;
   sheet.style.backgroundImage='url("'+f.url+'")';
   sheet.style.backgroundSize=f.width*f.count+'px '+f.height+'px';
   sheet.style.width=f.width+'px';sheet.style.height=f.height+'px';
   sheet.style.setProperty('--leaf-frame-size',f.width+'px');
   sheet.style.setProperty('--leaf-frame-count',String(f.count));
   sheet.style.setProperty('--leaf-frames-duration',f.duration+'ms');
   node.dataset.actorRig='source-animation';
   node.dataset.sourceAnimation=action;
  }else{
   sheet.hidden=true;
   // A temporary source-loading outage must NOT resurrect an unrelated
   // CardData/chm_N facial guess. Retain the card's own verified CHR art
   // when available and fall back to genuine IMG/avatarback if its pixels
   // are unreachable. Never substitute a Registry avatar or another actor.
   let portrait=node.querySelector('.leaf-chess-original-card-fallback');
   if(!portrait){
    portrait=document.createElement('img');
    portrait.className='leaf-chess-original-card-fallback';
    portrait.alt='';portrait.draggable=false;
    portrait.setAttribute('aria-hidden','true');
    node.append(portrait);
   }
   const source=node.querySelector('.leaf-chess-portrait')?.getAttribute('src');
   const cardback='./original/IMG/avatarback.png';
   const image=source&&
    (source.startsWith('./original/OBS/')||source===cardback)
     ?source:cardback;
   portrait.onerror=()=>{
    portrait.onerror=null;
    // The same original CHR member may be unavailable for the main actor
    // and for its smaller thumbnail. A second 404 is not an infinite retry.
    if(portrait.getAttribute('src')!==cardback){
     portrait.src=cardback;
     portrait.dataset.artEvidence='source-CHR-fetch-failed/IMG-cardback';
     node.dataset.actorFallbackArt='IMG/avatarback/source-outage';
    }
   };
   portrait.dataset.artEvidence=image===cardback
    ?'IMG-cardback/no-verified-source':'CHR-own-source-body';
   node.dataset.actorFallbackArt=image===cardback?'IMG/avatarback':'CHR/own-body';
   if(portrait.getAttribute('src')!==image)portrait.src=image;
   portrait.hidden=false;
   node.dataset.actorRig='original-card-portrait-fallback';
   node.dataset.actorSource=image===cardback?'Original-IMG/cardback-fallback':'Original-CHR/own-body-fallback';
   node.dataset.actorOriginalModelRecovered='false';
   node.dataset.sourceAnimation='unavailable';
   node.dataset.sourcePoseMapping=Object.hasOwn(NON_ACTOR_OBS,src)
    ?'OBS-member-is-non-character-effect/original-IMG-fallback'
    :'source-OBS-unavailable/own-CHR-or-IMG-cardback';
   node.dataset.originalObsMemberRole='CHR-original-body-unpublished-or-unavailable';
  }
 }
 function pose(pawn,requested='idle',duration=0){
  if(!pawn)return;
  const action=VALID.includes(requested)?requested:'idle';
  // A real roll advances its pawn every ~60ms. If each step restarts the
  // 120ms native-source frame clock, gameplay can NEVER show frame 2..7
  // although manual QA plays all eight. Continue the SAME source walk
  // across successive DMP cell transitions; keep the original OBS pixels.
  const continueSourceWalk=action==='walk'&&pawn.dataset.actorPose==='walk'&&
   pawn.dataset.actorRig==='original-obs-sprite'&&
   (pawn.dataset.sourceFrontWalkVerified==='true'||
    pawn.dataset.sourceWalkCoverage?.startsWith('8-of-8-'))&&
   // A turn from front to rear (or back) must switch frame sets at once.
   (pawn.dataset.actorWalkFacing||'toward')===(pawn.dataset.travelFacing||'toward');
  clearTimeout(timeouts.get(pawn));
  if(!continueSourceWalk){
   pawn.dataset.actorPose=action;
   const counts=states.get(pawn)||{};
   states.set(pawn,{...counts,[action]:(counts[action]||0)+1});
   renderFrame(pawn,pawn.dataset.chessmanId,action);
  }
  // A genuine slot-12 attack already begins after the original dice land.
  // Propagate its documented CHR source event to the independent OBS effect
  // sprite renderer without touching damage/turn calculations or pose clock.
  if(action==='attack'&&pawn.closest?.('#battle-visual')&&
     typeof CustomEvent==='function')
   pawn.dispatchEvent(new CustomEvent('leaf-native-duel-attack',{
    bubbles:true,detail:{card:pawn.dataset.chessmanId,
     slot:pawn.dataset.sourceNativeSlot||''}
   }));
  pawn.dataset.walkSourceClock=continueSourceWalk
   ?'continuous-across-real-DMP-steps/WEB-120ms':
    action==='walk'?'new-source-sequence/WEB-120ms':'inactive';
  if(duration>0&&action!=='idle'){
   const nativeMs=Number(pawn.dataset.sourceNativeDurationMs)||0;
   // +150ms: the duel outcome timer (game.js, same span) must win the race
   // so the attacker goes lunge -> hurt/victory, never lunge -> idle -> outcome.
   if(nativeMs+150>duration)duration=nativeMs+150;
   const token=setTimeout(()=>{
    if(pawn.isConnected&&pawn.dataset.actorPose===action)pose(pawn,'idle',0);
   },duration);
   timeouts.set(pawn,token);
  }
 }
 function mount(pawn,player,portrait){
  if(!pawn||!player)return null;
  const src=sourceId(player);
  let rig=pawn.querySelector('.leaf-chess-actor');
  if(!rig)rig=createRig(pawn);
  const image=rig.querySelector('img.leaf-chess-portrait');
  if(pawn.dataset.chessmanId!==src||!image.getAttribute('src')){
   pawn.dataset.chessmanId=src;
   delete pawn.dataset.obsUnavailable;
   // Errors from another actor must never force the new source to legacy.
   delete pawn.dataset.sourceFullUnavailable;
   const previousSourceImage=pawn.querySelector('img.leaf-chess-original-obs');
   if(previousSourceImage){
    previousSourceImage.dataset.obsRetryCount='0';
    delete previousSourceImage.dataset.obsRetryFor;
   }
   pawn.dataset.actorSource=originalFor(src)?'OBS/'+originalFor(src).originalMember:'CardData';
   pawn.dataset.actorOriginalModelRecovered=String(!!originalFor(src));
   const num=Number(src.replace(/\D/g,''))||0;
   pawn.style.setProperty('--chess-armor-hue',String((num*19)%360)+'deg');
   image.src=portrait;
   image.onerror=()=>{image.hidden=true};
   image.onload=()=>{image.hidden=false};
   pose(pawn,'idle',0);
  }
  return rig;
 }
 function poseByPlayer(id,action,duration){
  // Both native game-board and duel podium render independently mounted OBS
  // actors. Propagate one *real player* action to both renderers, never to an
  // opponent or a keeper without an original Genesis identity.
  for(const pawn of document.querySelectorAll(
    '#board-pawns .board-pawn, #battle-visual .leaf-battle-chessman')){
    if(pawn.dataset.id===String(id))pose(pawn,action,duration);
  }
 }
 function registerFrames(chessmanId,poses){
  if(!/^\d{4}$/.test(chessmanId))throw new Error('Source chessman ID required');
  const entries={};
  for(const action of VALID){
   const p=poses?.[action];
   if(!p)continue;
   if(typeof p.url!=='string'||!/^\.\/original\//.test(p.url)||
     ![p.width,p.height,p.count,p.duration].every(Number.isFinite)||
     p.width<=0||p.height<=0||p.count<1||p.duration<=0)
    throw new Error('Invalid recovered chessman animation sheet');
   entries[action]={url:p.url,width:p.width,height:p.height,
    count:p.count,duration:p.duration};
  }
  frames.set(chessmanId,entries);
  // Late-loaded verified source sheets must replace already visible web
  // proxies immediately, on the game board AND the battle podium.
  for(const pawn of document.querySelectorAll(
    '#board-pawns .board-pawn, #battle-visual .leaf-battle-chessman')){
    if(pawn.dataset.chessmanId!==chessmanId)continue;
    renderFrame(pawn,chessmanId,pawn.dataset.actorPose||'idle');
    pawn.dataset.actorOriginalAnimationRegistered=String(Boolean(Object.keys(entries).length));
  }
 }
 // After reconnection retry both missing original images and full 37-frame
 // originals that temporarily downgraded to real, older OBS sprite pixels.
 // Never fabricate recovered full bodies for source-missing card members.
 const recoverAvailableOriginals=()=>{
   for(const pawn of document.querySelectorAll(
     '#board-pawns .board-pawn, #battle-visual .leaf-battle-chessman')){
     const unavailable=pawn.dataset.obsUnavailable==='true';
     const downgraded=pawn.dataset.sourceFullUnavailable==='true';
     if((!unavailable&&!downgraded)||!originalFor(pawn.dataset.chessmanId))continue;
     delete pawn.dataset.obsUnavailable;
     delete pawn.dataset.sourceFullUnavailable;
     const img=pawn.querySelector('img.leaf-chess-original-obs');
     if(img){img.dataset.obsRetryCount='0';delete img.dataset.obsRetryFor;}
     pawn.dataset.actorSourceLoad='retry-after-online';
     renderFrame(pawn,pawn.dataset.chessmanId,pawn.dataset.actorPose||'idle');
   }
 };
 window.addEventListener('online',recoverAvailableOriginals);
 window.__LEAF_GENESIS_ACTORS__={
  mount,pose,poseByPlayer,registerFrames,recoverAvailableOriginals,
  getState:()=>({
   originalFullBodyFramesRecovered:Object.keys(window.__LEAF_CHR_BODY_MAP__?.cards||{}).filter(id=>!!originalFor(id)),
   chrSourceMapping:window.__LEAF_CHR_BODY_MAP__?.getState()||null,
   nativeActionMapping:window.__LEAF_NATIVE_CARD_ACTIONS__?.getState()||null,
   nativeObsEffectMembers:{...NON_ACTOR_OBS},
   originalFrontVisualAudited:{...AUDITED_FRONT_SOURCE},
   reviewedBackWalk:[...REVIEWED_BACK_WALK],
   reviewedFrontAttack:[...REVIEWED_FRONT_ATTACK],
   rendered:[...document.querySelectorAll('#board-pawns .board-pawn')].map(p=>({
    playerId:p.dataset.id,chessmanId:p.dataset.chessmanId,
    pose:p.dataset.actorPose,rig:p.dataset.actorRig,
    originalRecovered:p.dataset.actorOriginalModelRecovered,
    source:p.dataset.actorSource,frame:p.dataset.actorFrame,
    poseMapping:p.dataset.sourcePoseMapping,sourceLoad:p.dataset.actorSourceLoad||'unknown',
    counts:states.get(p)||{}
   }))
  })
 };
})();
