#!/usr/bin/env python3
"""Real mobile browser regression for four previously owned incident albums.

Chrome/WebKit visit the deployed GitHub Pages viewer, wait for the owner
catalog, open actual detail thumbnails and full-screen images, and independently
compare returned bytes to existing SHA. No credentials, image persistence,
screenshots, collection or publisher data changes.
"""
import argparse
import hashlib
import json
from urllib.parse import urlparse
from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

PAGES="https://koith.github.io/browser-app-lab/apps"
TARGET={
 "mimmi":[("djawa-janus-scary-lantern-night",15),
          ("mimmi-indie-sana-sopmod2-2019",7)],
 "yui":[("djawa-privaty-public-samples",30),
        ("yui-chinokun-illustar-2026-public",4)],
}

def detail(browser,model):
    ctx=browser.new_context(viewport={"width":390,"height":844},
        is_mobile=True,has_touch=True,device_scale_factor=2,locale="ko-KR")
    page=ctx.new_page()
    errors=[]
    bad=[]
    page.on("pageerror",lambda e:errors.append(str(e)[:200]))
    page.on("response",lambda r:bad.append({
        "status":r.status,"path":urlparse(r.url).path[-100:]
    }) if r.status>=400 and "/media/" in r.url else None)
    base=PAGES+"/"+model+"-gallery/"
    try:
        response=page.goto(base,wait_until="domcontentloaded",timeout=65000)
        assert response and response.status==200,(model,"Pages HTML not available")
        for album_id,count in TARGET[model]:
            # A page's static index is not evidence that the owner catalog
            # finished merging. Require the expected stored private entries.
            try:
                page.wait_for_function("""pair => {
                  if(typeof photosFor !== 'function'||!Array.isArray(stored))return false;
                  const a=stored.find(a=>a.id===pair[0]);
                  if(!a)return false;
                  return photosFor(a).filter(p=>p.ownerAlbum).length>=pair[1];
                }""",arg=[album_id,count],timeout=70000)
            except PWTimeout:
                summary=page.evaluate("""id=>{
                  const a=typeof stored==='undefined'?null:stored.find(x=>x.id===id);
                  return {available:!!a,total:a?.images?.length||0,
                    owners:a?.images?.filter(p=>p.ownerAlbum).length||0};
                }""",album_id)
                raise AssertionError((model,album_id,"owner catalog not joined",summary))
            candidates=page.evaluate("""id => {
              const a=stored.find(x=>x.id===id);
              return photosFor(a).map((p,index)=>({
                index,number:p.number,sha:p.sha256,bytes:p.bytes,
                owner:!!p.ownerAlbum,hasLocal:!!exactSavedViewerCopy(p),
              })).filter(x=>x.owner);
            }""",album_id)
            assert len(candidates)>=count,(model,album_id,len(candidates))
            # At least one owner-only photo, not just an already public Pages
            # static image, must decode in the *actual* album and lightbox.
            remote=[x for x in candidates if not x["hasLocal"]]
            first=(remote or candidates)[0]
            page.evaluate("id=>openAlbum(id)",album_id)
            assert page.locator("#detail").is_visible(),(model,album_id,"detail closed")
            photo=page.locator("#detailphotos .photo").nth(first["index"])
            photo.scroll_into_view_if_needed(timeout=35000)
            try:
                page.wait_for_function("""idx => {
                  const node=document.querySelectorAll('#detailphotos .photo')[idx];
                  const im=node?.querySelector('img');
                  return im?.complete && im.naturalWidth>=160;
                }""",arg=first["index"],timeout=65000)
            except PWTimeout as exc:
                state=page.evaluate("""idx => {
                  const node=document.querySelectorAll('#detailphotos .photo')[idx];
                  const im=node?.querySelector('img');
                  return {present:!!node,src:im?.getAttribute('src')?.split('?')[0]||null,
                    decoded:im?.naturalWidth||0,
                    failed:node?.dataset.imageState||null};
                }""",first["index"])
                raise AssertionError((model,album_id,"detail image failed",state,bad[-5:])) from exc
            photo.click()
            try:
                page.wait_for_function("""() => {
                  const im=document.querySelector('#full');
                  return !!document.querySelector('#lightbox.open') &&
                    im?.complete && im.naturalWidth>=160;
                }""",timeout=65000)
            except PWTimeout as exc:
                state=page.evaluate("""() => ({
                  status:document.querySelector('#media-status')?.textContent||'',
                  src:document.querySelector('#full')?.getAttribute('src')?.split('?')[0]||null,
                  decoded:document.querySelector('#full')?.naturalWidth||0
                })""")
                raise AssertionError((model,album_id,"lightbox image failed",state,bad[-5:])) from exc
            source=page.locator("#full").evaluate("(im)=>im.currentSrc||im.src")
            image=ctx.request.get(source,timeout=65000,headers={"Cache-Control":"no-cache"})
            assert image.status==200,(model,album_id,"lightbox image HTTP",image.status)
            payload=image.body()
            assert hashlib.sha256(payload).hexdigest()==first["sha"],(model,album_id,"lightbox SHA mismatch")
            assert len(payload)==first["bytes"],(model,album_id,"lightbox byte count mismatch")
            print("LIVE_INCIDENT_MOBILE_LIGHTBOX_PASS",json.dumps({
              "model":model,"album":album_id,"browser":browser.browser_type.name,
              "photo_number":first["number"],"owner_only":bool(remote),
              "detail_decoded":True,"full_decoded":True,
              "independent_sha":True,"mobile_viewport":True,
              "physical_iphone_verified":False
            }),flush=True)
            page.locator("#close").click()
            page.evaluate("()=>setMode('albums')")
        assert not errors,(model,"JS exceptions",errors[-5:])
    finally:ctx.close()


if __name__=="__main__":
    args=argparse.ArgumentParser()
    args.add_argument("--browser",choices=("chromium","webkit"),required=True)
    args.add_argument("--model",choices=("mimmi","yui"),required=True)
    opts=args.parse_args()
    with sync_playwright() as pw:
        browser=getattr(pw,opts.browser).launch(headless=True)
        try:detail(browser,opts.model)
        finally:browser.close()
