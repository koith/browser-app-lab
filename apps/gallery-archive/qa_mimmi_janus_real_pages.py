#!/usr/bin/env python3
"""Live Pages regression for the user-reported Mimmi Janus album.

Block Render/TeraBox completely: seven SHA-verified first-party originals
already committed to Pages must render in photo grid and full-screen.
No credentials, downloads to new storage, or changes to originals.
"""
from __future__ import annotations

import argparse
import hashlib
import json

from playwright.sync_api import sync_playwright

URL="https://koith.github.io/browser-app-lab/apps/mimmi-gallery/"
WORK="djawa-janus-scary-lantern-night"


def check(browser):
    ctx=browser.new_context(viewport={"width":390,"height":844},
                            is_mobile=True,has_touch=True,locale="ko-KR")
    page=ctx.new_page()
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)[:220]))
    page.route("**/*onrender.com/**",lambda route:route.abort("blockedbyclient"))
    try:
        response=page.goto(URL,wait_until="domcontentloaded",timeout=60000)
        assert response and response.status==200
        page.wait_for_function("""() => Array.isArray(stored) &&
          stored.some(a => a.id==='djawa-janus-scary-lantern-night') &&
          Array.isArray(localStored) && localStored.length>0
        """,timeout=70000)
        record=page.evaluate("""() => {
          const a=stored.find(a=>a.id==='djawa-janus-scary-lantern-night');
          const raw=localStored.find(a=>a.id===a.id);
          const known=new Map(raw.images.map(p=>[p.sha256,p]));
          const photos=photosFor(a);
          return {
            all:photos.length,
            local:photos.map((p,i) => {
              const copied=known.get(p.sha256);
              return copied ? {index:i,url:copied.url,
                sha:copied.sha256,bytes:copied.bytes,
                width:copied.width,height:copied.height,
                selected_url:p.url,selected_owner:!!p.ownerAlbum} : null
            }).filter(Boolean)
          };
        }""")
        assert record["all"] >= 8, record
        assert len(record["local"])==7,("seven existing saved photos are expected",record)
        page.evaluate("id=>openAlbum(id)",WORK)
        page.wait_for_function("""() => document.querySelectorAll(
          '#detailphotos .photo').length >= 8""",timeout=25000)
        rendered=page.evaluate("""indices => indices.map(i => {
            const image=document.querySelectorAll('#detailphotos .photo img')[i];
            return {
              index:i,raw_src:image?.getAttribute('src')||'',
              current:image?.currentSrc||'',has_owner:image?.hasAttribute('data-owner'),
              natural_width:image?.naturalWidth||0
            };
        })""",[x["index"] for x in record["local"]])
        wrong=[v for v in rendered if
               not v["raw_src"].startswith("stored-albums/")]
        assert not wrong,("stored original wrongly forwarded to Render",wrong,record)
        # Browser must decode all seven independent first-party photographs.
        page.wait_for_function("""indices => indices.every(i => {
            const img=document.querySelectorAll('#detailphotos .photo img')[i];
            return img && img.complete && img.naturalWidth >= 160;
        })""",arg=[x["index"] for x in record["local"]],timeout=60000)
        for row in record["local"]:
            file_response=ctx.request.get(URL+row["url"],timeout=60000)
            assert file_response.status==200,(row["index"],file_response.status)
            content=file_response.body()
            assert hashlib.sha256(content).hexdigest()==row["sha"],row["index"]
            assert len(content)==row["bytes"],row["index"]
        index=record["local"][0]["index"]
        page.locator("#detailphotos .photo").nth(index).click()
        page.wait_for_function("""expected => {
          const full=document.querySelector('#full');
          return document.querySelector('#lightbox.open') &&
              full && full.complete && full.naturalWidth>=160 &&
              new URL(full.currentSrc||full.src,location.href).href===expected;
        }""",arg=URL+record["local"][0]["url"],timeout=40000)
        assert not errors,errors
        print("LIVE_JANUS_ALL_SEVEN_FIRST_PARTY_SHA_PHOTOS_DECODED",json.dumps({
            "album":WORK,"browser":browser.browser_type.name,
            "real_pages_album_count":record["all"],
            "static_originals_sha_and_byte_verified":7,
            "all_seven_detail_images_decoded":True,
            "first_party_lightbox_passed":True,
            "render_provider_blocked":True,
            "remaining_remote_only_unverified":record["all"]-7,
            "physical_iphone_tested":False
        }),flush=True)
    finally:
        ctx.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=("chromium","webkit"),required=True)
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=getattr(p,args.browser).launch(headless=True)
        try:check(browser)
        finally:browser.close()
