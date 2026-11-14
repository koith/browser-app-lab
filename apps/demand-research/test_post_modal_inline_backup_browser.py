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
const suspectedAd=()=>false,hideMedia=()=>false;
const appendMedia=()=>{};
window.__trackedPosts=[];
window.INTERSECTION_watchPublicAccount=selection=>{
  window.__trackedPosts.push(selection);
  return true;
};
"""
    harness+=TILE_CODE
    harness+=POST_DETAIL
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
window.showFixturePost=(platform="bluesky",candidate=false)=>{
  openDetail({platform,profileUrl:platform==="mastodon"?
      "https://mastodon.social/@example":"https://bsky.app/profile/public-test.bsky.social",
    author:"Synthetic public author",avatarUrl:"https://example.com/fixture-avatar.png",
    url:"https://bsky.app/profile/public-test.bsky.social/post/123",
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
</nav><section id="postsView"><div style="height:2500px">POSTS</div></section>
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
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as playwright:
        exercise(playwright.chromium,"desktop-chromium",1200)
        exercise(playwright.webkit,"mobile-webkit",390)
        exercise(playwright.webkit,"compact-mobile-webkit",320)
