"""Real Chromium/WebKit DOM QA for pinned primary tabs and inline account backup.

Production CSS, production post-detail handler and full private backup client
are loaded verbatim. All account/HTTP values are synthetic and intercepted.
No live SNS/TeraBox reads, no credentials or actual backup job is created.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
INDEX=(ROOT/"index.html").read_text(encoding="utf-8")
BACKUP=(ROOT/"target_archive_client.js").read_text(encoding="utf-8")
SW=(ROOT/"intersection-sw.js").read_text(encoding="utf-8")
# Offline-first Render shell must ship the SAME script version as the page.
# Otherwise the modal renders a new button but restores the old JS handler.
CLIENT_SRC=re.search(r'<script src="(target_archive_client\.js\?[^"]+)"',INDEX)
assert CLIENT_SRC is not None,"Public backup client script reference missing"
assert '"/'+CLIENT_SRC.group(1)+'"' in SW,"Stale service-worker script URL"

STYLE=INDEX.split("<style>",1)[1].split("</style>",1)[0]
NAV_START=INDEX.index("/* Core navigation remains usable")
NAV_END=INDEX.index("</script>",NAV_START)
CORE_NAV=INDEX[NAV_START:NAV_END]
TILE_START=INDEX.index("function tile(p){")
TILE_END=INDEX.index("function appendMedia(",TILE_START)
TILE_CODE=INDEX[TILE_START:TILE_END]
DETAIL_START=INDEX.index("function confirmPostAccountAction(")
DETAIL_END=INDEX.index("function closeDetail(){",DETAIL_START)
POST_DETAIL=INDEX[DETAIL_START:DETAIL_END]
BLOCK_START=INDEX.index("/* A manually maintained personal exclusion list")
BLOCK_END=INDEX.index("function matchesText(",BLOCK_START)
BLOCK_CODE=INDEX[BLOCK_START:BLOCK_END]
FILTER_END=INDEX.index("/* The main feed",BLOCK_END)
FILTER_CODE=INDEX[BLOCK_END:FILTER_END]
BLOCK_HANDLER_START=INDEX.index('$("detailBlockAccount").addEventListener("click"')
BLOCK_HANDLER_END=INDEX.index('$("openDate").addEventListener("click"',BLOCK_HANDLER_START)
BLOCK_HANDLERS=INDEX[BLOCK_HANDLER_START:BLOCK_HANDLER_END]
assert "isManualBlocked(p)" in FILTER_CODE
assert "localStorage.setItem(MANUAL_BLOCK_STORAGE_KEY" in BLOCK_CODE
assert '#detail .dialog-foot' in STYLE
AMBIENT_START=INDEX.index("/* Interactive halftone:")
AMBIENT_END=INDEX.index("</script>",AMBIENT_START)
AMBIENT_SCRIPT=INDEX[AMBIENT_START:AMBIENT_END]
DRAW_START=INDEX.index("function draw(){")
DRAW_END=INDEX.index("/* Public activity ranking:",DRAW_START)
DRAW_SCRIPT=INDEX[DRAW_START:DRAW_END]
assert "list.insertBefore(item,cursor)" in DRAW_SCRIPT
assert 'list.replaceChildren()' not in DRAW_SCRIPT
assert "content-visibility:auto" in STYLE
PRIVATE="https://intersection-originals-free.onrender.com"
PUBLIC="https://koith.github.io/browser-app-lab/apps/demand-research"
PROFILE="https://bsky.app/profile/public-test.bsky.social"
OTHER="https://mastodon.social/@example"


def html_fixture():
    harness=r"""
const $=id=>document.getElementById(id);
const el=(tag,klass,text)=>{
  const n=document.createElement(tag);
  if(klass)n.className=klass;
  if(text!==undefined)n.textContent=String(text);
  return n;
};
const niceDate=()=> "2026.11.14";
const SERVICES={
  bluesky:{name:"Bluesky",favicon:"https://example.com/bluesky.svg"},
  mastodon:{name:"Mastodon",favicon:"https://example.com/mastodon.svg"},
  misskey:{name:"Misskey",favicon:"https://example.com/misskey.svg"},
  cloud:{name:"Archive",favicon:"https://example.com/archive.svg"}
};
const validUrl=s=>{try{const u=new URL(s);return u.protocol==="https:"?u.href:""}catch{return ""}};
const sourceBadge=p=>el("span","source-badge",p.platform);
const profileLink=p=>{
  const a=el("a","dialog-author",p.author);
  a.href=p.profileUrl;
  return a;
};
const sourceLink=(p,label)=>{
  const a=el("a","",label||"원문 보기");a.href=p.url;return a;
};
let cloudMode=false,detailSelectedPost=null,needle="";
let posts=[],indexedCandidates=[];
const suspectedAd=()=>false,hideMedia=()=>false;
function draw(){window.__visibleFeed=filtered().map(p=>p.id)}

const appendMedia=()=>{};
window.__trackedPosts=[];
window.INTERSECTION_watchPublicAccount=selection=>{
  window.__trackedPosts.push(selection);
  return true;
};
"""
    harness+=BLOCK_CODE
    harness+=FILTER_CODE
    harness+=TILE_CODE
    harness+=POST_DETAIL
    harness+=BLOCK_HANDLERS
    harness+="""
window.testFixtureThumbnailLifecycle=()=>{
  const row={id:"qa-image",platform:"bluesky",author:"QA",text:"뒷계 test only",
    profileUrl:"https://bsky.app/profile/qa.bsky.social",
    url:"https://bsky.app/profile/qa.bsky.social/post/1",
    posted:new Date().toISOString(),terms:new Set(["뒷계"]),
    media:[{type:"image",url:"https://example.com/pending-qa.png",
       thumb:"https://example.com/pending-qa.png"}],
    restricted:false,adultLabeled:false,discoveryCandidate:false};
  const tileImage=tile(row);
  document.body.append(tileImage);
  const thumb=tileImage.querySelector(".post-thumb");
  const img=tileImage.querySelector("img.post-media-img");
  const before=thumb.classList.contains("is-loading");
  const visible=getComputedStyle(thumb,"::after").animationName;
  img.dispatchEvent(new Event("load"));
  const after=!thumb.classList.contains("is-loading");
  tileImage.remove();
  const textOnly=tile({...row,id:"qa-text",media:[]});
  const noSpin=!textOnly.querySelector(".post-thumb").classList.contains("is-loading");
  const failure=tile({...row,id:"qa-failed"});
  failure.querySelector("img.post-media-img").dispatchEvent(new Event("error"));
  const failed=!!failure.querySelector(".thumb-placeholder")&&
    !failure.querySelector(".post-thumb").classList.contains("is-loading");
  return {before,visible,after,noSpin,failed};
};
window.setupManualBlockFeed=()=>{
  posts=[
    {id:"a-1",platform:"bluesky",profileUrl:"https://bsky.app/profile/public-test.bsky.social",
     authorDid:"did:plc:fixed123",text:"뒷계 synthetic one",indexed:"2026-11-14T08:00:00Z"},
    {id:"a-2",platform:"bluesky",profileUrl:"https://bsky.app/profile/public-test.bsky.social",
     authorDid:"did:plc:fixed123",text:"뒷계 synthetic two",indexed:"2026-11-14T07:00:00Z"},
    {id:"a-did",platform:"bluesky",profileUrl:"https://bsky.app/profile/renamed.bsky.social",
     authorDid:"did:plc:fixed123",text:"뒷계 synthetic renamed",indexed:"2026-11-14T06:00:00Z"},
    {id:"b-1",platform:"mastodon",profileUrl:"https://mastodon.social/@example",
     text:"뒷계 synthetic other",indexed:"2026-11-14T05:00:00Z"},
    {id:"c-1",platform:"mastodon",profileUrl:"https://bsky.app/profile/public-test.bsky.social",
     text:"뒷계 synthetic same-url-other-platform",indexed:"2026-11-14T04:00:00Z"}
  ];
  draw();
  return window.__visibleFeed;
};
window.showFixturePost=(platform="bluesky",candidate=false)=>{
  openDetail({platform,profileUrl:platform==="mastodon"?
      "https://mastodon.social/@example":"https://bsky.app/profile/public-test.bsky.social",
    author:"Synthetic public author",avatarUrl:"https://example.com/fixture-avatar.png",
    url:"https://bsky.app/profile/public-test.bsky.social/post/123",
    authorDid:platform==="bluesky"?"did:plc:fixed123":"",
    text:"Synthetic public post",posted:"2026-11-14T00:00:00Z",
    media:[],terms:new Set(),discoveryCandidate:candidate,restricted:false});
};
"""
    return ("""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">""" +
            "<style>"+STYLE+"</style></head><body>"+
            '<header class="site-head"><div class="head-inner"><h1>INTERSECTION</h1></div></header>'+
            """<main><nav class="primary-views" role="tablist">
<button type="button" id="viewPosts" class="active" role="tab" aria-selected="true">게시글</button>
<button type="button" id="viewAccounts" role="tab" aria-selected="false">계정 분석</button>
<button type="button" id="viewArchives" role="tab" aria-selected="false">백업 보관함</button>
</nav><button id="manualBlockOpen" type="button">차단 계정 <span id="manualBlockCount">0</span> · 관리</button><section id="postsView"><div style="height:2500px">POSTS</div></section>
<section id="accountsView" class="hidden"><div id="accountBackupSection">
 <div id="targetArchivePanel">
  <form id="targetArchiveForm">
   <select id="targetArchivePlatform"><option value="bluesky">Bluesky</option>
   <option value="mastodon">Mastodon</option></select>
   <input id="targetArchiveAccount">
   <button type="submit" id="targetArchiveSubmit">백업 시작</button>
  </form>
  <span id="targetArchiveInputHint"></span>
  <a href="#" id="targetArchiveWorkflow">Legacy</a>
  <p id="targetArchiveStatus"></p>
 </div></div><div style="height:2500px"></div></section>
<section id="archivesView" class="hidden"><div style="height:2500px">ARCHIVES</div></section>
</main><dialog id="detail" aria-labelledby="detailTitle">
 <div class="dialog-head"><b id="detailTitle"><span class="dialog-profile-name">작성자 정보</span></b>
 <div id="detailActionBar" class="dialog-tools" role="group" aria-label="게시글 주요 작업"></div>
 <button type="button" id="closeDetail" aria-label="게시글 닫기">×</button></div>
 <div class="dialog-content" id="detailContent"></div>
 <div class="dialog-foot"><button id="detailBlockAccount" type="button">차단하기</button>
 <span id="detailBlockStatus" role="status" aria-live="polite"></span></div>
</dialog><dialog id="manualBlockDialog" aria-labelledby="manualBlockTitle">
 <div class="manual-block-head"><h2 id="manualBlockTitle">차단 계정 관리</h2>
 <button id="manualBlockClose" type="button">×</button></div>
 <div class="manual-block-body"><p>브라우저 전용</p>
 <ul id="manualBlockList"></ul><p id="manualBlockStatus"></p></div>
</dialog><dialog id="postActionConfirm" aria-labelledby="postActionConfirmTitle" aria-describedby="postActionConfirmMessage">
 <h3 id="postActionConfirmTitle">계정 작업 확인</h3>
 <p id="postActionConfirmMessage">선택한 공개 계정에 작업을 실행할까요?</p>
 <div class="post-confirm-buttons"><button id="postActionCancel" type="button">취소</button>
 <button id="postActionAccept" type="button">확인</button></div>
</dialog><script>"""+CORE_NAV+"</script><script>"+harness+
            '</script><script src="/target_archive_client.js" defer></script></body></html>')


def exercise(browser_type,name,width):
    browser=browser_type.launch(headless=True)
    try:
        for host in (PRIVATE,PUBLIC):
            page=browser.new_page(viewport={"width":width,"height":850})
            errors=[]
            posts=[]
            page.on("pageerror",lambda e:errors.append(str(e)[:250]))
            def route_it(route):
                parsed=urlsplit(route.request.url)
                path=parsed.path
                if path=="/target_archive_client.js":
                    route.fulfill(status=200,content_type="application/javascript",body=BACKUP)
                elif path.endswith(".svg"):
                    route.fulfill(status=200,content_type="image/svg+xml",body=
                      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>')
                elif path.endswith("/fixture-avatar.png"):
                    route.fulfill(status=200,content_type="image/png",body=
                      base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGPUit7yn4GBgYGJAQoAIS4CPGFQl4cAAAAASUVORK5CYII="))
                elif path=="/api/target-archive/status":
                    route.fulfill(status=200 if host==PRIVATE else 503,
                        content_type="application/json",body='{"enabled":true}' if host==PRIVATE else '{}')
                elif path=="/api/account-archives":
                    route.fulfill(status=200,content_type="application/json",body='{"accounts":[]}')
                elif path=="/api/target-archive/start":
                    posts.append(json.loads(route.request.post_data))
                    route.fulfill(status=200,content_type="application/json",
                        body=json.dumps({"accepted":True,"state":"QUEUED_NOT_VERIFIED",
                                         "run_id":123456+len(posts),"receipt":"synthetic-job-receipt-"+str(len(posts))}))
                elif path.startswith("/api/target-archive/jobs/"):
                    route.fulfill(status=200,content_type="application/json",
                                  body='{"state":"QUEUED","queued_seconds":1}')
                elif path==urlsplit(host).path or path=="/":
                    route.fulfill(status=200,content_type="text/html",body=html_fixture())
                else:
                    route.abort()
            page.route("**/*",route_it)
            page.goto(host+"?tab=posts",wait_until="domcontentloaded",timeout=25000)
            page.wait_for_function("typeof window.INTERSECTION_startPublicAccountBackup==='function'")
            if host==PRIVATE:
                page.wait_for_function("document.querySelector('#targetArchiveStatus')?.textContent?.includes('계정 이름')",timeout=10000)
            # Natural document scrolling must never scroll away the three tabs.
            for label in ("게시글","계정 분석","백업 보관함"):
                page.get_by_role("tab",name=label).click()
                page.evaluate("window.scrollTo(0,1400)")
                page.wait_for_function("window.scrollY>200")
                top=page.locator(".primary-views").evaluate(
                    "node=>node.getBoundingClientRect().top")
                assert -1<=top<=2,(host,name,label,"tabs not pinned",top)
            page.get_by_role("tab",name="게시글").click()
            progress=page.evaluate("window.testFixtureThumbnailLifecycle()")
            assert progress=={
                "before":True,"visible":"thumb-load-spin","after":True,
                "noSpin":True,"failed":True
            },progress
            page.evaluate("window.showFixturePost('bluesky')")
            modal=page.locator("#detail")
            assert modal.get_attribute("open") is not None
            before=page.url
            header=modal.locator(".dialog-head")
            actions=modal.locator("#detailActionBar")
            button=modal.get_by_role("button",name="이 계정 바로 백업")
            assert button.count()==1
            assert actions.get_by_role("link",name="SNS 원문 보기").count()==1
            assert actions.get_by_role("button",name="계정 추적").count()==1
            assert modal.get_by_role("button",name="게시글 닫기").count()==1
            assert modal.locator(".dialog-content .dialog-backup-btn").count()==0
            assert modal.locator("#detailContent .dialog-source-row").count()==0
            assert modal.locator("#detailContent .source-badge").count()==0
            assert modal.locator("#detailContent .profile-link").count()==0
            profile=header.locator("#detailTitle a.dialog-profile-link")
            assert profile.count()==1
            assert profile.get_attribute("href")==PROFILE
            assert profile.get_attribute("target")=="_blank"
            assert profile.locator(".dialog-platform-icon").count()==1
            assert profile.locator(".dialog-avatar-frame img").count()==1
            assert profile.locator(".dialog-profile-name").inner_text()=="Synthetic public author"
            assert profile.locator(".dialog-profile-address").inner_text()=="bsky.app/profile/public-test.bsky.social"
            assert modal.get_attribute("data-platform")=="bluesky"
            # Real footer positioning and both actions must remain in-place.
            block=modal.get_by_role("button",name="이 계정 게시물 차단하기")
            assert block.is_visible(),(host,name)
            bounds=page.evaluate("""() => {
              const modal=document.querySelector('#detail').getBoundingClientRect();
              const foot=document.querySelector('#detail .dialog-foot').getBoundingClientRect();
              const button=document.querySelector('#detailBlockAccount').getBoundingClientRect();
              return {modalLeft:modal.left,modalBottom:modal.bottom,
                footLeft:foot.left,footBottom:foot.bottom,
                buttonLeft:button.left,buttonBottom:button.bottom,
                buttonWidth:button.width};
            }""")
            assert bounds["buttonLeft"]<=bounds["modalLeft"]+27,bounds
            assert bounds["buttonBottom"]>=bounds["modalBottom"]-55,bounds
            assert bounds["buttonWidth"]<120,bounds
            # Source icon, service-style avatar and account name share the
            # exact same clickable profile link; no extra modal navigation.
            page.evaluate("""() => {
              window.__sourceProfileClicks=0;
              document.querySelector('#detail .dialog-profile-link')
                .addEventListener('click',e=>{e.preventDefault();window.__sourceProfileClicks++})
            }""")
            profile.locator(".dialog-platform-icon").click()
            profile.locator(".dialog-avatar-frame").click()
            profile.locator(".dialog-profile-name").click()
            assert page.evaluate("window.__sourceProfileClicks")==3
            assert page.url==before
            # Single strong-contrast action header with buttons on ONE line.
            # Unlike the old body button bar it must remain fixed while only
            # the dialog body scrolls through potentially dozens of images.
            frame=page.evaluate("""() => {
              const d=document.querySelector('#detail');
              const h=d.querySelector('.dialog-head');
              const tools=d.querySelector('#detailActionBar');
              const nodes=[h.querySelector('b'),...tools.children,
                           d.querySelector('#closeDetail')];
              const boxes=nodes.map(n=>n.getBoundingClientRect());
              const bounds=d.getBoundingClientRect();
              return {top:h.getBoundingClientRect().top,
                minTop:Math.min(...boxes.map(r=>r.top)),
                maxTop:Math.max(...boxes.map(r=>r.top)),
                minLeft:Math.min(...boxes.map(r=>r.left)),
                maxRight:Math.max(...boxes.map(r=>r.right)),
                modalLeft:bounds.left,modalRight:bounds.right,
                modalHeight:bounds.height,modalTop:bounds.top,
                sticky:getComputedStyle(h).position,
                backdrop:getComputedStyle(d,'::backdrop').backgroundColor,
                headerBg:getComputedStyle(h).backgroundColor,
                bodyBg:getComputedStyle(d.querySelector('.dialog-content')).backgroundColor
              };
            }""")
            assert frame["sticky"]=="sticky",frame
            assert frame["maxTop"]-frame["minTop"]<24,("header wrapped",frame)
            assert frame["minLeft"]>=frame["modalLeft"]-1,frame
            assert frame["maxRight"]<=frame["modalRight"]+1,("header clipped",frame)
            assert frame["modalTop"]>=30,("modal covers too much screen",frame)
            assert frame["modalHeight"]<=page.viewport_size["height"]*.84,frame
            assert frame["backdrop"] not in ("rgba(0, 0, 0, 0)","transparent"),frame
            assert frame["headerBg"]!="rgb(255, 249, 237)",frame
            page.evaluate("""() => {
              const body=document.querySelector('#detailContent');
              const long=document.createElement('div');
              long.style.height='1700px';
              long.textContent='synthetic body content for scroll testing';
              body.append(long);
              body.scrollTop=1000;
            }""")
            scrolled=page.evaluate("""() => ({
              scroll:document.querySelector('#detailContent').scrollTop,
              headerTop:document.querySelector('#detail .dialog-head').getBoundingClientRect().top,
              modalTop:document.querySelector('#detail').getBoundingClientRect().top
            })""")
            assert scrolled["scroll"]>100,("dialog body did not scroll",scrolled)
            # When a short centered dialog grows taller, the browser recenters
            # the modal itself. Header fixation is measured relative to the
            # dialog border, not the changing absolute viewport coordinate.
            before_offset=frame["top"]-frame["modalTop"]
            after_offset=scrolled["headerTop"]-scrolled["modalTop"]
            assert abs(after_offset-before_offset)<=2,("header moved inside modal",frame,scrolled)
            assert button.is_visible(),"fixed header backup button scrolled away"
            # Modal-only tracking: asking and cancelling never changes tabs;
            # confirming adds only the selected public account.
            track=modal.get_by_role("button",name="계정 추적")
            track.click()
            confirm=page.locator("#postActionConfirm")
            debug=page.evaluate("""() => {
              const d=document.querySelector('#postActionConfirm');
              const h=document.querySelector('#detail');
              const r=d?.getBoundingClientRect();
              return {exists:!!d,open:d?.open,display:d&&getComputedStyle(d).display,
                width:r?.width,height:r?.height,originalOpen:h?.open,
                title:d?.querySelector('h3')?.textContent};
            }""")
            assert confirm.is_visible(),(debug,errors)
            assert "추적" in confirm.locator("h3").inner_text()
            assert page.evaluate("window.__trackedPosts.length")==0
            confirm.get_by_role("button",name="취소").click()
            assert not confirm.is_visible()
            assert page.evaluate("window.__trackedPosts.length")==0
            track.click()
            confirm.get_by_role("button",name="확인").click()
            assert page.evaluate("window.__trackedPosts.length")==1
            assert modal.get_attribute("open") is not None
            assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
            assert page.url==before
            assert modal.locator(".dialog-watch-status").is_visible()

            # No POST before explicit backup confirmation. A previous run must
            # NEVER block accepting the next independently selected account.
            button.click()
            assert confirm.is_visible()
            assert "백업" in confirm.locator("h3").inner_text()
            assert len(posts)==0,posts
            confirm.get_by_role("button",name="취소").click()
            assert len(posts)==0,posts
            button.click()
            confirm.get_by_role("button",name="확인").click()
            status=modal.locator(".dialog-backup-status")
            if host==PRIVATE:
                page.wait_for_function("document.querySelector('#detail .dialog-backup-status')?.textContent?.includes('백업 접수 완료')",timeout=15000)
                assert len(posts)==1,posts
                assert posts[0]=={"platform":"bluesky","account":PROFILE},posts
                assert button.is_disabled(),"Already queued account must not resubmit on double-click"
                assert "원본 검증 완료" not in status.inner_text()
                page.evaluate("document.querySelector('#detail').close()")
                page.evaluate("window.showFixturePost('mastodon')")
                second=modal.get_by_role("button",name="이 계정 바로 백업")
                second.click()
                assert confirm.is_visible()
                assert len(posts)==1,"Second request needs confirmation"
                confirm.get_by_role("button",name="확인").click()
                page.wait_for_function(
                    "document.querySelector('#targetArchiveJobStatus')?.textContent?.includes('백업 접수 완료') && "
                    "document.querySelector('.target-archive-queue-count')?.textContent?.includes('2건')",
                    timeout=15000)
                assert len(posts)==2,posts
                assert posts[1]=={"platform":"mastodon","account":OTHER},posts
                own=page.evaluate("window.INTERSECTION_getOwnBackupRequests()")
                assert len(own)==2,own
                assert [job["platform"] for job in own]==["bluesky","mastodon"]
                assert own[0]["createdAt"]>0 and own[0]["createdAt"]<=own[1]["createdAt"]
                assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
                assert modal.get_attribute("open") is not None
            else:
                page.wait_for_function("document.querySelector('#detail .dialog-backup-status')?.textContent?.includes('공개 미러')",timeout=7000)
                assert len(posts)==0,"Pages must never cross-origin POST"
            assert page.url==before,"post dialog backup must not change page or tab"
            page.evaluate("document.querySelector('#detail').close()")
            page.evaluate("window.showFixturePost('bluesky')")
            assert page.evaluate("window.setupManualBlockFeed()")==[
                "a-1","a-2","a-did","b-1","c-1"]
            modal.locator("#detailBlockAccount").click()
            assert "차단" in confirm.locator("h3").inner_text()
            assert page.evaluate("window.__visibleFeed")==[
                "a-1","a-2","a-did","b-1","c-1"],"Must not hide before confirmation"
            confirm.get_by_role("button",name="취소").click()
            assert page.evaluate("window.__visibleFeed")==[
                "a-1","a-2","a-did","b-1","c-1"],"Cancel must not mutate feed"
            modal.locator("#detailBlockAccount").click()
            confirm.get_by_role("button",name="확인").click()
            assert page.evaluate("window.__visibleFeed")==["b-1","c-1"],("same author and DID must all disappear",host)
            assert page.evaluate("posts.length")==5,"Blocking must NEVER delete originals"
            assert page.evaluate("JSON.parse(localStorage.getItem(MANUAL_BLOCK_STORAGE_KEY)).length")==1
            assert modal.get_attribute("open") is not None,"Blocking should not navigate/close detail"
            assert modal.get_by_role("button",name="이 계정 차단 해제").is_visible()
            # Closing/reopening this modal keeps the exclusion list and
            # dedicated manager exposes a one-click reversible unblock.
            page.evaluate("document.querySelector('#detail').close()")
            page.locator("#manualBlockOpen").click()
            assert page.locator("#manualBlockDialog").is_visible()
            assert page.locator("#manualBlockList li").count()==1
            page.locator("#manualBlockList button").click()
            assert page.evaluate("window.__visibleFeed")==[
                "a-1","a-2","a-did","b-1","c-1"]
            assert page.evaluate("JSON.parse(localStorage.getItem(MANUAL_BLOCK_STORAGE_KEY)).length")==0
            page.locator("#manualBlockClose").click()
            # Run the blocking workflow a second time and confirm persistence
            # across a full page reload on the same origin.
            page.evaluate("window.showFixturePost('bluesky')")
            modal.locator("#detailBlockAccount").click()
            confirm.get_by_role("button",name="확인").click()
            assert page.evaluate("window.__visibleFeed")==["b-1","c-1"]
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("typeof window.setupManualBlockFeed==='function'")
            assert page.evaluate("window.setupManualBlockFeed()")==["b-1","c-1"]
            assert page.locator("#manualBlockCount").inner_text()=="1"
            page.evaluate("window.showFixturePost('bluesky')")
            assert modal.get_by_role("button",name="이 계정 차단 해제").count()==1
            # Personal presentation filter is never applied to private archive.
            assert page.evaluate("(()=>{cloudMode=true;const ids=filtered().map(p=>p.id);cloudMode=false;return ids})()")==[
                "a-1","a-2","a-did","b-1","c-1"]

            assert modal.get_attribute("open") is not None
            page.evaluate("document.querySelector('#detail').close()")
            page.evaluate("window.showFixturePost('misskey')")
            assert page.locator("#detail .dialog-backup-btn").count()==0
            page.evaluate("document.querySelector('#detail').close()")
            page.evaluate("window.showFixturePost('bluesky',true)")
            assert page.locator("#detail .dialog-backup-btn").count()==0
            assert not errors,errors
            print("INTERSECTION_STICKY_TABS_MODAL_BACKUP_PASS",name,host,
                  "pinned_tabs=3","direct_jobs=",len(posts),
                  "no_navigation=YES","synthetic_only=YES",flush=True)
            page.close()
        # Regression for the former forever-running full-screen Canvas2D.
        # At rest there should be at most two scheduled frames, not ~15
        # per 500ms while the visitor tries to scroll the post grid.
        perf=browser.new_page(viewport={"width":width,"height":850})
        perf.set_content(
            "<canvas id='dotField'></canvas><script>"
            "window.__frames=0;const originalRAF=requestAnimationFrame.bind(window);"
            "window.requestAnimationFrame=fn=>{window.__frames++;return originalRAF(fn)};"
            "</script><script>"+AMBIENT_SCRIPT+"</script>",
            wait_until="load")
        perf.wait_for_timeout(550)
        idle=perf.evaluate("window.__frames")
        assert idle<=3,("idle Canvas redrew while not touched",name,idle)
        perf.mouse.click(min(width-10,70),90)
        perf.wait_for_timeout(180)
        active=perf.evaluate("window.__frames")
        assert active>idle,("touch ripple did not animate",name,idle,active)
        perf.close()
        print("INTERSECTION_SCROLL_IDLE_CANVAS_PASS",name,
              "idle_frames=",idle,"active_frames=",active,flush=True)
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as playwright:
        exercise(playwright.chromium,"desktop-chromium",1200)
        exercise(playwright.webkit,"mobile-webkit",390)
        exercise(playwright.webkit,"compact-mobile-webkit",320)
