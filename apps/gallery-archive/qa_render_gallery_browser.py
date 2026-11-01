#!/usr/bin/env python3
"""Real Render user-entry gallery browser QA; no login, private artifacts or credentials."""
import argparse
import json
from playwright.sync_api import sync_playwright

ROOT="https://mimmi-private-gallery-free.onrender.com/gallery"
WORKS={"yui":["yuis-present33","athletic-club104","teddy-bear97"],"mimmi":["mimmi-indie-sana-sopmod2-2019","djawa-rei-beyond-the-heart"]}
MIN={"yui":3050,"mimmi":4000}

def exercise(browser,model):
    context=browser.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,locale="ko-KR")
    page=context.new_page()
    errors=[];bad=[]
    page.on("pageerror",lambda e:errors.append(str(e)[:240]))
    page.on("response",lambda r:bad.append((r.status,r.url.split("?")[0][-130:])) if r.status>=400 and "/gallery/" in r.url else None)
    url=f"{ROOT}/{model}/"
    try:
        resp=page.goto(url,wait_until="domcontentloaded",timeout=70000)
        assert resp and resp.status==200,(model,"HTTP",resp.status if resp else None)
        assert page.url.startswith(url)
        assert page.locator('input[type="password"]').count()==0
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
        print("RENDER_USER_ENTRY_REAL_PHOTO_BROWSER_PASS",json.dumps({"model":model,**stats,"opened":WORKS[model],"reload":True,"real_iphone_hardware":False}),flush=True)
    finally:context.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=["webkit","chromium"],required=True)
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=getattr(p,args.browser).launch(headless=True)
        try:
            for m in ("yui","mimmi"):exercise(browser,m)
        finally:browser.close()
    print("BOTH_RENDER_GALLERIES_REAL_BROWSER_PASS",args.browser,flush=True)
