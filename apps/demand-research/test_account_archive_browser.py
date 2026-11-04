"""Offline Chromium+WebKit smoke of the private account archive webview.

Only synthetic profile/post/comment data, no live SNS requests, passwords,
TeraBox reads, screenshots of real accounts or raw personal records.
"""
from __future__ import annotations

from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
PAGE="https://testserver/account-archive"
ACCOUNT="bluesky-"+"a"*40
POST="b"*40
POST2="f"*40


def response_fixture(path):
    if path=="/api/account-archives":
        return {"accounts":[{"key":ACCOUNT,"platform":"bluesky",
                "profile_url":"https://bsky.app/profile/qa.bsky.social"}]}
    if path.endswith("/profile"):
        return {"available":True,"platform":"bluesky","identity":"did:plc:"+"c"*24,
                "handle":"qa.bsky.social","display_name":"Synthetic QA",
                "description":"Synthetic biography for browser verification",
                "followers_count":13,"following_count":4,"posts_count":29,
                "assets":{"avatar":None,"banner":None},
                "captured_at":"2026-11-04T00:00:00Z",
                "profile_url":"https://bsky.app/profile/qa.bsky.social"}
    if "/feed" in path:
        return {"total":1,"offset":0,"more":False,"posts":[{
            "id":POST,"kind":"post","posted_at":"2026-11-03T00:00:00Z",
            "text":"Synthetic posted image and comment history",
            "source_url":"https://bsky.app/profile/qa.bsky.social/post/abc",
            "media_expected":1,"media_saved":1,"archive_complete":True,
            "media":[{"kind":"image","mime":"image/png","verified_sha256":True,
                    "url":"/api/account-archives/"+ACCOUNT+"/media/"+POST+"/0"}]},
            {"id":POST2,"kind":"post","posted_at":"2026-11-03T01:00:00Z",
             "text":"Synthetic second archived post",
             "source_url":"https://bsky.app/profile/qa.bsky.social/post/def",
             "media_expected":0,"media_saved":0,"archive_complete":True,
             "media":[]}]}
    if "/graph/followers" in path or "/graph/following" in path:
        return {"captured_unique":1,"offset":0,"more":False,
                "full_network_coverage_guaranteed":False,
                "accounts":[{"id":"did:plc:"+"d"*24,"handle":"reader.bsky.social",
                             "display_name":"Public Reader",
                             "profile_url":"https://bsky.app/profile/reader.bsky.social"}]}
    if path.endswith("/threads/"+POST2):
        return {"captured":True,"truncated":False,"captured_at":"2026-11-04T00:00:00Z",
                "replies":[{"id":"reply2","text":"Synthetic second comment",
                            "display_name":"Second Reader","posted_at":"2026-11-04T01:00:00Z"}]}
    if "/threads/" in path:
        return {"captured":True,"truncated":False,"captured_at":"2026-11-04T00:00:00Z",
                "comment_media_backed_up":False,
                "replies":[{"id":"reply","display_name":"Public Reader",
                            "author":"reader.bsky.social",
                            "text":"Synthetic comment in private view",
                            "posted_at":"2026-11-04T00:00:00Z",
                            "uri":"https://bsky.app/profile/reader.bsky.social/post/comment"}]}
    raise AssertionError("Unknown synthetic API route: "+path)


def run(browser_type,name,width,height):
    browser=browser_type.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":width,"height":height},
                              color_scheme="light")
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)[:160]))
        def route_it(route):
            url=route.request.url
            from urllib.parse import urlsplit
            path=urlsplit(url).path
            if path=="/account-archive":
                route.fulfill(status=200,content_type="text/html; charset=utf-8",
                              body=(ROOT/"account_archive_view.html").read_text("utf-8"))
            elif path=="/account-archive/account_archive_view.css":
                route.fulfill(status=200,content_type="text/css",
                              body=(ROOT/"account_archive_view.css").read_text("utf-8"))
            elif path=="/account-archive/account_archive_view.js":
                route.fulfill(status=200,content_type="text/javascript",
                              body=(ROOT/"account_archive_view.js").read_text("utf-8"))
            elif path.startswith("/api/account-archives"):
                if "/media/" in path:
                    route.fulfill(status=200,content_type="image/png",
                        body=bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082"))
                else:
                    import json
                    route.fulfill(status=200,content_type="application/json",
                                  body=json.dumps(response_fixture(path),ensure_ascii=False))
            else:
                route.abort()
        page.route("**/*",route_it)
        # Delay the first post thread and page responses to reproduce UI races.
        page.add_init_script("""
(() => {
  const realFetch=window.fetch.bind(window);
  window.fetch=async (...args) => {
    const url=String(args[0]||"");
    const response=await realFetch(...args);
    if(url.includes("/feed?")||url.endsWith("/threads/POST_SHA"))
      await new Promise(resolve=>setTimeout(resolve,750));
    return response;
  };
})();
""".replace("POST_SHA",POST))
        response=page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
        assert response and response.status==200
        page.get_by_role("heading",name="Synthetic QA").wait_for(timeout=12000)
        assert page.get_by_text("Synthetic biography for browser verification").count()==1
        assert page.locator("#followerCount").inner_text()=="13"
        page.locator("#results").get_by_text("Synthetic posted image and comment history").wait_for(timeout=10000)
        assert page.locator(".post-media img").count()==1
        page.locator("#results article.post").first.get_by_role("button",name="댓글·상세 보기").click()
        assert page.locator("#postDetail[open]").count()==1
        page.get_by_text("Synthetic comment in private view").wait_for(timeout=5000)
        page.locator("#closeDetail").click()
        assert page.locator("#postDetail[open]").count()==0
        page.get_by_role("tab",name="팔로워").click()
        page.locator("#results .person").get_by_text("Public Reader").wait_for(timeout=5000)
        page.get_by_role("tab",name="팔로잉").click()
        assert page.get_by_text("reader.bsky.social").count()>=1
        page.get_by_role("tab",name="게시글·답글").click()
        page.locator("#results").get_by_text("Synthetic posted image and comment history").wait_for(timeout=10000)
        # Switching tabs during the previous request must launch the new tab\x27s page.
        page.evaluate("""() => {
          document.querySelector(\x27[data-section="posts"]\x27).click();
          document.querySelector(\x27[data-section="followers"]\x27).click();
        }""")
        page.locator("#results .person").get_by_text("Public Reader").wait_for(timeout=5000)
        page.wait_for_timeout(850)
        assert page.locator("#results .person").count()==1,"stale feed must not replace new tab"
        # Closing an old thread and opening another must not display the old replies.
        page.get_by_role("tab",name="게시글·답글").click()
        page.locator("#results article.post").nth(1).get_by_text("Synthetic second archived post").wait_for(timeout=5000)
        page.locator("#results article.post").first.get_by_role("button",name="댓글·상세 보기").click()
        page.locator("#closeDetail").click()
        page.locator("#results article.post").nth(1).get_by_role("button",name="댓글·상세 보기").click()
        page.locator("#detailBody").get_by_text("Synthetic second comment").wait_for(timeout=5000)
        page.wait_for_timeout(850)
        assert page.locator("#detailBody").get_by_text("Synthetic comment in private view").count()==0, "stale first thread leaked into second detail"
        page.locator("#closeDetail").click()
        doc=page.evaluate("() => ({w:document.documentElement.scrollWidth, v:innerWidth})")
        assert doc["w"]<=doc["v"]+2,("horizontal overflow",doc)
        assert not errors,errors
        print("ACCOUNT_ARCHIVE_BROWSER_PASS",name,
              "verified_profile_feed_thread_graph_mobile_usable=YES")
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        run(p.chromium,"desktop-chromium",1200,900)
        run(p.webkit,"mobile-webkit",390,844)
