"""Offline Chromium/WebKit QA: essential tabs survive account-script failure.

Extract the EXACT production inline fallback from index.html. Build only
synthetic empty panels, avoiding private storage/API, SNS, or actual user data.
"""
from __future__ import annotations

from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent


def run(engine,label):
    raw=(ROOT/"index.html").read_text("utf-8")
    anchor="<script>\n/* Core navigation remains usable"
    assert raw.count(anchor)==1, "core tab fallback script missing"
    start=raw.index(anchor)
    end=raw.index("</script>",start)+len("</script>")
    nav=raw[start:end]
    html="""<!doctype html><html lang="ko"><head><title>INTERSECTION</title>
      <style>.hidden{display:none}</style></head>
      <body><nav role="tablist">
      <button id="viewPosts" role="tab" aria-selected="true">게시글</button>
      <button id="viewAccounts" role="tab" aria-selected="false">계정 분석</button>
      <button id="viewArchives" role="tab" aria-selected="false">보관함</button>
      </nav>
      <div id="postsView">POSTS</div>
      <div id="accountsView" class="hidden">ACCOUNTS</div>
      <div id="archivesView" class="hidden">ARCHIVES</div>""" + nav + """</body></html>"""
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":390,"height":844})
        page.route("https://test.intersection.invalid/**",
                   lambda route:route.fulfill(status=200,content_type="text/html",body=html))
        page.goto("https://test.intersection.invalid/?tab=archives",
                  wait_until="domcontentloaded")
        assert page.evaluate("window.INTERSECTION_NAV_FALLBACK===true"), (
            "missing account script did not activate core tab fallback")
        assert page.locator("#archivesView").is_visible()
        assert page.locator("#viewArchives").get_attribute("aria-selected")=="true"
        page.locator("#viewAccounts").click()
        assert page.locator("#accountsView").is_visible()
        assert page.locator("#viewArchives").get_attribute("aria-selected")=="false"
        page.locator("#viewArchives").click()
        assert page.locator("#archivesView").is_visible()
        page.reload(wait_until="domcontentloaded")
        assert page.locator("#postsView").is_visible(), (
            "refresh must return first tab even if account analysis was offline")
        assert page.locator("#archivesView").is_hidden()
        assert "tab=archives" not in page.url
        page.locator("#viewArchives").focus()
        page.keyboard.press("Home")
        assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
        print("INTERSECTION_CORE_TABS_FALLBACK_PASS",label,
              "account_analysis_absent=PASS",
              "archive_navigation=PASS","reload_first_tab=PASS",
              "keyboard_home=PASS",flush=True)
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as playwright:
        run(playwright.chromium,"desktop-chromium")
        run(playwright.webkit,"mobile-webkit-simulated")
