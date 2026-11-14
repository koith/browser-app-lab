"""Offline real Chromium/WebKit QA for archived nickname(account-id) picker.

All data and account identities here are synthetic; no live SNS or cloud writes.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
HTML=(ROOT/"account_archive_view.html").read_text(encoding="utf-8")
JS=(ROOT/"account_archive_view.js").read_text(encoding="utf-8")
CSS=(ROOT/"account_archive_view.css").read_text(encoding="utf-8")
BASE="https://private.intersection.test"
KEY_A="bluesky-"+"a"*40
KEY_B="mastodon-"+"b"*40
ACCOUNTS=[
    {"key":KEY_A,"platform":"bluesky","profile_url":"https://bsky.app/profile/did:plc:synthetic",
     "display_name":"코코","handle":"coco.bsky.social","profile_snapshot_verified":True},
    {"key":KEY_B,"platform":"mastodon","profile_url":"https://test.example/@sample",
     "display_name":"마루","handle":"maru@test.example","profile_snapshot_verified":True},
]
IDS={KEY_A:("코코","coco.bsky.social"),KEY_B:("마루","maru@test.example")}


def verify(browser_type,label):
    browser=browser_type.launch(headless=True)
    try:
        for embedded in (False,True):
            page=browser.new_page(viewport={"width":430 if label=="webkit" else 1200,
                                            "height":932})
            errors=[]
            hits=[]
            page.on("pageerror",lambda e:errors.append(type(e).__name__))
            def respond(route):
                request=route.request
                parsed=urlsplit(request.url)
                path=parsed.path
                hits.append(path)
                if path=="/account-archive":
                    route.fulfill(status=200,content_type="text/html",body=HTML)
                elif path=="/account-archive/account_archive_view.js":
                    route.fulfill(status=200,content_type="application/javascript",body=JS)
                elif path=="/account-archive/account_archive_view.css":
                    route.fulfill(status=200,content_type="text/css",body=CSS)
                elif path=="/api/account-archives":
                    route.fulfill(status=200,content_type="application/json",
                                  body=json.dumps({"accounts":ACCOUNTS},ensure_ascii=False))
                else:
                    matched=next((key for key in IDS
                                 if path.startswith("/api/account-archives/"+key+"/")),None)
                    if matched:
                        name,handle=IDS[matched]
                        if path.endswith("/profile"):
                            data={"available":True,"platform":"bluesky","identity":"synthetic",
                                  "display_name":name,"handle":handle,
                                  "description":"원격 검증된 합성 프로필",
                                  "posts_count":1,"followers_count":0,"following_count":0,
                                  "assets":{},"profile_url":"https://example.test/profile",
                                  "captured_at":"2026-11-09T00:00:00Z"}
                        elif "/feed" in path:
                            data={"total":1,"offset":0,"limit":20,"more":False,
                                  "posts":[{"id":"a"*40,"posted_at":"2026-11-09T00:00:00Z",
                                            "kind":"post","text":"Synthetic verified post",
                                            "media":[],"media_saved":0,"media_expected":0,
                                            "archive_complete":True}]}
                        else:
                            data={"captured_unique":0,"accounts":[],"more":False}
                        route.fulfill(status=200,content_type="application/json",
                                      body=json.dumps(data,ensure_ascii=False))
                    else:
                        route.abort()
            page.route("**/*",respond)
            url=BASE+"/account-archive"+(
                "?embedded=1&account="+KEY_A if embedded
                else "?account="+KEY_B)
            page.goto(url,wait_until="domcontentloaded",timeout=20000)
            page.locator("#results article.post").first.wait_for(timeout=20000)
            expected_provider="bluesky" if embedded else "mastodon"
            assert page.locator("html").get_attribute("data-platform")==expected_provider
            assert page.locator("#snsProviderTitle").inner_text()=="프로필"
            assert page.locator("#snsProviderSubtitle").count()==0
            assert page.locator(".sns-archive-pill").count()==0
            assert page.locator("#results .post-byline strong").count()==1
            # Profile can finish after the feed: social cards must show the
            # saved author nickname and handle instead of generic "보관 계정".
            expected_name="코코" if embedded else "마루"
            expected_handle="@coco.bsky.social" if embedded else "@maru@test.example"
            page.wait_for_function(
                "([name,handle]) => { const card=document.querySelector('#results article.post');"
                " return card?.querySelector('.post-byline strong')?.textContent===name"
                " && card?.querySelector('.post-handle')?.textContent===handle; }",
                arg=[expected_name,expected_handle],timeout=12000)
            assert page.locator("#results .post-action-reply").count()==1
            assert page.locator("#results article.post").first.get_attribute("data-kind")=="post"
            background=page.locator("body").evaluate(
                "el => getComputedStyle(el).backgroundColor")
            assert background=="rgb(25, 27, 35)" if expected_provider=="mastodon" else background=="rgb(245, 248, 251)", background
            if embedded:
                assert "/api/account-archives" not in hits, (
                    "embedded viewer must reuse parent's preloaded account choices")
                assert not page.locator(".account-picker").is_visible()
                assert not page.locator(".page-lead").is_visible()
                assert page.locator("#displayName").inner_text()=="코코"
                assert page.locator("#snsProviderSymbol").inner_text()=="🦋"
            else:
                page.wait_for_function(
                    "() => document.querySelector('#accountCount')"
                    "?.textContent?.includes('2개')",timeout=20000)
                select=page.locator("#accountSelect")
                options=select.locator("option").all_text_contents()
                assert "코코(@coco.bsky.social)" in options,options
                assert "마루(@maru@test.example)" in options,options
                assert all("https://" not in text and not text.startswith("bluesky-")
                           for text in options)
                assert select.input_value()==KEY_B
                assert page.locator("#displayName").inner_text()=="마루"
                select.select_option(KEY_A)
                page.wait_for_function(
                    "() => document.querySelector('#displayName')?.textContent==='코코'",
                    timeout=15000)
                assert page.locator("html").get_attribute("data-platform")=="bluesky"
                assert page.locator("#snsProviderTitle").inner_text()=="프로필"
                assert page.locator("#snsProviderSymbol").inner_text()=="🦋"
                page.wait_for_function(
                    "() => document.querySelector('#results .post-byline strong')?.textContent==='코코'"
                    " && document.querySelector('#results .post-handle')?.textContent==='@coco.bsky.social'",
                    timeout=12000)
                # Data switch cannot leave Mastodon's dark canvas behind.
                assert page.locator("body").evaluate(
                    "el => getComputedStyle(el).backgroundColor")=="rgb(245, 248, 251)"
                assert page.locator("#results article.post").count()==1
                assert "account="+KEY_A in page.url
                # One list load across changing accounts; all responses re-use the choice cache.
                assert hits.count("/api/account-archives")==1
            doc=page.evaluate(
                "() => ({width:innerWidth,scroll:document.documentElement.scrollWidth})")
            assert doc["scroll"]<=doc["width"]+3, "mobile horizontal overflow"
            assert not errors,errors
            print("ARCHIVE_NICKNAME_PICKER_PASS",label,
                  "embedded" if embedded else "standalone",
                  "nickname_id=PASS","auto_load=PASS",
                  "no_duplicate_list=PASS","responsive=PASS",flush=True)
            page.close()
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        verify(p.chromium,"chromium")
        verify(p.webkit,"webkit")
