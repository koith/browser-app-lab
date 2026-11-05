#!/usr/bin/env python3
"""Real Pages mobile browser acceptance for the two failed iPhone screenshot albums.

No media writes, owner credentials, source-site crawling or synthetic placeholders.
Exact historical album IDs and counts must show real decoded images in the
DOM; independent 214-photo SHA readback is handled in qa_live_214_*.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE = "https://koith.github.io/browser-app-lab/apps"
TARGETS = {
    "mimmi": ("v2ph-actor-a8n8n85a", 61),
    "yui": ("teddy-bear97", 97),
}

def check(browser, model):
    album, wanted = TARGETS[model]
    ctx = browser.new_context(
        viewport={"width":390,"height":844},is_mobile=True,has_touch=True,
        device_scale_factor=2,locale="ko-KR",
    )
    page = ctx.new_page()
    errors = []
    failures = []
    page.on("pageerror", lambda err: errors.append(str(err)[:200]))
    page.on("response", lambda resp: failures.append({
        "code":resp.status,"route":resp.url.split("?")[0].split("/")[-3:]
    }) if resp.status >= 400 and "/media/" in resp.url else None)
    url = f"{BASE}/{model}-gallery/#album={album}"
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=65000)
        assert resp and resp.status == 200, (model,"Pages HTML",resp.status if resp else None)
        page.wait_for_function("""({album,wanted}) => {
          const a=stored.find(a=>a.id===album);
          return a && photosFor(a).length===wanted &&
                 document.querySelector('#detail')?.hidden===false &&
                 document.querySelectorAll('#detailphotos .photo').length===wanted;
        }""",arg={"album":album,"wanted":wanted},timeout=95000)
        tiles = page.locator("#detailphotos .photo")
        assert tiles.count() == wanted, (model,"missing original photo tiles",tiles.count())
        # Navigate as a visitor to cause IntersectionObserver to start every
        # actual image request, rather than merely checking its index record.
        for i in range(wanted):
            img=tiles.nth(i).locator("img")
            img.scroll_into_view_if_needed(timeout=25000)
            try:
                page.wait_for_function("""idx => {
                  const im=document.querySelectorAll('#detailphotos .photo img')[idx];
                  return im && im.complete && im.naturalWidth >= 160 && im.naturalHeight>=160;
                }""",arg=i,timeout=24000)
            except PlaywrightTimeoutError as exc:
                state=page.evaluate("""i => {
                  const im=document.querySelectorAll('#detailphotos .photo img')[i];
                  const card=im?.closest('.photo');
                  return {has_image:!!im,complete:im?.complete,
                          width:im?.naturalWidth||0,
                          failed:card?.dataset.imageState||null,
                          has_owner:im?.hasAttribute('data-owner')||false,
                          source_host:(()=>{try{return new URL(im?.currentSrc||im?.src,location.href).hostname}catch{return null}})()};
                }""",i)
                raise AssertionError((model,album,"user-visible-photo-did-not-decode",i+1,state)) from exc
        # Actual tapped fullscreen viewer at beginning, middle and end;
        # independently read displayed original and verify exact saved SHA.
        samples=sorted({0, wanted//2, wanted-1})
        for index in samples:
            tiles.nth(index).click(timeout=35000)
            page.wait_for_function("""() => {
              const im=document.querySelector('#full');
              return document.querySelector('#lightbox.open')&&
                im?.complete && im.naturalWidth>=160 && im.naturalHeight>=160;
            }""",timeout=55000)
            meta=page.evaluate("""i => {
              const a=stored.find(a=>a.id===location.hash.match(/album=([^&]+)/)?.[1])||
                stored.find(a=>a.id===document.querySelector('#detailphotos')?.dataset.album);
              const first=stored.find(a=>a.id==='__ALBUM__');
              const p=photosFor(first)[i];
              const im=document.querySelector('#full');
              return {src:new URL(im.currentSrc||im.src,location.href).href,
                sha:p.sha256, bytes:p.bytes, width:p.width, height:p.height,
                actual_width:im.naturalWidth, actual_height:im.naturalHeight};
            }""".replace("__ALBUM__",album),index)
            assert (meta["actual_width"],meta["actual_height"]) == (
                meta["width"],meta["height"]), (model,index,"wrong decoded image dimensions")
            response=ctx.request.get(meta["src"],timeout=60000)
            assert response.status==200, (model,index,"fullscreen HTTP",response.status)
            payload=response.body()
            assert len(payload)==meta["bytes"], (model,index,"wrong original length")
            assert hashlib.sha256(payload).hexdigest()==meta["sha"],(model,index,"wrong original hash")
            page.locator("#close").click(timeout=12000)
            page.wait_for_function("() => !document.querySelector('#lightbox.open')",timeout=12000)
        assert not errors,(model,"browser runtime errors",errors)
        print("USER_SCREENSHOT_ACTUAL_PAGES_ALBUM_BROWSER_PASS",json.dumps({
            "model":model,"album":album,"browser":browser.browser_type.name,
            "expected":wanted,"all_photo_tiles_decoded":wanted,
            "fullscreen_sample_exact_original_SHA":len(samples),
            "runtime_errors":0,"provider_error_requests_observed":len(failures),
            "physical_iPhone_hardware_tested":False,
            "render_cold_restart_survival_verified":False
        },ensure_ascii=False),flush=True)
    finally:
        ctx.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",required=True,choices=("chromium","webkit"))
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=getattr(p,args.browser).launch(headless=True)
        try:
            for model in ("yui","mimmi"):
                check(browser,model)
        finally:
            browser.close()
