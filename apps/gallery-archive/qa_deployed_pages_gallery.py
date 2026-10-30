#!/usr/bin/env python3
"""Verify deployed GitHub Pages really opens both archived-photo galleries.

This is intentionally NOT the localhost test gateway. A PASS requires images
to render in the publicly deployed gallery using its ordinary visitor session.
No owner cookies, bearer tokens, bypasses or screenshots are supplied.
"""
from __future__ import annotations
import argparse
import json
import time
from playwright.sync_api import sync_playwright, Error as PlaywrightError

ROOT = "https://koith.github.io/browser-app-lab"
RENDER = "mimmi-private-gallery-free.onrender.com"
MODELS = {
    "yui": {"min_count": 3022, "min_private": 2999, "raw_owner_index":2999,
            "album_ids": ("yuis-present33", "athletic-club104", "teddy-bear97")},
    "mimmi": {"min_count": 3157, "min_private": 3156, "raw_owner_index":3178,
              "album_ids": ("mimmi-indie-sana-sopmod2-2019", "djawa-rei-beyond-the-heart")},
}



def scroll_current(page, selector: str, *, timeout: float = 35):
    """Refetch a live locator after asynchronous gallery card replacement."""
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            current = page.locator(selector).first
            current.wait_for(state="visible", timeout=4000)
            current.scroll_into_view_if_needed(timeout=4000)
            return
        except PlaywrightError as exc:
            last_error = exc
            detail = str(exc).lower()
            if not ("not attached" in detail or "detached" in detail
                    or "not stable" in detail):
                raise
            page.wait_for_timeout(250)
    raise AssertionError(("dynamic gallery did not stabilize", selector, str(last_error)))


def click_current(page, selector: str, *, timeout: float = 35):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            page.locator(selector).first.click(timeout=5000)
            return
        except PlaywrightError as exc:
            last_error = exc
            detail = str(exc).lower()
            if not ("not attached" in detail or "detached" in detail
                    or "not stable" in detail):
                raise
            page.wait_for_timeout(250)
    raise AssertionError(("dynamic gallery click did not stabilize", selector, str(last_error)))


def exercise(browser, model: str, rule: dict, engine: str):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2, is_mobile=True, has_touch=True,
        locale="ko-KR", reduced_motion="reduce",
    )
    page = context.new_page()
    start = time.monotonic()
    url = f"{ROOT}/apps/{model}-gallery/"
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)[:180]))
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "deployed HTML status", response.status if response else None)
        assert page.url.startswith(url), (model, "unexpected redirect away from GitHub Pages", page.url)
        assert RENDER not in page.url, (model, "Render interstitial", page.url)
        page.wait_for_function("""([minimum, privateMinimum]) => {
          if (typeof stored === 'undefined' || !Array.isArray(stored)) return false;
          const total=stored.reduce((n,a)=>n+(a.images||[]).length,0);
          const owner=stored.reduce((n,a)=>n+(a.images||[]).filter(p=>!!p.ownerAlbum).length,0);
          return total>=minimum && owner>=privateMinimum;
        }""", arg=[rule["min_count"], rule["min_private"]], timeout=170000)
        counts = page.evaluate("""() => ({
          total:stored.reduce((n,a)=>n+a.images.length,0),
          owner:stored.reduce((n,a)=>n+a.images.filter(p=>!!p.ownerAlbum).length,0),
          albums:stored.filter(a=>a.images&&a.images.length).length,
          banner:document.querySelector('#inventory')?.textContent,
        })""")
        # The raw owner ledger can contain the same work/number across aliases;
        # the visible viewer intentionally deduplicates those positions.
        # Verify both inventories instead of equating raw rows with photo cards.
        owner_raw = page.evaluate("""async () => {
          const response=await fetch('owner-index.json', {cache:'no-store'});
          if(!response.ok) throw Error('Deployed owner index unavailable');
          const document=await response.json();
          return {model:document.model, physical:document.physical_originals_indexed,
            albums:document.albums?.length || 0};
        }""")
        assert owner_raw["model"] == model, (model, owner_raw)
        assert owner_raw["physical"] >= rule["raw_owner_index"], (model, owner_raw)
        assert "실제 저장본" in counts["banner"], (model, counts)
        assert page.locator("#albumgrid .album").count() >= 1, model
        verified = []
        for album_id in rule["album_ids"]:
            album = page.locator(f'#albumgrid .album[data-id="{album_id}"]')
            assert album.count() == 1, (model, "missing gallery album", album_id)
            scroll_current(page, f'#albumgrid .album[data-id="{album_id}"]')
            # First-party owner preview must decode; not just a URL or placeholder.
            img = album.locator("img")
            assert img.count() >= 1, (model, album_id, "missing cover")
            page.wait_for_function("""(id) => {
              const album=document.querySelector('#albumgrid .album[data-id="'+id+'"]');
              const img=album?.querySelector('img');
              return !!img && img.complete && img.naturalWidth>=160;
            }""", arg=album_id, timeout=105000)
            click_current(page, f'#albumgrid .album[data-id="{album_id}"]')
            assert page.locator("#detail").is_visible(), (model, album_id, "detail hidden")
            photo = page.locator("#detailphotos .photo").first
            scroll_current(page, "#detailphotos .photo")
            page.wait_for_function("""() => [...document.querySelectorAll('#detailphotos img')].some(img =>
              img.complete && img.naturalWidth>=160 && 
              (img.src.includes('/api/') || img.src.startsWith('blob:')))""", timeout=110000)
            click_current(page, "#detailphotos .photo")
            page.wait_for_function("""() => {
              const img=document.querySelector('#full');
              return !!img && img.complete && img.naturalWidth>=160
                && (img.src.includes('/api/') || img.src.startsWith('blob:'));
            }""", timeout=110000)
            assert page.locator("#lightbox").is_visible(), (model, album_id)
            verified.append(album_id)
            page.locator("#close").click(timeout=18000)
            page.go_back(wait_until="domcontentloaded", timeout=30000)
            # Some browsers restore the previous album view on history back.
            if page.locator("#detail").is_visible():
                page.go_back(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_function("()=>!!document.querySelector('#albumgrid .album')", timeout=45000)
        # Reload the public gallery, not the gateway, then assert it still shows photos.
        page.reload(wait_until="domcontentloaded", timeout=60000)
        assert page.url.startswith(url), (model, "reload left gallery", page.url)
        page.wait_for_function("()=>document.querySelectorAll('#albumgrid .album').length>0", timeout=50000)
        elapsed = round(time.monotonic() - start, 2)
        print("DEPLOYED_GALLERY_PHYSICAL_ORIGINAL_OPEN_PASS",
              json.dumps({"model":model,"browser":engine,
                          "album_count":counts["albums"],"visible_photo_rows":counts["total"],
                          "owner_private_photo_rows":counts["owner"],
                          "owner_index_raw_verified_photos":owner_raw["physical"],
                          "opened_albums":verified,
                          "reloaded_direct_pages":True,"elapsed_seconds":elapsed,
                          "unhandled_page_errors":failures[:3]},ensure_ascii=False), flush=True)
        return counts
    finally:
        context.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium","webkit"), default="chromium")
    args=parser.parse_args()
    with sync_playwright() as pw:
        browser=getattr(pw,args.browser).launch(headless=True)
        try:
            for model,rule in MODELS.items():
                exercise(browser,model,rule,args.browser)
        finally:
            browser.close()
    print("BOTH_DEPLOYED_GITHUB_PAGES_GALLERIES_IMAGE_AND_RELOAD_PASS",flush=True)


if __name__ == "__main__":
    main()
