"""CI QA of the *deployed* public INTERSECTION Pages UI, with zero real SNS capture.

No user post, account, credential, image or private archive contents are read,
printed or stored. Desktop Chromium and mobile WebKit approximate browsers;
the latter is NOT a physical iPhone certification.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from test_live_browser import assert_rank_rows_centered

ROOT = Path(__file__).resolve().parent
URL = os.getenv(
    "INTERSECTION_PAGES_URL",
    "https://koith.github.io/browser-app-lab/apps/demand-research/"
)
FILES = ("index.html", "post_activity_ranking.js")
EXPECTED = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in FILES}


def verify_pages_bytes():
    """Refuse to certify stale Pages bytes as the current main release."""
    failures = []
    for attempt in range(18):
        failures.clear()
        for name, digest in EXPECTED.items():
            address = URL + name + "?ci_ref=" + digest[:16]
            try:
                request = Request(address, headers={
                    "User-Agent": "INTERSECTION-read-only-Pages-QA/1.0",
                    "Cache-Control": "no-cache",
                })
                with urlopen(request, timeout=25) as response:
                    if response.status != 200:
                        raise RuntimeError("deployed path HTTP not successful")
                    raw = response.read(3_000_000)
                if hashlib.sha256(raw).hexdigest() != digest:
                    failures.append(name + ":stale_or_mismatched")
            except Exception:
                failures.append(name + ":unavailable")
        if not failures:
            print("PAGES_DEPLOYED_MAIN_BYTES_SHA256_PASS: index and ranking JS")
            return
        if attempt < 17:
            time.sleep(12)
    raise AssertionError("Pages current-main byte verification failed: " +
                         ",".join(failures))


def inspect_browser(browser_type, label, width, height):
    browser = browser_type.launch(headless=True)
    try:
        page = browser.new_page(viewport={"width": width, "height": height})
        # Explicitly block third-party networking: this is a Pages UI deployment
        # test, not another SNS crawler or a browser that fetches personal posts.
        def restrict_network(route):
            parsed = urlparse(route.request.url)
            if (parsed.scheme == "https"
                    and parsed.hostname == "koith.github.io"
                    and parsed.path.startswith("/browser-app-lab/apps/demand-research/")):
                route.continue_()
            else:
                route.abort()
        page.route("**/*", restrict_network)
        response = page.goto(URL + "?qa=public-ui", wait_until="domcontentloaded",
                             timeout=45000)
        assert response and response.status == 200, "deployed HTML unavailable"
        assert page.locator("#viewPosts").count() == 1, "posts navigation missing"
        assert page.locator("#feed").count() == 1, "feed missing"
        assert page.locator("#activityRankingRows").count() == 1, "rank UI missing"
        assert page.locator("#activityRankingDialog").count() == 1, "rank dialog missing"
        assert_rank_rows_centered(page, width)

        # Feed only synthetic source-proof data through the *deployed* ranking
        # module; no provider response or real account detail is accessed.
        page.evaluate("""() => {
          const now=Date.now();
          window.INTERSECTION_publicRankingSnapshot=()=>({
            fromMs:now-7*86400000,toMs:now+86400000,
            verified:[{
              id:"synthetic-qa-only",platform:"bluesky",
              profileUrl:"https://bsky.app/profile/qa-only.invalid",
              author:"배포 QA",posted:new Date(now-86400000).toISOString(),
              profileCreatedAt:new Date(now-120*86400000).toISOString(),
              engagement:{likes:1},thumbnailUrl:"",avatarUrl:""
            }]
          });
          window.dispatchEvent(new Event("intersection:feed-updated"));
        }""")
        page.locator("#activityRankingRows .activity-rank-card").first.wait_for(
            state="visible",timeout=10000)
        assert page.locator('[data-rank-cohort="established"]').get_attribute(
            "aria-selected") == "true", "verified mature source wrongly classified"
        page.locator("#activityRankingRows .activity-rank-card").first.click()
        assert page.locator("#activityRankingDialog[open]").count() == 1, "rank dialog not opening"
        assert "배포 QA" in page.locator("#activityRankingDialogContent").inner_text()
        assert page.locator("#activityRankingDialogContent a[target='_blank']").count() == 1
        page.locator("#activityRankingDialogClose").click()
        assert page.locator("#activityRankingDialog[open]").count() == 0
        viewport = page.evaluate("""() => ({
          contentWidth:document.documentElement.scrollWidth,
          windowWidth:window.innerWidth
        })""")
        assert viewport["contentWidth"] <= viewport["windowWidth"] + 2, (
            "page horizontal overflow",viewport)
        print("PAGES_PUBLIC_UI_PASS:",label,
              "rank_cards=1 dialog=open-close responsive_layout=PASS no_third_party_crawl")
    finally:
        browser.close()


if __name__ == "__main__":
    verify_pages_bytes()
    with sync_playwright() as playwright:
        inspect_browser(playwright.chromium, "desktop-chromium", 1200, 900)
        inspect_browser(playwright.webkit, "mobile-webkit-simulation", 390, 844)
    print("INT_08_DEPLOYED_BROWSER_QA_PASS (physical iPhone still UNVERIFIED)")
