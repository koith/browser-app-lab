"""Browser-local WebKit/Chromium regression for account search reset.

All handles and posts here are synthetic. No live cloud reads or user data.
This covers the search-input clear gesture without blur, which WebKit previously
ignored, while preserving filter and cursor semantics.
"""
import json
from urllib.parse import parse_qs,urlsplit
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
APP_JS=(ROOT/"account_index_client.js").read_text(encoding="utf-8")
ORIGIN="https://intersection-qa.invalid/"
HTML="""<!doctype html><html lang="ko"><head><meta charset="utf-8"></head><body>
<button id="viewAccounts" type="button">계정 분석</button>
<section id="accountsView">
  <details id="accountServerData" hidden>
    <summary>서버 계정 인덱스</summary>
    <div id="privateAccountIndexMount"></div>
  </details>
</section>
<script src="/account_index_client.js" defer></script>
</body></html>"""
ROWS=([{"platform":"bluesky",
        "profileUrl":"https://bsky.app/profile/qa%d.bsky.social"%i,
        "verified_posts":i+1} for i in range(160)]
      +[{"platform":"x","profileUrl":"https://x.com/qa%d"%i,
         "verified_posts":1} for i in range(40)])


def run_case(engine,name):
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":430,"height":932})
        errors=[]
        queries=[]
        page.on("pageerror",lambda error:errors.append(type(error).__name__))
        page.route(ORIGIN,lambda route:route.fulfill(
            status=200,content_type="text/html",body=HTML))
        page.route(ORIGIN+"account_index_client.js",lambda route:route.fulfill(
            status=200,content_type="application/javascript",body=APP_JS))
        page.route(ORIGIN+"api/accounts/status",lambda route:route.fulfill(
            status=200,content_type="application/json",
            body=json.dumps({"accounts":200,"source_rows":350,
                             "refreshing":False,"remote_snapshot_verified":True})))
        def account_page(route):
            query=parse_qs(urlsplit(route.request.url).query)
            offset=int(query.get("offset",["0"])[0])
            limit=int(query.get("limit",["80"])[0])
            platform=query.get("platform",[""])[0]
            term=query.get("q",[""])[0]
            queries.append({"offset":offset,"query_empty":not bool(term),
                            "platform":platform})
            rows=[row for row in ROWS if
                  (not platform or row["platform"]==platform)
                  and (not term or term in row["profileUrl"])]
            route.fulfill(status=200,content_type="application/json",
                          body=json.dumps({"items":rows[offset:offset+limit],
                                           "total":len(rows)}))
        page.route(ORIGIN+"api/accounts?*",account_page)
        page.goto(ORIGIN,wait_until="domcontentloaded",timeout=15000)
        page.locator("#viewAccounts").click()
        page.wait_for_function(
            "() => document.querySelectorAll('#privateAccountRows > div').length===80",
            timeout=18000)
        assert not page.locator("#accountServerData").evaluate("(el) => el.open")
        page.locator("#accountOverview > summary").click()
        page.locator("#accountServerData > summary").click()
        assert page.locator("#accountServerData").evaluate("(el) => el.open")
        page.locator(".account-auto-more").click()
        page.wait_for_function(
            "() => document.querySelectorAll('#privateAccountRows > div').length===160",
            timeout=15000)
        page.locator("#privateAccountIndex select").select_option("bluesky")
        page.wait_for_function(
            "() => [...document.querySelectorAll('#privateAccountRows a')].length===80"
            " && [...document.querySelectorAll('#privateAccountRows a')]"
            ".every(a => a.href.startsWith('https://bsky.app/profile/'))",
            timeout=15000)
        search=page.locator("#privateAccountIndex input")
        search.fill("qa-phrase-with-zero-matches")  # Do not press Tab or blur.
        page.wait_for_function(
            "() => document.querySelector('#privateAccountRows')"
            "?.textContent?.includes('일치하는 보관 계정이 없습니다.')",
            timeout=15000)
        search.fill("")  # Safari's search clear must fetch WITHOUT blur.
        page.wait_for_function(
            "() => document.querySelectorAll('#privateAccountRows > div').length===80"
            " && [...document.querySelectorAll('#privateAccountRows a')]"
            ".every(a => a.href.startsWith('https://bsky.app/profile/'))",
            timeout=15000)
        assert any(q["query_empty"] is False for q in queries)
        assert queries[-1]["query_empty"] is True
        assert queries[-1]["platform"]=="bluesky"
        assert not errors, "Unexpected JavaScript exception in synthetic index UI"
        print("ACCOUNT_SEARCH_RESET_PASS",name,"filters=PASS",
              "pagination=PASS","input_clear_without_blur=PASS",
              "javascript_errors=0","requests="+str(len(queries)),flush=True)
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        run_case(p.chromium,"chromium")
        run_case(p.webkit,"mobile_webkit")
