"""Actual production tab-switch and reload logic in Chromium and mobile WebKit.

Uses exact JS snippets from account_watch.js; no private data or network.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
SRC=(HERE/"account_watch.js").read_text("utf-8")
SWITCH=SRC[SRC.index("function setView(view){"):SRC.index("function scheduleRender(){")]
INIT=SRC[SRC.index("const navigation=performance.getEntriesByType"):SRC.index("// On page load, bounded refresh:")]
HTML="""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<style>.hidden{display:none}</style></head><body>
<nav role="tablist">
<button id="viewPosts" role="tab" aria-selected="true">게시글</button>
<button id="viewAccounts" role="tab" aria-selected="false">계정 분석</button>
<button id="viewArchives" role="tab" aria-selected="false">백업 보관함</button>
</nav>
<div id="postsView">첫 번째 게시글 탭</div>
<div id="accountsView" class="hidden">두 번째 계정 분석</div>
<div id="archivesView" class="hidden">세 번째 백업 보관함</div>
<script>
"use strict";
let currentView="posts";
const $=id=>document.getElementById(id);
function render(){}
__SWITCH__
document.querySelector("#viewArchives").addEventListener("click",()=>setView("archives"));
document.querySelector("#viewAccounts").addEventListener("click",()=>setView("accounts"));
__INIT__
</script>
</body></html>""".replace("__SWITCH__",SWITCH).replace("__INIT__",INIT)

ROOT="https://intersection-originals-free.onrender.com/"


def run(browser,label):
    ctx=browser.new_context(viewport={"width":390,"height":844})
    page=ctx.new_page()
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.route(ROOT+"**",lambda route:route.fulfill(
        status=200,content_type="text/html; charset=utf-8",body=HTML))
    try:
        page.goto(ROOT+"?tab=archives&mode=accounts",wait_until="load")
        assert page.locator("#archivesView").is_visible()
        assert page.locator("#viewArchives").get_attribute("aria-selected")=="true"
        assert page.locator("#postsView").is_hidden()
        # The reported bug: reloading an archives URL wrongly reopened tab 3.
        page.reload(wait_until="load")
        assert page.locator("#postsView").is_visible()
        assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
        assert page.locator("#archivesView").is_hidden()
        assert "tab=archives" not in page.url
        assert "mode=accounts" in page.url  # never delete unrelated deep-link state
        page.locator("#viewArchives").click()
        assert page.locator("#archivesView").is_visible()
        # A fresh, non-reload deep link still enters the requested view.
        page.goto(ROOT+"?tab=accounts",wait_until="load")
        assert page.locator("#accountsView").is_visible()
        assert page.locator("#viewAccounts").get_attribute("aria-selected")=="true"
        assert not errors,errors
        print("FIRST_TAB_RELOAD_PASS",label,"deep_link=preserved",
              "reload=posts","archive_click=works",flush=True)
    finally:
        ctx.close()


if __name__=="__main__":
    with sync_playwright() as playwright:
        run(playwright.chromium.launch(headless=True),"desktop_chromium")
        run(playwright.webkit.launch(headless=True),"mobile_webkit")
