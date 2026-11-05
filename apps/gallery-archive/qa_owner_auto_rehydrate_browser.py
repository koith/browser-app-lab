#!/usr/bin/env python3
"""Test automatic owner tile recovery after a genuine mocked 503->200 transition.

Only the candidate inline gallery HTML comes from the PR. All photo metadata
comes from the real Pages owner-index. The returned tiny synthetic PNG is a
mock for UI behavior and MUST NOT be mistaken for restored owner photos.
"""
import argparse
import io
import json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

TARGET={
    "yui":[("teddy-bear97",0),("djawa-privaty-public-samples",0)],
    "mimmi":[("v2ph-actor-a8n8n85a",10),("v2ph-actor-zo5n754z",16)],
}
BASE="https://koith.github.io/browser-app-lab/apps"

def exercise(browser,model,album,index):
    ctx=browser.new_context(viewport={"width":390,"height":844},
            is_mobile=True,has_touch=True,service_workers="block",locale="ko-KR")
    page=ctx.new_page()
    root=f"{BASE}/{model}-gallery/"
    html=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
    png=io.BytesIO()
    Image.new("RGB",(320,480),(30,60,120)).save(png,format="PNG")
    mock_bytes=png.getvalue()
    phase={"warm":False,"errors":0,"recoveries":0,"readiness":0}
    def mock_media(route):
        link=route.request.url
        if f"/media/{album}/" not in link:
            route.continue_()
            return
        if phase["warm"] and "/original" in link:
            phase["recoveries"]+=1
            route.fulfill(status=200,body=mock_bytes,content_type="image/png",
                headers={"Access-Control-Allow-Origin":"https://koith.github.io"})
        else:
            phase["errors"]+=1
            route.fulfill(status=503,body="mock temporary owner 503",
                headers={"Access-Control-Allow-Origin":"https://koith.github.io",
                         "Cache-Control":"no-store"})
    def reject_global_poll(route):
        phase["readiness"]+=1
        route.fulfill(status=500,body="old global readiness endpoint must not gate an album")
    page.route(root,lambda route:route.fulfill(status=200,content_type="text/html",body=html))
    page.route("**/api/gallery-media-readiness",reject_global_poll)
    page.route("**/media/**",mock_media)
    try:
        response=page.goto(root+"#album="+album,wait_until="domcontentloaded",timeout=60000)
        assert response and response.status==200
        page.wait_for_function("""album=>typeof ownerRecoveryPending!=='undefined' &&
          stored.some(a=>a.id===album) &&
          document.querySelector('#detail')?.hidden===false
        """,arg=album,timeout=90000)
        photo=page.locator("#detailphotos .photo").nth(index)
        image=photo.locator("img")
        photo.scroll_into_view_if_needed(timeout=20000)
        page.wait_for_function("""idx=>ownerRecoveryPending.size>0 &&
          !!document.querySelectorAll('#detailphotos .photo img')[idx]?.dataset.owner
        """,arg=index,timeout=45000)
        assert phase["errors"]>=1,(model,"mocked 503 not exercised",phase)
        # Backend becomes ready without a page refresh. The user refocuses
        # the existing tab and the same tile must repaint automatically.
        phase["warm"]=True
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        page.wait_for_function("""idx=>{
          const im=document.querySelectorAll('#detailphotos .photo img')[idx];
          return im && im.complete && im.naturalWidth===320 &&
                 im.naturalHeight===480 && !im.hidden &&
                 !im.closest('.photo')?.classList.contains('broken-source') &&
                 im.closest('.photo')?.dataset.imageState!=='failed';
        }""",arg=index,timeout=30000)
        assert phase["recoveries"]>=1,(model,"no original retry after healthy status",phase)
        assert phase["readiness"]==0,(model,"global readiness must not be polled",phase)
        print("GALLERY_OWNER_AUTO_RECOVERY_503_TO_200_MOCK_UI_PASS",json.dumps({
            "model":model,"album":album,"browser":browser.browser_type.name,
            "original_mock_errors":phase["errors"],
            "unnecessary_global_readiness_polls":phase["readiness"],
            "original_mock_recoveries":phase["recoveries"],
            "same_page_no_reload":True,
            "real_owner_media_claimed":False,
            "real_iphone_hardware_claimed":False
        }),flush=True)
    finally:
        ctx.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=("chromium","webkit"),required=True)
    args=parser.parse_args()
    with sync_playwright() as pw:
        browser=getattr(pw,args.browser).launch(headless=True)
        try:
            for model in ("mimmi","yui"):
                for album,index in TARGET[model]:exercise(browser,model,album,index)
        finally:
            browser.close()
