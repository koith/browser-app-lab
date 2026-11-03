import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";

// Synthetic only. Production getMedia/adEvidence are extracted verbatim.
const html=readFileSync(new URL("./index.html",import.meta.url),"utf8");
function between(start,end){
  const a=html.indexOf(start),b=html.indexOf(end,a);
  assert.ok(a>=0&&b>a,"expected production source anchors");
  return html.slice(a,b);
}
const mediaSource=between("function getMedia(p){","// Bluesky label settings");
const adSource=between("const AD_PATTERNS=[","function matchesText(p)");
const context={
  posts:[],indexedCandidates:[],cloudMode:false,console,
  validUrl:value=>{
    try{const u=new URL(value);return u.protocol==="https:"?u.href:"";}
    catch{return "";}
  }
};
runInNewContext(mediaSource+"\n"+adSource+
  "\nglobalThis.testing={getMedia,adEvidence,updateAdScores,suspectedAd,fingerprint};",context);
const f=context.testing;
const alt="nimi.wiki 실시간 SNS 영상 랭킹 프로모션 티저";
const six=[
  "요즘 이런 영상 금방 묻히니까 랭킹에서 체크",
  "실시간으로 올라오는 클립 중에 반응 괜찮은 쪽",
  "지금 반응 올라오는 중이라 전체 흐름 찾는 사람 많을 듯",
  "짧게만 보고 넘어가기 아까운 쪽",
  "방금 뜬 영상인데 뒤쪽까지 보려는 사람 많을 듯",
  "방금 랭킹에 올라온 영상인데 뒤쪽 궁금한 사람 있을 듯"
];
const identities=[
  {did:"did:plc:kqwzwtujwjh5lmss6erzpaid",handle:"y2ujhh.bsky.social"},
  {did:"did:plc:uhvj2kaf4z3ovdyvzks3ui2v",handle:"gxzmcg.bsky.social"}
];
for(const a of identities){
  for(let i=0;i<50;i++){
    const source={
      record:{text:six[i%six]+"\n\n#섹블 #섹트",
              embed:{$type:"app.bsky.embed.video",alt}},
      embed:{$type:"app.bsky.embed.video#view",alt,
             playlist:"https://video.bsky.app/watch/example/playlist.m3u8",
             thumbnail:"https://video.bsky.app/watch/example/thumbnail.jpg"}
    };
    const media=f.getMedia(source);
    assert.equal(media[0].alt,alt,"video alt metadata must be retained");
    context.posts.push({
      id:"at://"+a.did+"/app.bsky.feed.post/test"+i,
      platform:"bluesky",text:source.record.text,media,authorDid:a.did,
      profileUrl:"https://bsky.app/profile/"+a.handle
    });
  }
}
const fallback=f.getMedia({
  embed:{$type:"app.bsky.embed.video#view",playlist:"https://video.bsky.app/watch/example/playlist.m3u8"},
  record:{embed:{$type:"app.bsky.embed.video",alt}}
});
assert.equal(fallback[0].alt,alt,"fallback original record alt must remain available");
const legitimate=[
  {text:"오늘 바다 파도 소리 영상을 기록했어요 #풍경",media:[{type:"video",alt:"일몰 때 해변 풍경"}]},
  {text:"프로모션 광고로 과장된 내용인지 검토한 비평입니다",media:[]},
  ...Array.from({length:6},(_,i)=>({
    text:"기록된 날씨 정말 맑았어요 #일상",media:[{type:"image",alt:"날씨 사진 "+i}]
  })),
  {text:"지역 축제 영상과 무료 참여 행사",media:[{type:"video",alt:"행사 아카이브"}]}
];
context.posts.push(...legitimate);
f.updateAdScores();
for(const p of context.posts.slice(0,100)){
  assert.ok(f.suspectedAd(p),"high repetition promotional video must be hidden");
  assert.ok(p.adEvidence.reasons.includes("미디어 설명 내 홍보·광고 표기"));
}
for(const p of legitimate){
  assert.equal(f.suspectedAd(p),false,
    "ordinary commentary and benign repeated media should not be blocked");
}
assert.equal(context.posts.filter(f.suspectedAd).length,100);
const withoutAlt={text:six[0]+"\n\n#섹블 #섹트",media:[]};
context.posts=[withoutAlt,...legitimate];
f.updateAdScores();
assert.equal(f.suspectedAd(withoutAlt),false,
  "one short hashtagged post must remain visible without ad evidence");
assert.ok(html.includes("return posts.filter(p=>matchesText(p)&&!suspectedAd(p))"));
assert.ok(html.includes('!p.restricted&&!suspectedAd(p)).map(p=>({'));
console.log("INTERSECTION_AD_FILTER_QA_PASS: 2 observed campaigns x50 filtered, alt retained, benign controls");
