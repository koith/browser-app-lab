"""Browser QA: 3-column gallery, modal, date sharding, no password.
Synthetic mode never stores real third-party posts. Live mode returns counts only.
"""
import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

HTML=Path(__file__).with_name("index.html").read_text(encoding="utf-8")
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
TERMS=("뒷계","섹트","일탈계")
PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGPUit7yn4GBgYGJAQoAIS4CPGFQl4cAAAAASUVORK5CYII=")

def fake_post(term, i=1):
    return {
      "uri":f"at://did:plc:synthetic{term}{i}/app.bsky.feed.post/{i+100}",
      "author":{"did":"did:plc:safe-synthetic", "handle":"sample.invalid", "displayName":"TEST"},
      "record":{"text":term+(" 광고 판매 홍보 할인 구독 문의 텔레그램 "+str(i) if i%15==0 else " synthetic QA sample without personal details "+str(i)),
                "createdAt":datetime.now(timezone.utc).isoformat()},
      "indexedAt":datetime.now(timezone.utc).isoformat(),
      "labels":([{"val":"porn"}] if i%15==1 else
                [{"val":"graphic-media"}] if i%15==2 else
                [{"val":"!hide"}] if i%15==3 else []),
      "embed":{"$type":"app.bsky.embed.images#view","images":[{
        "fullsize":"https://example.com/qa.png",
        "thumb":"https://example.com/qa.png","alt":"QA fixture"}]}
    }

def run(live=False):
    errors=[]
    api_calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":1200,"height":900})
            page.on("pageerror",lambda error:errors.append(str(error)[:200]))
            page.route(PAGE,lambda route:route.fulfill(status=200,
                      content_type="text/html; charset=utf-8",body=HTML))
            if not live:
                def mock_api(route):
                    u=urlparse(route.request.url)
                    q=parse_qs(u.query)
                    term=q.get("q",[""])[0]
                    api_calls.append(q)
                    day=int(q.get("since",["2026-11-01"])[0][8:10])
                    records=[fake_post(term,day*100+i) for i in range(15)] if term in TERMS else []
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body=json.dumps({"posts":records},ensure_ascii=False))
                page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",mock_api)
                page.route("https://example.com/qa.png",
                    lambda route:route.fulfill(status=200,body=PNG,content_type="image/png"))
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_selector("article.post",timeout=60000)
            page.wait_for_function("document.getElementById('refresh').disabled === false",timeout=120000)
            n=page.locator("article.post").count()
            imgs=page.locator("article.post img").count()
            pwd=page.locator("input[type=password], #login").count()
            assert pwd==0,"Unexpected password/login UI"
            assert page.locator('input[type="date"]').count()==2
            cols=page.locator("#feed").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")
            assert cols==3,f"Expected desktop three columns, got {cols}"
            assert page.locator(".halftone").count()==2
            assert page.locator("#filterDetails").count()==1
            assert page.locator("#dateDisclosure").count()==1
            assert page.locator("#dateDisclosure").evaluate("e=>!e.open"),"Date controls should start compact"
            assert page.locator("#filterDetails").evaluate("e=>!e.open"),"Filters should start compact"
            assert page.locator("body").evaluate("e=>getComputedStyle(e).color")=="rgb(23, 24, 21)"
            assert page.locator(".halftone-a").evaluate("e=>getComputedStyle(e).animationName")=="dot-drift"
            assert page.locator("#showAdultMedia").is_checked()
            # Advanced switches stay collapsed until deliberately opened.
            page.locator("#filterDetails summary").click()
            assert page.locator("#filterDetails").evaluate("e=>e.open")
            assert page.locator("input[type=password]").count()==0
            adult=page.locator('article[data-media-policy="adult"]')
            restricted=page.locator('article[data-media-policy="restricted"]')
            adult_thumb=adult.locator("img").count()
            assert restricted.locator("img").count()==0, "Restricted media must not be previewed"
            if live:
                assert n>=1,f"Expected public results, saw {n} posts"
                # Warn-class adult labels are no longer blanked by app code.
                if adult.count():
                    assert adult_thumb>=1,"Public adult-labeled media with thumbnails should display"
                assert page.locator("#count").inner_text().find("조회")!=-1
                page.locator(".post-open").first.click()
                assert page.locator("dialog#detail").is_visible()
                assert page.locator("#detailContent .dialog-text").inner_text().strip()
                page.locator("#closeDetail").click()
            else:
                assert n==270,f"Expected first 270 of 315 synthetic posts; saw {n}"
                assert 200<=imgs<270,f"Expected visible adult media but blocked graphic labels: {imgs}"
                assert adult.count()>0 and adult_thumb>0,"Available adult-labeled images must display"
                assert restricted.count()>0
                adult.first.locator(".post-open").click()
                assert page.locator("#detailContent .dialog-media img").count()>0
                page.locator("#closeDetail").click()
                page.locator("#showAdultMedia").uncheck()
                assert page.locator('article[data-media-policy="adult"] img').count()==0
                page.locator('article[data-media-policy="adult"] .post-open').first.click()
                assert "성인 미디어 표시가 꺼져" in page.locator("#detailContent .dialog-notice").inner_text()
                page.locator("#closeDetail").click()
                page.locator("#showAdultMedia").check()
                assert page.locator('article[data-media-policy="adult"] img').count()>0
                assert page.locator('article[data-media-policy="restricted"] img').count()==0
                page.locator('article[data-media-policy="restricted"] .post-open').first.click()
                assert "서비스 제한" in page.locator("#detailContent .dialog-notice").inner_text()
                assert page.locator("#detailContent .dialog-media img").count()==0
                page.locator("#closeDetail").click()
                assert len(api_calls)>=21, f"Expected daily shards, got {len(api_calls)}"
                assert "315개 조회" in page.locator("#count").inner_text()
                assert page.locator("#hideAds").is_checked()
                assert "광고 의심 21건" in page.locator("#adSummary").inner_text()
                assert page.locator("#showMore").is_visible()
                page.locator("#showMore").click()
                assert page.locator("article.post").count()==294
                page.locator("#hideAds").uncheck()
                assert page.locator("article.post").count()==270
                page.locator("#showMore").click()
                assert page.locator("article.post").count()==315
                assert page.locator(".post-ad-marker").count()>=1
                page.locator(".post-ad-marker").first.click()
                assert page.locator("dialog#detail").is_visible()
                assert "광고 의심" in page.locator("#detailContent .ad-detail").inner_text()
                page.locator("#closeDetail").click()
                assert all("since" in q and "until" in q for q in api_calls)
                assert all(int(q["limit"][0])==100 for q in api_calls)
                page.locator(".post-open").first.click()
                assert page.locator("dialog#detail").is_visible()
                assert page.locator("#detailContent .dialog-text").inner_text().strip()
                assert page.locator("#detailContent img").count()>=1
                page.keyboard.press("Escape")
                assert not page.locator("dialog#detail").is_visible()
                page.get_by_role("button",name="섹트",exact=True).click()
                assert page.locator("article.post").count()==105
                assert "섹트" in page.locator("article.post .post-excerpt").first.inner_text()
                page.get_by_role("button",name="전체",exact=True).click()
                assert page.locator("article.post").count()==270
                page.set_viewport_size({"width":390,"height":844})
                mobile=page.locator("#feed").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")
                assert mobile==3,f"Expected iPhone three columns, got {mobile}"
                page.locator(".post-open").first.click()
                assert page.locator("dialog#detail").is_visible()
                page.locator("#closeDetail").click()
                page.locator("#dateDisclosure summary").click()
                assert page.locator("#dateDisclosure").evaluate("e=>e.open")
                page.locator('button[data-days="7"]').click()
                page.wait_for_function("document.getElementById('refresh').disabled === false",timeout=120000)
                assert page.locator('input[type="date"]#startDate').input_value()
                assert page.locator('input[type="date"]#endDate').input_value()
                assert page.locator("article.post").count()==270
            assert not errors,"JavaScript exceptions: "+repr(errors[:5])
            print("REAL_PUBLIC_BROWSER_SMOKE" if live else "THREE_COLUMN_MODAL_DATE_QA",
                  json.dumps({"visible_post_cards":n,"thumbs":imgs,"columns":cols,
                              "password_inputs":pwd,"requests":len(api_calls), "adult_thumbnails":adult_thumb, "restricted_cards":restricted.count()}))
        finally:
            browser.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    run(live=parser.parse_args().live)
