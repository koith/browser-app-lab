#!/usr/bin/env python3
"""Verify an exact-SHA Pages original opens in the live mobile lightbox.

G-09-D is independent of TeraBox-only originals (which may return 403/503).
This checks actual first-party bytes and browser image decode, not just a link.
No auth, credentials, data writes, new image discovery or collector calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json

from playwright.sync_api import sync_playwright

BASE = "https://koith.github.io/browser-app-lab/apps"


def check(browser, model: str) -> None:
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True, has_touch=True, device_scale_factor=2, locale="ko-KR",
    )
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)[:180]))
    root = f"{BASE}/{model}-gallery/"
    try:
        response = page.goto(root, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "Pages HTML")
        page.wait_for_function("""() =>
            typeof stored !== 'undefined' && Array.isArray(stored) &&
            stored.length > 0 && Array.isArray(localStored) &&
            localStored.length > 0 &&
            typeof exactSavedViewerCopy === 'function'
        """, timeout=70000)

        # The gallery itself must decide that this is an exact same-work,
        # same-SHA, same-size, same-dimensions first-party original.
        result = page.evaluate("""() => {
          const matches=[];
          for(const album of stored) {
            for(const [i,p] of photosFor(album).entries()) {
              // Same-SHA public originals win in SavedGalleryPhotoUnion:
              // the merged photo no longer has ownerAlbum. Treat the actual
              // local record as a verified candidate, not as "missing".
              const copy=p.url?.startsWith('stored-albums/')
                ? p : exactSavedViewerCopy(p);
              if(!copy ||
                copy.sha256 !== p.sha256 || copy.bytes !== p.bytes ||
                copy.width !== p.width || copy.height !== p.height ||
                !copy.url?.startsWith('stored-albums/') ||
                !(p.width >= 160 && p.height >= 160) || i >= 32) continue;
              matches.push({album:album.id, index:i, sha256:p.sha256,
                bytes:p.bytes, width:p.width, height:p.height, url:copy.url});
            }
          }
          // Screenshot regression first: Janus is a real locally stored work.
          matches.sort((a,b)=>
            Number(b.album==='djawa-janus-scary-lantern-night')-
              Number(a.album==='djawa-janus-scary-lantern-night') ||
            a.index-b.index || a.bytes-b.bytes);
          return {candidate_count:matches.length,target:matches[0]||null};
        }""")
        target = result["target"]
        assert target, (model, "no exact-SHA local first-party photo within first 32 positions")

        # Click an actual detail photo card: this exercises the same path
        # as a visitor rather than calling the renderer with a fake photo.
        page.evaluate("album => openAlbum(album)", target["album"])
        page.wait_for_function("""idx =>
            document.querySelectorAll('#detailphotos .photo').length > idx
        """, arg=target["index"], timeout=20000)
        page.locator("#detailphotos .photo").nth(target["index"]).click(timeout=25000)
        expected_url = root + target["url"]
        page.wait_for_function("""expected => {
          const img=document.querySelector('#full');
          return document.querySelector('#lightbox.open') !== null &&
            img && img.complete && img.naturalWidth>=160 &&
            new URL(img.currentSrc||img.src,location.href).href===expected;
        }""", arg=expected_url, timeout=45000)

        measured = page.evaluate("""() => {
          const image=document.querySelector('#full');
          return {src:new URL(image.currentSrc||image.src,location.href).href,
            width:image.naturalWidth,height:image.naturalHeight,
            complete:image.complete};
        }""")
        assert measured["src"] == expected_url, (model, measured)
        assert (measured["width"], measured["height"]) == (
            target["width"], target["height"]), (model, "browser dimensions", measured)

        # Independently read the same public Pages bytes. Never log the bytes.
        file_response = ctx.request.get(expected_url, timeout=60000)
        assert file_response.status == 200, (model, "Pages image status", file_response.status)
        payload = file_response.body()
        actual_sha = hashlib.sha256(payload).hexdigest()
        assert actual_sha == target["sha256"], (model, "original SHA mismatch")
        assert len(payload) == target["bytes"], (model, "original byte size mismatch")
        assert not errors, (model, "page JavaScript exceptions", errors)
        print("GALLERY_LIVE_EXACT_SHA_STATIC_LIGHTBOX_PASS", json.dumps({
            "model": model, "album": target["album"],
            "position": target["index"]+1, "candidates": result["candidate_count"],
            "sha256": actual_sha, "bytes": len(payload),
            "decoded_width": measured["width"],
            "decoded_height": measured["height"],
            "visitor_clicked_actual_photo": True,
            "cross_model_route_accepted": False,
            "terabox_readback_tested": False, "physical_iphone_tested": False,
        }, ensure_ascii=False), flush=True)
    finally:
        ctx.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium","webkit"), required=True)
    args = parser.parse_args()
    with sync_playwright() as pw:
        browser = getattr(pw,args.browser).launch(headless=True)
        try:
            for model in ("mimmi", "yui"):
                check(browser, model)
        finally:
            browser.close()
    print("GALLERY_LIVE_SAVED_LIGHTBOX_BOTH_MODELS_PASS", args.browser, flush=True)


if __name__ == "__main__":
    main()
