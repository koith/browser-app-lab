"use strict";
function releaseGate(manifest,curriculum,lessons){
  if(!manifest||manifest.schemaVersion!=="1.0.0"||!Array.isArray(manifest.publishedDayIds)||typeof manifest.stage!=="string"||!Array.isArray(curriculum?.days)||curriculum.days.length!==120||!Array.isArray(lessons?.lessons))throw Error("출고 목록 또는 교재 형식 오류");
  const days=new Map(), byId=new Map(), byDay=new Map();
  for(let i=0;i<120;i++){const d=curriculum.days[i];if(d.day!==i+1||d.id!=="D"+String(i+1).padStart(3,"0"))throw Error("교육과정 ID 오류");days.set(d.id,d)}
  for(const l of lessons.lessons){if(!days.has(l.id)||days.get(l.id).day!==l.day||byId.has(l.id))throw Error("교재 ID 오류");byId.set(l.id,l)}
  const ids=manifest.publishedDayIds;
  if(new Set(ids).size!==ids.length||ids.some(id=>typeof id!=="string"||!days.has(id)))throw Error("잘못된 공개 ID");
  if(ids.length&&(manifest.stage==="development"||!manifest.releaseId||!manifest.contentRevision||!manifest.verifiedAt))throw Error("승인 정보가 불완전합니다");
  for(const id of ids){const l=byId.get(id);if(!l||!Array.isArray(l.words)||!Array.isArray(l.examples)||!l.examples.length||!Array.isArray(l.dialogue)||!l.dialogue.length||!Array.isArray(l.questions)||!l.questions.length||l.questions.some(q=>q.type!=="choice"||!Array.isArray(q.choices)||q.choices.filter(c=>c===q.answer).length!==1)||new Set(l.questions.map(q=>q.id)).size!==l.questions.length)throw Error("공개 교재 무결성 오류: "+id);byDay.set(l.day,l)}
  return {ids:new Set(ids),byDay,allowed:day=>byDay.has(day),lesson:day=>byDay.get(day)};
}

const approvedArtifactPaths={curriculum:"curriculum.json",lessons:"lessons.json",assessment:"content/assessments.json",audioManifest:"audio/manifest.json"};
async function verifyReleaseBytes(manifestText,raw){
 const parse=bytes=>JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));
 const manifest=parse(manifestText);
 if(!Array.isArray(manifest.publishedDayIds))throw Error("출고 목록 오류");
 if(manifest.publishedDayIds.length){
   if(!globalThis.crypto?.subtle)throw Error("해시 검증 불가");
   for(const [key,path] of Object.entries(approvedArtifactPaths)){
     const spec=manifest.artifactDigests?.[key], bytes=raw[path];
     if(spec?.path!==path||!/^[a-f0-9]{64}$/.test(spec.sha256)||!bytes)throw Error("승인 자료 누락: "+key);
     const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
     if(hash!==spec.sha256)throw Error("승인 자료 불일치: "+key);
     parse(bytes);
   }
 }
 const curriculum=parse(raw["curriculum.json"]),lessons=parse(raw["lessons.json"]);
 releaseGate(manifest,curriculum,lessons);
 return [curriculum,lessons,manifest];
}
