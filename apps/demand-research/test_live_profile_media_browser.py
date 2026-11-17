"""Read-only acceptance of real saved profile art in the deployed intersection UI.

No credentials, source account identifiers, media bytes or profile text printed.
Runs against production HTTPS; never writes an archive or external account.
"""
from __future__ import annotations

import re
from urllib.parse import quote
from playwright.sync_api import sync_playwright

BASE = "https://intersection-originals-free.onrender.com"
KEY_PATTERN = re.compile(r"^(?:bluesky|mastodon)-[0-9a-f]{40}$")


def candidate(request):
    index = request.get(BASE + "/api/account-archives", timeout=120000)
    assert index.status == 200, "live account index HTTP failure"
    accounts = index.json().get("accounts", [])
    assert isinstance(accounts, list) and accounts, "no saved accounts"
    attempted = 0
    failures = 0
    for item in accounts[:30]:
        key = item.get("key")
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            continue
        attempted += 1
        try:
            result = request.get(
                BASE + "/api/account-archives/" + quote(key, safe="") + "/profile",
                timeout=90000,
            )
            if result.status != 200:
                failures += 1
                continue
            profile = result.json()
            assets = profile.get("assets") or {}
            image = assets.get("banner")
            if not profile.get("available") or not isinstance(image, str):
                continue
            allowed = ("/api/account-archives/" + key + "/profile-asset/banner")
            assert image.startswith(allowed), "unsafe or cross-account banner path"
            # This is the actual SHA-verified public account archive gateway.
            original = request.get(BASE + image, timeout=120000)
            assert original.status == 200, "saved banner readback HTTP failure"
            assert original.headers.get("content-type", "").lower().startswith("image/"), (
                "banner endpoint served non-image content"
            )
            assert len(original.body()) > 0, "saved banner contained no bytes"
            return key, profile, attempted, failures
        except AssertionError:
            raise
        except Exception:
            failures += 1
    raise AssertionError(
        f"no readable archived banner: checked={attempted}, errors={failures}"
    )


def run():
    with sync_playwright() as pw:
        request = pw.request.new_context(ignore_https_errors=False)
        try:
            key, profile, checked, failures = candidate(request)
            for engine, label, width, height in (
                (pw.chromium, "desktop-chromium", 1200, 900),
                (pw.webkit, "iphone-webkit", 430, 932),
            ):
                browser = engine.launch(headless=True)
                try:
                    page = browser.new_page(
                        viewport={"width": width, "height": height},
                        color_scheme="light",
                    )
                    response = page.goto(
                        BASE + "/account-archive?account=" + quote(key, safe=""),
                        wait_until="domcontentloaded", timeout=180000,
                    )
                    assert response is not None and response.status == 200
                    page.locator("#coverImage").wait_for(state="visible", timeout=150000)
                    page.wait_for_function(
                        "() => {const x=document.querySelector('#coverImage');"
                        "return x && x.complete && x.naturalWidth>0 && x.naturalHeight>0}",
                        timeout=150000,
                    )
                    assert page.locator("#cover").evaluate(
                        "(x)=>x.classList.contains('has-image')"
                    ), "real banner not revealed after image decode"
                    assert page.locator("#coverImage").evaluate(
                        "(x)=>getComputedStyle(x).objectFit"
                    ) == "cover", "real banner crop incorrect"
                    if profile.get("assets", {}).get("avatar"):
                        page.locator("#avatarImage").wait_for(
                            state="visible", timeout=150000
                        )
                        box = page.locator("#avatar").evaluate(
                            """(frame) => {
                              const b=frame.getBoundingClientRect(),
                                    i=frame.querySelector('img').getBoundingClientRect(),
                                    c=getComputedStyle(frame);
                              return {
                                frame:b.width,inner:i.width,
                                border:parseFloat(c.borderLeftWidth),
                                radius:c.borderRadius,
                                innerFit:getComputedStyle(frame.querySelector('img')).objectFit
                              };
                            }"""
                        )
                        expected = (94, 90, 2) if key.startswith("bluesky-") else (80, 78, 1)
                        assert abs(box["frame"] - expected[0]) < 1, "circular frame size mismatch"
                        assert abs(box["inner"] - expected[1]) < 1, "inner avatar size mismatch"
                        assert abs(box["border"] - expected[2]) < .5, "frame ring mismatch"
                        assert box["innerFit"] == "cover", "avatar content not centered/cropped"
                    print(
                        "LIVE_PROFILE_NATIVE_IMAGES_PASS",
                        "browser=" + label, "banner=decoded", "avatar=checked",
                        "saved_original=HTTP200", flush=True,
                    )
                finally:
                    browser.close()
            print(
                "LIVE_PROFILE_SOURCE_COVERAGE",
                "checked=" + str(checked), "unreadable=" + str(failures),
                flush=True,
            )
        finally:
            request.dispose()


if __name__ == "__main__":
    run()
