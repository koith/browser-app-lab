"""Headless browser proof that the Pages viewer immediately displays post cards.
The fixture contains synthetic posts and never stores any third-party post content.
Live mode only counts visible cards and does not print or save the fetched records.
"""
import argparse, json, pathlib
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

HTML=pathlib.Path(__file__).with_name("index.html").read_text(encoding="utf-8")
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
TERMS=["뒷계","섹트","일탈계"]

def fake_post(term,i):
    return {
      "uri":f"at://did:plc:synthetic{term}{i}/app.bsky.feed.post/{i+100}",
      "author":{"handle":"sample.invalid","displayName":"TEST"},
      "record":{"text":term+" synthetic post for UI QA, no personal information",
        "createdAt":"2026-11-01T12:00:00Z"},
      "embed":{"$type":"app.bsky.embed.images#view","images":[{
        "fullsize":"https://example.com/qa.png",
        "thumb":"https://example.com/qa.png","alt":"QA fixture"}]}
    }

def run(live=False):
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page()
            page.on("pageerror",lambda error:errors.append(str(error)[:200]))
            page.route(PAGE,lambda route:route.fulfill(status=200,content_type="text/html; charset=utf-8",body=HTML))
            if not live:
                def mock_api(route):
                    q=parse_qs(urlparse(route.request.url).query).get("q",[""])[0]
                    posts=[fake_post(q,1)] if q in TERMS else []
                    route.fulfill(status=200,content_type="application/json",
                                  headers={"Access-Control-Allow-Origin":"*"},
                                  body=json.dumps({"posts":posts},ensure_ascii=False))
                page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",mock_api)
                page.route("https://example.com/qa.png",lambda route:route.fulfill(status=200,body=b"\x89PNG\r\n\x1a\n",content_type="image/png"))
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_selector("article.post",timeout=35000)
            n=page.locator("article.post").count()
            imgs=page.locator("article.post img").count()
            pwd=page.locator("input[type=password], #login").count()
            assert pwd==0,"Login/password prompt unexpectedly present"
            if live:
                assert n>=1,f"Expected real public results, saw {n} posts"
            else:
                assert n==3,f"Expected three mocked grouped posts, saw {n}"
                assert imgs==3,f"Image not grouped under its parent post: {imgs}"
                page.get_by_role("button",name="섹트",exact=True).click()
                assert page.locator("article.post").count()==1
                assert "섹트" in page.locator("article.post p").first.inner_text()
            assert not errors,"JavaScript exceptions: "+repr(errors[:3])
            print("REAL_PUBLIC_BROWSER_SMOKE" if live else "SYNTHETIC_BROWSER_SMOKE",
                  json.dumps({"visible_post_cards":n,"images":imgs,"password_inputs":pwd}))
        finally:browser.close()

if __name__=="__main__":
    args=argparse.ArgumentParser()
    args.add_argument("--live",action="store_true")
    options=args.parse_args()
    run(live=options.live)
