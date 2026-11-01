#!/usr/bin/env python3
"""Real Render user-entry gallery browser QA; no login, private artifacts or credentials."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT="https://mimmi-private-gallery-free.onrender.com/gallery"
WORKS={"yui":["yuis-present33","athletic-club104","teddy-bear97"],"mimmi":["mimmi-indie-sana-sopmod2-2019","djawa-rei-beyond-the-heart"]}
MIN={"yui":3050,"mimmi":4000}

def exercise(browser,model,branch_html=False):
    context=browser.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,locale="ko-KR")
    page=context.new_page()
    errors=[];bad=[]
    page.on("pageerror",lambda e:errors.append(str(e)[:240]))
    page.on("response",lambda r:bad.append((r.status,r.url.split("?")[0][-130:])) if r.status>=400 and "/gallery/" in r.url else None)
    url=f"{ROOT}/{model}/"
    # PR builds test their candidate UI against the REAL deployed Render API;
    # production main runs must use real, unmodified Render HTML end-to-end.
    if branch_html:
        body=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
        page.route(url,lambda route:route.fulfill(status=200,content_type="text/html",body=body))
    try:
        resp=page.goto(url,wait_until="domcontentloaded",timeout=70000)
        assert resp and resp.status==200,(model,"HTTP",resp.status if resp else None)
        assert page.url.startswith(url)
        # A live production PASS must verify the new code is served by Render,
        # not old proxy-cached HTML that happens to pass a nondeterministic race.
        if not branch_html:
            marker="GalleryPhotoQuality.preferred(previous,p)"
            for _ in range(9):
                if page.evaluate("""marker=>[...document.scripts].some(s=>s.textContent.includes(marker))""",marker):
                    break
                page.wait_for_timeout(30000)
                page.reload(wait_until="domcontentloaded",timeout=70000)
            assert page.evaluate("""marker=>[...document.scripts].some(s=>s.textContent.includes(marker))""",marker),(model,"Render still serves old gallery HTML")
        assert page.locator('input[type="password"]').count()==0
        # Both first-party origins must actually load the new script (not only
        # return old HTML/200 shell from a proxy cache).
        page.wait_for_function("""()=>typeof GalleryPhotoQuality!=='undefined'
            &&typeof GalleryPhotoQuality.preferred==='function'
            &&!!document.querySelector('script[src^="image-quality.js"]')""",timeout=30000)
        if model=="yui":
            assert page.evaluate("""()=>['sweetbox','bcut','milkybomb'].every(id=>{
                const group=publisherRegistry.publishers.find(x=>x.id===id);
                return group && YuiPublishers.logo(group)===null;
            })"""),"Unverified publisher logos reappeared"
        page.wait_for_function("""limit=>typeof stored!=='undefined'&&stored.reduce((n,a)=>n+a.images.length,0)>=limit&&document.querySelectorAll('#albumgrid .album').length>0&&document.querySelector('#inventory')?.textContent.includes('실제 저장본')""",arg=MIN[model],timeout=90000)
        stats=page.evaluate("""()=>({photos:stored.reduce((n,a)=>n+a.images.length,0),owner:stored.reduce((n,a)=>n+a.images.filter(p=>p.ownerAlbum).length,0),works:document.querySelectorAll('#albumgrid .album').length})""")
        assert not errors and not bad,(model,"script or asset failures",errors,bad)
        for album_id in WORKS[model]:
            selector=f'#albumgrid .album[data-id="{album_id}"]'
            assert page.locator(selector).count()==1,(model,album_id,"missing")
            page.locator(selector).scroll_into_view_if_needed(timeout=20000)
            page.wait_for_function("""id=>{const im=document.querySelector('#albumgrid .album[data-id="'+id+'"] img');return im?.complete&&im.naturalWidth>=160}""",arg=album_id,timeout=90000)
            page.locator(selector).click()
            assert page.locator("#detail").is_visible()
            page.locator("#detailphotos .photo").first.scroll_into_view_if_needed()
            page.wait_for_function("""()=>{const im=document.querySelector('#detailphotos .photo img');return im?.complete&&im.naturalWidth>=160}""",timeout=90000)
            page.locator("#detailphotos .photo").first.click()
            page.wait_for_function("""()=>{const im=document.querySelector('#full');return im?.complete&&im.naturalWidth>=160}""",timeout=90000)
            assert page.locator("#lightbox").is_visible()
            page.locator("#close").click()
            page.locator("#back").click()
            page.wait_for_function("()=>document.querySelectorAll('#albumgrid .album').length>0",timeout=20000)
        page.reload(wait_until="domcontentloaded",timeout=70000)
        page.wait_for_function("()=>document.querySelectorAll('#albumgrid .album').length>0",timeout=90000)
        assert not errors and not bad,(model,"errors after reload",errors,bad)
        print("RENDER_BRANCH_UI_LIVE_API_BROWSER_PASS" if branch_html else "RENDER_USER_ENTRY_REAL_PHOTO_BROWSER_PASS",json.dumps({"model":model,**stats,"opened":WORKS[model],"reload":True,"real_iphone_hardware":False}),flush=True)
    finally:context.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=["webkit","chromium"],required=True)
    parser.add_argument("--branch-html",action="store_true",help="Only for PR: checkout HTML + production API")
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=getattr(p,args.browser).launch(headless=True)
        try:
            for m in ("yui","mimmi"):exercise(browser,m,args.branch_html)
        finally:browser.close()
    print("BOTH_RENDER_BRANCH_UI_BROWSER_PASS" if args.branch_html else "BOTH_RENDER_GALLERIES_REAL_BROWSER_PASS",args.browser,flush=True)
