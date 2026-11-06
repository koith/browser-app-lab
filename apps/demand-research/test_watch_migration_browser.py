"""Real-browser regression for restoring an old first-party Pages watch list.

The same Safari browser holds distinct localStorage partitions for GitHub
Pages and Render. This test uses the EXACT migration and profile parser from
the production account_watch.js, with a minimal DOM host to isolate migration.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
CODE=(ROOT/"account_watch.js").read_text("utf-8")
PARSER=CODE[CODE.index("function profile(raw){"):CODE.index("// Interest accounts were originally saved")]
MIGRATION=CODE[CODE.index("// Interest accounts were originally saved"):
               CODE.index("function setView(view){")]
PAGES="https://koith.github.io/browser-app-lab/apps/demand-research/"
RENDER="https://intersection-originals-free.onrender.com/"
KEY="intersection:public-account-watch:v1"
EXPECTED=["https://bsky.app/profile/legacy-one.bsky.social",
          "https://mastodon.social/@legacy-two"]
HTML="""<!doctype html><html><head><meta charset="utf-8"></head><body>
<section id="accountWatchSection">
<div class="account-list-toolbar"></div>
<p id="accountWatchStatus"></p></section>
<script>
(function(){
"use strict";
const STORE="intersection:public-account-watch:v1",MAX_WATCH=80;
const $=id=>document.getElementById(id);
let watches=[],storageWorks=true;
function node(tag,cls,text){
 const result=document.createElement(tag);
 result.className=cls||"";result.textContent=text||"";return result;
}
%s
%s
window.TEST_WATCHES=watches.map(x=>x.url);
})();
</script>
</body></html>""" % (PARSER, MIGRATION)


def verify(browser,label):
    context=browser.new_context(viewport={"width":390,"height":844})
    page=context.new_page()
    problems=[]
    page.on("pageerror",lambda e: problems.append(str(e)))
    def respond(route):
        route.fulfill(status=200,content_type="text/html; charset=utf-8",
                      body=HTML)
    page.route(PAGES+"**",respond)
    page.route(RENDER+"**",respond)
    try:
        page.goto(PAGES)
        page.evaluate("(rows,key)=>localStorage.setItem(key,JSON.stringify(rows))",
                      EXPECTED,KEY)
        assert page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))",
                             KEY)==EXPECTED
        page.goto(RENDER+"?tab=accounts")
        assert page.evaluate("window.TEST_WATCHES")==[]
        button=page.get_by_role("button",name="기존 관심 계정 복원")
        assert button.is_visible()
        button.click()
        page.wait_for_function("window.TEST_WATCHES && window.TEST_WATCHES.length===2",
                               timeout=12000)
        assert page.evaluate("window.TEST_WATCHES")==EXPECTED
        assert page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))",
                             KEY)==EXPECTED
        assert "watch_import" not in page.url,"import fragment must be removed"
        assert "기존 관심 계정 2개를 복원" in page.locator("#accountWatchStatus").inner_text()
        # Merge must not create duplicates; neither browser store is deleted.
        page.get_by_role("button",name="기존 관심 계정 복원").click()
        page.wait_for_function("window.TEST_WATCHES && window.TEST_WATCHES.length===2",
                               timeout=12000)
        assert "기존 관심 계정 2개가" in page.locator("#accountWatchStatus").inner_text()
        page.goto(PAGES)
        assert page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))",
                             KEY)==EXPECTED
        # Tampered fragments cannot remove existing saved accounts.
        page.goto(RENDER+"?tab=accounts#watch_import=malformed")
        assert page.evaluate("window.TEST_WATCHES")==EXPECTED
        assert "watch_import" not in page.url
        assert not problems,problems
        print("WATCH_ORIGIN_MIGRATION_PASS",label,"from_pages=2","render=2",
              "source_retained=yes","duplicates=no","browser_errors=0",flush=True)
    finally:
        context.close()


def main():
    with sync_playwright() as p:
        verify(p.chromium.launch(headless=True),"desktop_chromium")
        verify(p.webkit.launch(headless=True),"mobile_webkit")


if __name__=="__main__":
    main()
