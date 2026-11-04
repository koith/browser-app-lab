/* Synthetic read-only trend QA. No SNS or TeraBox network calls. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {createRequire} from "node:module";
import {JSDOM} from "jsdom";
const DIR=path.dirname(new URL(import.meta.url).pathname);
const script=fs.readFileSync(path.join(DIR,"public_video_trends.js"),"utf8");
const {allVideos,derive,months,summarizeSources}=createRequire(import.meta.url)("./public_video_trends.js");
const NOW=Date.parse("2026-11-04T09:00:00Z");
const h=3600000;
const mk=(id,ago,platform="bluesky",extra={})=>({
 id,platform,profileUrl:platform==="bluesky"?"https://bsky.app/profile/qa.bsky.social":"https://mastodon.social/@qa",
 url:platform==="bluesky"?"https://bsky.app/profile/qa.bsky.social/post/"+id:"https://mastodon.social/@qa/"+id,
 author:"Synthetic public author",posted:new Date(NOW-ago*h).toISOString(),
 media:[{type:"video",thumb:"https://cdn.bsky.app/img/"+id+".jpg",url:"https://video.example.org/"+id+".mp4"}],
 engagement:{likes:5,replies:2},...extra
});
const good1=mk("a",1,"bluesky",{engagement:{likes:8,reposts:2}});
const midnight=mk("month-boundary",90,"bluesky",{
  posted:"2026-10-31T16:30:00Z"
});
assert.equal(allVideos({verified:[midnight]})[0].month,"2026-11",
  "Nov 1 at 01:30 KST must not be assigned to UTC October");
assert.deepEqual(months({verified:[midnight]},NOW),["2026-11"],
  "month picker groups by Korean calendar month");
const good2=mk("b",2,"bluesky",{engagement:null,
  media:[{type:"video",thumb:"https://cdn.bsky.app/img/b.jpg"},
         {type:"video",thumb:"https://cdn.bsky.app/img/b2.jpg"}]});
const old=mk("c",36);
const week=mk("d",150);
const month=mk("e",240);
const historical=mk("f",900);
const rows=[good1,good2,good1,old,week,month,historical,
  mk("unsafe",1,"bluesky",{restricted:true}),
  mk("labeled",1,"bluesky",{adultLabeled:true}),
  mk("candidate",1,"bluesky",{discoveryCandidate:true}),
  mk("ad",1,"bluesky",{adSuspected:true}),
  mk("no-video",1,"bluesky",{media:[{type:"image",url:"https://cdn.bsky.app/img/only.jpg"}]}),
  mk("bad-url",1,"bluesky",{url:"javascript:alert(1)"})
];
const snap={verified:rows,partial:true};
assert.equal(allVideos(snap).length,6,"dedupe repeated post and skip unsafe/unverified rows");
assert.deepEqual(derive(snap,{mode:"hot",nowMs:NOW}).map(x=>x.id),["a","b"],
  "recent 3h is filtered on publication time; missing reactions sort after measured");
assert.equal(derive(snap,{mode:"day",nowMs:NOW}).length,2);
assert.equal(derive(snap,{mode:"week",nowMs:NOW}).length,4);
assert.equal(derive(snap,{mode:"month",nowMs:NOW}).length,5);
assert.deepEqual(derive(snap,{mode:"latest",nowMs:NOW}).map(x=>x.id),["a","b","c","d","e","f"]);
assert.equal(derive(snap,{mode:"archive",month:"2026-10",nowMs:NOW}).length,2,
  "monthly archive is limited to actually loaded historical posts");
assert.deepEqual(months(snap,NOW),["2026-11","2026-10","2026-09"]);
assert.equal(derive(snap,{mode:"archive",month:"2025-01",nowMs:NOW}).length,0);
assert.equal(derive(snap,{mode:"day",nowMs:NOW})[1].measured,false);
assert.equal(derive(snap,{mode:"day",nowMs:NOW})[1].score,0,
  "do not present unknown engagement as genuine saving/view metrics");
const sameId=mk("a",1,"mastodon");
assert.equal(allVideos({verified:[good1,sameId]}).length,2,
  "different platforms must not collide on post ID");
const mixedSources={verified:[good1,good2,sameId,old]};
assert.deepEqual(summarizeSources(derive(mixedSources,{mode:"day",nowMs:NOW})),[
  {platform:"bluesky",count:2,measured:1},
  {platform:"mastodon",count:1,measured:1}
],"per-source number of posts and observed engagement coverage, not download counts");
assert.deepEqual(derive(mixedSources,{mode:"day",platform:"mastodon",nowMs:NOW}).map(x=>x.id),["a"]);
assert.deepEqual(derive(mixedSources,{mode:"day",platform:"reddit",nowMs:NOW}),[],
  "filter absent sources without inventing results");
const differentProfile=mk("a",1,"bluesky",{profileUrl:"https://bsky.app/profile/other.bsky.social"});
assert.equal(allVideos({verified:[good1,differentProfile]}).length,2,
  "same provider ID from another account is not a duplicate");
assert.equal(allVideos({verified:[mk("bad-thumb",1,"bluesky",{
  media:[{type:"video",thumb:"http://localhost:8000/private"}]})]})[0].thumb,"");

const html='<!doctype html><html lang="ko"><body><details id="videoTrends"><summary>영상 트렌드</summary>'+
 '<div><button data-video-mode="hot">3시간</button><button data-video-mode="day">24시간</button>'+
 '<button data-video-mode="week">7일</button><button data-video-mode="month">30일</button>'+
 '<button data-video-mode="latest">최신</button><button data-video-mode="archive">월별</button>'+
 '<select id="videoTrendMonth"></select><select id="videoTrendSource"></select></div><p id="videoTrendCount"></p><p id="videoTrendCoverage"></p>'+
 '<div id="videoTrendRows"></div><button id="videoTrendMore" hidden>더 보기</button></details></body></html>';
const dom=new JSDOM(html,{url:"https://koith.github.io/browser-app-lab/apps/demand-research/",
  runScripts:"outside-only"});
dom.window.Date.now=()=>NOW;
const many=Array.from({length:14},(_,i)=>mk("item"+i,1+i/10));
dom.window.INTERSECTION_publicVideoSnapshot=()=>({verified:[...rows,...many],partial:true});
dom.window.eval(script);
const doc=dom.window.document,$=id=>doc.getElementById(id);
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card").length,12);
assert.match($("videoTrendCount").textContent,/일부 미완료/);
assert.equal($("videoTrendMore").hidden,false);
assert.match($("videoTrendCoverage").textContent,/Bluesky/);
assert.equal($("videoTrendSource").querySelectorAll("option").length,2,
  "source dropdown includes all only and observed Bluesky; not absent sources");
assert.match($("videoTrendCoverage").textContent,/반응 제공/);
assert.equal($("videoTrendRows").firstChild.target,"_blank");
assert.equal($("videoTrendRows").firstChild.rel,"noopener noreferrer");
assert.match($("videoTrendRows").firstChild.textContent,/KST/,
  "video list timestamps must explicitly identify Korean local time");
$("videoTrendMore").click();
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card").length,16);
// The DOM source selector must filter both cards and count, not just a label.
dom.window.INTERSECTION_publicVideoSnapshot=()=>({verified:[...rows,...many,sameId],partial:true});
dom.window.dispatchEvent(new dom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal($("videoTrendSource").querySelectorAll("option").length,3);
$("videoTrendSource").value="mastodon";
$("videoTrendSource").dispatchEvent(new dom.window.Event("change"));
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card").length,1);
assert.match($("videoTrendCount").textContent,/1건/);
assert.match($("videoTrendCoverage").textContent,/Mastodon 1건/);
$("videoTrendSource").value="all";
$("videoTrendSource").dispatchEvent(new dom.window.Event("change"));
doc.querySelector('[data-video-mode="hot"]').click();
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card").length,12,
  "switch mode resets visible count");
doc.querySelector('[data-video-mode="archive"]').click();
assert.equal($("videoTrendMonth").hidden,false);
$("videoTrendMonth").value="2026-10";
$("videoTrendMonth").dispatchEvent(new dom.window.Event("change"));
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card").length,2);
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card")[0].href,
  "https://bsky.app/profile/qa.bsky.social/post/d","archive source original");
doc.querySelector('[data-video-mode="latest"]').click();
assert.equal($("videoTrendMonth").hidden,true);
const oldCount=$("videoTrendCount").textContent;
dom.window.INTERSECTION_publicVideoSnapshot=()=>({verified:[good1],partial:false});
dom.window.dispatchEvent(new dom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.notEqual($("videoTrendCount").textContent,oldCount,"fresh feed updates trend counts");
assert.equal($("videoTrendRows").querySelectorAll("a.video-trend-card").length,1);
dom.window.close();
const main=fs.readFileSync(path.join(DIR,"index.html"),"utf8");
assert.ok(main.includes('id="videoTrends"'));
assert.ok(main.includes('id="videoTrendCoverage"'));
assert.ok(main.includes('id="videoTrendSource"'));
assert.ok(main.includes("window.INTERSECTION_publicVideoSnapshot"));
assert.ok(main.includes('<script src="public_video_trends.js" defer></script>'));
assert.ok(main.indexOf('id="videoTrends"')<main.indexOf('id="feed"'));
assert.ok(!script.includes("localStorage")&&!script.includes("sessionStorage")&&!script.includes("download="));
console.log("PUBLIC_VIDEO_TRENDS_QA_PASS: hot/day/week/month/latest/archive source-linked cards, partial coverage, isolated public-only engagement, safe URLs and load-more");
