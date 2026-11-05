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
FILES = ("index.html", "post_activity_ranking.js", "public_video_trends.js",
         "target_archive_client.js", "account_auto_analysis.js", "account_watch.js",
         "account_index_client.js", "account_group_client.js")
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
            print("PAGES_DEPLOYED_MAIN_BYTES_SHA256_PASS: index, ranking, video, account analysis and backup button JS")
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
            elif (parsed.scheme == "https" and parsed.hostname=="github.com"
                    and parsed.path=="/koith/browser-app-lab/actions/workflows/intersection-target-account-bundle.yml"):
                route.fulfill(status=200,content_type="text/html",
                              body='<html><body><p id="workflow-opened">Owner GitHub workflow</p></body></html>')
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
        assert page.locator("#videoTrends").count() == 1, "video trends UI missing"
        assert_rank_rows_centered(page, width)
        # Static Pages has no private write token. The *deployed* backup
        # control must still become usable and open the authenticated GitHub
        # workflow rather than remaining disabled forever.
        page.locator("#viewAccounts").click()
        # Actual deployed account-analysis page must prioritize three clear
        # user tasks and keep implementation details behind disclosure.
        page.locator("#accountAutoSearch").wait_for(state="visible",timeout=12000)
        assert page.locator(".account-section-heading h3").all_inner_texts()==[
            "전체 계정 현황","관심 계정 관리","계정 백업"]
        assert page.locator("#accountAutoMount #intersectionAutoAccounts").count()==1
        assert page.locator("#accountServerData").is_hidden()
        assert page.locator("#accountMoreOptions").evaluate("(el)=>el.open") is False
        assert page.locator("#accountBackupSection").is_visible()
        assert page.locator("#accountWatchForm").is_visible()
        page.locator("#targetArchiveStatus").get_by_text("공개 페이지",exact=False).wait_for(timeout=12000)
        page.locator("#targetArchiveAccount").fill(
            "https://bsky.app/profile/synthetic-qa.bsky.social")
        assert page.locator("#targetArchiveSubmit").is_enabled()
        assert page.locator("#targetArchiveSubmit").inner_text()=="GitHub에서 백업 실행"
        page.locator("#targetArchiveAccount").fill("")
        page.locator("#targetArchiveSubmit").click()
        assert "먼저 공개 SNS 계정" in page.locator("#targetArchiveStatus").inner_text()
        page.locator("#targetArchiveAccount").fill(
            "https://bsky.app/profile/synthetic-qa.bsky.social")
        assert page.locator("#targetArchiveWorkflow").get_attribute("href")==(
            "https://github.com/koith/browser-app-lab/actions/workflows/"
            "intersection-target-account-bundle.yml")
        page.locator("#targetArchiveSubmit").click()
        page.wait_for_url(
            "https://github.com/koith/browser-app-lab/actions/workflows/"
            "intersection-target-account-bundle.yml",timeout=15000)
        assert page.locator("#workflow-opened").is_visible()
        print("PAGES_BACKUP_BUTTON_ENABLED_PASS:",label,
              "empty_input_feedback=PASS same_tab_mobile_navigation=PASS private_dispatch=NOT_CLAIMED")
        page.goto(URL + "?qa=return",wait_until="domcontentloaded",timeout=45000)
        page.locator("#viewPosts").click()

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
        # Video trends must use the exact verified code deployed on Pages,
        # never real social-media calls. Assert both public providers can be
        # compared and that changing source filters the actual cards.
        page.evaluate("""() => {
          const now=Date.now();
          window.INTERSECTION_publicVideoSnapshot=()=>({
            partial:false,verified:[
              {
                id:"synthetic-video-blue",platform:"bluesky",
                profileUrl:"https://bsky.app/profile/qa-only.invalid",
                url:"https://bsky.app/profile/qa-only.invalid/post/videoqa",
                author:"영상 QA Bluesky",
                posted:new Date(now-30*60000).toISOString(),
                engagement:{likes:4,replies:1},
                media:[{type:"video",thumb:""}]
              },
              {
                id:"synthetic-video-masto",platform:"mastodon",
                profileUrl:"https://mastodon.social/@qa-synthetic",
                url:"https://mastodon.social/@qa-synthetic/123",
                author:"영상 QA Mastodon",
                posted:new Date(now-80*60000).toISOString(),
                engagement:null,
                media:[{type:"video",thumb:""}]
              }
            ]
          });
          window.dispatchEvent(new Event("intersection:feed-updated"));
        }""")
        page.locator("#videoTrends > summary").click()
        page.locator("#videoTrendRows a.video-trend-card").first.wait_for(
            state="visible", timeout=12000)
        assert page.locator("#videoTrendRows a.video-trend-card").count()==2
        assert "Bluesky 1건" in page.locator("#videoTrendCoverage").inner_text()
        assert "Mastodon 1건" in page.locator("#videoTrendCoverage").inner_text()
        assert "반응 제공 1/1" in page.locator("#videoTrendCoverage").inner_text()
        assert "반응 제공 0/1" in page.locator("#videoTrendCoverage").inner_text()
        page.locator("#videoTrendSource").select_option("mastodon")
        assert page.locator("#videoTrendRows a.video-trend-card").count()==1
        assert page.locator("#videoTrendRows a.video-trend-card").first.get_attribute(
            "href")=="https://mastodon.social/@qa-synthetic/123"
        assert page.locator("#videoTrendRows a.video-trend-card").first.get_attribute(
            "target")=="_blank"
        page.locator("#videoTrendSource").select_option("bluesky")
        assert page.locator("#videoTrendRows a.video-trend-card").count()==1
        assert page.locator("#videoTrendRows a.video-trend-card").first.get_attribute(
            "href")=="https://bsky.app/profile/qa-only.invalid/post/videoqa"
        page.locator('[data-video-mode="archive"]').click()
        assert page.locator("#videoTrendMonth").is_visible()
        assert page.locator("#videoTrendRows a.video-trend-card").count()==1
        page.locator('[data-video-mode="hot"]').click()
        assert page.locator("#videoTrendMonth").is_hidden()
        assert page.locator("#videoTrendRows a.video-trend-card").count()==1
        print("PAGES_PUBLIC_VIDEO_TRENDS_PASS:",label,
              "sources=2 source_filter=PASS periods=PASS source_links=PASS")
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
