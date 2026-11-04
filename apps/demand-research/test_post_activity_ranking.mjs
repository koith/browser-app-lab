/* Isolated browser and pure-unit QA; never fetches live SNS content. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { JSDOM } from "jsdom";

const dir=path.dirname(new URL(import.meta.url).pathname);
const script=fs.readFileSync(path.join(dir,"post_activity_ranking.js"),"utf8");
const {compute,cohortOf}=createRequire(import.meta.url)("./post_activity_ranking.js");
const DAY=86400000,from=Date.parse("2026-11-01T00:00:00Z"),to=from+7*DAY;
const row=(id,profileUrl,engagement,platform="bluesky",author="테스트 계정",day=1,thumbnailUrl="")=>({
  id,profileUrl,engagement,platform,author,thumbnailUrl,
  posted:new Date(from+day*DAY).toISOString()
});
const fixture={
 fromMs:from,toMs:to,partial:false,
 verified:[
  row("b1","https://bsky.app/profile/alpha.bsky.social",
    {likes:10,reposts:2,replies:3},"bluesky","테스트 계정",1,"https://cdn.bsky.app/img/old.jpg"),
  row("b2","https://bsky.app/profile/alpha.bsky.social",
    {likes:30,reposts:1,replies:1},"bluesky","Alpha",2,"https://cdn.bsky.app/img/new.jpg"),
  row("b2","https://bsky.app/profile/alpha.bsky.social",
    {likes:30,reposts:1,replies:1},"bluesky","Alpha",2,"https://cdn.bsky.app/img/new.jpg"),
  row("b3","https://bsky.app/profile/bravo.bsky.social",{likes:3},"bluesky","Bravo",3),
  row("r1","https://www.reddit.com/user/alpha/",{likes:100,replies:9},"reddit","Alpha"),
  row("x1","https://x.com/alpha",undefined,"x","Alpha",4,"javascript:alert(1)"),
  row("evil","javascript:alert(1)",{likes:999}),
  row("private","https://127.0.0.1/profile/x",{likes:888},"mastodon"),
  row("outside","https://bsky.app/profile/outside.bsky.social",{likes:500},"bluesky","Outside",10),
 ]
};
fixture.verified[1].avatarUrl="https://cdn.bsky.app/img/profile-avatar.jpg";
fixture.verified[3].avatarUrl="https://cdn.bsky.app/img/bravo-avatar.jpg";
const rank=compute(fixture);
assert.equal(rank.length,4,"only valid dated public accounts");
assert.equal(rank[0].platform,"reddit");
const b=rank.find(x=>x.profileUrl.endsWith("alpha.bsky.social"));
assert.equal(b.posts,2,"same post ID counted once");
assert.equal(b.activeDays,2);
assert.equal(b.reactions,47);
assert.equal(b.measuredPosts,2);
assert.equal(b.score,4+6+Math.round(6*Math.log2(48)));
assert.equal(b.latestThumbnail,"https://cdn.bsky.app/img/new.jpg","latest post thumbnail");
assert.equal(b.latestAvatar,"https://cdn.bsky.app/img/profile-avatar.jpg",
  "retain verified public account avatar fallback");
assert.equal(b.latestPosted,new Date(from+2*DAY).toISOString());
assert.equal(rank.find(x=>x.platform==="x").latestThumbnail,"","unsafe thumbnails dropped");
assert.equal(rank.find(x=>x.platform==="x").engagementAvailable,false);
assert.equal(rank.find(x=>x.platform==="x").reactions,0);
assert.deepEqual(compute(fixture),compute(fixture),"rank deterministic");
// Federated Mastodon / Misskey post IDs can be scoped to their instance.
// Repeated IDs belonging to distinct account profiles must not erase a user.
const localIdFixture={fromMs:from,toMs:to,verified:[
 row("local-42","https://mastodon.social/@alice",{likes:4},"mastodon","Alice"),
 row("local-42","https://fosstodon.org/@bob",{likes:3},"mastodon","Bob"),
 row("local-42","https://mastodon.social/@alice",{likes:4},"mastodon","Alice"),
 row("local-42","https://misskey.io/@alice",{likes:1},"misskey","Alice"),
 row("local-42","https://misskey.design/@bob",{likes:2},"misskey","Bob")
]};
const localRanks=compute(localIdFixture);
assert.equal(localRanks.length,4,"same local ID on different federated profiles remains four accounts");
assert.equal(localRanks.reduce((sum,p)=>sum+p.posts,0),4,
 "deduplicate the same account post but never another instance's post");
assert.equal(localRanks.find(p=>p.profileUrl.includes("mastodon.social")).posts,1);

assert.equal(cohortOf({...b,profileCreatedAt:"2026-01-01T00:00:00Z",posts:1,activeDays:1},
  Date.parse("2026-11-03T00:00:00Z")),"established","one captured post does not mean newcomer");
assert.equal(cohortOf({...b,profileCreatedAt:"2026-11-01T00:00:00Z"},
  Date.parse("2026-11-03T00:00:00Z")),"new");
assert.equal(cohortOf({...b,posts:1,activeDays:1,profilePostCount:30}),"established");
assert.equal(compute({fromMs:from,toMs:to,verified:[]}).length,0);
assert.equal(compute({fromMs:to,toMs:from,verified:fixture.verified}).length,0);

const html='<!doctype html><html lang="ko"><body><section id="activityRanking">'+
 '<select id="activityRankingPlatform"><option value="all">전체</option></select>'+
 '<select id="activityRankingSort"><option value="signal">점수</option><option value="posts">게시글</option><option value="reactions">반응</option><option value="days">일수</option></select>'+
 '<div role="tablist"><button data-rank-cohort="established" class="active">기존 활동</button><button data-rank-cohort="new">신규 활동</button></div><div id="activityRankingRows"></div><button id="activityRankingMore" class="hidden" aria-expanded="false"></button>'+
 '</section><dialog id="activityRankingDialog"><button id="activityRankingDialogClose">닫기</button><div id="activityRankingDialogContent"></div></dialog></body></html>';
const dom=new JSDOM(html,{url:"https://koith.github.io/browser-app-lab/apps/demand-research/",runScripts:"outside-only"});
dom.window.INTERSECTION_publicRankingSnapshot=()=>fixture;
dom.window.eval(script);
const document=dom.window.document;
const $=id=>document.getElementById(id);
assert.equal(document.querySelectorAll(".activity-rank-card").length,1,
  "repeat activity across two distinct days qualifies as observed established activity");
const alphaCard=document.querySelector(".activity-rank-card");
assert.ok(alphaCard.getAttribute("aria-label").includes("테스트 계정"));
assert.equal(alphaCard.querySelector(".activity-rank-thumb img").src,"https://cdn.bsky.app/img/new.jpg");
alphaCard.querySelector(".activity-rank-thumb img").dispatchEvent(new dom.window.Event("error"));
assert.equal(alphaCard.querySelector(".activity-rank-thumb img"),null,
  "broken post media must never become an unrelated account image");
alphaCard.click();
assert.equal($("activityRankingDialog").hasAttribute("open"),true);
assert.match($("activityRankingDialogContent").textContent,/계정 공개 이력/);
const detailThumb=$("activityRankingDialogContent").querySelector(".activity-rank-detail-thumb");
assert.ok(detailThumb);
detailThumb.dispatchEvent(new dom.window.Event("error"));
assert.equal(detailThumb.isConnected,false,"failed post media is removed, not swapped to profile avatar");
assert.match($("activityRankingDialogContent").textContent,/기존 활동/);
$("activityRankingDialogClose").click();
document.querySelector('[data-rank-cohort="new"]').click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,3);
assert.equal(document.querySelectorAll(".activity-rank-user").length,0,"no visible username");
assert.equal(document.querySelectorAll(".activity-rank-card > *").length,6,"number and thumbnail only");
assert.match(document.querySelector('[data-rank-cohort="established"]').textContent,/1/);
assert.match(document.querySelector('[data-rank-cohort="new"]').textContent,/3/);
$("activityRankingPlatform").value="bluesky";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,1,"new-only platform filter");
const extra=Array.from({length:44},(_,i)=>row("n"+i,
  "https://bsky.app/profile/test"+i+".bsky.social",{likes:i},"bluesky","테스트 "+i,3));
fixture.verified=[...fixture.verified,...extra];
dom.window.dispatchEvent(new dom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(document.querySelectorAll(".activity-rank-card").length,20,"initial 20");
assert.match($("activityRankingMore").getAttribute("aria-label"),/20명 더 보기/);
$("activityRankingMore").click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,40,"first click adds 20");
$("activityRankingMore").click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,45,"remaining five");
assert.equal($("activityRankingMore").classList.contains("hidden"),true);
$("activityRankingPlatform").value="reddit";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,1);
$("activityRankingPlatform").value="bluesky";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,20,"filter resets to twenty");
dom.window.dispatchEvent(new dom.window.Event("intersection:date-range-change"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(document.querySelectorAll(".activity-rank-card").length,20,"date reset");
document.querySelector('[data-rank-cohort="established"]').click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,1);
dom.window.close();

// A one-post public search result can be an established account.
// The official, bounded Bluesky profile metadata must fix that classification.
const oldAccount=row("single1","https://bsky.app/profile/veteran.bsky.social",
  {likes:0},"bluesky","기존 사용자",2);
const ageDom=new JSDOM(html,{url:"https://koith.github.io/browser-app-lab/apps/demand-research/",
  runScripts:"outside-only"});
let profileRequests=0;
ageDom.window.INTERSECTION_publicRankingSnapshot=()=>({
  fromMs:from,toMs:to,verified:[oldAccount]
});
ageDom.window.fetch=async (url,opts)=>{
  profileRequests++;
  assert.match(url,/app.bsky.actor.getProfiles/);
  assert.equal(new URL(url).searchParams.get("actors"),"veteran.bsky.social");
  assert.equal(opts.credentials,"omit");
  return {ok:true,json:async()=>({profiles:[{
    did:"did:plc:abcdefghijklmnopqrstuvwxyz",
    handle:"veteran.bsky.social",createdAt:"2021-05-01T00:00:00Z",postsCount:122
  }]})};
};
ageDom.window.eval(script);
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(profileRequests,1,"one official getProfiles lookup");
assert.equal(ageDom.window.document.querySelectorAll(".activity-rank-card").length,1,
  "known old account must appear even if just one post in selected period");
ageDom.window.document.querySelector('[data-rank-cohort="new"]').click();
assert.equal(ageDom.window.document.querySelectorAll(".activity-rank-card").length,0,
  "verified older account not misclassified as newcomer");
ageDom.window.close();

// A failed profile response must not permanently brand a veteran as new,
// and the initial tab must never appear empty when valid new/unknown rows exist.
const retryDom=new JSDOM(html,{url:"https://koith.github.io/browser-app-lab/apps/demand-research/",
  runScripts:"outside-only"});
let attempts=0,clock=Date.now();
retryDom.window.Date.now=()=>clock;
retryDom.window.INTERSECTION_publicRankingSnapshot=()=>({
  fromMs:from,toMs:to,verified:[oldAccount]
});
retryDom.window.fetch=async()=>{
  attempts++;
  if(attempts===1)throw new Error("transient public API failure");
  return {ok:true,json:async()=>({profiles:[{
    handle:"veteran.bsky.social",createdAt:"2021-05-01T00:00:00Z",postsCount:122
  }]})};
};
retryDom.window.eval(script);
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(attempts,1);
assert.equal(retryDom.window.document.querySelector('[data-rank-cohort="new"]').getAttribute("aria-selected"),"true",
  "when age evidence is temporarily unavailable, show verified current activity rather than an empty panel");
assert.equal(retryDom.window.document.querySelectorAll(".activity-rank-card").length,1);
retryDom.window.dispatchEvent(new retryDom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(attempts,1,"backoff avoids rapid profile retries");
clock+=61000;
retryDom.window.dispatchEvent(new retryDom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(attempts,2,"a temporary failure is retryable");
assert.equal(retryDom.window.document.querySelector('[data-rank-cohort="established"]').getAttribute("aria-selected"),"true");
assert.equal(retryDom.window.document.querySelectorAll(".activity-rank-card").length,1);
retryDom.window.close();

const historic=row("historic","https://bsky.app/profile/historic.bsky.social",
  null,"bluesky","Historic",1);
historic.posted="2026-09-01T12:00:00Z";
const history=compute({fromMs:Date.parse("2026-09-01"),toMs:to,verified:[historic]});
assert.equal(cohortOf(history[0],Date.parse("2026-11-03T00:00:00Z")),"established",
  "an actual old public post is sufficient independent evidence the account existed 30 days ago");

const main=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const posPanel=main.indexOf('id="activityRanking"'),posFeed=main.indexOf('id="feed"');
assert.ok(posPanel>0&&posFeed>posPanel,"ranking physically above post feed");
assert.ok(main.includes("post_activity_ranking.js"));
assert.ok(main.includes("grid-template-columns:repeat(20,minmax(0,1fr))"),"desktop exactly ten equal-width tiles spanning two tracks each");
assert.ok(main.includes("grid-template-columns:repeat(10,minmax(0,1fr))"),"mobile exactly five equal-width tiles spanning two tracks each");
assert.ok(main.includes("profileCreatedAt:account.created_at"),"Mastodon age provenance");
assert.ok(main.includes("profileCreatedAt:u.createdAt"),"Misskey age provenance");
assert.ok(main.includes("profileCreatedAt:p.profileCreatedAt"),"snapshot preserves provider age");
assert.ok(script.includes("app.bsky.actor.getProfiles"),"Bluesky public metadata enrichment");
assert.ok(main.includes('id="activityRankingTitle">RANK</h2>'));
assert.ok(main.includes('id="activityRankingDialog"'));
assert.ok(main.includes("thumbnailUrl:safePublicLink(p.media?.[0]?.thumb"));
assert.ok(main.includes('avatarUrl:safePublicLink(p.avatarUrl||"")'),"rank snapshot includes public avatar fallback");
assert.ok(!main.includes('id="activityRankingStatus"'));
assert.ok(!main.includes("activity-ranking-kicker")&&!main.includes("activity-ranking-note"));
assert.ok(main.includes("INTERSECTION_publicRankingSnapshot"));
assert.ok(main.includes("!p.adultLabeled")&&main.includes("!p.discoveryCandidate"));
assert.ok(main.includes("!p.restricted"));
assert.ok(main.includes("filtered().filter"),"ranking honors visible post filtering");
const headerStart=main.indexOf('<header class="site-head">'),headerEnd=main.indexOf("</header>",headerStart);
const consumerLink=main.indexOf('class="header-consumer-entry"');
assert.ok(headerStart>=0&&consumerLink>headerStart&&consumerLink<headerEnd,"consumer shortcut belongs in page title header");
assert.equal((main.match(/href="\.\/consumer\/"/g)||[]).length,1,"single consumer shortcut link");
assert.ok(!main.includes('class="consumer-entry"'),"no oversized standalone consumer banner");
assert.ok(main.includes("thumb.append(sourceBadge(p,true))"),"post thumbnail requests icon-only source badge");
assert.ok(main.includes('if(!iconOnly)badge.append(el("span","",meta.name))'),"icon badge has no platform-name text");
assert.ok(main.includes('"source-badge"+(iconOnly?" source-badge--icon-only":"")'),"accessible icon-only badge variant");
assert.ok(main.includes('cloud:{name:"Archive",favicon:"https://koith.github.io/browser-app-lab/apps/demand-research/assets/archive.svg"}'),"archive has a pictogram");
assert.ok(!script.includes("localStorage")&&!script.includes("sessionStorage"));
console.log("PUBLIC_ACTIVITY_RANKING_QA_PASS: fixed-grid 10/5-column 20-at-a-time cohort ranking, source-logo-only tiles, compact header link, detail dialog, dedup and safe URLs");
