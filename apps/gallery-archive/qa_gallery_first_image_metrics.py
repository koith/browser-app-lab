#!/usr/bin/env python3
"""Read-only, real-GitHub-Pages mobile first-paint and first-image audit.

Reports separately: first HTML, first populated album card, first DECODED
cover, and the complete static owner ledger's presence in the viewer. It does
not claim every original photo decoded just because a card appeared.
"""
from __future__ import annotations

import argparse
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout

BASE = "https://koith.github.io/browser-app-lab/apps"


def audit(browser, model: str, timeout_ms: int, verify_progressive: bool = False) -> dict:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True,
        has_touch=True, device_scale_factor=2, locale="ko-KR",
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)[:180]))
    start = time.monotonic()
    result = {"model": model, "backend_auth_supplied": False,
              "real_iphone_hardware_tested": False}
    try:
        response = page.goto(f"{BASE}/{model}-gallery/",
                             wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "HTML not 200")
        result["dom_content_loaded_s"] = round(time.monotonic() - start, 2)
        page.wait_for_function(
            "() => typeof stored !== 'undefined' && Array.isArray(stored) "
            "&& stored.length>0 && document.querySelectorAll('#albumgrid .album').length>0",
            timeout=timeout_ms,
        )
        result["first_album_card_s"] = round(time.monotonic() - start, 2)
        # Diagnostic only until the new HTML is deployed: a newly constructed
        # <img> can cancel the prepaint image's in-flight download.
        result["first_paint_image_nodes_reused"] = page.locator(
            '#albumgrid img[data-fast-preserved="1"]').count()
        # A rendered card or image URL is NOT evidence that a thumbnail decoded.
        # Only count a decoded, viewport-visible image with real image dimensions.
        try:
            page.wait_for_function("""() => [...document.querySelectorAll('#albumgrid .album img')]
              .some(img => {
                const r=img.getBoundingClientRect();
                return r.bottom>0 && r.top<innerHeight &&
                  img.complete && img.naturalWidth>=160 && img.naturalHeight>=160;
              })""", timeout=timeout_ms)
            result["first_decoded_visible_cover_s"] = round(
                time.monotonic() - start, 2)
            # First visibly decoded image's origin only; never emit signed URLs.
            result["first_cover"] = page.evaluate("""() => {
              const img=[...document.querySelectorAll('#albumgrid .album img')]
                .find(im => {const r=im.getBoundingClientRect();
                  return r.bottom>0 && r.top<innerHeight && im.complete &&
                    im.naturalWidth>=160 && im.naturalHeight>=160;});
              if(!img)return null;
              let host='unknown';
              try{host=new URL(img.currentSrc).hostname}catch{}
              return {host, width:img.naturalWidth,height:img.naturalHeight};
            }""")
        except BrowserTimeout:
            result["first_decoded_visible_cover_s"] = None
            result["thumbnail_failure"] = (
                f"No decoded visible album cover within {timeout_ms} ms")
        # Count every saved owner SHA, not just a sample of popular works.
        result["coverage"] = page.evaluate("""async () => {
          const response = await fetch('owner-index.json', {cache:'no-store'});
          if (!response.ok) throw Error('owner index HTTP '+response.status);
          const source = await response.json();
          if (source.model !== 'MODEL') throw Error('wrong model in owner index');
          const ledger = source.albums.flatMap(a => a.images.map(p => ({
            work:a.id,sha:p.sha256})));
          const shown = new Set(stored.flatMap(a =>
            (a.images||[]).map(p => p.sha256)).filter(Boolean));
          const missing = [...new Set(ledger.map(p=>p.sha))]
            .filter(sha => !shown.has(sha));
          const repeatedInOwner = ledger.length -
            new Set(ledger.map(p=>p.work+'|'+p.sha)).size;
          return {indexed_rows:ledger.length,
            indexed_unique_sha:new Set(ledger.map(p=>p.sha)).size,
            rendered_rows:stored.reduce((n,a)=>n+(a.images||[]).length,0),
            rendered_albums:stored.length,
            owner_sha_absent_from_rendered_gallery:missing.length,
            sample_absent_sha:missing.slice(0,5),
            duplicate_sha_within_owner_work:repeatedInOwner};
        }""".replace("MODEL", model))
        result["coverage_verified_s"] = round(time.monotonic() - start, 2)
        if verify_progressive:
            # Verify the deployed full-photo view actually paginates thousands
            # of saved photos instead of inserting every <img> on mobile load.
            page.evaluate("setMode('photos')")
            page.wait_for_function(
                "() => document.querySelectorAll('#photogrid .photo').length >= 64",
                timeout=12000)
            first_batch = page.locator("#photogrid .photo").count()
            if first_batch != 64:
                raise AssertionError((model, "unbounded first photo batch", first_batch))
            page.locator("#photogrid .photo").last.scroll_into_view_if_needed(
                timeout=12000)
            page.wait_for_function(
                "() => document.querySelectorAll('#photogrid .photo').length > 64",
                timeout=12000)
            second_batch = page.locator("#photogrid .photo").count()
            result["photo_grid_progressive"] = {
                "first_batch": first_batch,
                "after_scroll": second_batch,
                "viewer_total": result["coverage"]["rendered_rows"],
                "full_inventory_assembled_immediately": False,
            }
            page.evaluate("setMode('albums')")
            # G-11: the real deployed page must restore an exact saved-photo
            # deep link after reload without pushing a phantom history entry.
            # No TeraBox access is required merely to show the lightbox route.
            target = page.evaluate("""() => {
              const album=available().find(a=>photosFor(a).length>=2);
              if(!album)throw Error('No saved album with two photos');
              const first=photosFor(album)[0];
              return {album:album.id,photo:first.number};
            }""")
            from urllib.parse import urlencode
            direct = f"{BASE}/{model}-gallery/#"+urlencode(target)
            page.goto(direct,wait_until="domcontentloaded",timeout=60000)
            page.reload(wait_until="domcontentloaded",timeout=60000)
            page.wait_for_function("""wanted => {
              const state=history.state;
              return state && state.depth===0 &&
                state.album===wanted.album &&
                Number(state.photo)===Number(wanted.photo) &&
                document.querySelector('#lightbox.open')!==null;
            }""",arg=target,timeout=20000)
            page.evaluate("closeViewer()")
            page.wait_for_function("""() =>
              !document.querySelector('#lightbox.open') &&
              history.state?.depth===0 &&
              !history.state?.photo
            """,timeout=10000)
            page.evaluate("""album => openAlbum(album)""",target["album"])
            page.wait_for_function("""() =>
              !document.querySelector('#detail').hidden &&
              history.state?.depth===1
            """,timeout=10000)
            page.evaluate("""album => openViewer(photosFor(stored.find(
              a=>a.id===album)),0)""",target["album"])
            page.wait_for_function("""() =>
              !!document.querySelector('#lightbox.open') &&
              history.state?.depth===2
            """,timeout=10000)
            page.go_back(wait_until="domcontentloaded",timeout=20000)
            page.wait_for_function("""() =>
              !document.querySelector('#lightbox.open') &&
              !document.querySelector('#detail').hidden &&
              history.state?.depth===1
            """,timeout=15000)
            result["mobile_route_history"] = {
              "saved_album":target["album"],
              "direct_photo_reload":True,
              "no_duplicate_deep_link_entry":True,
              "viewer_back_returns_to_album":True,
              "backend_auth_required":False,
            }
            # G-11-B: historic links used a bare "#work-id" fragment.
            # Test the actual deployed page on Chromium and WebKit rather
            # than treating a JavaScript unit mock as a public-site PASS.
            from urllib.parse import quote
            old_url = f"{BASE}/{model}-gallery/#" + quote(target["album"], safe="")
            page.goto(old_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_function("""wanted => {
              const state=history.state;
              return state && state.depth===0 &&
                state.album===wanted &&
                document.querySelector('#detail')?.hidden===false;
            }""", arg=target["album"], timeout=20000)
            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_function("""wanted =>
              history.state?.album===wanted &&
              document.querySelector('#detail')?.hidden===false
            """, arg=target["album"], timeout=20000)
            # Safari may emit popstate without the gallery's typed state.
            # Explicitly clear only this test page's history.state and
            # emit a real browser event from the historic URL.
            page.evaluate("""album => {
              history.replaceState(null, '', '#'+encodeURIComponent(album));
              setMode('albums');
              window.dispatchEvent(new PopStateEvent('popstate', {state:null}));
            }""", target["album"])
            page.wait_for_function("""wanted =>
              document.querySelector('#detail')?.hidden===false &&
              detailAlbum?.id===wanted
            """, arg=target["album"], timeout=15000)
            result["legacy_bare_hash_route"] = {
              "album":target["album"],
              "opens_on_direct_navigation":True,
              "survives_reload":True,
              "restores_on_untyped_popstate":True,
              "physical_iphone_tested":False,
            }
        result["script_errors"] = errors
        result["status"] = (
            "FAIL" if result["coverage"]["owner_sha_absent_from_rendered_gallery"]
            or result["first_decoded_visible_cover_s"] is None or errors
            else "PASS")
        return result
    finally:
        context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium", "webkit"),
                        default="chromium")
    parser.add_argument("--image-timeout-ms", type=int, default=110000)
    parser.add_argument("--verify-progressive", action="store_true",
                        help="Run only after the new HTML is deployed by Pages")
    args = parser.parse_args()
    if args.image_timeout_ms < 1000:
        parser.error("--image-timeout-ms must be >= 1000")
    # Compare opposite model orders in independent browser processes.
    # The two galleries use the same Render gateway; a first-request cold
    # start must not be misreported as a Mimmi-specific frontend slowdown.
    # Each model gets its own clean incognito context in both orders.
    orders = (("mimmi", "yui"), ("yui", "mimmi"))
    results = []
    with sync_playwright() as playwright:
        for order in orders:
            browser = getattr(playwright, args.browser).launch(headless=True)
            try:
                for position, model in enumerate(order):
                    measured = audit(browser, model, args.image_timeout_ms,
                                 args.verify_progressive)
                    measured["order"] = " -> ".join(order)
                    measured["position_in_order"] = position + 1
                    results.append(measured)
            finally:
                browser.close()
    for result in results:
        print("GALLERY_FIRST_IMAGE_AUDIT",
              json.dumps({"browser": args.browser, **result},
                         ensure_ascii=False), flush=True)
    assert all(r["status"] == "PASS" for r in results), results
    print("BOTH_GALLERY_FIRST_IMAGE_AND_FULL_SHA_COVERAGE_PASS",
          args.browser, flush=True)


if __name__ == "__main__":
    main()
