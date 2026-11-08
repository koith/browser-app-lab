"""Real HTTPS read-only public account-index UI acceptance.

No synthetic API interception, screenshots, identifiers, post bodies, external
profile navigation, credentials or storage mutations. This confirms that the
SHA-verified backend index is actually visible on desktop and mobile WebKit.
"""
from __future__ import annotations
import re
from playwright.sync_api import sync_playwright

def safe_browser_error(value):
    # Only finite error classes and known static filenames may reach CI logs.
    # Never print the raw exception (which could contain source/post URLs).
    raw=str(value)
    kind=next((k for k in ("TypeError","ReferenceError","SyntaxError",
                           "RangeError","SecurityError","NetworkError",
                           "UnhandledPromiseRejection") if k in raw),"Other")
    scripts=("account_index_client.js","account_group_client.js",
             "account_auto_analysis.js","account_watch.js","archive_tab.js",
             "target_archive_client.js","free_discovery.js",
             "post_activity_ranking.js","public_video_trends.js",
             "index.html")
    src=next((n for n in scripts if n in raw),"unknown")
    import re
    pos=re.search(r"(?:"+re.escape(src)+r")(?:\\?[^\\s]*)?:(\\d+):\\d+",raw) if src!="unknown" else None
    line=int(pos.group(1)) if pos else 0
    return {"kind":kind,"source":src,"line":line}

SITE="https://intersection-originals-free.onrender.com"

def verify(engine,label,width,height):
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":width,"height":height},
                             color_scheme="light")
        js_errors=[]
        page.on("pageerror",lambda error:js_errors.append(safe_browser_error(error)))
        status=page.request.get(SITE+"/api/accounts/status",timeout=90000)
        assert status.status==200, "live account status HTTP failed"
        counts=status.json()
        expected=int(counts.get("accounts",0))
        assert expected>=300, "verified live account index has not been restored"
        assert int(counts.get("source_rows",0))>=expected
        assert counts.get("remote_snapshot_verified") is True

        response=page.goto(SITE+"/",wait_until="domcontentloaded",timeout=120000)
        assert response and response.status==200, "deployed app HTML unavailable"
        page.locator("#viewAccounts").click()
        summary=page.locator("#privateAccountSummary")
        page.wait_for_function(
            "(total) => document.querySelector('#privateAccountSummary')"
            "?.textContent?.includes('계정 '+total.toLocaleString('ko-KR')+'개')",
            arg=expected,timeout=90000)
        page.wait_for_function(
            "() => document.querySelectorAll('#privateAccountRows > div').length>=80",
            timeout=90000)
        first_count=page.locator("#privateAccountRows > div").count()
        assert first_count==80, "live account first page must contain 80 items"

        more=page.locator("#privateAccountIndex button.account-auto-more")
        assert more.is_visible() and more.is_enabled()
        more.click()
        page.wait_for_function(
            "() => document.querySelectorAll('#privateAccountRows > div').length>80",
            timeout=60000)
        assert page.locator("#privateAccountRows > div").count()>=160, (
            "live account pagination did not load the next 80 rows")

        source=page.locator("#privateAccountIndex select[aria-label='SNS 필터']")
        source.select_option("bluesky")
        page.wait_for_function(
            "() => {const rows=[...document.querySelectorAll('#privateAccountRows a')];"
            "return rows.length>0 && rows.every(x => x.href.startsWith("
            "'https://bsky.app/profile/'));}",
            timeout=60000)
        links=page.locator("#privateAccountRows a")
        assert links.count()>0, "no real filtered Bluesky rows"
        assert all((links.nth(i).get_attribute("href") or "").startswith(
            "https://bsky.app/profile/") for i in range(min(links.count(),5))), (
            "provider filter mixed nonmatching profiles")

        search=page.locator("#privateAccountIndex input[aria-label='누적 공개 계정 검색']")
        search.fill("this_unmatchable_qa_phrase_123456")
        search.press("Tab")  # Input change event applies the server-side search.
        page.wait_for_function(
            "() => document.querySelector('#privateAccountRows')"
            "?.textContent?.includes('일치하는 보관 계정이 없습니다.')",
            timeout=60000)
        search.fill("")
        search.press("Tab")
        page.wait_for_function(
            "() => document.querySelectorAll('#privateAccountRows > div').length>0",
            timeout=60000)

        size=page.evaluate("() => ({width:innerWidth,scroll:document.documentElement.scrollWidth})")
        assert size["scroll"]<=size["width"]+3, "horizontal overflow on live account page"
        if js_errors:
            print("LIVE_ACCOUNT_INDEX_JS_ERROR_SAFE",sorted(js_errors,key=lambda o:(o["source"],o["line"],o["kind"])),flush=True)
        assert not js_errors, "uncaught JavaScript error on account-index page"
        print("LIVE_ACCOUNT_INDEX_UI_PASS","client="+label,
              "accounts="+str(expected),"initial_page="+str(first_count),
              "pagination=PASS","filter=PASS","search=PASS","responsive=PASS",
              flush=True)
    finally:
        browser.close()

if __name__=="__main__":
    with sync_playwright() as browser:
        verify(browser.chromium,"desktop-chromium",1440,900)
        verify(browser.webkit,"iphone-webkit",430,932)
