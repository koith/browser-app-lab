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


def audit(browser, model: str, timeout_ms: int) -> dict:
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
    args = parser.parse_args()
    if args.image_timeout_ms < 1000:
        parser.error("--image-timeout-ms must be >= 1000")
    with sync_playwright() as playwright:
        browser = getattr(playwright, args.browser).launch(headless=True)
        try:
            results = [audit(browser, model, args.image_timeout_ms)
                       for model in ("mimmi", "yui")]
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
