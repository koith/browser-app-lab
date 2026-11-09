"""Live read-only browser acceptance of the deployed private account archive.

Uses ACTUAL verified public-account storage through the public HTTPS gateway:
no synthetic API interception, credentials, screenshots, raw account text,
profile IDs, media URL printouts, or mutations of the backup source.
"""
from __future__ import annotations

from playwright.sync_api import sync_playwright
from urllib.parse import quote
import time

SITE = "https://intersection-originals-free.onrender.com/account-archive"


def verify(engine, *, label, width, height):
    browser = engine.launch(headless=True)
    try:
        page = browser.new_page(
            viewport={"width": width, "height": height},
            color_scheme="light",
        )
        javascript_errors = []
        page.on("pageerror", lambda _error: javascript_errors.append("pageerror"))
        # Select an independently verified six-post TeraBox ZIP upfront.
        # An arbitrary first account may have incomplete legacy records, and
        # waiting on every such profile masked the actual usable archive.
        account_api=page.request.get(
            SITE.rsplit("/",1)[0]+"/api/account-archives",timeout=120000,
        )
        assert account_api.status==200, "live verified account index unavailable"
        sources=account_api.json().get("accounts",[])
        # Direct TeraBox reads may be provider-denied on the free viewer host.
        # An AES-GCM GitHub mirror of a TeraBox SHA-verified six-post ZIP is
        # an acceptable *temporary* readback, never a claim of TeraBox access.
        available=[item for item in sources
                   if item.get("backup_kind") in (
                       "terabox_zip_sha_verified","github_temp_sha_verified")
                   and item.get("posts_verified_in_bundle",0)>=6]
        assert available, "six-post verified account ZIP not discoverable in webapp"
        # Only an authenticated SHA-read-back public profile snapshot can
        # supply real account-picker names; do not invent a nickname from URL.
        readable=next((item for item in available
                       if item.get("profile_snapshot_verified") is True
                       and isinstance(item.get("display_name"),str)
                       and item["display_name"].strip()
                       and isinstance(item.get("handle"),str)
                       and item["handle"].strip()),None)
        assert readable is not None, "verified account has no archived nickname/handle"
        key=readable["key"]
        response = page.goto(SITE+"?account="+quote(key,safe=""),
                             wait_until="domcontentloaded", timeout=180000)
        assert response and response.status == 200, "live account-viewer HTML unavailable"
        chooser=page.locator("#accountSelect")
        chooser.wait_for(timeout=20000)
        page.wait_for_function(
            "() => document.querySelector('#accountSelect')?.selectedOptions[0]"
            "?.value?.startsWith('bluesky-') || "
            "document.querySelector('#accountSelect')?.selectedOptions[0]"
            "?.value?.startsWith('mastodon-')",timeout=120000)
        labels=chooser.locator("option").all_text_contents()
        assert labels and all("https://" not in text for text in labels), (
            "archive account selector still displays raw profile URLs"
        )
        selected_option=chooser.locator("option:checked").text_content() or ""
        assert readable["display_name"].strip() in selected_option, (
            "saved nickname is missing from actual account picker"
        )
        assert readable["handle"].strip().lstrip("@") in selected_option, (
            "saved handle is missing from actual account picker"
        )
        assert chooser.input_value()==key, "deep-linked saved account not selected"
        print("LIVE_ARCHIVE_NICKNAME_PICKER_PASS","client="+label,
              "auto_loaded=PASS","nickname_handle=PASS","no_raw_url=PASS",
              flush=True)
        page.locator("#results article.post").first.wait_for(timeout=120000)
        posts=page.locator("#results article.post").count()
        assert posts>=6, "verified TeraBox six-post archive not rendered"
        assert page.locator("#displayName").inner_text().strip(), "profile display missing"
        assert "미확인" not in page.locator("#displayName").inner_text(), "profile not loaded"
        assert page.locator("#results article.post").first.get_by_role(
            "link", name="SNS 원문"
        ).count() == 1, "public original attribution missing"

        # Check a real archived original and its source binding in the browser,
        # not merely an API JSON response or a synthetic Playwright fixture.
        for _ in range(12):
            image = page.locator("#results .post-media img")
            video = page.locator("#results .post-media video")
            audio = page.locator("#results .post-media audio")
            if image.count() or video.count() or audio.count():
                break
            more = page.locator("#more")
            if not more.is_visible() or not more.is_enabled():
                break
            before = page.locator("#results article.post").count()
            more.click()
            page.wait_for_function(
                "(old) => document.querySelectorAll('#results article.post').length > old"
                " || document.querySelector('#more')?.textContent?.includes('다시 시도')",
                arg=before, timeout=60000,
            )
            assert "다시 시도" not in more.inner_text(), "live feed pagination failed"
        media_count = image.count() + video.count() + audio.count()
        assert media_count > 0, "real feed has no accessible original media"
        if image.count():
            image.first.scroll_into_view_if_needed()
            page.wait_for_function(
                "() => {const img=document.querySelector('#results .post-media img');"
                "return !!img && img.complete && img.naturalWidth > 0;}",
                timeout=90000,
            )
        for m in (image, video, audio):
            if m.count():
                actual = m.first.get_attribute("src")
                assert actual and actual.startswith("/api/account-archives/"), (
                    "media did not come from the verified account-archive reader"
                )

        page.locator("#results article.post").first.get_by_role(
            "button", name="댓글·상세 보기"
        ).click()
        page.locator("#postDetail[open]").wait_for(timeout=10000)
        page.get_by_role("button", name="닫기").click()
        assert page.locator("#postDetail[open]").count() == 0, "detail did not close"

        tabs_started=time.monotonic()
        for tab in ("팔로워", "팔로잉", "게시글·답글"):
            page.get_by_role("tab", name=tab).click()
            if tab=="게시글·답글":
                # Require ACTUAL saved posts after the user returns, not a
                # nonempty loading placeholder from a stale tab.
                page.locator("#results article.post").first.wait_for(timeout=40000)
            else:
                page.wait_for_function(
                    "() => !!document.querySelector('#results')?.textContent?.trim()",
                    timeout=30000,
                )
        tab_elapsed=time.monotonic()-tabs_started
        assert tab_elapsed<40, "verified six-post archive tab round-trip too slow"
        print("LIVE_VERIFIED_ACCOUNT_TAB_ROUNDTRIP_PASS",
              "client="+label, "elapsed_seconds="+str(round(tab_elapsed,1)),
              flush=True)
        doc = page.evaluate(
            "() => ({scroll:document.documentElement.scrollWidth,width:innerWidth})"
        )
        assert doc["scroll"] <= doc["width"] + 2, "horizontal overflow on live page"
        assert not javascript_errors, "deployed browser JavaScript errors occurred"
        # Verify that the same selected archive still shows its six posts.
        assert page.locator("#results article.post").count()>=6
        assert page.locator("#displayName").inner_text().strip()
        # Some independently verified source posts contain video or audio
        # rather than images. Validate the exact *actual* HTML media element,
        # source binding and byte-range read, never assume the account has <img>.
        originals=page.locator(
            "#results .post-media img, #results .post-media video, "
            "#results .post-media audio"
        )
        assert originals.count()>=media_count>0, (
            "previously visible verified media disappeared after tab round-trip"
        )
        originals.first.scroll_into_view_if_needed()
        media_kind=originals.first.evaluate("(node) => node.tagName.toLowerCase()")
        assert media_kind in ("img","video","audio"), "unsupported source media node"
        if media_kind=="img":
            page.wait_for_function(
                "() => {const img=document.querySelector('#results .post-media img');"
                "return !!img && img.complete && img.naturalWidth > 0;}",
                timeout=90000,
            )
        else:
            assert originals.first.evaluate("(node) => node.controls === true"), (
                "verified video or audio has no playback controls"
            )
        source=originals.first.get_attribute("src")
        assert source and source.startswith("/api/account-archives/"), (
            "verified original was not delivered through authenticated reader"
        )
        response=page.request.get(SITE.rsplit("/",1)[0]+source,
                                  headers={"Range":"bytes=0-1023"},
                                  timeout=90000)
        assert response.status==206 and response.body(), (
            "deployed verified media HTTP Range read failed"
        )
        assert response.headers.get("content-range","").startswith("bytes 0-"), (
            "original source did not provide a valid media byte range"
        )
        mime=response.headers.get("content-type","").split(";",1)[0].lower()
        if media_kind=="img":
            assert mime.startswith("image/"), "image source MIME mismatch"
        else:
            assert mime.startswith(media_kind+"/"), (
                "video/audio original source MIME mismatch"
            )
        page.locator("#results article.post").first.get_by_role(
            "button",name="댓글·상세 보기"
        ).click()
        page.locator("#postDetail[open]").wait_for(timeout=12000)
        page.get_by_role("button",name="닫기").click()
        assert page.locator("#postDetail[open]").count()==0
        assert not javascript_errors, "TeraBox browser raised a JavaScript error"
        print("LIVE_VERIFIED_SIX_POST_BROWSER_PASS",
              "client="+label,"post_cards="+str(
                  page.locator("#results article.post").count()),
              "source="+available[0]["backup_kind"],
              "original_media=PASS","range206=PASS","detail=PASS",
              flush=True)
        print(
            "LIVE_ACCOUNT_BROWSER_PASS",
            "client=" + label,
            "post_cards=" + str(posts),
            "archived_media=" + str(media_count),
            "detail=PASS",
            "tabs=PASS",
            "responsive=PASS",
            flush=True,
        )
    finally:
        browser.close()


def verify_main_archive_hub(engine):
    """Check actual signed web app preloads its picker without extra clicks."""
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":430,"height":932})
        base=SITE.rsplit("/account-archive",1)[0]
        response=page.goto(base+"/?tab=archives",wait_until="domcontentloaded",
                           timeout=180000)
        assert response and response.status==200
        quick=page.locator("#archiveQuickSelect")
        quick.wait_for(state="attached",timeout=20000)
        page.wait_for_function(
            "() => !document.querySelector('#archiveQuickSelect')?.disabled"
            " && document.querySelector('#archiveQuickSelect')?.options?.length>=1"
            " && document.querySelector('#archiveAccountPicker')?.hidden===false",
            timeout=120000)
        labels=quick.locator("option").all_text_contents()
        assert labels and all("https://" not in name for name in labels), (
            "main archive picker shows raw addresses or was not preloaded"
        )
        assert page.locator("#archiveModeAccounts").get_attribute(
            "aria-selected")=="true", "saved account view not selected by default"
        frame=page.locator("#archiveHubFrame")
        page.wait_for_function(
            "() => document.querySelector('#archiveHubFrame')?.getAttribute('src')"
            "?.includes('embedded=1&account=')",timeout=120000)
        assert frame.is_visible(), "saved account feed not shown immediately"
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= innerWidth+3"), (
            "mobile archive page has horizontal overflow"
        )
        print("LIVE_MAIN_ARCHIVE_AUTO_PICKER_PASS",
              "client=mobile-chromium","no_clicks=PASS",
              "names=PASS","embedded_feed=PASS","responsive=PASS",
              flush=True)
    finally:
        browser.close()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        verify(playwright.chromium, label="desktop-chromium", width=1200, height=900)
        verify(playwright.webkit, label="iphone-webkit", width=430, height=932)
        verify_main_archive_hub(playwright.chromium)
