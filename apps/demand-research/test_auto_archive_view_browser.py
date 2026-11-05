"""Offline browser checks: automatic captures show byte-backed original media, not previews.

Every account and post is synthetic; no provider sites or private TeraBox data accessed.
"""
from pathlib import Path
import json
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
HTML=(ROOT/"auto_archive_view.html").read_text("utf-8")
JS=(ROOT/"auto_archive_view.js").read_text("utf-8")
CSS=(ROOT/"auto_archive_view.css").read_text("utf-8")
BASE="https://private.intersection.test"
ID1="a"*40
ID2="b"*40
SRC=lambda pid,index: "/api/media/"+pid+"/"+str(index)+"?exp=9999999999&sig="+("a"*64)
POSTS=[
 {"id":ID1,"platform":"bluesky","posted_at":"2026-11-06T00:00:00Z",
  "text":"Synthetic #keyword original photo, not a remote thumbnail <script>danger()</script>",
  "profile_url":"https://bsky.app/profile/qa-public.test",
  "source_url":"https://bsky.app/profile/qa-public.test/post/example1",
  "capture_status":"remote_verified","media_expected":2,"media_saved":2,
  "media":[{"kind":"image","mime":"image/png","bytes":70,"verified":True,"url":SRC(ID1,0)},
           {"kind":"video","mime":"video/mp4","bytes":144,"verified":True,"url":SRC(ID1,1)}]},
 {"id":ID2,"platform":"mastodon","posted_at":"2026-11-05T00:00:00Z",
  "text":"Synthetic public post with an audio file and a missing original",
  "profile_url":"https://mastodon.social/@qa-public",
  "source_url":"https://mastodon.social/@qa-public/123",
  "capture_status":"partial_media","media_expected":2,"media_saved":1,
  "media":[{"kind":"audio","mime":"audio/mpeg","bytes":230,"verified":True,"url":SRC(ID2,0)},
           {"kind":"image","mime":"image/png","bytes":200,"verified":False,
             "url":"https://random-untrusted.example/original.png"}]}
]

def exercise(browser_type,label):
    browser=browser_type.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":390 if label.startswith("mobile") else 1280,
                                        "height":844})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        def route_it(route):
            parsed=urlsplit(route.request.url)
            if parsed.hostname!="private.intersection.test":
                route.abort();return
            if parsed.path=="/auto-archive":
                route.fulfill(status=200,content_type="text/html",body=HTML)
            elif parsed.path=="/auto-archive/auto_archive_view.js":
                route.fulfill(status=200,content_type="application/javascript",body=JS)
            elif parsed.path=="/auto-archive/auto_archive_view.css":
                route.fulfill(status=200,content_type="text/css",body=CSS)
            elif parsed.path=="/api/posts":
                params=parse_qs(parsed.query)
                rows=[p for p in POSTS if
                      params.get("q",[""])[0].lower() in p["text"].lower() and
                      (not params.get("platform",[""])[0] or
                       p["platform"]==params["platform"][0]) and
                      (not params.get("media_status",[""])[0] or
                       (params["media_status"][0]=="partial")==
                       (p["capture_status"]=="partial_media"))]
                start=int(params.get("offset",["0"])[0])
                route.fulfill(status=200,content_type="application/json",
                              body=json.dumps({"total":len(rows),"offset":start,
                                "posts":rows[start:start+20],"storage":"TeraBox"}))
            elif parsed.path.startswith("/api/media/"):
                route.fulfill(status=200,content_type="application/octet-stream",body="synthetic")
            else:
                route.abort()
        page.route("**/*",route_it)
        page.goto(BASE+"/auto-archive",wait_until="domcontentloaded",timeout=30000)
        page.locator("#posts article.post").first.wait_for(state="visible",timeout=12000)
        assert page.locator("#posts article.post").count()==2
        assert page.locator("#posts img").count()==1
        assert page.locator("#posts video").count()==1
        assert page.locator("#posts audio").count()==1
        assert page.locator("#posts .media a").count()==3
        assert "미보관 원본 있음" in page.locator("#posts article.post").last.inner_text()
        assert page.locator("#posts .post-body script").count()==0
        assert "<script>danger()</script>" in page.locator("#posts .post-body").first.text_content()
        assert page.locator("#posts img").first.get_attribute("src").startswith("/api/media/")
        assert page.locator("#posts video").first.get_attribute("src").startswith("/api/media/")
        assert page.locator("#posts a[href^='https://random-untrusted.example']").count()==0
        page.locator("#query").fill("audio")
        page.locator("#search button").click()
        page.wait_for_function("document.querySelector('#status').textContent.includes('1건 중 1건')",
                               timeout=12000)
        assert page.locator("#posts article.post").count()==1
        page.locator("#query").fill("")
        page.locator("#platform").select_option("bluesky")
        page.locator("#search button").click()
        page.wait_for_function("document.querySelector('#status').textContent.includes('1건 중 1건')",
                               timeout=12000)
        assert page.locator("#posts article.post").count()==1
        assert page.locator("#posts video").count()==1
        w=page.evaluate("({scroll:document.documentElement.scrollWidth,width:innerWidth})")
        assert w["scroll"]<=w["width"]+2,w
        assert not errors,errors
        print("AUTO_ORIGINAL_ARCHIVE_BROWSER_PASS",label,
              "image=1 video=1 audio=1 missing-original-marked=YES external-mix=NO")
    finally:
        browser.close()

if __name__=="__main__":
    with sync_playwright() as p:
        exercise(p.chromium,"desktop-chromium")
        exercise(p.webkit,"mobile-webkit")
