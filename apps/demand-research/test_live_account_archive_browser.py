"""Live read-only browser acceptance of the deployed private account archive.

Uses ACTUAL verified public-account storage through the public HTTPS gateway:
no synthetic API interception, credentials, screenshots, raw account text,
profile IDs, media URL printouts, or mutations of the backup source.
"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

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
        response = page.goto(SITE, wait_until="domcontentloaded", timeout=180000)
        assert response and response.status == 200, "live account-viewer HTML unavailable"
        page.wait_for_function(
            "() => document.querySelectorAll('#accountSelect option').length > 1",
            timeout=120000,
        )

        # Work through verified accounts without assuming the first has posts.
        posts = 0
        options = page.locator("#accountSelect option")
        for i in range(1, min(options.count(), 9)):
            value = options.nth(i).get_attribute("value")
            if not value:
                continue
            page.locator("#accountSelect").select_option(value)
            try:
                page.locator("#results article.post").first.wait_for(timeout=45000)
            except Exception:
                continue
            posts = page.locator("#results article.post").count()
            if posts:
                break
        assert posts, "no live saved posts visible on the deployed page"
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

        for tab in ("팔로워", "팔로잉", "게시글·답글"):
            page.get_by_role("tab", name=tab).click()
            page.wait_for_function(
                "() => !!document.querySelector('#results')?.textContent?.trim()",
                timeout=45000,
            )
        page.locator("#results article.post").first.wait_for(timeout=60000)
        doc = page.evaluate(
            "() => ({scroll:document.documentElement.scrollWidth,width:innerWidth})"
        )
        assert doc["scroll"] <= doc["width"] + 2, "horizontal overflow on live page"
        assert not javascript_errors, "deployed browser JavaScript errors occurred"
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


if __name__ == "__main__":
    with sync_playwright() as playwright:
        verify(playwright.chromium, label="desktop-chromium", width=1200, height=900)
        verify(playwright.webkit, label="iphone-webkit", width=430, height=932)
