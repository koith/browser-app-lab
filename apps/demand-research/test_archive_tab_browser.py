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
 <p id="archiveHubStatus"></p>
 <div id="archiveHubActions" hidden><button id="archiveHubReload">새로고침</button></div>
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
                elif parsed.path=="/account-archive":
                    requests.append("viewer")
                    route.fulfill(status=200,content_type="text/html",
                      body='<html><body><p id="archived-posts">Synthetic verified posts / photos</p></body></html>')
                elif parsed.path.endswith("/archive_tab.js"):
                    route.fulfill(status=200,content_type="application/javascript",body=JS)
                elif parsed.path==urlsplit(base).path:
                    route.fulfill(status=200,content_type="text/html",body=HTML)
                else:
                    route.abort()
            page.route("**/*",route_it)
            page.goto(base+"?tab=archives&account="+KEY,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_function("""() => document.querySelector('#archiveHubStatus')
               .textContent.includes('비공개')""",timeout=10000)
            if private:
                page.locator("#archiveHubFrameBox").wait_for(state="visible",timeout=12000)
                iframe=page.locator("#archiveHubFrame")
                assert iframe.get_attribute("src")=="/account-archive?account="+KEY
                assert page.frame_locator("#archiveHubFrame").locator("#archived-posts").is_visible()
                page.evaluate("""() => window.INTERSECTION_openArchive('mastodon-'+('b'.repeat(40)))""")
                assert page.locator("#archiveHubFrame").get_attribute("src")==(
                    "/account-archive?account=mastodon-"+"b"*40)
                assert "account=mastodon-" in page.url
                assert "viewer" in requests
                assert page.locator("#archiveHubActions").is_visible()
            else:
                assert page.locator("#archiveHubFrameBox").is_hidden()
                assert page.locator("#archiveHubFrame").get_attribute("src") is None
                assert "viewer" not in requests
                assert page.locator("#archiveHubActions").is_hidden()
                allowed["value"]=True
                page.evaluate("window.dispatchEvent(new Event('intersection:private-session-ready'))")
                page.locator("#archiveHubFrameBox").wait_for(state="visible",timeout=12000)
                assert page.locator("#archiveHubFrame").get_attribute("src")==(
                    "/account-archive?account="+KEY)
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
