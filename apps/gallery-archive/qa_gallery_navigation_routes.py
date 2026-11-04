#!/usr/bin/env python3
"""Independent mobile navigation regression on real deployed GitHub Pages.

Photo bytes may be unavailable from a third-party provider; that must not
prevent verifying gallery routes, reload, old links or Back history.
This test intentionally does NOT certify image decoding or iPhone hardware.
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import quote, urlencode

from playwright.sync_api import sync_playwright

BASE = "https://koith.github.io/browser-app-lab/apps"
MODELS = ("mimmi", "yui")


def check(browser, model: str) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True,
        has_touch=True, device_scale_factor=2, locale="ko-KR",
    )
    errors: list[str] = []
    pages = []

    def new_page():
        page = context.new_page()
        pages.append(page)
        page.on("pageerror", lambda error: errors.append(str(error)[:180]))
        return page

    url = f"{BASE}/{model}-gallery/"
    try:
        seed = new_page()
        response = seed.goto(url, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "HTML unavailable")
        seed.wait_for_function("""() => typeof available === 'function' &&
          typeof photosFor === 'function' && available().some(a => photosFor(a).length >= 2)
        """, timeout=70000)
        target = seed.evaluate("""() => {
          const album = available().find(a => photosFor(a).length >= 2);
          return {album: album.id, photo: photosFor(album)[0].number};
        }""")
        seed.close()

        # Direct photo URL must bootstrap from a new browser document, without
        # requiring its remote image to decode successfully.
        page = new_page()
        direct = url + "#" + urlencode(target)
        response = page.goto(direct, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "photo URL unavailable")
        photo_route = """wanted => history.state?.depth === 0 &&
          history.state?.album === wanted.album &&
          Number(history.state?.photo) === Number(wanted.photo) &&
          document.querySelector('#lightbox.open') !== null"""
        page.wait_for_function(photo_route, arg=target, timeout=45000)
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(photo_route, arg=target, timeout=45000)

        page.evaluate("closeViewer()")
        page.wait_for_function("""() =>
          !document.querySelector('#lightbox.open') &&
          history.state?.depth === 0 && !history.state?.photo
        """, timeout=20000)
        page.evaluate("album => openAlbum(album)", target["album"])
        page.wait_for_function("""() => history.state?.depth === 1 &&
          document.querySelector('#detail')?.hidden === false
        """, timeout=20000)
        page.evaluate("""album =>
          openViewer(photosFor(stored.find(a => a.id === album)), 0)
        """, target["album"])
        page.wait_for_function("""() => history.state?.depth === 2 &&
          document.querySelector('#lightbox.open') !== null
        """, timeout=20000)
        page.go_back(wait_until="domcontentloaded", timeout=30000)
        page.wait_for_function("""() => history.state?.depth === 1 &&
          !document.querySelector('#lightbox.open') &&
          document.querySelector('#detail')?.hidden === false
        """, timeout=20000)

        # Historic share links used #album-id. Open a fresh document, reload,
        # then simulate a browser popstate without typed history state.
        old = new_page()
        old_url = url + "#" + quote(str(target["album"]), safe="")
        response = old.goto(old_url, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "legacy URL unavailable")
        old_route = """wanted => history.state?.depth === 0 &&
          history.state?.album === wanted &&
          document.querySelector('#detail')?.hidden === false"""
        old.wait_for_function(old_route, arg=target["album"], timeout=45000)
        old.reload(wait_until="domcontentloaded", timeout=60000)
        old.wait_for_function(old_route, arg=target["album"], timeout=45000)
        old.evaluate("""album => {
          history.replaceState(null, '', '#'+encodeURIComponent(album));
          setMode('albums');
          window.dispatchEvent(new PopStateEvent('popstate',{state:null}));
        }""", target["album"])
        old.wait_for_function("""wanted =>
          document.querySelector('#detail')?.hidden === false &&
          detailAlbum?.id === wanted
        """, arg=target["album"], timeout=20000)

        assert not errors, (model, "page JavaScript exceptions", errors)
        print("GALLERY_INDEPENDENT_LIVE_MOBILE_NAVIGATION_PASS", json.dumps({
            "model": model, "album": target["album"],
            "fresh_photo_link": True, "photo_reload": True,
            "close_and_history_back": True, "historic_link": True,
            "historic_reload": True, "untyped_popstate": True,
            "image_decode_required": False, "real_iphone_hardware_tested": False,
            "javascript_errors": 0,
        }, ensure_ascii=False), flush=True)
    finally:
        context.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium", "webkit"), default="chromium")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = getattr(playwright, args.browser).launch(headless=True)
        try:
            for model in MODELS:
                check(browser, model)
        finally:
            browser.close()
    print("BOTH_GALLERIES_MOBILE_ROUTES_BACK_RELOAD_PASS", args.browser, flush=True)


if __name__ == "__main__":
    main()
