"""Offline desktop/mobile QA: built-in archive tab is private by default.

No real account credentials or private TeraBox objects are used.
"""
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
JS=(ROOT/"archive_tab.js").read_text(encoding="utf-8")
KEY="bluesky-"+"a"*40
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
PRIVATE="https://private.intersection.test/"
HTML="""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="archive_tab.js" defer></script></head><body>
<button id="viewArchives">백업 보관함</button>
<section id="archivesView">
 <div role="tablist">
  <button id="archiveModeAuto" role="tab" aria-selected="false">자동 저장 게시글</button>
  <button id="archiveModeAccounts" role="tab" aria-selected="false">지정 계정 백업</button>
 </div>
 <div id="archiveAccountPicker" hidden>
 <label for="archiveQuickSelect">보관된 계정</label>
 <span id="archiveQuickCount"></span>
 <select id="archiveQuickSelect" disabled><option value="">보관 목록 확인 중</option></select>
 <input id="archiveQuickSearch" type="search" hidden>
 <p id="archiveQuickStatus"></p>
</div>
 <p id="archiveHubStatus"></p>
 <div id="archiveHubActions" hidden><button id="archiveHubReload">새로고침</button>
 <a id="archiveHubFullView"></a></div>
 <div id="archiveHubFrameBox" hidden><iframe id="archiveHubFrame"></iframe></div>
</section></body></html>"""


def exercise(browser_type,label):
    browser=browser_type.launch(headless=True)
    try:
        for private in (False,True):
            base=PRIVATE if private else PAGE
            errors=[]
            requests=[]
            allowed={"value":private}
            page=browser.new_page(viewport={"width":390,"height":844})
            page.on("pageerror",lambda error:errors.append(str(error)))
            def route_it(route):
                parsed=urlsplit(route.request.url)
                if parsed.scheme!="https":
                    route.abort();return
                if parsed.path=="/api/session":
                    requests.append("session")
                    route.fulfill(status=200 if allowed["value"] else 401,
                      content_type="application/json",
                      body='{"connected":true}' if allowed["value"] else '{"detail":"Private link required"}')
                elif parsed.path=="/api/account-archives":
                    requests.append("choices")
                    route.fulfill(status=200,content_type="application/json",
                      body='{"accounts":['
                        '{"key":"'+KEY+'","platform":"bluesky","display_name":"코코",'
                        '"handle":"coco.bsky.social","profile_snapshot_verified":true},'
                        '{"key":"mastodon-'+('b'*40)+'","platform":"mastodon",'
                        '"display_name":"마루","handle":"maru@example.test",'
                        '"profile_snapshot_verified":true}]}')
                elif parsed.path=="/api/archive-overview":
                    requests.append("overview")
                    route.fulfill(status=200,content_type="application/json",
                      body='{"automated_posts":null,"automated_posts_state":"not_read_verified",'
                           '"post_journal_candidates":3,"post_journal_state":"candidates_unverified",'
                           '"account_zip_candidates":2,"account_zip_read_verified":null,'
                           '"account_bundles_state":"candidates_unverified",'
                           '"account_registry_count":null,"account_registry_state":"not_checked"}')
                elif parsed.path=="/account-archive":
                    requests.append("viewer")
                    route.fulfill(status=200,content_type="text/html",
                      body='<html><body><p id="archived-posts">Synthetic verified posts / photos</p></body></html>')
                elif parsed.path=="/auto-archive":
                    requests.append("automatic-viewer")
                    route.fulfill(status=200,content_type="text/html",
                      body='<html><body><p id="keyword-posts">Synthetic auto-captured original videos and images</p></body></html>')
                elif parsed.path.endswith("/archive_tab.js"):
                    route.fulfill(status=200,content_type="application/javascript",body=JS)
                elif parsed.path==urlsplit(base).path:
                    route.fulfill(status=200,content_type="text/html",body=HTML)
                else:
                    route.abort()
            page.route("**/*",route_it)
            page.goto(base+"?tab=archives&account="+KEY,wait_until="domcontentloaded",timeout=30000)
            page.locator("#archiveHubStatus").wait_for(state="visible",timeout=12000)
            if private:
                page.locator("#archiveHubFrameBox").wait_for(state="visible",timeout=12000)
                iframe=page.locator("#archiveHubFrame")
                assert iframe.get_attribute("src")=="/account-archive?embedded=1&account="+KEY
                page.frame_locator("#archiveHubFrame").locator("#archived-posts").wait_for(
                    state="visible",timeout=12000)
                page.evaluate("""() => window.INTERSECTION_openArchive('mastodon-'+('b'.repeat(40)))""")
                assert page.locator("#archiveHubFrame").get_attribute("src")==(
                    "/account-archive?embedded=1&account=mastodon-"+"b"*40)
                assert "account=mastodon-" in page.url
                assert "viewer" in requests
                page.locator("#archiveQuickSelect option").first.wait_for(timeout=20000)
                page.wait_for_function(
                    "() => document.querySelector('#archiveQuickCount')"
                    "?.textContent?.includes('2개')",timeout=20000)
                labels=page.locator("#archiveQuickSelect option").all_text_contents()
                assert "코코(@coco.bsky.social)" in labels
                assert "마루(@maru@example.test)" in labels
                assert all("https://" not in text for text in labels)
                assert requests.count("choices")==1, "account list must preload once"
                page.locator("#archiveHubStatus").get_by_text(
                    "ZIP 파일 후보 2개 발견",exact=False).wait_for(timeout=12000)
                assert "overview" in requests
                assert page.locator("#archiveHubActions").is_visible()
                page.locator("#archiveModeAuto").click()
                assert page.locator("#archiveHubFrame").get_attribute("src")=="/auto-archive"
                page.frame_locator("#archiveHubFrame").locator("#keyword-posts").wait_for(
                    state="visible",timeout=12000)
                assert "automatic-viewer" in requests
                page.locator("#archiveHubStatus").get_by_text(
                    "저널 파일 후보 3개 발견",exact=False).wait_for(timeout=12000)
                assert page.locator("#archiveHubFullView").get_attribute("href")=="/auto-archive"
                page.locator("#archiveModeAccounts").click()
                assert page.locator("#archiveHubFrame").get_attribute("src")==(
                    "/account-archive?embedded=1&account=mastodon-"+"b"*40)
                page.evaluate("window.INTERSECTION_openArchive('bluesky-'+('a'.repeat(40)))")
                assert page.locator("#archiveHubFrame").get_attribute("src")==(
                  "/account-archive?embedded=1&account="+KEY)
                page.locator("#archiveQuickSelect").select_option("mastodon-"+("b"*40))
                assert page.locator("#archiveHubFrame").get_attribute("src")==(
                    "/account-archive?embedded=1&account=mastodon-"+"b"*40)
                assert requests.count("choices")==1
            else:
                assert page.locator("#archiveHubFrameBox").is_hidden()
                assert page.locator("#archiveHubFrame").get_attribute("src") is None
                assert "viewer" not in requests
                # Public Pages must show an in-product archive link to the
                # dedicated Intersection web app, not a GitHub Actions page.
                assert page.locator("#archiveHubActions").is_visible()
                link=page.locator("#archiveHubFullView")
                assert link.get_attribute("href")==(
                    "https://intersection-originals-free.onrender.com/"
                    "?tab=archives&mode=accounts&account="+KEY)
                assert "교집합 보관함" in link.inner_text()
                allowed["value"]=True
                page.evaluate("window.dispatchEvent(new Event('intersection:private-session-ready'))")
                assert page.locator("#archiveHubFrameBox").is_hidden()
                assert "viewer" not in requests
                assert "session" not in requests, "public Pages must not probe private sessions"
                page.locator("#archiveModeAuto").click()
                assert page.locator("#archiveHubFrame").get_attribute("src") is None
                assert "mode=auto" in link.get_attribute("href")
                page.locator("#archiveModeAccounts").click()
                assert page.locator("#archiveHubFrame").get_attribute("src") is None
                assert "mode=accounts" in link.get_attribute("href")
            assert not errors,errors
            print("ARCHIVE_TAB_BROWSER_PASS",label,
                  "private_gateway" if private else "public_unlinked_then_login",
                  "requests=",len(requests),flush=True)
            page.close()
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as playwright:
        exercise(playwright.chromium,"desktop-chromium")
        exercise(playwright.webkit,"mobile-webkit")
