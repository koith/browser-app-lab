#!/usr/bin/env python3
"""Real Pages bytes + browser integration for SHA-identical cross-album fallback.

PR mode overlays the candidate HTML/JS onto the REAL Pages origin. Post-deploy
mode uses the exact live published files without overlay; those are distinct
levels of evidence. No Render, TeraBox secrets or actual phone hardware.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

BASE="https://koith.github.io/browser-app-lab/apps"
MAX_PHOTOS_PER_MODEL=5

def exercise(browser,model,overlay):
    root=f"{BASE}/{model}-gallery/"
    page_context=browser.new_context(viewport={"width":390,"height":844},
       device_scale_factor=2,is_mobile=True,has_touch=True,locale="ko-KR",
       service_workers="block")
    page=page_context.new_page()
    exceptions=[]
    page.on("pageerror",lambda e:exceptions.append(str(e)[:300]))
    if overlay:
        html=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
        script=Path(f"apps/{model}-gallery/saved-photo-union.js").read_text(encoding="utf-8")
        page.route(root,lambda route:route.fulfill(status=200,content_type="text/html",body=html))
        page.route("**/saved-photo-union.js*",lambda route:route.fulfill(
            status=200,content_type="application/javascript",body=script))
        if model=="mimmi":
            groups=Path("apps/mimmi-gallery/album-grouping.js").read_text(encoding="utf-8")
            page.route("**/album-grouping.js*",lambda route:route.fulfill(
                status=200,content_type="application/javascript",body=groups))
    try:
        r=page.goto(root,wait_until="domcontentloaded",timeout=60000)
        assert r and r.status==200,(model,"gallery HTML",r.status if r else None)
        page.wait_for_function("""() =>
            Array.isArray(stored) && stored.length>0 &&
            stored.some(a=>a.images.some(p=>p.shaPinnedLocalCopy===true)) &&
            document.querySelectorAll('#albumgrid .album').length>0
        """,timeout=80000)
        data=page.evaluate("""() => {
          const matches=[];
          for(const a of stored){
            const visible=photosFor(a);
            visible.forEach((p,i)=>{
              if(p.shaPinnedLocalCopy===true &&
                 typeof p.url==='string' && p.url.startsWith('stored-albums/') &&
                 !p.ownerAlbum && p.originalAlbumId && p.originalAlbumId!==a.id &&
                 p.bytes>4500 && p.width>=160 && p.height>=160) {
                 matches.push({album:a.id,index:i,url:p.url,sha:p.sha256,
                   bytes:p.bytes,width:p.width,height:p.height,originalAlbumId:p.originalAlbumId});
              }
            });
          }
          const favorite=matches.filter(p=>p.album==='teddy-bear97'||
                        p.album==='v2ph-actor-a584e85z');
          const targets=(favorite.length?favorite:matches).slice(0,5);
          return {total:matches.length,targets};
        }""")
        assert data["total"]>0,(model,"no real cross-album photos used in composed UI")
        assert len(data["targets"])>=1,(model,"nothing to decode")
        opened=0
        for target in data["targets"]:
            page.evaluate("id=>openAlbum(id)",target["album"])
            page.wait_for_function("idx=>document.querySelectorAll('#detailphotos .photo').length>idx",
                                    arg=target["index"],timeout=25000)
            card=page.locator("#detailphotos .photo").nth(target["index"])
            card.scroll_into_view_if_needed(timeout=25000)
            card.locator("img").wait_for(state="visible",timeout=25000)
            card.click(timeout=25000)
            expected=root+target["url"]
            page.wait_for_function("""wanted=>{
              const img=document.querySelector('#full');
              return !!document.querySelector('#lightbox.open') &&
                img && img.complete && img.naturalWidth>=160 &&
                new URL(img.currentSrc||img.src,location.href).href===wanted;
            }""",arg=expected,timeout=45000)
            picture=page.evaluate("""()=>{
               const im=document.querySelector('#full');
               return {width:im.naturalWidth,height:im.naturalHeight,src:im.currentSrc||im.src};
            }""")
            assert picture["width"]==target["width"] and picture["height"]==target["height"],(model,"browser dimensions",target,picture)
            independent=page_context.request.get(expected,timeout=45000)
            assert independent.status==200,(model,"actual Pages image HTTP",independent.status,expected)
            data_bytes=independent.body()
            assert hashlib.sha256(data_bytes).hexdigest()==target["sha"],(model,"live bytes SHA",target["album"])
            assert len(data_bytes)==target["bytes"],(model,"live bytes length",target["album"])
            with Image.open(io.BytesIO(data_bytes)) as img:
                img.verify()
            opened+=1
            page.locator("#close").click(timeout=20000)
        assert not exceptions,(model,"JavaScript exceptions",exceptions)
        print("REAL_PAGES_CROSS_ALBUM_SHA_LIGHTBOX_PASS",json.dumps({
            "model":model,"candidate_html":overlay,"sha_exact_cross_album_candidates":data["total"],
            "actual_independent_sha_and_pixel_rechecks":opened,
            "real_pages_assets":True,"render_dependency":False,
            "iphone_hardware":False},sort_keys=True),flush=True)
    finally:
        page_context.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=("chromium","webkit"),required=True)
    parser.add_argument("--candidate-html",action="store_true")
    args=parser.parse_args()
    with sync_playwright() as playwright:
        browser=getattr(playwright,args.browser).launch(headless=True)
        try:
            for model in ("mimmi","yui"):exercise(browser,model,args.candidate_html)
        finally:browser.close()
