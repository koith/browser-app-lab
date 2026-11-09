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
from urllib.parse import urlsplit
from PIL import Image
from playwright.sync_api import sync_playwright

TARGET={
    # Teddy Bear pages 1-10 have exact local copies: select an owner-only tile.
    "yui":[("teddy-bear97",13),("djawa-privaty-public-samples",0)],
    "mimmi":[("v2ph-actor-a8n8n85a",10),("v2ph-actor-zo5n754z",16)],
}
BASE="https://koith.github.io/browser-app-lab/apps"

def is_target_owner_media(url, model, album):
    # The restored production transport uses /api/v1/media/MODEL/ALBUM/...
    # while the legacy Render gateway used /api/MODEL/media/ALBUM/...
    # Match only the requested model and album; never weaken the 503->200 gate.
    path=urlsplit(url).path
    return (
        path.startswith(f"/api/v1/media/{model}/{album}/") or
        path.startswith(f"/api/{model}/media/{album}/") or
        path.startswith(f"/media/{album}/")
    )


def exercise(browser,model,album,index):
    ctx=browser.new_context(viewport={"width":390,"height":844},
            is_mobile=True,has_touch=True,service_workers="block",locale="ko-KR")
    page=ctx.new_page()
    root=f"{BASE}/{model}-gallery/"
    html=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
    png=io.BytesIO()
    Image.new("RGB",(320,480),(30,60,120)).save(png,format="PNG")
    mock_bytes=png.getvalue()
    phase={"warm":False,"errors":0,"recoveries":0,"readiness":0,"unnecessary_catalog":0}
    def mock_media(route):
        link=route.request.url
        if not is_target_owner_media(link,model,album):
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
    def reject_optional_catalog(route):
        phase["unnecessary_catalog"]+=1
        route.fulfill(status=503,body="static owner index should make this optional")
    page.route("**/api/catalog",reject_optional_catalog)
    page.route("**/api/yui/catalog",reject_optional_catalog)
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
        page.wait_for_function("""()=>
          [...ownerRecoveryPending].some(im=>im.isConnected&&
            !!im.closest('#detailphotos')&&!!im.dataset.owner)
        """,timeout=45000)
        # The intersection observer can have multiple owner photos in flight;
        # a fixed grid index is not necessarily the image whose 503 queued a
        # retry. Prove restoration of the EXACT failed image, not a neighbor.
        retry_index=page.evaluate("""() => {
          const all=[...document.querySelectorAll('#detailphotos .photo img')];
          return all.findIndex(im=>ownerRecoveryPending.has(im)&&im.dataset.owner);
        }""")
        assert retry_index>=0,(model,"no pending visible owner photo",phase)
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
        }""",arg=retry_index,timeout=30000)
        assert phase["recoveries"]>=1,(model,"no original retry after healthy status",phase)
        assert phase["readiness"]==0,(model,"global readiness must not be polled",phase)
        assert phase["unnecessary_catalog"]==0,(model,"static owner manifest triggered optional Render catalog",phase)
        print("GALLERY_OWNER_AUTO_RECOVERY_503_TO_200_MOCK_UI_PASS",json.dumps({
            "model":model,"album":album,"browser":browser.browser_type.name,
            "verified_failed_owner_tile_index":retry_index,
            "original_mock_errors":phase["errors"],
            "unnecessary_global_readiness_polls":phase["readiness"],
            "unnecessary_remote_catalog_requests":phase["unnecessary_catalog"],
            "original_mock_recoveries":phase["recoveries"],
            "same_page_no_reload":True,
            "real_owner_media_claimed":False,
            "real_iphone_hardware_claimed":False
        }),flush=True)
    finally:
        ctx.close()

if __name__=="__main__":
    assert is_target_owner_media("https://archive.example/api/v1/media/yui/teddy-bear97/13/original?h=x","yui","teddy-bear97")
    assert is_target_owner_media("https://archive.example/api/mimmi/media/v2ph-actor-a8n8n85a/11/original","mimmi","v2ph-actor-a8n8n85a")
    assert not is_target_owner_media("https://archive.example/api/v1/media/yui/other/13/original","yui","teddy-bear97")
    assert not is_target_owner_media("https://archive.example/api/v1/media/mimmi/teddy-bear97/13/original","yui","teddy-bear97")
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
