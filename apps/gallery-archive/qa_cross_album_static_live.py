#!/usr/bin/env python3
"""Live Pages exact-SHA fallback across different albums with Render blocked.

This only reuses already-published SHA-identical bytes within the same model.
No cross-model routes, new uploads, provider requests or private media writing.
"""
import argparse
import hashlib
import json
from playwright.sync_api import sync_playwright

ROOT="https://koith.github.io/browser-app-lab/apps"

def check(browser,model):
    context=browser.new_context(viewport={"width":390,"height":844},
        is_mobile=True,has_touch=True,locale="ko-KR",device_scale_factor=2)
    page=context.new_page()
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)[:180]))
    page.route("**/*onrender.com/**",lambda route:route.abort("blockedbyclient"))
    root=f"{ROOT}/{model}-gallery/"
    try:
        result=page.goto(root,wait_until="domcontentloaded",timeout=60000)
        assert result and result.status==200
        page.wait_for_function("""() => Array.isArray(localStored)&&
            localStored.length>0 && Array.isArray(stored)&&stored.length>0 &&
            typeof localSavedFor==='function'""",timeout=70000)
        choice=page.evaluate("""() => {
          const full=localStored.flatMap(a=>a.images.map(p=>({
            album:a.id,sha:p.sha256,bytes:p.bytes,width:p.width,height:p.height,url:p.url
          })));
          const exact=p=>[p.sha256,p.bytes,p.width,p.height].join('|');
          const sha=new Map(full.map(p=>[exact(p),p]));
          const candidates=[];
          for(const a of stored){
            for(const [i,p] of photosFor(a).entries()){
              if(!p.ownerAlbum||i>=48)continue;
              const local=sha.get(exact(p));
              if(!local||local.album===a.id)continue;
              const copy=localSavedFor(p);
              if(!copy||copy.url!==local.url)continue;
              candidates.push({album:a.id, index:i, sha:p.sha256,
                  bytes:p.bytes,width:p.width,height:p.height,url:copy.url,
                  from:local.album,originalOwnerUrl:p.url});
            }
          }
          candidates.sort((a,b)=>a.index-b.index||a.bytes-b.bytes);
          return {count:candidates.length,choice:candidates[0]||null};
        }""")
        candidate=choice["choice"]
        assert candidate,(model,"no existing cross-work exact-SHA photo in first 48 rows")
        page.evaluate("album => openAlbum(album)",candidate["album"])
        page.wait_for_function("""i=>document.querySelectorAll('#detailphotos .photo').length>i""",
            arg=candidate["index"],timeout=25000)
        image=page.locator("#detailphotos .photo img").nth(candidate["index"])
        page.wait_for_function("""i => {
          const img=document.querySelectorAll('#detailphotos .photo img')[i];
          return img&&img.complete&&img.naturalWidth>=160;
        }""",arg=candidate["index"],timeout=50000)
        src=image.get_attribute("src")
        assert src==candidate["url"],(model,"wrong source selected",src,candidate)
        response=context.request.get(root+candidate["url"],timeout=60000)
        assert response.status==200,(model,response.status)
        data=response.body()
        assert hashlib.sha256(data).hexdigest()==candidate["sha"],model
        assert len(data)==candidate["bytes"],model
        image.click(timeout=30000)
        page.wait_for_function("""expected => {
          const img=document.querySelector('#full');
          return document.querySelector('#lightbox.open') &&
            img && img.complete && img.naturalWidth>=160 &&
            new URL(img.currentSrc||img.src,location.href).href===expected;
        }""",arg=root+candidate["url"],timeout=45000)
        assert not errors,(model,errors)
        print("GALLERY_CROSS_WORK_EXACT_PAGES_ORIGINAL_LIVE_PASS",json.dumps({
            "browser":browser.browser_type.name,"model":model,
            "cross_album_candidate_count":choice["count"],
            "owner_album":candidate["album"],"public_source_album":candidate["from"],
            "sha256_verified":True,"bytes_verified":True,
            "tile_and_lightbox_decoded":True,"render_blocked":True,
            "other_owner_private_bytes_published":False,
            "actual_iphone_hardware":False
        }),flush=True)
    finally:
        context.close()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--browser",choices=("chromium","webkit"),required=True)
    args=p.parse_args()
    with sync_playwright() as pw:
        browser=getattr(pw,args.browser).launch(headless=True)
        try:
            for model in ("mimmi","yui"):check(browser,model)
        finally:browser.close()
