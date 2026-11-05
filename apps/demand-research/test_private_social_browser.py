"""Private gateway UI smoke with local synthetic provider responses only."""
import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=Path(__file__).with_name("index.html").read_text(encoding="utf-8")
AUTO=Path(__file__).with_name("account_auto_analysis.js").read_text(encoding="utf-8")
ACCOUNT_UI=Path(__file__).with_name("account_index_client.js").read_text(encoding="utf-8")
GROUP_UI=Path(__file__).with_name("account_group_client.js").read_text(encoding="utf-8")
WATCH=Path(__file__).with_name("account_watch.js").read_text(encoding="utf-8")
ORIGIN="https://private.intersection.test/"

def run():
    errors=[];requested=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":390,"height":844})
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.route(ORIGIN,lambda route:route.fulfill(status=200,content_type="text/html",body=HTML))
            page.route(ORIGIN+"account_watch.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=WATCH))
            page.route(ORIGIN+"account_auto_analysis.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=AUTO))
            page.route(ORIGIN+"account_index_client.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=ACCOUNT_UI))
            page.route(ORIGIN+"account_group_client.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=GROUP_UI))
            def group_page(route):
                from urllib.parse import urlsplit,parse_qs
                params=parse_qs(urlsplit(route.request.url).query)
                offset=int(params.get("offset",[0])[0])
                accounts=[{"platform":"bluesky",
                  "profileUrl":"https://bsky.app/profile/fake%d.bsky.social"%i,
                  "verified_posts":i+1} for i in range(10)]
                item={"group_id":"A-fixture123","account_count":10,"distinct_posts":55,"capped_daily_contributions":1,
                  "accounts":accounts,"evidence":"reciprocal_explicit_public_self_declaration"}
                items=[item] if offset==0 else []
                route.fulfill(status=200,content_type="application/json",
                  body=json.dumps({"total":1,"account_count":20002,
                  "linked_accounts":10,"unresolved_accounts":19992,"items":items}))
            page.route(ORIGIN+"api/account-groups?*",group_page)
            page.route(ORIGIN+"api/accounts/status",lambda route:route.fulfill(
                status=200,content_type="application/json",body=json.dumps({
                "accounts":20002,"source_rows":28000,"last_catalog_sync":1793600000,
                "refreshing":False,"last_catalog_skipped":0})))
            def account_page(route):
                from urllib.parse import urlsplit,parse_qs
                params=parse_qs(urlsplit(route.request.url).query)
                offset=int(params.get("offset",[0])[0]);limit=int(params.get("limit",[80])[0])
                items=[{"platform":"bluesky",
                    "profileUrl":"https://bsky.app/profile/fixture"+str(i)+".bsky.social",
                    "verified_posts":2,"latest_posted":"2026-11-02T00:00:00Z"}
                    for i in range(offset,min(20002,offset+limit))]
                route.fulfill(status=200,content_type="application/json",
                    body=json.dumps({"total":20002,"items":items,"limit":limit,"offset":offset}))
            page.route(ORIGIN+"api/accounts?*",account_page)
            page.route(ORIGIN+"api/posts?*",lambda route:route.fulfill(
                status=200,content_type="application/json",body=json.dumps({"total":0,"posts":[]})))
            def discovery(route):
                requested.append(route.request.url)
                utc=datetime.now(timezone.utc).isoformat()
                row={"id":"x:synthetic-fixture","platform":"x","author":"QA fixture",
                     "profileUrl":"https://x.com/qa","url":"https://x.com/qa/status/1234567890",
                     "text":"섹트 synthetic QA public test","posted":utc,"indexed":utc,
                     "media":[],"adultLabeled":False,"restricted":False}
                route.fulfill(status=200,content_type="application/json",
                   body=json.dumps({"provider":"socialcrawl","items":[row],"received":1,"accepted":1}))
            page.route(ORIGIN+"api/discovery?*",discovery)
            page.route("https://koith.github.io/browser-app-lab/apps/demand-research/assets/*.svg",
                lambda route:route.fulfill(status=200,content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><circle cx="10" cy="10" r="7"/></svg>'))
            page.goto(ORIGIN,wait_until="domcontentloaded")
            page.wait_for_function("document.getElementById('socialControls') && !document.getElementById('socialControls').classList.contains('hidden')")
            assert page.locator("#socialControls").is_visible()
            page.select_option("#socialPlatform","x")
            page.select_option("#socialTerm","섹트")
            page.locator("#socialFind").click()
            page.wait_for_selector("article.post",timeout=20000)
            assert len(requested)==1
            assert "platform=x" in requested[0] and "%EC%84%B9%ED%8A%B8" in requested[0]
            assert page.locator('.source-badge[aria-label="출처: X"]').count()==1
            assert page.locator("article.post a.author").get_attribute("href")=="https://x.com/qa"
            assert page.locator("#socialStatus").inner_text().find("1건 추가")>=0
            page.locator("#viewAccounts").click()
            # Private account indexes are optional advanced panels in the new
            # UX. Open the section before verifying its existing functionality.
            page.locator("#accountServerData > summary").click()
            page.wait_for_selector("#intersectionGroupRows details",timeout=25000)
            assert "A-fixture123" in page.locator("#intersectionGroupRows summary").inner_text()
            page.locator("#intersectionGroupRows summary").click()
            assert page.locator("#intersectionGroupRows details a").count()==10
            page.wait_for_function("document.querySelectorAll('#privateAccountRows > div').length===80",timeout=25000)
            assert "20,002" in page.locator("#privateAccountSummary").inner_text()
            page.locator("#privateAccountIndex .account-auto-more").click()
            page.wait_for_function("document.querySelectorAll('#privateAccountRows > div').length===160",timeout=15000)
            assert not errors,errors
            print("PRIVATE_SOCIAL_BROWSER_FIXTURE",json.dumps({"cards":1,"calls":len(requested),"indexed_account_rows":160,"total_accounts":20002,"self_declared_group_accounts":10,"source_badge":"X","errors":len(errors)}))
        finally: browser.close()
if __name__=="__main__":run()
