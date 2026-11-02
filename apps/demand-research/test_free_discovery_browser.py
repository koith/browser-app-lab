"""Browser QA for zero-key, separate indexed SNS candidates (synthetic and live).

Synthetic mode asserts safe canonical URL validation, cross-provider dedup,
visible status warning, profile links and zero paid credentials. Live mode uses
exactly two anonymous provider calls in Chromium, prints only aggregate counts.
"""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
ROOT=Path(__file__).resolve().parent
HTML=(ROOT/"index.html").read_text(encoding="utf-8")
JS=(ROOT/"free_discovery.js").read_text(encoding="utf-8")
LIVE="--live" in sys.argv

def run():
    errors=[];upstream=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":390,"height":844})
            page.on("pageerror",lambda err:errors.append(str(err)[:100]))
            page.route(PAGE,lambda route:route.fulfill(status=200,content_type="text/html",body=HTML))
            page.route(PAGE+"free_discovery.js",lambda route:route.fulfill(status=200,
                content_type="application/javascript",body=JS))
            # The usual Bluesky auto-loading is unrelated to this manual index-search test.
            page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",
                lambda route:route.fulfill(status=200,content_type="application/json",
                  headers={"Access-Control-Allow-Origin":"*"},body='{"posts":[]}'))
            def api(route,provider):
                upstream.append({"provider":provider,"method":route.request.method})
                if route.request.method=="OPTIONS":
                    route.fulfill(status=204,headers={
                        "Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"POST,OPTIONS",
                        "Access-Control-Allow-Headers":"content-type,x-keenable-title"})
                    return
                assert not route.request.headers.get("authorization"),"No paid key allowed"
                body=route.request.post_data_json
                assert "섹트" in body["query"]
                rows=[
                    {"url":"https://x.com/example/status/12345678","title":"섹트 synthetic indexed result","description":"Synthetic only"},
                    {"url":"https://x.com.evil.example/example/status/999","title":"섹트 bad spoof URL"},
                    {"url":"http://x.com/example/status/321","title":"섹트 http disallowed"}
                ]
                if provider=="keenable":
                    rows.append({"url":"https://x.com/example2/status/987654","title":"Other index result"})
                else:
                    rows.append({"url":"https://twitter.com/example3/status/777777","description":"섹트 next candidate"})
                data={"results":rows} if provider=="keenable" else {"success":True,"data":{"web":rows}}
                route.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps(data))
            if not LIVE:
                page.route("https://api.keenable.ai/v1/search/public",lambda route:api(route,"keenable"))
                page.route("https://api.firecrawl.dev/v2/search",lambda route:api(route,"firecrawl"))
            else:
                page.on("response",lambda resp:upstream.append({"provider":"firecrawl" if
                    "firecrawl.dev" in resp.url else "keenable","method":"POST","status":resp.status})
                    if ("firecrawl.dev" in resp.url or "keenable.ai" in resp.url)
                    and resp.request.method=="POST" else None)
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_selector("#freeDiscovery:not(.hidden)",timeout=20000)
            assert page.locator("#indexResults .index-result").count()==0
            assert page.locator("#indexStatus").inner_text().find("자동·유료 검색은 실행하지 않습니다")>=0
            page.select_option("#indexPlatform","x")
            page.select_option("#indexTerm","섹트")
            page.locator("#indexFind").click()
            page.wait_for_function("document.getElementById('indexFind').disabled === false",timeout=90000)
            n=page.locator("#indexResults .index-result").count()
            msg=page.locator("#indexStatus").inner_text()
            assert "원문" in msg and "미확인" in msg, msg
            assert not errors,errors
            if not LIVE:
                assert n==3,{"count":n,"status":msg}
                assert page.locator("#indexResults a[href^='http://']").count()==0
                assert page.locator("#indexResults a[href*='evil.example']").count()==0
                assert page.locator("#indexResults a").filter(has_text="작성자 프로필").count()==3
                assert page.locator("#indexResults .index-indexed").count()>=3
                assert len([x for x in upstream if x["method"]=="POST"])==2
                print("INDEX_DISCOVERY_BROWSER_FIXTURE",json.dumps({"cards":n,"paid_keys":0,
                      "canonical_safe":True,"dedup":True,"errors":len(errors)}))
            else:
                print("INDEX_DISCOVERY_BROWSER_LIVE",json.dumps({"cards":n,
                    "status_contains_error":("응답 실패" in msg or "오류" in msg),
                    "http_codes":[x.get("status") for x in upstream if x.get("status")],
                    "errors":len(errors)}))
        finally:browser.close()

if __name__=="__main__":run()
