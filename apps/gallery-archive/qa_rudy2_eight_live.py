#!/usr/bin/env python3
"""Check the 8 newly saved real Mimmi Rudy2 public photographs against Pages.

No synthetic image substitutions, guessed original links, owner secrets or
assertion that the publisher's 200-photo paid edition has been collected.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
SITE="https://koith.github.io/browser-app-lab/apps/mimmi-gallery/"
ID="djawa-rudy2-codename-wolfgirl"

def offline():
    base=ROOT/"apps/mimmi-gallery"
    albums=json.loads((base/"stored-albums.json").read_text())["albums"]
    owner=json.loads((base/"owner-index.json").read_text())["albums"]
    works=[a for a in albums if a["id"]==ID]
    assert len(works)==1
    photos=works[0]["images"]
    assert len(photos)==8,("not 8 actual stored JPG files",len(photos))
    own_sha={p["sha256"] for a in owner for p in a["images"]}
    sha=set()
    total=0
    for i,p in enumerate(photos,1):
        assert p["number"]==i and p["sha256"] not in sha and p["sha256"] not in own_sha
        sha.add(p["sha256"])
        path=(base/p["url"]).resolve()
        assert path.is_relative_to((base/"stored-albums"/ID).resolve())
        raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==p["sha256"]
        assert len(raw)==p["bytes"]
        with Image.open(path) as im:
            im.load()
            assert im.format=="JPEG"
            assert im.size==(p["width"],p["height"])
            assert min(im.size)>=500
        total+=len(raw)
    assert total==4923277,("wrong real photo bytes",total)
    print("RUDY2_ALL_8_REAL_SHA_PIL_NO_OWNER_DUP_PASS",json.dumps({
       "count":len(photos),"bytes":total,"model":"mimmi","work":ID}),flush=True)
    return photos

def live(browser_type,photos):
    with sync_playwright() as playwright:
        browser=getattr(playwright,browser_type).launch()
        context=browser.new_context(viewport={"width":390,"height":844},
             is_mobile=True,has_touch=True)
        page=context.new_page()
        response=page.goto(SITE+"#album="+ID,
                 wait_until="domcontentloaded",timeout=80000)
        assert response and response.status==200
        page.wait_for_function("""id=>{
           return typeof stored!=='undefined' && stored.some(a=>a.id===id)
             && !document.querySelector('#detail').hidden;
        }""",arg=ID,timeout=85000)
        page.wait_for_function("""count=>document.querySelectorAll('#detailphotos .photo').length>=count
        """,arg=len(photos),timeout=45000)
        for photo in photos:
            url=SITE+photo["url"]
            reply=context.request.get(url,timeout=50000)
            assert reply.status==200,(browser_type,photo["number"],reply.status)
            assert len(reply.body())==photo["bytes"]
            assert hashlib.sha256(reply.body()).hexdigest()==photo["sha256"]
            decoded=page.evaluate("""async url=>{
               const im=new Image();im.src=url;await im.decode();
               return [im.naturalWidth,im.naturalHeight];
            }""",url)
            assert decoded==[photo["width"],photo["height"]]
            tile=page.locator('#detailphotos button.photo').filter(
                has=page.locator('img[src*="'+photo["sha256"][:20]+'"]'))
            assert tile.count()==1,(browser_type,photo["number"],"tile")
        for photo in (photos[0],photos[-1]):
            tile=page.locator('#detailphotos button.photo').filter(
                has=page.locator('img[src*="'+photo["sha256"][:20]+'"]'))
            tile.first.click(timeout=45000)
            page.wait_for_function("""()=>document.querySelector('#lightbox')?.classList.contains('open')
                && document.querySelector('#full')?.complete
                && document.querySelector('#full')?.naturalWidth>0""",timeout=70000)
            displayed=page.evaluate("""()=>({
               url:document.querySelector('#full').currentSrc,
               width:document.querySelector('#full').naturalWidth,
               height:document.querySelector('#full').naturalHeight
            })""")
            assert displayed["width"]==photo["width"] and displayed["height"]==photo["height"]
            assert photo["sha256"][:20] in displayed["url"]
            page.locator("#close").click()
            page.wait_for_function("""()=>!document.querySelector('#lightbox').classList.contains('open')""")
        page.reload(wait_until="domcontentloaded",timeout=80000)
        page.wait_for_function("""id=>{
          const a=stored.find(a=>a.id===id);
          return a && a.images.length===8 &&
            document.querySelectorAll('#detailphotos .photo').length>=8;
        }""",arg=ID,timeout=85000)
        print("RUDY2_ALL_EIGHT_REAL_DEPLOYED_BROWSER_PASS",json.dumps({
           "engine":browser_type,"all_eight_sha_bytes_image_decode":True,
           "first_and_last_actual_lightbox":True,"reload":True,
           "real_iphone_hardware":False}),flush=True)
        browser.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=["chromium","webkit"])
    a=parser.parse_args()
    images=offline()
    if a.browser:live(a.browser,images)
