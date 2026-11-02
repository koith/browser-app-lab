'use strict';
/* Source-native 3-direction animation frames decoded from 18-byte OBS records.
 * PIXEL INDEX and relative 3-tick key positions VERIFIED; action names and
 * real tick -> milliseconds mapping INFERRED/UNVERIFIED. No effects played. */
(function(){
 const alphabet='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
 const raw="0125=-/678/pqr/012345/9abcde/stuvwx\n0126=-/666666666786/pppppppppqrp/012345/9abcde/stuvwx\n0127=-/6666666666666666666789a6/xxxxxxxxxxxxxxxxxxxyzABx/01234/bcdefg/CDEFGH\n0128=-/678/tuv/012345/bcdefg/yzABCD\n0129=-/666666666666666666666789/tttttttttttttttttttttuvw/012345/abcdef/xyzABC\n0130=-/66789abcdefg/CCDEFGHIJKLM/012345/hijklm/NOPQRS\n0131=-/666666666666666666789aaa/yyyyyyyyyyyyyyyyyyzABCCC/012345/bcdefg/DEFGHI\n0132=-/6666666666666666666789ab/ssssssssssssssssssstuvwx/012345/cdefgh/yzABCD\n0133=-/6789ab/zABCDE/012345/cdefgh/FGHIJK\n0134=-/bbbbbbbbbbbbbbbb6789a98b/xxxxxxxxxxxxxxxyzABCBAzy/012345/cdefgh/DEFGHI\n0135=-/444444444444/rrrrrrrrrrrr/-/-/-\n0136=-/678/GHI/012345/defghi/NOPQRS\n0137=-/666666666666666666789ab6/wwwwwwwwwwwwwwwwwwxyzABw/012345/cdefgh/CDEFGH\n0139=-/6666666789abbbbbbbbb9876/ssssssstuvwxxxxxxxxxvuts/012345/cdefgh/yzABCD\n0140=-/6666666666666666666789ab/uuuuuuuuuuuuuuuuuuuvwxyz/012345/cdefgh/ABCDEF\n0141=-/666666789ab6/yyyyyyzABCDy/012345/cdefgh/EFGHIJ\n0142=-/666666789ab6/sssssstuvwxs/012345/cdefgh/yzABCD\n0143=-/666666666786/vvvvvvvvvwxv/012345/9abcde/yzABCD\n0144=-/666666666666678786/xxxxxxxxxxxxxyzyzx/012345/cdefgh/DEFGHI\n0145=-/456/jkl/012012/789789/mnomno\n0146=-/666666666666667897/wwwwwwwwwwwwwwxyzx/012345/abcdef/ABCDEF\n0147=-/789ab6/pqrstu/012345/cdefgh/vwxyzA\n0157=-/678/mno/012345/9abcde/pqrstu\n0158=012/bcd/mno/35678/efghij/pqrstu\n0160=-/7777777778999999999abbb/yyyyyyyyyzAAAAAAAABCCCC/0123456/cdefgh/DEFGHI\n0161=012345/hijklm/yzABCD/9abcde/qrstuv/HIJKLM\n0162=-/66/gg/012345/789abc/hijklm\n0163=-/6789ab/CDEFGH/012345/cdefgh/IJKLMN\n0164=012/bcd/mno/35678/efghij/pqrstu\n0165=-/6789ab/zABCDE/012345/cdefgh/FGHIJK\n0166=-/6789a/xyzAB/012345/bcdefg/CDEFGH\n0167=-/-/-/012345/9abcde/wxyzAB\n0168=-/66666666666666666789a987/tttttttttttttttttuvwxwvu/012345/bcdefg/yzABCD\n0169=-/abcd/0123/pqrstu/efghij/456789\n0170=-/6789ab/yzABCD/012345/cdefgh/EFGHIJ\n0171=-/666666666666666666666666789aaaaaaaaaaaaa987/xxxxxxxxxxxxxxxxxxxxxxxxyzABBBBBBBBBBBBBzyx/012345/bcdefg/CDEFGH";
 const source={};
 for(const line of raw.split('\n')){
  const [card,sections]=line.split('='),parts=sections?.split('/');
  if(!/^0[0-9]{3}$/.test(card)||parts?.length!==6||source[card])
   throw Error('Invalid source-native OBS2/3 map');
  source[card]=parts.map(p=>p==='-'?[]:[...p].map(ch=>{
   const n=alphabet.indexOf(ch);
   if(n<0)throw Error('Unknown native frame code');
   return n;
  }));
 }
 if(Object.keys(source).length!==36)throw Error('OBS2/3 published actor census must be 36');
 const classic=[[0,1,2],[11,12,13],[22,23,24],
  [3,5,6,7,8],[14,15,16,17,18,19],[25,26,27,28,29,30]];
 const lookup=card=>{
  const m=window.__LEAF_CHR_BODY_MAP__?.lookup(card);
  if(!m||!window.__LEAF_CHR_BODY_MAP__?.resolve(card))return null;
  return m.pak==='OBS'?classic:source[card]||null;
 };
 function frontFrame(native,card){
  const a=lookup(card),n=a?.[2]?.[0]??a?.[5]?.[0];
  return Number.isInteger(n)?native?.frames?.[n]||null:null;
 }
 function sequenceFor(native,card,action,travel,context={}){
  if(window.__LEAF_CHR_BODY_MAP__?.resolve(card)!==native||
     !['idle','walk'].includes(action))return null;
  const groups=lookup(card);
  if(!groups)return null;
  const dir=action==='walk'?travel:
   context.duel?'left':context.rest||'toward';
  const side=dir==='left'||dir==='right',rear=dir==='away';
  const orientation=rear?0:side?1:2;
  let indexes=groups[orientation+(action==='walk'?3:0)];
  let staticFallback=false;
  if(!indexes?.length){
   // Some OBS2/3 native idle groups have 0xFFFFFFFF duration with no
   // keyframes. Hold this SAME body's source motion or front reference.
   const fallback=groups[orientation+3]?.[0]??
    groups[2]?.[0]??groups[5]?.[0];
   if(!Number.isInteger(fallback))return null;
   indexes=[fallback];
   staticFallback=true;
  }
  if(indexes.some(i=>!native.frames[i]))return null;
  const result=indexes.map(i=>native.frames[i]);
  result.mirror=side&&(action==='walk'?dir==='right':
   context.duel?context.side==='attacker':dir==='right');
  // Round-10 original table proof: 0xFFFFFFFF + zero keys marks an
  // UNDEFINED action slot, not an infinite-loop instruction. A static
  // visible fallback is allowed, but must never claim native playback.
  result.loop=!staticFallback;
  result.nativeUndefinedSlot=staticFallback;
  result.nativeDefined=!staticFallback;
  result.table='native-CHR-'+action+'-'+(rear?'rear':side?'side':'front');
  result.nativeKeyTicks=indexes.map((_,i)=>i*3);
  result.nativeEvidence=staticFallback?
   'original-OBS-source-pixel/empty-group-static-INFERRED':
   'original-OBS-18-byte-keyframe-indices-VERIFIED/role-INFERRED';
  result.nativeMilliseconds='UNVERIFIED/WEB-timing-not-2002-original';
  result.nativeEffects='DISABLED/role-unverified';
  return result;
 }
 window.__LEAF_NATIVE_CARD_ACTIONS__=Object.freeze({
  lookup,frontFrame,sequenceFor,
  getState:()=>({classicBodies:42,obs23Bodies:36,
   nativeKeyIndicesVerified:true,originalTickMilliseconds:'UNVERIFIED',
   sourceEffectPlayback:false})
 });
})();
