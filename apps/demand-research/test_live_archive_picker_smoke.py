"""Read-only deployed account picker acceptance in real Chromium and WebKit.

No fixture interception, no account names, links, text, media bytes, cookies or
identifiers are logged. The real SHA-verified source remains unchanged.
"""
from __future__ import annotations

from urllib.parse import quote, urlsplit
from playwright.sync_api import sync_playwright

BASE="https://intersection-originals-free.onrender.com"


def inspect_browser(engine,label,width,height):
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":width,"height":height},
                              color_scheme="light")
        requests=[]
        page.on("request",lambda req:
                requests.append(urlsplit(req.url).path)
                if urlsplit(req.url).path=="/api/account-archives" else None)
        response=page.request.get(BASE+"/api/account-archives",timeout=120000)
        assert response.status==200,"live stored-account API unavailable"
        stored=response.json().get("accounts",[])
        assert len(stored)>=1,"no genuinely archived accounts"
        assert all(item.get("display_name") and item.get("handle")
                   and item.get("profile_snapshot_verified") is True
                   for item in stored),"stored accounts lack verified nickname/id"
        # Main webapp must load account choices before the user clicks
        # a separate "load" button or opens an external GitHub workflow.
        root=page.goto(BASE+"/?tab=archives",
                       wait_until="domcontentloaded",timeout=180000)
        assert root and root.status==200,"main live webapp unavailable"
        quick=page.locator("#archiveQuickSelect")
        page.wait_for_function(
            "() => {const el=document.querySelector('#archiveQuickSelect');"
            "return !!el && !el.disabled && el.options.length>=1 &&"
            "!document.querySelector('#archiveAccountPicker')?.hidden;}",
            timeout=120000)
        all_labels=quick.locator("option").all_text_contents()
        assert len(all_labels)==len(stored),"visible choices differ from verified API"
        assert all("https://" not in s and "(@" in s and ")" in s
                   for s in all_labels),"raw URLs or missing nickname(@handle)"
        assert page.locator("#archiveModeAccounts").get_attribute(
            "aria-selected")=="true","account archive is not the default mode"
        frame=page.locator("#archiveHubFrame")
        page.wait_for_function(
            "() => document.querySelector('#archiveHubFrame')"
            "?.getAttribute('src')?.includes('embedded=1&account=')",
            timeout=120000)
        assert frame.is_visible(),"account archive not visibly embedded"
        assert requests.count("/api/account-archives")==1, (
            "account dropdown required a redundant remote ZIP listing"
        )
        first=quick.input_value()
        assert first in {item["key"] for item in stored}
        others=[item for item in stored if item["key"]!=first]
        if others:
            new_key=others[0]["key"]
            quick.select_option(new_key)
            page.wait_for_function(
                "(key) => document.querySelector('#archiveHubFrame')"
                "?.getAttribute('src')?.includes('account='+encodeURIComponent(key))",
                arg=new_key,timeout=30000)
            assert page.locator("#archiveHubFullView").get_attribute(
                "href").endswith("account="+quote(new_key,safe=""))
            assert requests.count("/api/account-archives")==1, (
                "switching accounts unexpectedly refetched all private ZIPs"
            )
        assert page.evaluate(
            "() => document.documentElement.scrollWidth <= innerWidth+3"), (
            "mobile main archive overflows viewport"
        )
        print("LIVE_ARCHIVE_MAIN_PICKER_PASS",label,
              "accounts="+str(len(stored)),"preload=PASS",
              "nickname_id=PASS","switch=PASS","no_duplicate_list=PASS",
              "mobile_overflow=0",flush=True)

        # The separate full viewer must show a real six-post verified original,
        # not merely a mocked profile, card skeleton or failed remote request.
        source=next((item for item in stored
                     if item.get("posts_verified_in_bundle",0)>=6),None)
        assert source is not None,"no independently verified six-post archive"
        key=source["key"]
        page_errors=[]
        page.on("pageerror",lambda error:page_errors.append(type(error).__name__))
        view=page.goto(BASE+"/account-archive?account="+quote(key,safe=""),
                       wait_until="domcontentloaded",timeout=180000)
        assert view and view.status==200
        native=page.locator("#accountSelect")
        page.wait_for_function(
            "(key) => document.querySelector('#accountSelect')?.value===key",
            arg=key,timeout=120000)
        labels=native.locator("option").all_text_contents()
        expected=source["display_name"].strip()
        handle=source["handle"].strip().lstrip("@")
        assert any(expected in s and handle in s and "https://" not in s
                   for s in labels),"full viewer does not show archived name/ID"
        page.locator("#results article.post").first.wait_for(timeout=120000)
        count=page.locator("#results article.post").count()
        assert count>=6,"real saved posts not visible"
        assert page.locator("#displayName").inner_text().strip(), (
            "stored public profile not displayed"
        )
        assert not page_errors,"archive viewer raised JavaScript exception"
        print("LIVE_ARCHIVE_STANDALONE_PICKER_PASS",label,
              "six_post_archive=PASS","nickname_id=PASS",
              "auto_load=PASS","javascript_errors=0",flush=True)
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        inspect_browser(p.chromium,"desktop_chromium",1200,900)
        inspect_browser(p.webkit,"mobile_webkit",430,932)
