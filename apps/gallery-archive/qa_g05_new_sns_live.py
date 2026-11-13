#!/usr/bin/env python3
"""G05 exact newly saved Yui author photo: SHA/PIL + deployed browser acceptance."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://koith.github.io/browser-app-lab/apps/yui-gallery/"
SHA = "44b574ffd862004f4f0bf1e2b5391874925bcf089f7410862371a06b7ad940da"
SIZE = 434348
DIMS = (2048, 1799)


def physical_proof():
    base = ROOT / "apps/yui-gallery"
    albums = json.loads((base / "stored-albums.json").read_text())["albums"]
    owner = json.loads((base / "owner-index.json").read_text())["albums"]
    matches = [p for a in albums if a["id"] == "public-yui-sns"
               for p in a["images"] if p["sha256"] == SHA]
    assert len(matches) == 1, "new file must be unique and recorded in Yui SNS"
    p = matches[0]
    assert p["number"] == 469, "previous physical SNS slots must be append only"
    assert not any(x["sha256"] == SHA for a in owner for x in a["images"])
    assert p["bytes"] == SIZE and (p["width"], p["height"]) == DIMS
    assert p["source_url"] == "https://pbs.twimg.com/media/HW_KrxAaIAAWzVp.jpg?name=orig"
    target = (base / p["url"]).resolve()
    assert target.is_relative_to((base / "stored-albums/public-yui-sns").resolve())
    data = target.read_bytes()
    assert len(data) == SIZE and hashlib.sha256(data).hexdigest() == SHA
    with Image.open(target) as image:
        image.load()
        assert image.format == "JPEG" and image.size == DIMS
    print("G05_NEW_PHYSICAL_AUTHORED_PHOTO_469_SHA_AND_DECODE_PASS",flush=True)
    return p


def deployed(browser_type, photo):
    with sync_playwright() as pw:
        browser = getattr(pw, browser_type).launch()
        context = browser.new_context(viewport={"width":390,"height":844},
          is_mobile=True,has_touch=True)
        page = context.new_page()
        response = page.goto(BASE+"#album=public-yui-sns",
          wait_until="domcontentloaded",timeout=85000)
        assert response and response.status == 200
        page.wait_for_function("""sha=>{
          const a=stored.find(x=>x.id==='public-yui-sns');
          return a?.images.some(p=>p.sha256===sha);
        }""",arg=SHA,timeout=70000)
        page.wait_for_function("""sha=>{
          return [...document.querySelectorAll('#detailphotos .photo img')].some(
            img => (img.getAttribute('src')||'').includes(sha.slice(0,20)));
        }""",arg=SHA,timeout=70000)
        direct=context.request.get(BASE+photo["url"],timeout=60000,
            headers={"Cache-Control":"no-cache"})
        assert direct.status==200,("real Pages GET",direct.status)
        assert len(direct.body())==SIZE
        assert hashlib.sha256(direct.body()).hexdigest()==SHA
        tile=page.locator('#detailphotos button.photo').filter(
            has=page.locator('img[src*="'+SHA[:20]+'"]'))
        assert tile.count()==1
        tile.first.click(timeout=45000)
        page.wait_for_function("""()=>document.querySelector('#lightbox')?.classList.contains('open')
          && document.querySelector('#full')?.complete
          && document.querySelector('#full')?.naturalWidth > 0""",timeout=70000)
        native=page.evaluate("""()=>{
          const img=document.querySelector('#full');
          return [img.naturalWidth,img.naturalHeight,img.currentSrc];
        }""")
        assert native[:2]==list(DIMS),native
        assert SHA[:20] in native[2],native
        page.locator("#close").click()
        page.reload(wait_until="domcontentloaded",timeout=85000)
        page.wait_for_function("""sha=>{
          const a=stored.find(x=>x.id==='public-yui-sns');
          return a?.images.some(p=>p.sha256===sha);
        }""",arg=SHA,timeout=70000)
        print("G05_DEPLOYED_REAL_NEW_SNS_PHOTO_469_BROWSER_PASS",json.dumps({
          "engine":browser_type,"sha256":SHA,"bytes":SIZE,
          "image_decode":[native[0],native[1]],
          "tile_clicked":True,"lightbox":True,"reload":True,
          "physical_iPhone":False
        }),flush=True)
        browser.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=["chromium","webkit"])
    args=parser.parse_args()
    photo=physical_proof()
    if args.browser:
        deployed(args.browser,photo)
