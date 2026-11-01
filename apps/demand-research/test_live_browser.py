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
      "record":{"text":term+" synthetic QA sample without personal details",
                "createdAt":datetime.now(timezone.utc).isoformat()},
      "indexedAt":datetime.now(timezone.utc).isoformat(),
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
            if live:
                assert n>=1,f"Expected public results, saw {n} posts"
                assert page.locator("#count").inner_text().find("조회")!=-1
                page.locator(".post-open").first.click()
                assert page.locator("dialog#detail").is_visible()
                assert page.locator("#detailContent .dialog-text").inner_text().strip()
                page.locator("#closeDetail").click()
            else:
                assert n==270,f"Expected first 270 of 315 synthetic posts; saw {n}"
                assert imgs==270,f"Card thumbnail not grouped with parent: {imgs}"
                assert len(api_calls)>=21, f"Expected daily shards, got {len(api_calls)}"
                assert "315개 게시글" in page.locator("#count").inner_text()
                assert page.locator("#showMore").is_visible()
                page.locator("#showMore").click()
                assert page.locator("article.post").count()==27015
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
                assert page.locator("article.post").count()==3
                page.set_viewport_size({"width":390,"height":844})
                mobile=page.locator("#feed").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")
                assert mobile==3,f"Expected iPhone three columns, got {mobile}"
                page.locator(".post-open").first.click()
                assert page.locator("dialog#detail").is_visible()
                page.locator("#closeDetail").click()
                page.locator('button[data-days="7"]').click()
                page.wait_for_function("document.getElementById('refresh').disabled === false",timeout=120000)
                assert page.locator('input[type="date"]#startDate').input_value()
                assert page.locator('input[type="date"]#endDate').input_value()
                assert page.locator("article.post").count()==3
            assert not errors,"JavaScript exceptions: "+repr(errors[:5])
            print("REAL_PUBLIC_BROWSER_SMOKE" if live else "THREE_COLUMN_MODAL_DATE_QA",
                  json.dumps({"visible_post_cards":n,"thumbs":imgs,"columns":cols,
                              "password_inputs":pwd,"requests":len(api_calls)}))
        finally:
            browser.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    run(live=parser.parse_args().live)
