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
      "author":{"did":"did:plc:safe-synthetic", "handle":"qa-feed.bsky.social", "displayName":"TEST"},
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
    provider_http=[]
    provider_failed=[]
    provider_on={"enabled":False}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":1200,"height":900})
            page.on("pageerror",lambda error:errors.append(str(error)[:200]))
            if live:
                page.on("response",lambda resp:provider_http.append({
                    "host":urlparse(resp.url).hostname,"status":resp.status
                }) if urlparse(resp.url).hostname in ("mastodon.social","mstdn.social","lemmy.world") and "/api/" in resp.url else None)
                page.on("requestfailed",lambda req:provider_failed.append(
                    urlparse(req.url).hostname) if urlparse(req.url).hostname in (
                    "mastodon.social","mstdn.social","lemmy.world") else None)
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
                def mastodon_api(route):
                    from urllib.parse import unquote
                    term=unquote(route.request.url.split("/api/v1/timelines/tag/")[-1].split("?")[0])
                    if not provider_on["enabled"] or "mstdn.social" in route.request.url:
                        rows=[]
                    else:
                        rows=[{
                          "id":"112233"+str(TERMS.index(term)),
                          "uri":"https://mastodon.social/@sample/"+str(TERMS.index(term)+100),
                          "url":"https://mastodon.social/@sample/"+str(TERMS.index(term)+100),
                          "visibility":"public","content":"<p>"+term+" synthetic Mastodon test</p>",
                          "created_at":datetime.now(timezone.utc).isoformat(),
                          "account":{"display_name":"Mastodon QA","acct":"qa","url":"https://mastodon.social/@qa"},
                          "media_attachments":[{"type":"image","url":"https://example.com/qa.png",
                                                "preview_url":"https://example.com/qa.png"}]
                        }]
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},body=json.dumps(rows,ensure_ascii=False))
                def lemmy_api(route):
                    q=parse_qs(urlparse(route.request.url).query)
                    term=q.get("q",[""])[0]
                    records=[]
                    if provider_on["enabled"] and term in TERMS:
                        i=TERMS.index(term)
                        records=[{
                          "post":{"id":300+i,"ap_id":"https://lemmy.world/post/"+str(300+i),
                            "name":term+" synthetic Lemmy test",
                            "body":"test content","published":datetime.now(timezone.utc).isoformat()},
                          "creator":{"name":"qa","actor_id":"https://lemmy.world/u/qa"},
                        }]
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body=json.dumps({"posts":records},ensure_ascii=False))
                page.route("https://mastodon.social/api/**",mastodon_api)
                page.route("https://mstdn.social/api/**",mastodon_api)
                page.route("https://lemmy.world/api/**",lemmy_api)
                page.route("https://example.com/qa.png",
                    lambda route:route.fulfill(status=200,body=PNG,content_type="image/png"))
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_selector("article.post",timeout=60000)
            page.wait_for_function("document.getElementById('refresh').disabled === false",timeout=120000)
            n=page.locator("article.post").count()
            imgs=page.locator("article.post .post-thumb > img").count()
            pwd=page.locator("input[type=password], #login").count()
            assert pwd==0,"Unexpected password/login UI"
            assert page.locator('input[type="date"]').count()==2
            cols=page.locator("#feed").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")
            assert cols==3,f"Expected desktop three columns, got {cols}"
            assert page.title()=="INTERSECTION"
            assert page.locator("h1").inner_text()=="INTERSECTION"
            assert page.locator("h1").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")<=44
            assert page.locator("#dotField").count()==1
            assert page.locator("#filterDetails").count()==1
            assert page.locator("#filterDetails").evaluate("e=>!e.open"),"Filters should start compact"
            assert page.locator("#datePanel").is_visible()
            assert page.locator("#dateDisclosure").count()==0
            assert page.locator("#q, #find, .search-row").count()==0
            assert page.locator("#refresh").is_visible()
            assert page.locator("#datePanel input[type=date]").count()==2
            assert "건" in page.locator("#count").inner_text()
            assert "B315" in page.locator("#count").inner_text() or live
            assert page.locator("footer, #footnote, #showMore, #listMore").count()==0
            assert page.locator("#dotField").evaluate("e=>e.width>0 && e.height>0")
            # Touch scrub reveals a local round hole in the halftone and
            # automatically regrows the removed dots without page navigation.
            def dot_alpha():
                return page.locator("#dotField").evaluate("""c=>{
                    const context=c.getContext('2d');
                    const px=Math.round(c.width*.79),py=Math.round(c.height*.16);
                    const d=context.getImageData(px-45,py-45,90,90).data;
                    let sum=0; for(let i=3;i<d.length;i+=4)sum+=d[i];
                    return sum;
                }""")
            base=dot_alpha()
            assert base>12000, f"No visible animated dot field: {base}"
            page.evaluate("""()=>{
                document.dispatchEvent(new PointerEvent('pointerdown',{
                    clientX:innerWidth*.79,clientY:innerHeight*.16,pointerType:'touch',
                    bubbles:true,isPrimary:true
                }));
            }""")
            page.wait_for_timeout(180)
            cleared=dot_alpha()
            assert cleared<base*.65, f"Touch failed to clear local dots: {base}, {cleared}"
            page.wait_for_timeout(2100)
            grown=dot_alpha()
            assert grown>base*.78, f"Dot field failed to regrow: {base}, {grown}"
            assert page.locator("#showAdultMedia").is_checked()
            # Advanced switches stay collapsed until deliberately opened.
            page.locator("#filterDetails summary").click()
            assert page.locator("#filterDetails").evaluate("e=>e.open")
            assert page.locator("input[type=password]").count()==0
            adult=page.locator('article[data-media-policy="adult"]')
            restricted=page.locator('article[data-media-policy="restricted"]')
            adult_thumb=adult.locator(".post-thumb > img").count()
            assert restricted.locator(".post-thumb > img").count()==0, "Restricted media must not be previewed"
            if live:
                assert n>=1,f"Expected public results, saw {n} posts"
                # Warn-class adult labels are no longer blanked by app code.
                if adult.count():
                    assert adult_thumb>=1,"Public adult-labeled media with thumbnails should display"
                assert "건" in page.locator("#count").inner_text()
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
                assert page.locator('article[data-media-policy="adult"] .post-thumb > img').count()==0
                page.locator('article[data-media-policy="adult"] .post-open').first.click()
                assert "성인 미디어 표시가 꺼져" in page.locator("#detailContent .dialog-notice").inner_text()
                page.locator("#closeDetail").click()
                page.locator("#showAdultMedia").check()
                assert page.locator('article[data-media-policy="adult"] img').count()>0
                assert page.locator('article[data-media-policy="restricted"] .post-thumb > img').count()==0
                page.locator('article[data-media-policy="restricted"] .post-open').first.click()
                assert "서비스 제한" in page.locator("#detailContent .dialog-notice").inner_text()
                assert page.locator("#detailContent .dialog-media img").count()==0
                page.locator("#closeDetail").click()
                assert len(api_calls)>=21, f"Expected daily shards, got {len(api_calls)}"
                assert "건" in page.locator("#count").inner_text()
                assert page.locator("#hideAds").is_checked()
                assert "광고 의심 21건" in page.locator("#adSummary").inner_text()
                assert page.locator("#more").is_visible()
                page.locator("#more").click()
                assert page.locator("article.post").count()==294
                page.locator("#hideAds").uncheck()
                assert page.locator("article.post").count()==270
                page.locator("#more").click()
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
                assert page.locator("#detailContent .dialog-media img").count()>=1
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
                assert page.locator("h1").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")<=35
                date_boxes=page.locator("#datePanel input[type=date]").evaluate_all("els=>els.map(e=>e.getBoundingClientRect().toJSON())")
                assert abs(date_boxes[0]["y"]-date_boxes[1]["y"])<4,"Date inputs should stay side by side on iPhone"
                assert date_boxes[1]["right"]<=395,"Date picker overflows iPhone width"
                assert page.locator("#applyDate").is_visible()
                page.locator('button[data-days="7"]').click()
                page.wait_for_function("document.getElementById('refresh').disabled === false",timeout=120000)
                assert page.locator('input[type="date"]#startDate').input_value()
                assert page.locator('input[type="date"]#endDate').input_value()
                assert page.locator("article.post").count()==270
                provider_on["enabled"]=True
                page.locator("#refresh").click()
                page.wait_for_function("document.getElementById('refresh').disabled === false",timeout=120000)
                assert "M3" in page.locator("#count").inner_text()
                assert "L3" in page.locator("#count").inner_text()
                assert page.locator('.source-badge[aria-label="출처: Mastodon"]').count()>0 or (
                  page.locator("#more").click() is None and
                  page.locator('.source-badge[aria-label="출처: Mastodon"]').count()>0)
                assert page.locator('.source-badge[aria-label="출처: Lemmy"]').count()>0
                mast=page.locator('article.post').filter(has=page.locator('.source-badge[aria-label="출처: Mastodon"]')).first
                assert mast.locator('a.author').get_attribute("href")=="https://mastodon.social/@qa"
                lemmy=page.locator('article.post').filter(has=page.locator('.source-badge[aria-label="출처: Lemmy"]')).first
                assert lemmy.locator('a.author').get_attribute("href")=="https://lemmy.world/u/qa"
                bsky=page.locator('article.post').filter(has=page.locator('.source-badge[aria-label="출처: Bluesky"]')).first
                assert bsky.locator('a.author').get_attribute("href")=="https://bsky.app/profile/qa-feed.bsky.social"
                assert bsky.locator("a.author").get_attribute("target")=="_blank"
                bsky.locator(".post-open").click(position={"x":30,"y":30})
                assert page.locator("#detail").is_visible()
                assert page.locator("#detailContent .source-badge").count()==1
                assert page.locator("#detailContent .profile-link").count()==1
                page.locator("#closeDetail").click()
            assert not errors,"JavaScript exceptions: "+repr(errors[:5])
            print("REAL_PUBLIC_BROWSER_SMOKE" if live else "THREE_COLUMN_MODAL_DATE_QA",
                  json.dumps({"visible_post_cards":n,"thumbs":imgs,"columns":cols,
                              "password_inputs":pwd,"requests":len(api_calls),
                              "adult_thumbnails":adult_thumb, "restricted_cards":restricted.count(),
                              "source_counter":page.locator("#count").inner_text(),
                              "providers_http":provider_http,"providers_failed":provider_failed}))
        finally:
            browser.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    run(live=parser.parse_args().live)
