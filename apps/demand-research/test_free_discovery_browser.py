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
                    {"url":"https://x.com/example/status/1234567890123456789","title":"섹트 synthetic indexed result","description":"Synthetic only"},
                    {"url":"https://x.com.evil.example/example/status/999","title":"섹트 bad spoof URL"},
                    {"url":"http://x.com/example/status/321","title":"섹트 http disallowed"}
                ]
                if provider=="keenable":
                    rows.append({"url":"https://x.com/example2/status/9876543210123456789","title":"Other index result"})
                else:
                    rows.append({"url":"https://twitter.com/example3/status/7777777770123456789","description":"섹트 next candidate"})
                data={"results":rows} if provider=="keenable" else {"success":True,"data":{"web":rows}}
                route.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps(data))
            if not LIVE:
                page.route("https://api.fxtwitter.com/status/1234567890123456789",
                    lambda route:route.fulfill(status=200,content_type="application/json",
                        headers={"Access-Control-Allow-Origin":"*"},
                        body=json.dumps({"tweet":{"id":"1234567890123456789",
                            "text":"섹트 synthetic original public record",
                            "created_at":"2026-11-02T00:00:00Z",
                            "author":{"screen_name":"example","protected":False}}})))
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
            page.select_option("#indexPlatform","all" if LIVE else "x")
            page.select_option("#indexTerm","all" if LIVE else "섹트")
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
                page.locator(".index-result").filter(
                    has=page.locator("a[href='https://x.com/example/status/1234567890123456789']")
                    ).locator(".index-check").click()
                page.wait_for_function("""() =>
                    document.querySelector('.index-verify-result')?.textContent?.includes(
                        '섹트 synthetic original public record')""",timeout=20000)
                assert "공개 원문 확인" in page.locator(".index-verify-result").first.inner_text()
                page.wait_for_selector('article.post .source-badge[aria-label="출처: X"]',timeout=20000)
                assert page.locator("article.post").count()==1
                assert "X1" in page.locator("#count").text_content()
                print("INDEX_DISCOVERY_BROWSER_FIXTURE",json.dumps({"cards":n,"verified_x_feed":1,"paid_keys":0,
                      "canonical_safe":True,"dedup":True,"errors":len(errors)}))
            else:
                public_x=page.evaluate("""async () => {
                    const services=[
                        "https://api.fxtwitter.com/status/20",
                        "https://api.vxtwitter.com/Twitter/status/20"
                    ];
                    const output=[];
                    for(const endpoint of services){
                        try{
                            const res=await fetch(endpoint,{mode:"cors",credentials:"omit"});
                            const data=await res.json();
                            output.push({http:res.status,public_original:!!(data.tweet?.id||data.tweetID)});
                        }catch(error){output.push({error:"Browser CORS or network blocked"});}
                    }
                    return output;
                }""")
                # Expand every indexed candidate without storing any user identifiers.
                for _ in range(15):
                    if not page.locator("#indexMore").is_visible():break
                    page.locator("#indexMore").click()
                all_cards=page.locator("#indexResults .index-result")
                by_source={k:page.locator("#indexResults .index-origin").filter(
                    has_text=k).count() for k in ("X","Threads","Instagram")}
                confirmed=page.locator("article.post .source-badge[aria-label='출처: X']").count()
                checked=page.locator("#indexResults .index-indexed").filter(
                    has_text="텍스트 확인").count()
                print("INDEX_DISCOVERY_BROWSER_LIVE",json.dumps({"cards":all_cards.count(),
                    "by_source":by_source,"verified_date_scoped_x_feed":confirmed,
                    "third_party_page_text_confirmed":checked,
                    "status_contains_error":("응답 실패" in msg or "오류" in msg),
                    "http_codes":[x.get("status") for x in upstream if x.get("status")],
                    "public_x_read":public_x,"errors":len(errors)}))
        finally:browser.close()

if __name__=="__main__":run()
