"""Synthetic browser integration for the one-click all-SNS free search + dated X feed.
Not a live dataset test: live-source correctness is measured by separate probes.
"""
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import parse_qs,urlparse,unquote
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
HTML=(ROOT/"index.html").read_text(encoding="utf-8")
JS=(ROOT/"free_discovery.js").read_text(encoding="utf-8")
URLS={
"x":"https://x.com/qa/status/1234567890123456789",
"threads":"https://www.threads.com/@qa/post/C123fake",
"instagram":"https://www.instagram.com/p/C456fake"
}
def run():
    errors=[];calls=[];now=datetime.now(timezone.utc).isoformat()
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=b.new_page(viewport={"width":390,"height":844})
            page.on("pageerror",lambda error: errors.append(str(error)[:160]))
            page.route(PAGE,lambda r:r.fulfill(status=200,content_type="text/html",body=HTML))
            page.route(PAGE+"free_discovery.js",lambda r:r.fulfill(status=200,
                content_type="application/javascript",body=JS))
            page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",
                lambda r:r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body='{"posts":[]}'))
            def search(r,engine):
                if r.request.method=="OPTIONS":
                    r.fulfill(status=204,headers={"Access-Control-Allow-Origin":"*",
                        "Access-Control-Allow-Methods":"POST,OPTIONS",
                        "Access-Control-Allow-Headers":"content-type,x-keenable-title"});return
                body=r.request.post_data_json
                assert " OR " in body["query"]
                network=next((n for n,h in (("threads","threads.com"),("instagram","instagram.com"),
                    ("x","x.com")) if "site:"+h in body["query"]),None)
                assert network
                calls.append(engine+"-"+network)
                record={"url":URLS[network],"title":"섹트 synthetic public "+network+" example",
                        "description":"Synthetic QA result with target term"}
                result={"results":[record]} if engine=="keenable" else {"success":True,"data":{"web":[record]}}
                r.fulfill(status=200,content_type="application/json",headers={
                    "Access-Control-Allow-Origin":"*"},body=json.dumps(result))
            page.route("https://api.keenable.ai/v1/search/public",
                lambda r:search(r,"keenable"))
            page.route("https://api.firecrawl.dev/v2/search",
                lambda r:search(r,"firecrawl"))
            def fetch(r):
                if r.request.method=="OPTIONS":
                    r.fulfill(status=204,headers={"Access-Control-Allow-Origin":"*",
                        "Access-Control-Allow-Headers":"x-keenable-title",
                        "Access-Control-Allow-Methods":"GET,OPTIONS"});return
                orig=parse_qs(urlparse(r.request.url).query)["url"][0]
                result={"url":orig,"content":"섹트 synthetic public origin text",
                    "title":"Synthetic page test","published_at":now}
                r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps(result))
            page.route("https://api.keenable.ai/v1/fetch/public?*",fetch)
            page.route("https://api.fxtwitter.com/status/*",
                lambda r:r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps({
                        "tweet":{"id":"1234567890123456789","text":"섹트 synthetic X original body",
                            "created_at":now,"author":{"screen_name":"qa","protected":False}}
                    })))
            # Federated adapters are outside this all-source index-search QA.
            page.route("https://mastodon.social/api/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body="[]",
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route("https://planet.moe/api/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body="[]",
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route("https://twingyeo.kr/api/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body="[]",
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route("https://lemmy.world/api/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body='{"posts":[]}',
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route("https://misskey.io/api/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body="[]",
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route("https://hoto.moe/api/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body="[]",
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route("https://api.pullpush.io/**",
                lambda r:r.fulfill(status=200,content_type="application/json",body='{"data":[]}',
                    headers={"Access-Control-Allow-Origin":"*"}))
            page.route(PAGE+"assets/*.svg",
                lambda r:r.fulfill(status=200,content_type="image/svg+xml",
                    body='<svg xmlns="http://www.w3.org/2000/svg"></svg>'))
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            assert page.locator("#indexPlatform").input_value()=="all"
            assert page.locator("#indexTerm").input_value()=="all"
            assert page.locator("#tabs,[data-term]").count()==0
            page.locator("#indexFind").click()
            page.wait_for_function("document.getElementById('indexFind').disabled===false",timeout=90000)
            cards=page.locator("#indexResults article.index-result")
            assert cards.count()==3,cards.count()
            assert len(calls)==6,calls
            for name in ("X","Threads","Instagram"):
                assert page.locator('#indexResults .index-origin').filter(has_text=name).count()==1
            assert page.locator("#indexStatus").inner_text().find("공개 원문/페이지 확인 3건")>=0
            page.wait_for_selector('article.post .source-badge[aria-label="출처: X"]',timeout=15000)
            assert "X1" in page.locator("#count").text_content()
            assert page.locator("#freeDiscovery").bounding_box()["y"] < page.locator("#feed").bounding_box()["y"]
            assert not errors,errors
            print("ALL_SOCIAL_FREE_BROWSER_FIXTURE",json.dumps({"indexed_candidates":cards.count(),
                "search_provider_calls":len(calls),"origin_text_confirmed":3,
                "verified_dated_x_in_main_feed":1,"errors":len(errors)}))
        finally:b.close()
if __name__=="__main__":run()
