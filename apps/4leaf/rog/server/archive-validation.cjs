'use strict';
// Validate the ENTIRE authenticated chat archive before accepting any of it.
// A malformed record must never be silently filtered and later overwritten.
const PUBLIC_ROOM=/^leaf-public-(north|south)-([0-7])-([0-7])$/;
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
function validateArchive(archive,validDistrict){
 const bad=what=>{throw new Error('Invalid persisted ChatTown state: '+what)};
 if(!isObject(archive)||!Array.isArray(archive.rooms)||
  !Array.isArray(archive.history)||!Number.isSafeInteger(archive.sequence)||
  archive.sequence<0)bad('root shape or sequence');
 const ids=new Set();
 for(const r of archive.rooms){
  if(!isObject(r)||typeof r.id!=='string'||!r.id||r.id.length>128||
   !validDistrict(r.region,r.district)||typeof r.name!=='string'||!r.name.trim()||
   ![2,4,8,12].includes(r.capacity)||!Number.isInteger(r.background)||
   r.background<0||r.background>5||r.preset===true||PUBLIC_ROOM.test(r.id))
   bad('room record');
  if(ids.has(r.id))bad('duplicate room id');
  ids.add(r.id);
  if(r.ownerId!==undefined&&(typeof r.ownerId!=='string'||!r.ownerId))
   bad('room owner identity');
  if(r.ownerTokenHash!==undefined&&
   (typeof r.ownerTokenHash!=='string'||!/^[0-9a-f]{64}$/i.test(r.ownerTokenHash)))
   bad('room owner credential fingerprint');
  if(r.passwordHash!==undefined&&r.passwordHash!==''&&
   (typeof r.passwordHash!=='string'||!/^[0-9a-f]{64}$/i.test(r.passwordHash)||
    typeof r.passwordSalt!=='string'||!/^[0-9a-f]{32}$/i.test(r.passwordSalt)))
   bad('room password verifier');
 }
 // A token always names one actual guest identity, even when it appears
 // in multiple public rooms. Legacy archives without fingerprints remain valid.
 const sendersByToken=new Map();
 const histories=new Set();
 // ChatTown uses one global sequence across all rooms, including public ones.
 const globalSequences=new Set(),globalMessageIds=new Set();
 for(const pair of archive.history){
  if(!Array.isArray(pair)||pair.length!==2||
   typeof pair[0]!=='string'||!pair[0]||!Array.isArray(pair[1]))
   bad('history record');
  const [roomId,entries]=pair;
  const match=PUBLIC_ROOM.exec(roomId);
  if(!ids.has(roomId)&&!(
   match&&validDistrict(match[1],
    (match[1]==='north'?[
     '실버 호라이즌','화이트 크리스탈','퓨어 시티','샤이닝 브리즈','윈트리 아이스','스노우 폴','스위트 자스민','그린 에메랄드'
    ]:[
     '블루 사파이어','헤이즐리 웨이브','미쉘 에메랄드','엘핀 포레스트','아루아 코랄','블랙씨 아린','브라브 지피트','미스틱 머메이드'
    ])[Number(match[2])]))
  )bad('history for nonexistent room');
  if(histories.has(roomId))bad('duplicate history room');
  histories.add(roomId);
  // The server intentionally retains at most 200 messages per room.
  // Refuse a longer archive instead of losing records on startup.
  if(entries.length>200)bad('history exceeds retention limit');
  let last=0;
  const clientIds=new Set();
  for(const e of entries){
   if(!isObject(e)||typeof e.id!=='string'||!e.id||
    !Number.isSafeInteger(e.seq)||e.seq<=last||e.seq>archive.sequence||
    e.roomId!==roomId||typeof e.text!=='string'||
    typeof e.user!=='string'||typeof e.sender!=='string')
    bad('message record, room binding or sequence');
   if(e.senderTokenHash!==undefined){
    if(typeof e.senderTokenHash!=='string'||!/^[a-f0-9]{64}$/.test(e.senderTokenHash))
     bad('invalid message sender credential fingerprint');
    const priorSender=sendersByToken.get(e.senderTokenHash);
    if(priorSender!==undefined&&priorSender!==e.sender)
     bad('one sender credential maps to multiple identities');
    sendersByToken.set(e.senderTokenHash,e.sender);
   }
   if(globalMessageIds.has(e.id))bad('duplicate message id across rooms');
   globalMessageIds.add(e.id);
   if(globalSequences.has(e.seq))bad('duplicate global message sequence');
   globalSequences.add(e.seq);
   if(e.clientMessageId!==undefined){
    if(typeof e.clientMessageId!=='string'||!/^(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$/i.test(e.clientMessageId)||
     clientIds.has(e.clientMessageId.toLowerCase()))bad('duplicate or invalid client message id');
    clientIds.add(e.clientMessageId.toLowerCase());
   }
   last=e.seq;
  }
 }
 return archive;
}
module.exports={validateArchive};
