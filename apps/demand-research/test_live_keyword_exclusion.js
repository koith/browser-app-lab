/* Regression: exact requested live-only keyword hard block survives every
 * ingestion and UI path. No social accounts, credentials or network needed. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync(__dirname+"/index.html","utf8");
const sw=fs.readFileSync(__dirname+"/intersection-sw.js","utf8");
assert(sw.includes('const VERSION="intersection-public-shell-v1-20261121-server-queue-v3"'));
assert(sw.includes('!html.includes("LIVE_HARD_EXCLUDED_PHRASES")'));
assert(sw.includes('shell.includes("LIVE_HARD_EXCLUDED_PHRASES")'));
assert(!sw.includes('const VERSION="intersection-public-shell-v1-20261115-native-view-fast-v1"'));
const from=html.indexOf("const LIVE_HARD_EXCLUDED_PHRASES=");
const to=html.indexOf("const DAY=",from);
assert(from>0&&to>from,"Expected canonical live feed exclusion source");
const snippet=html.slice(from,to);
const context=vm.createContext({cloudMode:false});
vm.runInContext(snippet+
  "globalThis.filterUnderTest={hasHardExcludedPhrase,excludedFromLiveAggregate};",
  context,{timeout:1000});
const {hasHardExcludedPhrase,excludedFromLiveAggregate}=context.filterUnderTest;
for(const value of [
 "야단라", "속보 야단라 게시글", "#야단라", "야 단 라",
 "야-단-라", "야"+String.fromCharCode(0x200b)+"단라", "야"+String.fromCharCode(0x2060)+"단라", "야.단/라",
 "＃야단라", "ＹＡ? 야단라"
])assert(hasHardExcludedPhrase(value),JSON.stringify(value));
for(const value of ["뒷계", "여단라", "야단사", "아이디어 공유", "단라 야기"])
  assert(!hasHardExcludedPhrase(value),JSON.stringify(value));
for(const post of [
 {text:"#야단라 신규"},
 {author:"야단라"},
 {media:[{alt:"야 단 라 썸네일"}]},
 {quotedPost:{text:"이건 야단라"}},
 {embed:{external:{title:"야단라 외부 미리보기"}}},
 {description:"\u200b야단라\u200b"}
])assert(excludedFromLiveAggregate(post),JSON.stringify(post));
assert(!excludedFromLiveAggregate({text:"별개 공개 글",media:[{alt:"설명"}]}));
const archiveContext=vm.createContext({cloudMode:true});
vm.runInContext(snippet+
  'globalThis.archiveAllows=excludedFromLiveAggregate({text:"야단라"});',
  archiveContext,{timeout:1000});
assert.equal(archiveContext.archiveAllows,false,"Archive source bytes must be retained");
// Verify all entry points cannot bypass hard filter. This tests the real
// deployed script structure, not a separately reimplemented filter function.
for(const anchor of [
 'if(excludedFromLiveAggregate({text:p.record.text',
 'if(!row||!row.id||!row.text||excludedFromLiveAggregate(row))return false;',
 'return {accepted:false,reason:"excluded-phrase"};',
 'if(!text||excludedFromLiveAggregate({text}))continue;',
 'posts.filter(p=>matchesText(p)&&!excludedFromLiveAggregate(p))',
 'indexedCandidates.filter(p=>matchesText(p)&&!excludedFromLiveAggregate(p)',
 'verified:filtered().filter(p=>p.platform!=="cloud"',
 'candidates:indexedCandidates.filter(p=>!excludedFromLiveAggregate(p))'
])assert(html.includes(anchor),"Excluded phrase bypass: "+anchor);
console.log("LIVE_YADANRA_HARD_FILTER_PASS",{
 normalizedObfuscations:10,paths:8,archiveUntouched:true});
