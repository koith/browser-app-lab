"""Real Chromium/WebKit DOM QA for pinned primary tabs and inline account backup.

Production CSS, production post-detail handler and full private backup client
are loaded verbatim. All account/HTTP values are synthetic and intercepted.
No live SNS/TeraBox reads, no credentials or actual backup job is created.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
INDEX=(ROOT/"index.html").read_text(encoding="utf-8")
BACKUP=(ROOT/"target_archive_client.js").read_text(encoding="utf-8")
STYLE=INDEX.split("<style>",1)[1].split("</style>",1)[0]
NAV_START=INDEX.index("/* Core navigation remains usable")
NAV_END=INDEX.index("</script>",NAV_START)
CORE_NAV=INDEX[NAV_START:NAV_END]
DETAIL_START=INDEX.index("function openDetail(p){")
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
"""
    harness+=POST_DETAIL
    harness+="""
window.showFixturePost=(platform="bluesky",candidate=false)=>{
  openDetail({platform,profileUrl:platform==="mastodon"?
      "https://mastodon.social/@example":"https://bsky.app/profile/public-test.bsky.social",
    author:"Synthetic public author",url:"https://bsky.app/profile/public-test.bsky.social/post/123",
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
</main><dialog id="detail" aria-label="게시글 상세">
 <div class="dialog-head"><b>게시글 상세</b>
 <button type="button" id="closeDetail">×</button></div>
 <div class="dialog-content" id="detailContent"></div>
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
                elif path=="/api/target-archive/status":
                    route.fulfill(status=200 if host==PRIVATE else 503,
                        content_type="application/json",body='{"enabled":true}' if host==PRIVATE else '{}')
                elif path=="/api/account-archives":
                    route.fulfill(status=200,content_type="application/json",body='{"accounts":[]}')
                elif path=="/api/target-archive/start":
                    posts.append(json.loads(route.request.post_data))
                    route.fulfill(status=200,content_type="application/json",
                        body=json.dumps({"accepted":True,"state":"QUEUED_NOT_VERIFIED",
                                         "run_id":123456,"receipt":"synthetic-job-receipt"}))
                elif path.startswith("/api/target-archive/jobs/"):
                    route.fulfill(status=200,content_type="application/json",
                                  body='{"state":"QUEUED","queued_seconds":1}')
                elif path==urlsplit(host).path or path=="/":
                    route.fulfill(status=200,content_type="text/html",body=html_fixture())
                else:
                    route.abort()
            page.route("**/*",route_it)
            page.goto(host+"?tab=posts",wait_until="domcontentloaded",timeout=25000)
            page.wait_for_function("typeof window.showFixturePost==='function'")
            if host==PRIVATE:
                page.locator("#targetArchiveStatus").get_by_text(
                    "계정 이름",exact=False).wait_for(timeout=10000)
            # Natural document scrolling must never scroll away the three tabs.
            for label in ("게시글","계정 분석","백업 보관함"):
                page.get_by_role("tab",name=label).click()
                page.evaluate("window.scrollTo(0,1400)")
                page.wait_for_function("window.scrollY>200")
                top=page.locator(".primary-views").evaluate(
                    "node=>node.getBoundingClientRect().top")
                assert -1<=top<=2,(host,name,label,"tabs not pinned",top)
            page.get_by_role("tab",name="게시글").click()
            page.evaluate("window.showFixturePost('bluesky')")
            modal=page.locator("#detail")
            assert modal.get_attribute("open") is not None
            before=page.url
            button=modal.get_by_role("button",name="이 계정 바로 백업")
            assert button.count()==1
            button.click()
            status=modal.locator(".dialog-backup-status")
            if host==PRIVATE:
                status.get_by_text("백업 작업 접수",exact=False).wait_for(timeout=12000)
                assert len(posts)==1,("expected exactly one direct public account backup",posts)
                assert posts[0]=={"platform":"bluesky","account":PROFILE},posts
                assert button.is_disabled(),"queued job cannot be clicked twice"
                assert "원본 검증 완료" not in status.inner_text()
                # A second post popup must not duplicate an already queued job.
                page.evaluate("document.querySelector('#detail').close()")
                page.evaluate("window.showFixturePost('mastodon')")
                modal.get_by_role("button",name="이 계정 바로 백업").click()
                status.get_by_text("진행 중인 백업 요청",exact=False).wait_for(timeout=5000)
                assert len(posts)==1,posts
            else:
                status.get_by_text("공개 미러",exact=False).wait_for(timeout=5000)
                assert len(posts)==0,"public Pages must never cross-origin POST"
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
