"""INTERSECTION auto SNS -> one feed QA (fixture and real no-key browser).

Fixture: 3 networks search automatically, 6 provider calls, unverified links
listed separately from verified posts, genuine public X media promoted, date change
replays only originals, no separate user-facing search UI.
Live: no synthetic provider replies, aggregate statistics only, no user data.
"""
import json,sys,base64
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
HTML=(ROOT/"index.html").read_text(encoding="utf-8")
JS=(ROOT/"free_discovery.js").read_text(encoding="utf-8")
LIVE="--live" in sys.argv
PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGPUit7yn4GBgYGJAQoAIS4CPGFQl4cAAAAASUVORK5CYII=")
X_ID="1234567890123456789"
X_OTHER="9876543210123456789"
LINKS={
  "x":"https://x.com/qa/status/"+X_ID,
  "threads":"https://www.threads.com/@qa/post/C123fake",
  "instagram":"https://www.instagram.com/p/C456fake"
}

def setup_federated(page):
    for base,response in [
      ("https://mastodon.social/api/**","[]"),
      ("https://planet.moe/api/**","[]"),
      ("https://twingyeo.kr/api/**","[]"),
      ("https://lemmy.world/api/**",'{"posts":[]}'),
      ("https://misskey.io/api/**","[]"),
      ("https://hoto.moe/api/**","[]"),
      ("https://api.pullpush.io/**",'{"data":[]}')
    ]:
        def make_handler(raw):
            return lambda route:route.fulfill(
                status=200,content_type="application/json",
                headers={"Access-Control-Allow-Origin":"*"},body=raw)
        page.route(base,make_handler(response))
def run():
    errors=[];calls=[];now=datetime.now(timezone.utc).isoformat()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":390,"height":844})
            page.on("pageerror",lambda error:errors.append(str(error)[:130]))
            page.route(PAGE,lambda r:r.fulfill(status=200,content_type="text/html",body=HTML))
            page.route(PAGE+"free_discovery.js",lambda r:r.fulfill(
                status=200,content_type="application/javascript",body=JS))
            page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",
                lambda r:r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body='{"posts":[]}'))
            setup_federated(page)
            if not LIVE:
                def search(route,engine):
                    if route.request.method=="OPTIONS":
                        route.fulfill(status=204,headers={
                            "Access-Control-Allow-Origin":"*",
                            "Access-Control-Allow-Methods":"POST,OPTIONS",
                            "Access-Control-Allow-Headers":"content-type,x-keenable-title"})
                        return
                    payload=route.request.post_data_json
                    assert " OR " in payload["query"],"All topic terms must be combined"
                    network=next((n for n,h in (("threads","threads.com"),
                        ("instagram","instagram.com"),("x","x.com"))
                        if "site:"+h in payload["query"]),None)
                    assert network
                    calls.append(engine+"-"+network)
                    if network=="x":
                        rows=[
                          {"url":LINKS["x"],"title":"섹트 synthetic indexed public original",
                           "description":"Public QA"},
                          {"url":"https://twitter.com/other/status/"+X_OTHER,
                           "title":"Unverified indexed X candidate", "description":"Source term unknown"},
                          {"url":"https://x.com.evil.invalid/qa/status/1111111111111111111",
                           "title":"섹트 host spoof"},
                          {"url":"http://x.com/qa/status/1111111111111111111",
                           "title":"섹트 insecure HTTP"}
                        ]
                    else:
                        rows=[{"url":LINKS[network],"title":"Public "+network+" link",
                               "description":"Await source page verification"}]
                    content={"results":rows} if engine=="keenable" else \
                        {"success":True,"data":{"web":rows}}
                    route.fulfill(status=200,content_type="application/json",
                       headers={"Access-Control-Allow-Origin":"*"},body=json.dumps(content))
                page.route("https://api.keenable.ai/v1/search/public",
                           lambda r:search(r,"keenable"))
                page.route("https://api.firecrawl.dev/v2/search",
                           lambda r:search(r,"firecrawl"))
                def free_page(route):
                    link=parse_qs(urlparse(route.request.url).query)["url"][0]
                    route.fulfill(status=200,content_type="application/json",
                        headers={"Access-Control-Allow-Origin":"*"},
                        body=json.dumps({"url":link,"content":"섹트 synthetic PUBLIC PAGE TEXT",
                                         "title":"fixture","published_at":None}))
                page.route("https://api.keenable.ai/v1/fetch/public?*",free_page)
                def x_public(route):
                    post=route.request.url.rsplit("/",1)[-1]
                    if post!=X_ID:
                        route.fulfill(status=404,content_type="application/json",body='{}');return
                    route.fulfill(status=200,content_type="application/json",
                        headers={"Access-Control-Allow-Origin":"*"},
                        body=json.dumps({"tweet":{
                            "id":X_ID,"text":"섹트 synthetic verified public original",
                            "created_at":now,
                            "created_timestamp":int(datetime.now(timezone.utc).timestamp()),
                            "author":{"screen_name":"qa","protected":False,
                                      "avatar_url":"https://example.com/qa-avatar.jpg"},
                            "media":{"photos":[{"url":"https://example.com/qa.jpg"}],
                                     "videos":[{"url":"https://example.com/qa.mp4",
                                                "thumbnail_url":"https://example.com/qa-video.jpg"}]}
                        }}))
                page.route("https://api.fxtwitter.com/*/status/*",x_public)
                page.route("https://example.com/*.jpg",
                    lambda route:route.fulfill(status=200,content_type="image/png",
                      body=PNG))
            else:
                page.on("response",lambda response:calls.append({
                    "host":urlparse(response.url).hostname,
                    "status":response.status})
                    if urlparse(response.url).hostname in {
                        "api.keenable.ai","api.firecrawl.dev","api.fxtwitter.com"} and
                        response.request.method in ("POST","GET") else None)
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            assert page.locator("#freeDiscovery,#indexFind,#indexPlatform,#indexResults").count()==0
            assert page.locator("header .header-period #openDate").is_visible()
            assert page.locator("#tabs,[data-term]").count()==0
            page.wait_for_function(
              "window.INTERSECTION_autoCoverageStatus?.completed === true",timeout=160000)
            assert not errors,errors
            cards=page.locator('article.post[data-discovery-candidate="true"]')
            discovered=page.locator("#discoveryCandidateList a")
            verified=page.locator('article.post:not([data-discovery-candidate]) .source-badge[aria-label="출처: X"]')
            if LIVE:
                counts={label:discovered.filter(has_text=label).count()
                    for label in ("X","Threads","Instagram")}
                raw=page.evaluate("window.INTERSECTION_autoCoverageStatus")
                print("AUTO_UNIFIED_SNS_LIVE",json.dumps({
                    "visible_index_candidates":discovered.count(),
                    "by_source":counts,
                    "verified_date_scoped_x":verified.count(),
                    "sources_checked":raw["sources"],
                    "provider_http":[c["status"] for c in calls if c.get("status")],
                    "errors":len(errors)
                },ensure_ascii=False),flush=True)
            else:
                assert len(calls)==6,calls
                # Dedup 2 providers across 4 canonical links; X valid
                # promoted, other three remain as *undated* candidates.
                assert cards.count()==0,"search snippets must not be shown as dated post cards"
                assert discovered.count()==3,discovered.count()
                assert page.locator("#discoveryCandidates").is_visible()
                assert verified.count()==1
                assert "원문 미확인 링크 3건" in page.locator("#count").text_content()
                xcard=page.locator("article.post").filter(
                    has=page.locator('.source-badge[aria-label="출처: X"]')).first
                assert xcard.locator(".post-thumb > img").count()==1, "public X image must be shown"
                assert page.locator("article.post .post-date").filter(
                    has_text="작성일 미확인").count()==0
                assert page.locator("a[href*='evil.invalid']").count()==0
                assert page.locator("a[href^='http://']").count()==0
                # Manual period change should NOT fabricate dates for
                # search index cards and should replay only genuine X.
                page.locator("#openDate").click()
                page.fill("#startDate","2025-02-01")
                page.fill("#endDate","2025-02-02")
                page.locator("#applyDate").click()
                page.wait_for_function(
                    "document.getElementById('applyDate').disabled===false",timeout=30000)
                assert discovered.count()==3,"search leads remain without invented dates"
                assert page.locator(
                    'article.post .source-badge[aria-label="출처: X"]').count()==0
                page.locator("#openDate").click()
                page.locator('#dateDialog button[data-days="7"]').click()
                page.locator("#applyDate").click()
                page.wait_for_function(
                    "document.getElementById('applyDate').disabled===false",timeout=30000)
                assert page.locator(
                    'article.post .source-badge[aria-label="출처: X"]').count()==1
                print("AUTO_UNIFIED_SNS_FIXTURE",json.dumps({
                    "provider_search_calls":len(calls),
                    "undated_candidate_links":3,
                    "real_dated_x_cards":1,
                    "date_filter_replay":"pass",
                    "no_search_controls":True,
                    "errors":len(errors)
                }),flush=True)
        finally:browser.close()
if __name__=="__main__":run()
