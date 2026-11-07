#!/usr/bin/env python3
"""Trace exact Yui v04 SHA from stored union -> detail -> lightbox in real browser."""
import json
from playwright.sync_api import sync_playwright
BASE="https://koith.github.io/browser-app-lab/apps/yui-gallery/"
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)[:180]))
    page.goto(BASE,wait_until="domcontentloaded",timeout=70000)
    page.wait_for_function("""()=>typeof stored!=='undefined'&&stored.some(a=>a.id==='v04')
      &&document.querySelector('#albumgrid .album[data-id="v04"]')""",timeout=70000)
    selected=page.evaluate("""()=>{
      const a=stored.find(a=>a.id==='v04');
      return photosFor(a).map((p,i)=>({
        index:i,number:p.number,storageNumber:p.storageNumber??null,
        sha256:p.sha256,bytes:p.bytes,width:p.width,height:p.height,
        ownerAlbum:p.ownerAlbum||null,url:p.url
      }));
    }""")
    target=next((p for p in selected if p["ownerAlbum"]=="v04" and p["storageNumber"]==1),None)
    assert target, "Actual owner photo not found in saved v04 union"
    print("YUI_V04_GALLERY_UNION_OWNER_TARGET",json.dumps({
      "index":target["index"],"display_number":target["number"],
      "sha256":target["sha256"],"metadata_dimensions":[target["width"],target["height"]],
      "total_display_photos":len(selected)}),flush=True)
    page.locator('#albumgrid .album[data-id="v04"]').click(timeout=40000)
    page.locator('#detail').wait_for(state="visible",timeout=45000)
    locator=page.locator(f'#detailphotos .photo[data-i="{target["index"]}"]')
    locator.scroll_into_view_if_needed(timeout=30000)
    locator.click(timeout=30000)
    page.locator("#lightbox").wait_for(state="visible",timeout=30000)
    page.wait_for_function("""()=>document.querySelector('#full')?.complete
      &&document.querySelector('#full')?.naturalWidth>=100""",timeout=70000)
    observation=page.evaluate("""()=>({
      displayed:{width:document.querySelector('#full').naturalWidth,
       height:document.querySelector('#full').naturalHeight},
      viewer:{sha256:viewerList[viewerIndex]?.sha256,
        ownerAlbum:viewerList[viewerIndex]?.ownerAlbum||null,
        number:viewerList[viewerIndex]?.number,
        storageNumber:viewerList[viewerIndex]?.storageNumber||null,
        declaredWidth:viewerList[viewerIndex]?.width,
        declaredHeight:viewerList[viewerIndex]?.height,
        url:viewerList[viewerIndex]?.url},
      mediaSource:new URL(document.querySelector('#full').currentSrc||document.querySelector('#full').src).pathname,
      variantStatus:document.querySelector('#media-status')?.textContent,
      version:document.querySelector('#app-version')?.textContent
    })""")
    print("YUI_V04_GALLERY_SELECTED_PHOTO_TRACE",json.dumps(observation),flush=True)
    print("YUI_V04_GALLERY_PAGE_ERRORS",json.dumps(errors),flush=True)
    assert observation["viewer"]["sha256"]==target["sha256"],"Selected wrong SHA in UI"
    assert observation["viewer"]["ownerAlbum"]=="v04","Selected wrong media source"
    assert observation["displayed"]=={"width":target["width"],"height":target["height"]},(
      "Viewer decoded dimensions do not match actual selected SHA-indexed owner photo")
    browser.close()
    print("YUI_V04_END_TO_END_OWNER_SHA_AND_PIXELS_PASS",flush=True)
