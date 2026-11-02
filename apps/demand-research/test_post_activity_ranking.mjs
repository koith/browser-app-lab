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
 '<div id="activityRankingRows"></div><button id="activityRankingMore" class="hidden" aria-expanded="false"></button>'+
 '</section><dialog id="activityRankingDialog"><button id="activityRankingDialogClose">닫기</button><div id="activityRankingDialogContent"></div></dialog></body></html>';
const dom=new JSDOM(html,{url:"https://koith.github.io/browser-app-lab/apps/demand-research/",runScripts:"outside-only"});
dom.window.INTERSECTION_publicRankingSnapshot=()=>fixture;
dom.window.eval(script);
const document=dom.window.document;
const $=id=>document.getElementById(id);
assert.equal(document.querySelectorAll(".activity-rank-card").length,4);
assert.equal($("activityRankingPlatform").options.length,4);
assert.equal(document.querySelectorAll(".activity-rank-card > *").length,12,"only rank, name and thumbnail on each card");
assert.equal(document.querySelectorAll(".activity-rank-score,.activity-rank-stats,.activity-rank-source").length,0);
assert.equal(document.querySelectorAll(".activity-rank-card a").length,0,"profile link lives in detail dialog");
const alphaCard=[...document.querySelectorAll(".activity-rank-card")].find(c=>c.querySelector(".activity-rank-user")?.textContent==="테스트 계정");
assert.ok(alphaCard);
assert.equal(alphaCard.querySelector(".activity-rank-thumb img").src,"https://cdn.bsky.app/img/new.jpg");
assert.equal(alphaCard.querySelector(".activity-rank-thumb img").getAttribute("alt"),"");
assert.equal(alphaCard.textContent,"02테스트 계정","no extra visible text on tile");
alphaCard.click();
assert.equal($("activityRankingDialog").hasAttribute("open"),true,"card opens detail dialog");
assert.match($("activityRankingDialogContent").textContent,/활동 지수/);
assert.match($("activityRankingDialogContent").textContent,/게시글/);
assert.match($("activityRankingDialogContent").textContent,/반응 제공/);
const profile=$("activityRankingDialogContent").querySelector(".activity-rank-detail-link");
assert.equal(profile.href,"https://bsky.app/profile/alpha.bsky.social");
assert.equal(profile.target,"_blank");
assert.match(profile.rel,/noopener/);
$("activityRankingDialogClose").click();
assert.equal($("activityRankingDialog").hasAttribute("open"),false,"close returns to rank grid");
assert.ok([...document.querySelectorAll(".activity-rank-card")].some(c=>c.querySelector(".activity-rank-thumb-empty")),"unsafe or absent thumbnail uses empty block");
$("activityRankingPlatform").value="bluesky";
$("activityRankingPlatform").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelectorAll(".activity-rank-card").length,2,"platform filter");
$("activityRankingSort").value="posts";
$("activityRankingSort").dispatchEvent(new dom.window.Event("change"));
assert.equal(document.querySelector(".activity-rank-user").textContent,"테스트 계정");

const extra=Array.from({length:9},(_,i)=>row("n"+i,
  "https://bsky.app/profile/test"+i+".bsky.social",{likes:i},"bluesky","테스트 "+i,3));
fixture.verified=[...fixture.verified,...extra];
dom.window.dispatchEvent(new dom.window.Event("intersection:feed-updated"));
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(document.querySelectorAll(".activity-rank-card").length,5,"collapsed list capped to five");
assert.equal($("activityRankingMore").classList.contains("hidden"),false);
assert.equal($("activityRankingMore").textContent,"더 보기");
$("activityRankingMore").click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,11,"expanded list shows ranking");
assert.equal($("activityRankingMore").getAttribute("aria-expanded"),"true");
$("activityRankingMore").click();
assert.equal(document.querySelectorAll(".activity-rank-card").length,5);
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
assert.ok(!script.includes("localStorage")&&!script.includes("sessionStorage"));
console.log("PUBLIC_ACTIVITY_RANKING_QA_PASS: latest thumbnails, minimal tiles, detail dialog, dedup, filters, expanded ranks, safe media and links");
