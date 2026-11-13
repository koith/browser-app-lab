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
        # Select an independently SHA-verified account bundle, not an arbitrary
        # legacy entry. Incremental append-only releases can contain ONE new
        # post even when the combined verified feed has hundreds of records.
        account_api=page.request.get(
            SITE.rsplit("/",1)[0]+"/api/account-archives",timeout=120000,
        )
        assert account_api.status==200, "live verified account index unavailable"
        sources=account_api.json().get("accounts",[])
        # Direct TeraBox reads may be provider-denied on the free viewer host.
        # An AES-GCM GitHub mirror of an SHA-verified saved ZIP is acceptable
        # temporary readback, never proof of TeraBox permanent storage.
        # Latest increment may contain zero NEW posts even though signed
        # ancestor ZIPs contain complete saved history. For each legitimate
        # archive row, check the independently verified merged history endpoint.
        available=[item for item in sources
                   if item.get("backup_kind") in (
                       "terabox_zip_sha_verified","github_temp_sha_verified")
                   and isinstance(item.get("key"),str)
                   and item["key"].startswith(("bluesky-","mastodon-"))]
        assert available, "no verified account ZIP available"
        # Only SHA-read-back profile snapshots can supply display names.
        readable=None
        for item in available[:12]:
            if not (item.get("profile_snapshot_verified") is True
                    and isinstance(item.get("display_name"),str)
                    and item["display_name"].strip()
                    and isinstance(item.get("handle"),str)
                    and item["handle"].strip()):
                continue
            status=page.request.get(
                SITE.rsplit("/",1)[0]+"/api/account-archives/"+
                quote(item["key"],safe="")+"/backup-status",
                timeout=120000,
            )
            if status.status!=200:
                continue
            info=status.json()
            if (info.get("state")=="REMOTE_ZIP_SHA_VERIFIED"
                    and info.get("storage") in (
                        "private_terabox","github_encrypted_temporary")
                    and isinstance(info.get("public_posts"),int)
                    and info["public_posts"]>=1):
                readable=item
                break
        assert readable is not None, (
            "no signed SHA-verified account HISTORY with saved posts and profile")
        key=readable["key"]
        # Exercise the ACTUAL SHA-verified saved journal, not a mocked API.
        # These calls are read-only; never print source text or account IDs.
        if "chromium" in label:
            endpoint=SITE.rsplit("/",1)[0]+"/api/account-archives/"+quote(key,safe="")+"/feed"
            def real_feed(query):
                raw=page.request.get(endpoint+"?"+query,timeout=120000)
                assert raw.status==200, "actual archived feed API unavailable"
                data=raw.json()
                assert isinstance(data.get("posts"),list) and isinstance(data.get("total"),int)
                return data
            baseline=real_feed("offset=0&limit=50")
            total=baseline["total"]
            assert total>0 and baseline["posts"], "verified history feed empty"
            kinds=[real_feed("offset=0&limit=1&kind="+v)["total"]
                   for v in ("post","reply","revision")]
            assert sum(kinds)==total, "real post/reply/revision filter parity failed"
            media_states=[real_feed("offset=0&limit=1&media_status="+v)["total"]
                          for v in ("complete","partial")]
            assert sum(media_states)==total, "real media verification filter parity failed"
            sample=next((p for p in baseline["posts"]
                         if isinstance(p.get("text"),str) and p["text"].strip()),None)
            assert sample is not None, "no saved original body for actual full-history search"
            term=sample["text"].strip()[:12]
            searched=real_feed("offset=0&limit=50&q="+quote(term,safe=""))
            assert any(p["id"]==sample["id"] for p in searched["posts"]), (
                "full-history text search lost an actual saved post")
            if total>1:
                next_page=real_feed("offset=1&limit=1")
                assert next_page["posts"] and next_page["posts"][0]["id"]!=baseline["posts"][0]["id"], (
                    "real post pagination repeats or skips first original")
            print("LIVE_ARCHIVE_REAL_FILTERS_PASS",
                  "stored_posts="+str(total),
                  "kinds="+str(len(kinds)),
                  "media_statuses="+str(len(media_states)),
                  "text_search=PASS","pagination=PASS",flush=True)
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
        assert posts>=1, "SHA-verified saved account has no rendered posts"
        provider="mastodon" if key.startswith("mastodon-") else "bluesky"
        assert page.locator("html").get_attribute("data-platform")==provider, (
            "saved account is not displayed in its original SNS-style theme")
        expected="Mastodon" if provider=="mastodon" else "Bluesky"
        assert page.locator("#snsProviderTitle").inner_text().startswith(expected)
        assert page.locator("#results article.post .post-byline strong").count()>=1
        page.wait_for_function(
            "(name) => document.querySelector('#results article.post .post-byline strong')?.textContent===name",
            arg=readable["display_name"],timeout=20000)
        assert page.locator("#results article.post .post-handle").count()>=1, (
            "archived actor handle not rendered on social card")
        assert page.locator("#displayName").inner_text().strip(), "profile display missing"
        assert "미확인" not in page.locator("#displayName").inner_text(), "profile not loaded"
        assert page.locator("#results article.post").first.get_by_role(
            "link", name="SNS 원문"
        ).count() == 1, "public original attribution missing"

        # Check a real archived original and its source binding in the browser,
        # not merely an API JSON response or a synthetic Playwright fixture.
        for _ in range(26):
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
        # Keep an EXACT original media API path, not just the number of
        # thumbnails. Switching tabs intentionally resets pagination to
        # the first page; earlier media can only reappear after More.
        selected_original=next(
            (m.first.get_attribute("src") for m in (image,video,audio)
             if m.count()),None)
        assert selected_original and selected_original.startswith(
            "/api/account-archives/")

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
        assert tab_elapsed<40, "verified account archive tab round-trip too slow"
        print("LIVE_VERIFIED_ACCOUNT_TAB_ROUNDTRIP_PASS",
              "client="+label, "elapsed_seconds="+str(round(tab_elapsed,1)),
              flush=True)
        doc = page.evaluate(
            "() => ({scroll:document.documentElement.scrollWidth,width:innerWidth})"
        )
        assert doc["scroll"] <= doc["width"] + 2, "horizontal overflow on live page"
        assert not javascript_errors, "deployed browser JavaScript errors occurred"
        # Verify the selected SHA-verified archive still renders its posts after tab switch.
        assert page.locator("#results article.post").count()>=1
        assert page.locator("#displayName").inner_text().strip()
        # Some independently verified source posts contain video or audio
        # rather than images. Validate the exact *actual* HTML media element,
        # source binding and byte-range read, never assume the account has <img>.
        originals=page.locator(
            "#results .post-media img, #results .post-media video, "
            "#results .post-media audio"
        )
        # A valid tab round-trip resets pagination. Require that the SAME
        # independently SHA-verified original remains obtainable after
        # traversing the real live feed again, never substitute an avatar.
        def original_present():
            return page.evaluate("""(expected) => [...document.querySelectorAll(
                '#results .post-media img, #results .post-media video, #results .post-media audio'
            )].some(el => el.getAttribute('src')===expected)""",selected_original)
        for _ in range(26):
            if original_present():
                break
            more=page.locator("#more")
            if not more.is_visible() or not more.is_enabled():
                break
            before=page.locator("#results article.post").count()
            more.click()
            page.wait_for_function(
                "(before) => document.querySelectorAll('#results article.post').length>before"
                " || document.querySelector('#more')?.textContent?.includes('다시 시도')",
                arg=before,timeout=60000)
            assert "다시 시도" not in more.inner_text(), (
                "verified source became unreachable on re-pagination")
        assert original_present(), (
            "previously visible verified original cannot be recovered after tab round-trip")
        chosen=page.locator(
            "#results .post-media img[src], #results .post-media video[src], "
            "#results .post-media audio[src]"
        )
        # Match one exact stored source, regardless of its position among
        # older posts; do not claim the full media list must remain paginated in.
        original_index=page.evaluate("""(expected) => {
           const list=[...document.querySelectorAll(
             '#results .post-media img[src], #results .post-media video[src], #results .post-media audio[src]')];
           return list.findIndex(el=>el.getAttribute('src')===expected);
        }""",selected_original)
        assert original_index>=0
        exact_original=chosen.nth(original_index)
        exact_original.scroll_into_view_if_needed()
        media_kind=exact_original.evaluate("(node) => node.tagName.toLowerCase()")
        assert media_kind in ("img","video","audio"), "unsupported source media node"
        if media_kind=="img":
            page.wait_for_function(
                "(expected) => [...document.querySelectorAll('#results .post-media img')]"
                ".some(img => img.getAttribute('src')===expected "
                "&& img.complete && img.naturalWidth > 0)",
                arg=selected_original,timeout=90000,
            )
        else:
            assert exact_original.evaluate("(node) => node.controls === true"), (
                "verified video or audio has no playback controls"
            )
        source=exact_original.get_attribute("src")
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
        print("LIVE_NATIVE_SNS_ACCOUNT_BROWSER_PASS",
              "client="+label,"post_cards="+str(
                  page.locator("#results article.post").count()),
              "source="+readable["backup_kind"],"theme="+provider,
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
    """Account-mode deep link preloads the real picker without extra clicks."""
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":430,"height":932})
        base=SITE.rsplit("/account-archive",1)[0]
        response=page.goto(base+"/?tab=archives&mode=accounts",wait_until="domcontentloaded",
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
        print("LIVE_MAIN_ARCHIVE_ACCOUNT_DEEPLINK_PASS",
              "client=mobile-chromium","account_deeplink=PASS","no_extra_clicks=PASS",
              "names=PASS","embedded_feed=PASS","responsive=PASS",
              flush=True)
    finally:
        browser.close()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        verify(playwright.chromium, label="desktop-chromium", width=1200, height=900)
        verify(playwright.webkit, label="iphone-webkit", width=430, height=932)
        verify_main_archive_hub(playwright.chromium)
