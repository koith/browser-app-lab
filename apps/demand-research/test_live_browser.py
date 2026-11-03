"""Browser QA: INTERSECTION compact header date selector, date popup, automatic ad filtering,
one More button, federated provider badges/links and touchscreen halftone.
No real user post content is saved or printed.
"""
import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

HTML=Path(__file__).with_name("index.html").read_text(encoding="utf-8")
FREE_JS=Path(__file__).with_name("free_discovery.js").read_text(encoding="utf-8")
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
TERMS=("뒷계","섹트","일탈계")
PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGPUit7yn4GBgYGJAQoAIS4CPGFQl4cAAAAASUVORK5CYII=")

def fake_post(term,i):
    today=datetime.now(timezone.utc).isoformat()
    embed={"images":[{"fullsize":"https://example.com/qa.png",
                      "thumb":"https://example.com/qa.png","alt":"QA fixture"}]}
    if i%17==5:
        embed={"images":[]}  # actual source text-only post
    elif i%17==6:
        embed={"$type":"app.bsky.embed.video#view","playlist":"https://example.com/qa.m3u8"}  # no poster
    elif i%17==7:
        embed={"images":[{"fullsize":"https://example.com/qa.png",
                          "thumb":"https://example.com/broken-qa.png","alt":"QA fallback"}]}
    return {
        "uri":f"at://did:plc:synthetic{i}{term}/app.bsky.feed.post/{i+100}",
        "author":{"did":"did:plc:safe-synthetic","handle":"qa-feed.bsky.social","displayName":"TEST",
                   "avatar":"https://example.com/qa.png"},
        "record":{"text":term+(" 광고 판매 홍보 할인 구독 문의 텔레그램 "+str(i)
                 if i%15==0 else " synthetic QA without personal details "+str(i)),
                  "createdAt":today},
        "indexedAt":today,
        "labels":([{"val":"porn"}] if i%15==1 else
                  [{"val":"graphic-media"}] if i%15==2 else
                  [{"val":"!hide"}] if i%15==3 else []),
        "embed":embed
    }


def assert_rank_rows_centered(page, width):
    # Temporary synthetic DOM only: tests real Chromium layout without
    # fetching/storing any account or post data.
    measured=page.evaluate("""() => {
      const host=document.getElementById("activityRankingRows");
      const original=[...host.childNodes];
      const sample=Array.from({length:23},()=>{
        const tile=document.createElement("button");
        tile.type="button";
        tile.className="activity-rank-card";
        return tile;
      });
      host.replaceChildren(...sample);
      try{
        const parent=host.getBoundingClientRect();
        const boxes=sample.map(tile=>tile.getBoundingClientRect());
        const rows=[];
        for(const box of boxes){
          const at=rows.find(row=>Math.abs(row.y-box.y)<1);
          if(at)at.boxes.push(box);
          else rows.push({y:box.y,boxes:[box]});
        }
        const last=rows[rows.length-1].boxes;
        return {
          rowCounts:rows.map(row=>row.boxes.length),
          tileWidths:boxes.map(box=>box.width),
          leftGap:last[0].left-parent.left,
          rightGap:parent.right-last[last.length-1].right,
          overflow:boxes.some(box=>box.right>parent.right+2||box.left<parent.left-2)
        };
      }finally{host.replaceChildren(...original);}
    }""")
    columns=10 if width>720 else 5
    assert measured["rowCounts"]==([10,10,3] if columns==10 else [5,5,5,5,3]),measured
    assert max(measured["tileWidths"])-min(measured["tileWidths"])<1.1,measured
    assert abs(measured["leftGap"]-measured["rightGap"])<3,measured
    assert not measured["overflow"],measured

def run(live=False):
    errors=[];api_calls=[];provider_http=[];provider_failed=[];provider_on={"enabled":False}
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            page=browser.new_page(viewport={"width":1200,"height":900},color_scheme="light")
            page.on("pageerror",lambda error:errors.append(str(error)[:220]))
            if live:
                hosts={"mastodon.social","planet.moe","twingyeo.kr","lemmy.world","misskey.io","hoto.moe","api.pullpush.io"}
                page.on("response",lambda resp:provider_http.append({
                    "host":urlparse(resp.url).hostname,"status":resp.status
                }) if urlparse(resp.url).hostname in hosts and "/api/" in resp.url else None)
                page.on("requestfailed",lambda req:provider_failed.append(
                    urlparse(req.url).hostname) if urlparse(req.url).hostname in hosts else None)
            page.route(PAGE,lambda route:route.fulfill(status=200,
                        content_type="text/html; charset=utf-8",body=HTML))
            page.route(PAGE+"free_discovery.js",lambda route:route.fulfill(status=200,
                        content_type="application/javascript",body=FREE_JS))
            if not live:
                page.route("https://api.keenable.ai/v1/search/public",
                    lambda route:route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},body='{"results":[]}'))
                page.route("https://api.firecrawl.dev/v2/search",
                    lambda route:route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body='{"success":true,"data":{"web":[]}}'))

            if not live:
                def bluesky_api(route):
                    q=parse_qs(urlparse(route.request.url).query)
                    term=q.get("q",[""])[0]
                    api_calls.append(q)
                    day=int(q.get("since",["2026-11-01"])[0][8:10])
                    rows=[fake_post(term,day*100+i) for i in range(15)] if term in TERMS else []
                    route.fulfill(status=200,content_type="application/json",
                                  headers={"Access-Control-Allow-Origin":"*"},
                                  body=json.dumps({"posts":rows},ensure_ascii=False))
                page.route("https://api.bsky.app/xrpc/app.bsky.feed.searchPosts**",bluesky_api)
                def mastodon_api(route):
                    from urllib.parse import unquote
                    term=unquote(route.request.url.split("/api/v1/timelines/tag/")[-1].split("?")[0])
                    rows=[]
                    if provider_on["enabled"] and "mastodon.social" in route.request.url and term in TERMS:
                        i=TERMS.index(term)
                        rows=[{
                          "id":"112233"+str(i),"uri":"https://mastodon.social/@sample/"+str(i+100),
                          "url":"https://mastodon.social/@sample/"+str(i+100),
                          "visibility":"public","content":"<p>"+term+" synthetic Mastodon QA</p>",
                          "created_at":datetime.now(timezone.utc).isoformat(),
                          "account":{"display_name":"Mastodon QA","acct":"qa","url":"https://mastodon.social/@qa"},
                          "media_attachments":[{"type":"image","url":"https://example.com/qa.png",
                                                "preview_url":"https://example.com/qa.png"}]
                        }]
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body=json.dumps(rows,ensure_ascii=False))
                page.route("https://mastodon.social/api/**",mastodon_api)
                page.route("https://planet.moe/api/**",mastodon_api)
                page.route("https://twingyeo.kr/api/**",mastodon_api)
                def lemmy_api(route):
                    term=parse_qs(urlparse(route.request.url).query).get("q",[""])[0]
                    rows=[]
                    if provider_on["enabled"] and term in TERMS:
                        i=TERMS.index(term)
                        rows=[{"post":{"id":300+i,"ap_id":"https://lemmy.world/post/"+str(300+i),
                          "name":term+" synthetic Lemmy test","body":"public QA",
                          "published":datetime.now(timezone.utc).isoformat()},
                          "creator":{"name":"qa","actor_id":"https://lemmy.world/u/qa"}}]
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body=json.dumps({"posts":rows},ensure_ascii=False))
                page.route("https://lemmy.world/api/**",lemmy_api)
                def misskey_api(route):
                    payload=route.request.post_data_json or {}
                    term=payload.get("query","")
                    rows=[]
                    if provider_on["enabled"] and "misskey.io" in route.request.url and term in TERMS:
                        i=TERMS.index(term)
                        rows=[{"id":"mtest"+str(i),
                               "createdAt":datetime.now(timezone.utc).isoformat(),
                               "visibility":"public","text":term+" synthetic Misskey QA",
                               "user":{"username":"qa","name":"Misskey QA"},
                               "files":[{"type":"image/png","url":"https://example.com/qa.png",
                                         "thumbnailUrl":"https://example.com/qa.png"}]}]
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body=json.dumps(rows,ensure_ascii=False))
                page.route("https://misskey.io/api/**",misskey_api)
                page.route("https://hoto.moe/api/**",misskey_api)
                def reddit_api(route):
                    term=parse_qs(urlparse(route.request.url).query).get("q",[""])[0]
                    rows=[]
                    if provider_on["enabled"] and term in TERMS:
                        i=TERMS.index(term)
                        rows=[{"id":"mock"+str(i),"author":"qa_reddit",
                               "title":term+" synthetic Reddit QA","selftext":"public fixture",
                               "created_utc":int(datetime.now(timezone.utc).timestamp()),
                               "permalink":"/r/qa/comments/mock"+str(i)+"/fixture/",
                               "url":"https://example.com/qa.png"}]
                    route.fulfill(status=200,content_type="application/json",
                      headers={"Access-Control-Allow-Origin":"*"},
                      body=json.dumps({"data":rows},ensure_ascii=False))
                page.route("https://api.pullpush.io/reddit/search/submission/**",reddit_api)
                # Source logos exist on this branch but not yet on GitHub Pages
                # until merge; isolate fixture from the previous Pages release.
                page.route("https://koith.github.io/browser-app-lab/apps/demand-research/assets/*.svg",
                    lambda route:route.fulfill(status=200,content_type="image/svg+xml",
                      body='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"/></svg>'))
                page.route("https://example.com/qa.png",
                    lambda route:route.fulfill(status=200,content_type="image/png",body=PNG))
                page.route("https://example.com/broken-qa.png",
                    lambda route:route.fulfill(status=404,content_type="text/plain",body="synthetic missing"))
            page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            page.wait_for_selector("article.post",timeout=60000)
            page.wait_for_function("document.getElementById('applyDate').disabled === false",timeout=120000)

            assert page.title()=="INTERSECTION"
            assert page.locator("h1").inner_text()=="INTERSECTION"
            assert page.locator("input[type=password],#login,#refresh,#filterDetails,#hideAds,#showAdultMedia,#adLevel").count()==0
            assert page.locator("#count").evaluate("e=>getComputedStyle(e).clipPath==='inset(50%)'"), "Verbose statistics must be screen-reader-only"
            assert page.locator("footer,#footnote,#showMore,#listMore").count()==0
            assert page.locator("#tabs,[data-term],section.toolbar,#freeDiscovery,#indexFind,#socialControls:not(.hidden)").count()==0
            assert page.locator("header .head-inner > .head-title-group > h1").count()==1
            assert page.locator("header .head-title-group > a.header-consumer-entry").count()==1
            assert page.locator("header .header-consumer-entry").inner_text().strip()=="상품 수요 분석"
            assert page.locator(".consumer-entry").count()==0, "Old oversized banner must be removed"
            assert page.locator(".header-consumer-entry").get_attribute("href")=="./consumer/"
            assert page.locator("header .head-inner > .header-period #openDate").count()==1
            title_bounds=page.locator("header h1").bounding_box()
            date_bounds=page.locator("header #openDate").bounding_box()
            assert abs((title_bounds["y"]+title_bounds["height"]/2)-
                (date_bounds["y"]+date_bounds["height"]/2))<14, "Date should align with site title"
            assert page.locator("#openDate").is_visible()
            assert not page.locator("#dateDialog").is_visible()
            assert page.locator("main input[type=date]").count()==0
            assert page.locator("#feed").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")==3
            assert page.locator("#dotField").evaluate("e=>e.width>0 && e.height>0")
            assert page.locator("body").evaluate("e=>getComputedStyle(e).backgroundColor")!="rgb(221, 227, 224)"
            n=page.locator("article.post").count()
            thumbnails=page.locator("article.post .post-thumb > img").count()
            assert n>0
            assert page.locator("article.post .source-badge").count()==n
            assert page.locator("article.post .post-thumb > .source-badge--icon-only").count()==n
            assert page.locator("article.post .post-thumb > .source-badge--icon-only").evaluate_all(
                "els=>els.every(e=>e.textContent.trim()==='')"),"Source badges over thumbnails must have only logos"
            assert page.locator("article.post .source-badge img").count()>=1
            assert page.locator("article.post a.author[target=_blank]").count()>0
            if not live:
                assert page.locator('article.post[data-no-media="true"]').count()>0, "text-only and posterless video cards need compact fallback"
                assert page.locator("article.post .thumb-kind-label").count()>0, "source avatars must be explicitly labeled as profile pictures"
                text_tile=page.locator('article.post[data-no-media="true"]').first
                assert text_tile.locator(".post-thumb").evaluate("e=>e.getBoundingClientRect().height")<130, "no more full-height empty image boxes"
                before_candidates=page.locator("article.post").count()
                accepted=page.evaluate("""() => window.INTERSECTION_receiveCandidates([{
                  platform:'x',url:'https://x.com/qa_account/status/1234567890123456789',
                  title:'섹트 test-only search result',description:'Unverified synthetic link',
                  provider:'test'
                }])""")
                assert accepted==1
                assert page.locator("article.post").count()==before_candidates, "search hits must not masquerade as verified posts"
                assert page.locator("#discoveryCandidates").is_visible()
                page.locator("#discoveryCandidates summary").click()
                assert page.locator("#discoveryCandidateList a[target=_blank]").count()==1

            # Real canvas-alpha interaction: remove and restore at the pointer.
            def alpha():
                return page.locator("#dotField").evaluate("""c=>{
                  let ctx=c.getContext('2d'),x=Math.round(c.width*.79),y=Math.round(c.height*.16);
                  let d=ctx.getImageData(x-45,y-45,90,90).data,n=0;
                  for(let i=3;i<d.length;i+=4)n+=d[i];return n;
                }""")
            base=alpha();assert base>12000
            page.evaluate("""()=>document.dispatchEvent(new PointerEvent('pointerdown',{
               clientX:innerWidth*.79,clientY:innerHeight*.16,
               pointerType:'touch',bubbles:true,isPrimary:true}))""")
            page.wait_for_timeout(180)
            assert alpha()<base*.65,"Halftone failed to erase at touch"
            page.wait_for_timeout(2100)
            assert alpha()>base*.78,"Halftone failed to restore"

            assert page.locator(".post-open").count()==n
            page.locator(".post-open").first.click()
            assert page.locator("#detail").is_visible()
            assert page.locator("#detailContent .source-badge").count()==1
            assert page.locator("#detailContent .profile-link").count()==1
            assert page.locator("#detailContent .dialog-text").inner_text().strip()
            page.locator("#closeDetail").click()

            # Date selection has moved to a compact dialog, and one button
            # applies presets as well as user-specified custom dates.
            page.locator("#openDate").click()
            assert page.locator("#dateDialog").is_visible()
            assert page.locator('#dateDialog input[type=date]').count()==2
            assert page.locator('#dateDialog button[data-days]').count()==3
            page.locator('#dateDialog button[data-days="7"]').click()
            assert page.locator("#dateDialog").is_visible(), "Preset must not immediately submit"
            assert page.locator("#startDate").input_value()
            assert page.locator("#endDate").input_value()
            page.locator("#closeDate").click()
            assert not page.locator("#dateDialog").is_visible()

            if not live:
                assert_rank_rows_centered(page,1200)
                assert n==270,f"Expected initial 270 visible card limit, got {n}"
                assert "B315" in page.locator("#count").text_content()
                assert page.locator("#more").is_visible()
                page.locator("#more").click()
                assert page.locator("article.post").count()==294, "Ads must be hidden without UI controls"
                assert page.locator("article[data-media-policy=adult] .post-thumb > img").count()>0
                assert page.locator("article[data-media-policy=restricted] .post-thumb > img").count()==0
                assert len(api_calls)>=21 and all("since" in q and "until" in q for q in api_calls)
                assert page.locator("#tabs,[data-term]").count()==0
                # All three terms remain in the unsegmented post feed.
                all_text=" ".join(page.locator("article.post .post-excerpt").all_inner_texts())
                assert all(term in all_text for term in TERMS)

                page.set_viewport_size({"width":390,"height":844})
                assert_rank_rows_centered(page,390)
                assert page.locator("#feed").evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")==3
                assert page.locator("#openDate").is_visible()
                assert page.locator("#openDate").evaluate("e=>e.getBoundingClientRect().right")<=391
                title=page.locator("header h1").bounding_box()
                shortcut=page.locator("header .header-consumer-entry").bounding_box()
                date=page.locator("header #openDate").bounding_box()
                assert abs((title["y"]+title["height"]/2)-(date["y"]+date["height"]/2))<14
                assert abs((title["y"]+title["height"]/2)-(shortcut["y"]+shortcut["height"]/2))<14
                assert shortcut["x"]+shortcut["width"]<=date["x"]+2, "Shortcut must not overlap the date selector"
                assert shortcut["x"]+shortcut["width"]<=391, "Shortcut must remain inside iPhone viewport"
                page.locator("#openDate").click()
                boxes=page.locator("#dateDialog input[type=date]").evaluate_all(
                  "els=>els.map(e=>e.getBoundingClientRect().toJSON())")
                assert abs(boxes[0]["y"]-boxes[1]["y"])<4,"Date fields must be side by side"
                assert boxes[1]["right"]<=392,"Date field must fit iPhone"
                page.locator("#applyDate").click()
                page.wait_for_function("document.getElementById('applyDate').disabled === false",timeout=120000)
                assert not page.locator("#dateDialog").is_visible()
                assert page.locator("#periodLabel").inner_text().count("~")==1

                provider_on["enabled"]=True
                page.locator("#openDate").click()
                page.locator("#applyDate").click()
                page.wait_for_function("document.getElementById('applyDate').disabled === false",timeout=120000)
                for provider in ("M3","L3","K3","R3"):
                    assert provider in page.locator("#count").text_content()
                while page.locator('.source-badge[aria-label="출처: Mastodon"]').count()==0:
                    assert page.locator("#more").is_visible()
                    page.locator("#more").click()
                for provider in ("Mastodon","Lemmy","Misskey","Reddit","Bluesky"):
                    card=page.locator("article.post").filter(
                        has=page.locator('.source-badge[aria-label="출처: '+provider+'"]')).first
                    assert card.count()==1,f"Missing {provider} badge"
                    assert card.locator("a.author[target=_blank]").count()==1
                assert page.locator('.source-badge[aria-label="출처: Mastodon"]').first.locator("img").count()==1
                mast=page.locator("article.post").filter(
                    has=page.locator('.source-badge[aria-label="출처: Mastodon"]')).first
                assert mast.locator("a.author").get_attribute("href")=="https://mastodon.social/@qa"
                blu=page.locator("article.post").filter(
                    has=page.locator('.source-badge[aria-label="출처: Bluesky"]')).first
                assert blu.locator("a.author").get_attribute("href")=="https://bsky.app/profile/qa-feed.bsky.social"
                accepted=page.evaluate("""() => window.INTERSECTION_acceptPublicX({
                  id:'1234567890123456789',
                  url:'https://x.com/qa_account/status/1234567890123456789',
                  text:'섹트 test-only public X image',
                  created_at:new Date().toISOString(),
                  author:'synthetic QA account',avatarUrl:'https://example.com/qa.png',
                  media:[{type:'image',url:'https://example.com/qa.png',
                          thumb:'https://example.com/qa.png'}],
                  protected:false
                })""")
                assert accepted["accepted"] is True,accepted
                xcard=page.locator("article.post").filter(
                    has=page.locator('.source-badge[aria-label="출처: X"]')).first
                assert xcard.count()==1,"source-validated X post must enter verified feed"
                assert xcard.locator(".post-thumb > img.post-media-img").count()==1,"X image must render as original thumbnail"
                assert not page.locator("#discoveryCandidates").is_visible(),"verified X post removes unverified search lead"
            else:
                assert n>=1,"No real public posts"
                assert thumbnails>0,"No public thumbnails"
                assert "B" in page.locator("#count").text_content()
                # An <img> element is not proof its bytes loaded. Decode
                # a bounded visible sample and report only aggregate counts.
                integrity=page.evaluate("""async () => {
                  const photos=[...document.querySelectorAll('article.post .post-thumb > img.post-media-img')].slice(0,40);
                  photos.forEach(img=>{img.loading='eager';});
                  await Promise.all(photos.map(async img=>{
                    try{
                      await Promise.race([
                        img.decode(),
                        new Promise(resolve=>setTimeout(resolve,6500))
                      ]);
                    }catch{}
                  }));
                  const actual=photos.filter(img=>img.isConnected);
                  return {
                    image_elements_sampled:photos.length,
                    decoded:actual.filter(img=>img.complete&&img.naturalWidth>0).length,
                    still_loading:actual.filter(img=>!img.complete).length,
                    attached_but_failed:actual.filter(img=>img.complete&&img.naturalWidth===0).length,
                    replaced_with_profile:document.querySelectorAll('.post-thumb img[alt*="프로필 사진"]').length,
                    compact_without_media:document.querySelectorAll('article.post[data-no-media="true"]').length
                  };
                }""")
                print("LIVE_PUBLIC_IMAGE_INTEGRITY",json.dumps(integrity,ensure_ascii=False),flush=True)

            assert not errors, "Browser JS exceptions: "+str(errors[:5])
            print("REAL_PUBLIC_BROWSER_SMOKE" if live else "INTERSECTION_COMPACT_QA",json.dumps({
                "visible_cards":n,"thumbs":thumbnails,"columns":3,
                "date_dialog":True,"ad_filter_always_on":True,
                "provider_counts":page.locator("#count").text_content(),
                "providers_http":provider_http,"providers_failed":provider_failed
            },ensure_ascii=False))
        finally:
            browser.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    run(live=parser.parse_args().live)
