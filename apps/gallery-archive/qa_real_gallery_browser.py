#!/usr/bin/env python3
"""Prove original Yui/Mimmi gallery HTML displays real owner-private TeraBox bytes.

Run only on trusted main GitHub Actions with the model owner's private TeraBox
Secret and a randomly generated ephemeral bearer token. No images/screenshots,
browser storage or source credentials are uploaded as artifacts.
"""
from __future__ import annotations
import json
import os
from playwright.sync_api import sync_playwright

TOKEN=os.environ.get("GALLERY_ACCESS_TOKEN")
assert TOKEN and len(TOKEN)>=20,"Ephemeral gateway login required"
API="http://127.0.0.1:18765"

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    for model in ("yui","mimmi"):
        context=browser.new_context(
            viewport={"width":390,"height":810},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="ko-KR",
        )
        key=f"{model}-owner-session"
        context.add_init_script(
            "if(location.hostname==='localhost' && location.port==='8765'){"
            + "sessionStorage.setItem(" + json.dumps(key) + ", JSON.stringify("
            + json.dumps({"api": API, "token": TOKEN}) + "));}"
        )
        page=context.new_page()
        page.goto(f"http://localhost:8765/apps/{model}-gallery/",wait_until="domcontentloaded",timeout=30000)
        page.wait_for_function(
            "()=>typeof stored !== 'undefined' && stored.some(a=>(a.images||[]).some(p=>p.ownerAlbum))",
            timeout=105000
        )
        reported=page.evaluate("""() => ({
          count: stored.reduce((n,a)=>n+a.images.length,0),
          private: stored.reduce((n,a)=>n+a.images.filter(p=>!!p.ownerAlbum).length,0),
          works: stored.length,
          actualBanner: document.querySelector('#inventory')?.textContent
        })""")
        assert reported["private"] >= (2700 if model=="yui" else 400),reported
        assert reported["count"] >= (2700 if model=="yui" else 2600),reported
        assert "실제 저장본" in reported["actualBanner"],reported
        # Only PASS if a newly acquired independently photographed picture,
        # NOT an earlier unrelated photobook, actually appears in the existing
        # gallery grid and its real authenticated original opens.
        album_id = {
            "yui": "yui-indie-photographer-cos-swee-2026",
            "mimmi": "mimmi-indie-sana-sopmod2-2019",
        }[model]
        new_photos = page.evaluate("""(id) => {
          const a=stored.find(x=>x.id===id);
          return a ? {
            count:a.images.length,
            private:a.images.filter(p=>!!p.ownerAlbum).length,
            numbers:a.images.map(p=>p.number)
          } : null;
        }""",album_id)
        assert new_photos and new_photos["count"] >= 7,(model,"New independent photographed albums not added to gallery",new_photos)
        assert new_photos["private"]==new_photos["count"],(model,"Research links, not all physically saved",new_photos)
        album=page.locator(f'#albumgrid .album[data-id="{album_id}"]')
        album.scroll_into_view_if_needed(timeout=10000)
        album.click(timeout=12000)
        assert page.locator("#detail").is_visible()
        photo=page.locator("#detailphotos .photo").first
        photo.scroll_into_view_if_needed()
        # Actual image downloaded via the authenticated on-demand gateway,
        # checked against the SHA by the original owner-media.js client.
        page.wait_for_function(
            """() => [...document.querySelectorAll('#detailphotos img')].some(
              img => img.src.startsWith('blob:') && img.naturalWidth>=160)""",
            timeout=110000
        )
        photo.click(timeout=10000)
        page.wait_for_function(
            """() => {
              const img=document.querySelector('#full');
              return !!img && img.src.startsWith('blob:') && img.naturalWidth>=160;
            }""",
            timeout=110000
        )
        assert page.locator("#lightbox").is_visible()
        # Report only aggregate source-backed counts. No private photo paths,
        # hashes, credentials, screenshots, titles, post URLs, or full bytes.
        print("PRIVATE_TERA_BOX_GALLERY_ACTUAL_BROWSER_PHOTO_PASS",
              json.dumps({"model":model,"all_saved_album_photos":reported["count"],
                          "authenticated_owner_photos":reported["private"],
                          "album_count":reported["works"],
                          "new_independent_album_photos":new_photos["count"],
                          "verified_independent_album":True,
                          "preview_loaded":True,"original_lightbox_loaded":True}),flush=True)
        context.close()
    browser.close()
print("BOTH_MAIN_GALLERIES_REAL_PRIVATE_ARCHIVE_BROWSER_QA_PASS",flush=True)
