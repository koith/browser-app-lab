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
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

ROOT = "https://koith.github.io/browser-app-lab"
RENDER = "mimmi-private-gallery-free.onrender.com"
TASK_BASELINE = "e4b633fc189429e79c9b70038ef6f2b6b9fdd0a5"
MODELS = {
    "yui": {"min_count": 3053, "raw_owner_index":3030,
            "album_ids": ("yuis-present33", "athletic-club104", "teddy-bear97",
                          "yui-public-official-x-teapawt")},
    "mimmi": {"min_count": 2526, "raw_owner_index":3214,
              "album_ids": ("mimmi-indie-sana-sopmod2-2019", "djawa-rei-beyond-the-heart")},
}


def verify_saved_routes(context, page, model):
    """Check every saved file has a usable route in its actual canonical work.

    This is visibility coverage, separate from the per-photo browser decode and
    download-SHA jobs. A duplicate may share a route only inside the same work.
    """
    baseline_url = ("https://raw.githubusercontent.com/koith/browser-app-lab/"
                    f"{TASK_BASELINE}/apps/{model}-gallery/owner-index.json")
    before_response = context.request.get(baseline_url, timeout=60000)
    assert before_response.status == 200, (model, "baseline index unavailable")
    before = before_response.json()
    current_response = context.request.get(
        f"{ROOT}/apps/{model}-gallery/owner-index.json", timeout=60000,
        headers={"Cache-Control": "no-cache"})
    assert current_response.status == 200, (model, "current index unavailable")
    current = current_response.json()
    assert before.get("model") == current.get("model") == model
    old = {(a["id"], p["number"]): p["sha256"]
           for a in before["albums"] for p in a["images"]}
    expected = sum(len(a["images"]) for a in current["albums"])
    changed = sum(old.get((a["id"], p["number"])) != p["sha256"]
                  for a in current["albums"] for p in a["images"])
    routes = page.evaluate("""selection => {
      const exact = new Set(), byWork = new Set();
      for (const work of stored) for (const p of validImages(work)) {
        if(p.ownerAlbum) exact.add(JSON.stringify([p.ownerAlbum,
            p.storageNumber??p.number,p.sha256,p.width,p.height,p.bytes]));
        byWork.add(JSON.stringify([work.id,p.sha256,p.width,p.height,p.bytes]));
      }
      let checked=0,shared=0;const missing=[];
      for(const a of selection) for(const p of a.images) {
        if(exact.has(JSON.stringify([a.id,p.number,p.sha256,p.width,p.height,p.bytes]))) checked++;
        else if(byWork.has(JSON.stringify([canonicalId(a.id),p.sha256,p.width,p.height,p.bytes]))) {
          checked++;shared++;
        } else missing.push([a.id,p.number]);
      }
      return {checked,byte_identical_routes_in_same_work:shared,
        missing_count:missing.length,first_missing:missing.slice(0,5)};
    }""", current["albums"])
    assert routes["missing_count"] == 0 and routes["checked"] == expected, (model, routes)
    return {"baseline_commit": TASK_BASELINE, "saved_rows_checked": expected,
            "task_changed_rows_present": changed,
            "byte_identical_routes_in_same_work": routes["byte_identical_routes_in_same_work"],
            "all_saved_rows_routed_in_correct_work": True,
            "this_is_visibility_not_image_decode_coverage": True}



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
    page_resources = []
    page.on("pageerror", lambda error: failures.append(str(error)[:180]))
    # Log only sanitized resource names; never URLs carrying an auth token.
    page.on("requestfailed", lambda req: page_resources.append({
        "resource": req.url.split("?")[0].rsplit("/", 1)[-1],
        "error": str(req.failure)[:120],
    }))
    page.on("response", lambda res: page_resources.append({
        "resource": res.url.split("?")[0].rsplit("/", 1)[-1],
        "status": res.status,
    }) if res.status >= 400 else None)
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200, (model, "deployed HTML status", response.status if response else None)
        assert page.url.startswith(url), (model, "unexpected redirect away from GitHub Pages", page.url)
        assert RENDER not in page.url, (model, "Render interstitial", page.url)
        try:
            page.wait_for_function("""minimum => {
              if (typeof stored === 'undefined' || !Array.isArray(stored)) return false;
              const total=stored.reduce((n,a)=>n+(a.images||[]).length,0);
              const owner=stored.reduce((n,a)=>n+(a.images||[]).filter(p=>!!p.ownerAlbum).length,0);
              // Mimmi's owner originals can be served by byte-identical
              // Pages files. SavedGalleryPhotoUnion then intentionally drops
              // ownerAlbum on those rows. Requiring an old raw owner-flag count
              // makes a healthy gallery time out; the full per-file/album
              // SHA + dimensions + byte-count gate below proves coverage.
              return total>=minimum && owner>0;
            }""", arg=rule["min_count"], timeout=95000)
        except PlaywrightTimeoutError as exc:
            # An unlabelled timeout cannot tell a broken stored index from
            # a Pages/CDN fetch failure, blocked IndexedDB, or a JS error.
            try:
                state = page.evaluate("""() => ({
                  ready: document.readyState,
                  storedDefined: typeof stored !== 'undefined',
                  total: typeof stored !== 'undefined' && Array.isArray(stored)
                    ? stored.reduce((n,a)=>n+(a.images||[]).length,0) : null,
                  owner: typeof stored !== 'undefined' && Array.isArray(stored)
                    ? stored.reduce((n,a)=>n+(a.images||[]).filter(p=>!!p.ownerAlbum).length,0) : null,
                  inventory: document.querySelector('#inventory')?.textContent || '',
                  empty: document.querySelector('#nothing')?.textContent || '',
                  fastCovers: document.querySelectorAll('[data-fast-cover]').length,
                  renderedAlbums: document.querySelectorAll('#albumgrid .album').length,
                  scripts: [...document.scripts].filter(x=>x.src).map(x=>{
                    try{return new URL(x.src).pathname.split('/').pop()}catch{return 'unknown'}
                  }),
                })""")
            except PlaywrightError as diagnostic_error:
                state = {"diagnostic_error": str(diagnostic_error)[:180]}
            diagnostic = {"model": model, "browser": engine, "state": state,
                          "page_errors": failures[:8], "resource_errors": page_resources[-25:]}
            print("DEPLOYED_GALLERY_BOOTSTRAP_TIMEOUT",
                  json.dumps(diagnostic, ensure_ascii=False), flush=True)
            raise AssertionError(("gallery bootstrap did not reach physical count", diagnostic)) from exc
        # Mimmi's old raw threshold included 481 repeated SHA rows. Require
        # every baseline distinct original plus the unchanged raw owner ledger;
        # duplicate rows can no longer make this test pass.
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
        # This is the real acceptance gate: every current owner record must
        # have a SHA/bytes/dimensions-identical route in its correct work.
        # A visible count or minimal bootstrap can never replace this proof.
        saved_routes = verify_saved_routes(context, page, model)
        assert saved_routes["saved_rows_checked"] == owner_raw["physical"], (
            model, "raw owner ledger and displayed exact routes diverged")
        assert "실제 저장본" in counts["banner"], (model, counts)
        duplicate_cuts=page.evaluate("""()=>stored.reduce((n,a)=>{
          const hashes=validImages(a).map(p=>p.sha256);
          return n+hashes.length-new Set(hashes).size;
        },0)""")
        assert duplicate_cuts==0,(model,"same saved bytes repeated inside a work",duplicate_cuts)
        assert page.locator("#albumgrid .album").count() >= 1, model
        verified = []
        controls_verified = []
        for album_id in rule["album_ids"]:
            album = page.locator(f'#albumgrid .album[data-id="{album_id}"]')
            assert album.count() == 1, (model, "missing gallery album", album_id)
            scroll_current(page, f'#albumgrid .album[data-id="{album_id}"]')
            # First-party owner preview must decode; not just a URL or placeholder.
            img = album.locator("img")
            assert img.count() >= 1, (model, album_id, "missing cover")
            try:
                page.wait_for_function("""(id) => {
                  const album=document.querySelector('#albumgrid .album[data-id="'+id+'"]');
                  const img=album?.querySelector('img');
                  return !!img && img.complete && img.naturalWidth>=160;
                }""", arg=album_id, timeout=30000)
            except PlaywrightTimeoutError as exc:
                # Make the actual stuck album / gateway error observable rather
                # than spending 105 seconds and reporting an anonymous timeout.
                # No media URL query or private token is ever logged.
                state = page.evaluate("""id => {
                  const card=[...document.querySelectorAll('#albumgrid .album')]
                    .find(x=>x.dataset.id===id);
                  const image=card?.querySelector('img');
                  let host=null, path=null;
                  try {
                    const u=new URL(image?.currentSrc||image?.src||'',location.href);
                    host=u.hostname;
                    path=u.pathname;
                  } catch {}
                  return {album:id,hasCard:!!card,imagePresent:!!image,
                    complete:image?.complete??null,decodedWidth:image?.naturalWidth??0,
                    currentHost:host,currentPath:path,
                    ownerVariant:image?.dataset.ownerVariant||null,
                    sourceRetry:image?.dataset.sourceRetry||null,
                    imageState:card?.dataset.imageState||null,
                    imageError:card?.dataset.imageError||null,
                    initialCover:!!card?.dataset.fastCover};
                }""", album_id)
                diagnostic = {"model":model,"browser":engine,"cover":state,
                              "recent_http_errors":page_resources[-12:],
                              "js_errors":failures[-5:],
                              "elapsed_seconds":round(time.monotonic()-start,2)}
                print("DEPLOYED_GALLERY_COVER_TIMEOUT",
                      json.dumps(diagnostic,ensure_ascii=False),flush=True)
                raise AssertionError(("real saved cover did not decode within 30 seconds",
                                      diagnostic)) from exc
            click_current(page, f'#albumgrid .album[data-id="{album_id}"]')
            assert page.locator("#detail").is_visible(), (model, album_id, "detail hidden")
            photo = page.locator("#detailphotos .photo").first
            scroll_current(page, "#detailphotos .photo")
            # A SHA-matched existing Pages copy is the G-09 fast path. The
            # optimized thumbnail is permitted only from THIS model's saved
            # static originals; remote API and verified blob routes remain.
            page.wait_for_function("""(model) => [...document.querySelectorAll('#detailphotos img')].some(img => {
              let sameModelPagesCopy=false;
              try {
                const u=new URL(img.currentSrc||img.src,location.href);
                sameModelPagesCopy=u.origin===location.origin &&
                  u.pathname.startsWith('/browser-app-lab/apps/'+model+'-gallery/stored-albums/');
              } catch {}
              return img.complete && img.naturalWidth>=160 &&
                (sameModelPagesCopy || img.src.includes('/api/') ||
                 img.src.startsWith('blob:'));
            })""", arg=model, timeout=110000)
            click_current(page, "#detailphotos .photo")
            # G-09-B now prefers the exact saved Pages file when SHA, bytes and
            # dimensions match. Do not reject a fully decoded local original
            # solely because it is not a gateway /api/ or blob response.
            page.wait_for_function("""model => {
              const img=document.querySelector('#full');
              if (!img || !img.complete || img.naturalWidth<160) return false;
              const source=img.currentSrc||img.src||'';
              if (source.startsWith('blob:') || source.includes('/api/'))
                return true;
              try {
                const u=new URL(source, location.href);
                return u.origin===location.origin &&
                  u.pathname.startsWith('/browser-app-lab/apps/'+model+'-gallery/stored-albums/');
              } catch { return false; }
            }""", arg=model, timeout=110000)
            assert page.locator("#lightbox").is_visible(), (model, album_id)
            if album_id == rule["album_ids"][0]:
                # Use real mobile taps and decoded stored images. A local HTTP
                # bridge can time out before the native browser's image gate;
                # this check always runs with the native deployed transport.
                original = page.locator("#full").get_attribute("src")
                position = page.locator("#position").inner_text()
                close_box = page.locator("#close").bounding_box()
                page.locator("#next").tap()
                page.wait_for_function("""old => {
                  const im=document.querySelector('#full');
                  return im?.complete && im.naturalWidth>=160 && im.src!==old;
                }""", arg=original, timeout=105000)
                assert page.locator("#position").inner_text() != position
                assert page.locator("#close").bounding_box() == close_box
                page.locator("#prev").tap()
                page.wait_for_function("""old => {
                  const im=document.querySelector('#full');
                  return im?.complete && im.naturalWidth>=160 && im.src===old;
                }""", arg=original, timeout=105000)
                assert page.locator("#position").inner_text() == position
                assert page.locator("#close").bounding_box() == close_box
                viewport=page.locator('meta[name="viewport"]').get_attribute("content")
                assert "user-scalable=no" not in viewport and "maximum-scale=1" not in viewport
                controls_verified.append(album_id)
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
        assert not failures, (model, failures)
        print("DEPLOYED_GALLERY_PHYSICAL_ORIGINAL_OPEN_PASS",
              json.dumps({"model":model,"browser":engine,
                          "album_count":counts["albums"],"visible_photo_rows":counts["total"],
                          "owner_private_photo_rows":counts["owner"],
                          "owner_index_raw_verified_photos":owner_raw["physical"],
                          "saved_file_routes":saved_routes,
                          "opened_albums":verified,
                          "next_previous_fixed_close_and_zoom_markup":controls_verified,
                          "real_iphone_hardware_tested":False,
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
