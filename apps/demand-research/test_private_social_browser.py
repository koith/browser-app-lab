"""Private gateway UI smoke with local synthetic provider responses only."""
import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML=Path(__file__).with_name("index.html").read_text(encoding="utf-8")
ORIGIN="https://private.intersection.test/"

def run():
    errors=[];requested=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":390,"height":844})
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.route(ORIGIN,lambda route:route.fulfill(status=200,content_type="text/html",body=HTML))
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
            assert not errors,errors
            print("PRIVATE_SOCIAL_BROWSER_FIXTURE",json.dumps({"cards":1,"calls":len(requested),"source_badge":"X","errors":len(errors)}))
        finally: browser.close()
if __name__=="__main__":run()
