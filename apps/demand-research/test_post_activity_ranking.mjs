/* Isolated browser and pure-unit QA; never fetches live SNS content. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { JSDOM } from "jsdom";

const dir=path.dirname(new URL(import.meta.url).pathname);
const script=fs.readFileSync(path.join(dir,"post_activity_ranking.js"),"utf8");
const {compute}=createRequire(import.meta.url)("./post_activity_ranking.js");
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
assert.equal(b.latestPosted,new Date(from+2*DAY).toISOString());
assert.equal(rank.find(x=>x.platform==="x").latestThumbnail,"","unsafe thumbnails dropped");
assert.equal(rank.find(x=>x.platform==="x").engagementAvailable,false);
assert.equal(rank.find(x=>x.platform==="x").reactions,0);
assert.deepEqual(compute(fixture),compute(fixture),"rank deterministic");
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
assert.equal(document.querySelectorAll(".activity-rank-card").length,0,"no established accounts in short fixture");
document.querySelector('[data-rank-cohort="new"]').click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,4);
assert.equal(document.querySelectorAll(".activity-rank-user").length,0,"no nickname on tiles");
assert.equal(document.querySelectorAll(".activity-rank-card > *").length,8,"rank number and square thumbnail only");
const alphaCard=[...document.querySelectorAll(".activity-rank-card")].find(c=>c.getAttribute("aria-label").includes("테스트 계정"));
assert.ok(alphaCard);
assert.equal(alphaCard.querySelector(".activity-rank-thumb img").src,"https://cdn.bsky.app/img/new.jpg");
alphaCard.click();
assert.equal($("activityRankingDialog").hasAttribute("open"),true);
assert.match($("activityRankingDialogContent").textContent,/활동 지수/);
assert.match($("activityRankingDialogContent").textContent,/계정 생성일을 뜻하지 않음/);
$("activityRankingDialogClose").click();
$("activityRankingPlatform").value="bluesky";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,2);
const extra=Array.from({length:44},(_,i)=>row("n"+i,
  "https://bsky.app/profile/test"+i+".bsky.social",{likes:i},"bluesky","테스트 "+i,3));
fixture.verified=[...fixture.verified,...extra];
dom.window.dispatchEvent(new dom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(document.querySelectorAll(".activity-rank-card").length,20,"initial top 20");
assert.match($("activityRankingMore").getAttribute("aria-label"),/20명 더 보기/);
$("activityRankingMore").click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,40,"first click adds 20");
$("activityRankingMore").click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,46,"remaining six");
assert.equal($("activityRankingMore").classList.contains("hidden"),true);
$("activityRankingPlatform").value="reddit";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,1);
$("activityRankingPlatform").value="bluesky";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,20,"filter resets to 20");
dom.window.dispatchEvent(new dom.window.Event("intersection:date-range-change"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(document.querySelectorAll(".activity-rank-card").length,20,"date reset to 20");
dom.window.close();

const main=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const posPanel=main.indexOf('id="activityRanking"'),posFeed=main.indexOf('id="feed"');
assert.ok(posPanel>0&&posFeed>posPanel,"ranking physically above post feed");
assert.ok(main.includes("post_activity_ranking.js"));
assert.ok(main.includes('id="activityRankingTitle">RANK</h2>'));
assert.ok(main.includes('id="activityRankingDialog"'));
assert.ok(main.includes("thumbnailUrl:safePublicLink(p.media?.[0]?.thumb"));
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
console.log("PUBLIC_ACTIVITY_RANKING_QA_PASS: 20-at-a-time cohort ranking, source-logo-only tiles, compact header link, detail dialog, dedup and safe URLs");
