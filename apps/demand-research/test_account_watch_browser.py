"""Chromium integration QA for public account follow-up, dedup and product trends.

Public-source fixture only: fake posts and fake account endpoints. No private
accounts, identity resolution, personal profiling, or user text retention.
Run: python apps/demand-research/test_account_watch_browser.py
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
HTML=(ROOT/"index.html").read_text("utf-8")
FREE=(ROOT/"free_discovery.js").read_text("utf-8")
WATCH=(ROOT/"account_watch.js").read_text("utf-8")
AUTO=(ROOT/"account_auto_analysis.js").read_text("utf-8")
NOW=datetime.now(timezone.utc).isoformat()
BAD_HOST="https://x.com.evil.invalid/test"

def demo_post(idx):
    text=["제품 가격 확인 후기 입니다. 테스트 텍스트 A",
          "제품 가격 확인 후기 입니다. 테스트 텍스트 A",
          "테스트용 공개 게시글 B"][idx]
    return {
       "uri":f"at://did:plc:syntheticaccount/app.bsky.feed.post/{idx+100}",
       "author":{"did":"did:plc:syntheticaccount","handle":"qa-feed.bsky.social","displayName":"Fixture"},
       "record":{"text":"섹트 "+text,"createdAt":NOW},
       "indexedAt":NOW,"embed":{"images":[]},"labels":[]
    }

def run():
    errors=[];bsky_calls=[];latest_calls=[];mast_calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            context=browser.new_context(viewport={"width":390,"height":844})
            page=context.new_page()
            page.on("pageerror",lambda e:errors.append(str(e)[:220]))
            page.route(PAGE,lambda route:route.fulfill(
                status=200,content_type="text/html",body=HTML))
            page.route(PAGE+"free_discovery.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=FREE))
            page.route(PAGE+"account_watch.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=WATCH))
            page.route(PAGE+"account_auto_analysis.js",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=AUTO))
            def public_profiles(r):
                qs=parse_qs(urlparse(r.request.url).query)
                actors=qs.get("actors",[])
                profiles=([{"handle":"qa-feed.bsky.social","did":"did:plc:syntheticaccount",
                            "description":"My other account https://mastodon.social/@qa"}]
                          if "qa-feed.bsky.social" in actors else [])
                r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps({"profiles":profiles}))
            page.route("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles**",public_profiles)
            page.route(PAGE+"assets/*.svg",lambda route:route.fulfill(
                status=200,content_type="image/svg+xml",body="<svg xmlns='http://www.w3.org/2000/svg'></svg>"))
            def keenable(r):
                body=r.request.post_data_json if r.request.method=="POST" else {}
                q=str((body or {}).get("query",""))
                rows=([{"url":"https://x.com/qa_feed/status/1234567890123456789",
                        "title":"synthetic public QA","description":"product"}]
                      if q=="site:x.com/qa_feed/status" else [])
                r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps({"results":rows}))
            page.route("https://api.keenable.ai/v1/search/public",keenable)
            page.route("https://api.fxtwitter.com/status/1234567890123456789",
                lambda r:r.fulfill(status=200,content_type="application/json",
                  headers={"Access-Control-Allow-Origin":"*"},body=json.dumps({"tweet":{
                  "id":"1234567890123456789","text":"섹트 제품 가격 확인 후기 입니다. 테스트 텍스트 A",
                  "created_at":NOW,"author":{"screen_name":"qa_feed","protected":False}}})))
            page.route("https://api.firecrawl.dev/v2/search",lambda r:r.fulfill(
                status=200,content_type="application/json",headers={"Access-Control-Allow-Origin":"*"},
                body='{"success":true,"data":{"web":[]}}'))
            def bsky_search(r):
                bsky_calls.append(parse_qs(urlparse(r.request.url).query))
                r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},
                    body=json.dumps({"posts":[demo_post(i) for i in range(3)]},ensure_ascii=False))
            page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",bsky_search)
            def author_feed(r):
                qs=parse_qs(urlparse(r.request.url).query)
                latest_calls.append(qs)
                posts=[]
                for i in range(2):
                    posts.append({"post":{
                        "uri":f"at://did:plc:syntheticaccount/app.bsky.feed.post/{200+i}",
                        "record":{"text":"제품 가격 확인 후기 입니다. 테스트 텍스트 A" if i==0 else "배송 상품 리뷰 테스트 B",
                                  "createdAt":NOW},
                        "author":{"handle":"qa-feed.bsky.social","did":"did:plc:syntheticaccount"},
                        "indexedAt":NOW}})
                posts.append({"reason":{"$type":"app.bsky.feed.defs#reasonRepost"},"post":{
                    "uri":"at://did:plc:other/app.bsky.feed.post/300",
                    "record":{"text":"다른 사람 리포스트","createdAt":NOW},
                    "author":{"handle":"other.bsky.social","did":"did:plc:other"}}})
                r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps({"feed":posts},ensure_ascii=False))
            page.route("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed**",author_feed)
            def mastodon(r):
                mast_calls.append(r.request.url)
                if "/accounts/lookup" in r.request.url:
                    data={"id":"101","username":"qa","locked":False,
                          "fields":[{"name":"My other account","value":
                          '<a href="https://bsky.app/profile/qa-feed.bsky.social">Bluesky</a>'}]}
                elif "/statuses" in r.request.url:
                    data=[{"id":"111","account":{"id":"101"},"visibility":"public",
                         "created_at":NOW,"content":"<p>제품 리뷰 테스트</p>",
                         "url":"https://mastodon.social/@qa/111"},
                        {"id":"112","account":{"id":"101"},"visibility":"private",
                         "created_at":NOW,"content":"<p>사적 글</p>",
                         "url":"https://mastodon.social/@qa/112"}]
                else:data=[]
                r.fulfill(status=200,content_type="application/json",
                    headers={"Access-Control-Allow-Origin":"*"},body=json.dumps(data))
            page.route("https://mastodon.social/api/v1/accounts/**",mastodon)
            # Existing unrelated public adapters are mocked; watch tests do not
            # assert those adapters' coverage.
            for ptn,body in [
              ("https://mastodon.social/api/v1/timelines/**","[]"),
              ("https://planet.moe/api/**","[]"),
              ("https://twingyeo.kr/api/**","[]"),
              ("https://misskey.io/api/**","[]"),
              ("https://hoto.moe/api/**","[]"),
              ("https://lemmy.world/api/**",'{"posts":[]}'),
              ("https://api.pullpush.io/**",'{"data":[]}')
            ]:
                def route_json(raw):
                    return lambda route:route.fulfill(status=200,content_type="application/json",
                        headers={"Access-Control-Allow-Origin":"*"},body=raw)
                page.route(ptn,route_json(body))
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_selector("article.post",timeout=50000)
            page.wait_for_function("document.getElementById('applyDate').disabled===false",timeout=120000)
            assert page.locator(".primary-views button").count()==2
            assert not page.locator("#accountsView").is_visible()
            page.locator("#viewAccounts").click()
            # UX: a clear sequence instead of five competing technical panels.
            assert page.locator("#accountOverview").is_visible()
            assert page.locator("#accountWatchSection").is_visible()
            assert page.locator("#accountBackupSection").is_visible()
            assert page.locator("#accountAutoMount #intersectionAutoAccounts").count()==1
            assert page.locator("#accountAutoSearch").is_visible()
            assert page.locator("#accountServerData").is_hidden()
            assert page.locator("#accountMoreOptions").evaluate("(el)=>el.open") is False
            labels=page.locator(".account-section-heading h3").all_inner_texts()
            assert labels==["전체 계정 현황","관심 계정 관리","계정 백업"],labels
            assert page.locator("#accountDiscoveredList .account-discovered-card").count()==1
            assert "1개" in page.locator("#accountDiscoveredCount").text_content()
            page.locator("#viewPosts").click()

            assert page.locator("#tabs,[data-term]").count()==0
            page.locator(".post-open").first.click()
            assert page.locator("#detail .account-select-watch").is_visible()
            page.locator("#detail .account-select-watch").click()
            assert page.locator("#accountsView").is_visible()
            assert not page.locator("#postsView").is_visible()
            assert page.locator("#accountMetricTracked").text_content()=="1"
            assert page.locator("#accountWatchList article").count()==1
            page.locator(".account-watch-card").first.get_by_role(
                "button",name="백업 대상으로 선택").click()
            assert page.locator("#targetArchivePlatform").input_value()=="bluesky"
            assert page.locator("#targetArchiveAccount").input_value()==(
                "https://bsky.app/profile/qa-feed.bsky.social")
            assert page.locator("#targetArchiveSubmit").is_enabled()
            assert "백업 대상으로 선택" in page.locator("#accountWatchStatus").inner_text()
            page.wait_for_function("window.localStorage.getItem('intersection:public-account-watch:v1')!==null")
            saved=page.evaluate("JSON.parse(localStorage.getItem('intersection:public-account-watch:v1'))")
            assert saved==["https://bsky.app/profile/qa-feed.bsky.social"],saved
            # Source-based latest public feed: excludes repost from other account,
            # protects against duplicated posts from various discovery adapters.
            page.wait_for_function("document.querySelectorAll('.account-watch-card .account-stats strong').length && document.querySelector('.account-watch-card .account-stats strong').textContent==='5'",timeout=22000)
            assert len(latest_calls)>=1
            assert page.locator("#accountMetricVerified").text_content()=="5"
            page.locator(".account-watch-card button.primary").click()
            assert page.locator("#accountDialog").is_visible()
            body=page.locator("#accountDialogContent").inner_text()
            assert "상품 관련 단어가 있는 고유 글" in body
            assert "다른 사람 리포스트" not in body
            assert page.locator(".account-detail-posts > div").count()==5
            page.locator("#closeAccountDialog").click()
            # A fake login/host-spoof profile cannot be saved.
            page.locator("#accountProfileInput").fill(BAD_HOST)
            page.locator('#accountWatchForm button[type="submit"]').click()
            assert page.locator("#accountMetricTracked").text_content()=="1"
            page.locator("#accountProfileInput").fill("https://x.com/%ZZ")
            page.locator('#accountWatchForm button[type="submit"]').click()
            assert page.locator("#accountMetricTracked").text_content()=="1"
            # Identical handle on a different network is still a *separate
            # account*. It is never silently declared a distinct/new person.
            page.locator("#accountProfileInput").fill("https://x.com/qa_feed")
            page.locator('#accountWatchForm button[type="submit"]').click()
            assert page.locator("#accountMetricTracked").text_content()=="2"
            assert page.locator("#accountWatchList article").count()==2
            page.wait_for_function("document.querySelector('#accountMetricVerified').textContent==='6'",timeout=20000)
            assert int(page.locator("#accountMetricRepeat").text_content())>=2
            assert page.locator("#accountMetricCommerce").text_content()!=""

            assert "SNS 계정 수는 사람 수가 아닙니다" in page.locator(".account-analysis-note").text_content()
            # Add a public Mastodon account with a private status fixture: only
            # explicitly public statuses may appear in analysis.
            page.locator("#accountProfileInput").fill("https://mastodon.social/@qa")
            page.locator('#accountWatchForm button[type="submit"]').click()
            page.wait_for_function("document.querySelectorAll('.account-watch-card').length===3",timeout=15000)
            page.wait_for_function("document.querySelector('#accountMetricVerified').textContent==='7'",timeout=20000)
            assert len(mast_calls)>=2
            assert "사적 글" not in page.locator("#accountWatchList").inner_text()
            page.locator(".account-watch-card").filter(has_text="Mastodon").get_by_role(
                "button",name="백업 대상으로 선택").click()
            assert page.locator("#targetArchivePlatform").input_value()=="mastodon"
            assert page.locator("#targetArchiveAccount").input_value()==(
                "https://mastodon.social/@qa")
            assert page.locator("#targetArchiveSubmit").is_enabled()
            # Persistence: only profile URLs survive refresh. No content text.
            page.reload(wait_until="domcontentloaded",timeout=30000)
            page.locator("#viewAccounts").click()
            assert page.locator("#accountMetricTracked").text_content()=="3"
            saved=page.evaluate("JSON.parse(localStorage.getItem('intersection:public-account-watch:v1'))")
            assert len(saved)==3 and all(isinstance(s,str) for s in saved)
            page.locator("#accountWatchSearch").fill("mastodon")
            page.wait_for_function("document.querySelectorAll('#accountWatchList article').length===1",timeout=8000)
            assert page.locator("#accountWatchList article").count()==1
            page.locator("#accountWatchSearch").fill("")
            page.locator(".account-watch-card .danger").first.click()
            assert page.locator("#accountMetricTracked").text_content()=="2"
            # Account audit works without the user choosing profiles to track.
            # 20,000 distinct synthetic accounts test no 36/80-record audit cap.
            page.wait_for_function("window.INTERSECTION_autoAccountStats && window.INTERSECTION_autoAccountStats().scanFinished",timeout=25000)
            page.evaluate("""() => {
              const verified=[{profileUrl:'https://bsky.app/profile/qa-feed.bsky.social'},
                {profileUrl:'https://mastodon.social/@qa'}];
              for(let i=0;i<20000;i++)
                verified.push({profileUrl:'https://bsky.app/profile/qa-'+i+'.bsky.social'});
              window.INTERSECTION_publicAccountSnapshot=()=>({verified,candidates:[]});
              window.dispatchEvent(new Event('intersection:feed-updated'));
            }""")
            page.wait_for_function("window.INTERSECTION_autoAccountStats().accountCount===20002",timeout=15000)
            assert page.locator("#accountAutoRows > div").count()==12
            page.locator("#accountAutoMore").click()
            assert page.locator("#accountAutoRows > div").count()==24
            page.wait_for_function("window.INTERSECTION_autoAccountStats().linkGroups===1",timeout=35000)
            assert page.locator("#accountAutoGroups article").count()==1
            assert "20,002" in page.locator("#accountAutoSummary").inner_text()
            assert page.locator("#accountAutoGroups article a").count()==2
            page.locator("#accountAutoSearch").fill("qa-19999")
            assert page.locator("#accountAutoRows > div").count()==1
            assert "qa-19999.bsky.social" in page.locator("#accountAutoRows").inner_text()
            page.locator("#accountAutoSearch").fill("")
            assert page.locator("#accountAutoRows > div").count()==12
            # A narrow phone must not require sideways scrolling.
            width=page.evaluate("({scroll:document.documentElement.scrollWidth,viewport:innerWidth})")
            assert width["scroll"]<=width["viewport"]+2,width
            assert not errors,errors
            print("PUBLIC_ACCOUNT_WATCH_BROWSER_QA",json.dumps({
              "tabs":2,"discovered_source_accounts_visible":True,"opt_in_profiles_saved":3,"bluesky_direct_public_feed":True,
              "mastodon_direct_public_feed":True,"x_original_public_post_verified":True,
              "cross_account_duplicate_content_removed":True,"private_rows_excluded":True,
              "cross_platform_identity_inference":False,"auto_accounts_discovered":20002,
              "reciprocal_public_link_groups":1,"no_manual_selection_required":True,
              "malicious_urls_blocked":True,
              "post_history_persisted":False,"reload_persistence":True,
              "errors":len(errors)
            }),flush=True)
        finally:browser.close()
if __name__=="__main__":run()
