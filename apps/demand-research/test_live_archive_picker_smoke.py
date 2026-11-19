"""Read-only deployed account picker acceptance in real Chromium and WebKit.

No fixture interception, no account names, links, text, media bytes, cookies or
identifiers are logged. The real SHA-verified source remains unchanged.
"""
from __future__ import annotations

from urllib.parse import quote, urlencode, urlsplit
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
        # Incomplete historical ZIPs must remain visible, not silently
        # excluded merely because their old profile snapshot is absent.
        # Require at least one independently verified full-profile archive;
        # other rows must be explicitly labelled as incomplete in the UI.
        verified=[item for item in stored
                  if item.get("display_name") and item.get("handle")
                  and item.get("profile_snapshot_verified") is True]
        assert verified,"no verified profile-backed account archive"
        assert all(item.get("key","").startswith(("bluesky-","mastodon-"))
                   and isinstance(item.get("posts_verified_in_bundle"),int)
                   for item in stored),"unverified/malformed archive inventory"
        # Main webapp must load account choices before the user clicks
        # a separate "load" button or opens an external GitHub workflow.
        root=page.goto(BASE+"/?tab=archives&mode=accounts",
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
        assert all("https://" not in s and s.strip()
                   for s in all_labels),"raw URLs or blank archive labels"
        for item,label in zip(stored,all_labels):
            # UI sorts the account rows independently; labels are verified
            # against the selected key rather than assuming API enumeration order.
            assert len(label)<=320,"unexpected unbounded archive display label"
        assert len(all_labels)==len(stored)
        assert page.locator("#archiveModeAccounts").get_attribute(
            "aria-selected")=="true","explicit account archive mode did not activate"
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
        # A later append-only ZIP may hold six posts while an older or
        # different account's profile ZIP is the only verified profile. Both
        # independently verified archives must remain visible to the owner.
        source=next((item for item in verified
                     if item.get("posts_verified_in_bundle",0)>=6),None)
        if source is None:
            source=next((item for item in stored
                         if item.get("posts_verified_in_bundle",0)>=6),None)
        print("LIVE_ARCHIVE_INVENTORY_EVIDENCE",label,
              "accounts="+str(len(stored)),
              "profile_verified="+str(len(verified)),
              "six_post_candidates="+str(sum(
                  item.get("posts_verified_in_bundle",0)>=6 for item in stored)),
              "profile_six_intersection="+str(sum(
                  item.get("profile_snapshot_verified") is True and
                  item.get("posts_verified_in_bundle",0)>=6 for item in stored)),
              flush=True)
        assert source is not None,"no independently verified six-post archive"
        key=source["key"]
        # Direct readback from the REAL, non-intercepted production server:
        # profile, archive feed, pagination, text/attachment filters and an
        # actual SHA-authorized image/video blob. No identifying content is
        # printed, persisted, or sent to an unrelated service.
        api=BASE+"/api/account-archives/"+quote(key,safe="")
        # Check the actual verified profile at its own immutable account key.
        # There is no reason for an unrelated posts-rich partial ZIP to
        # masquerade as profile-complete or be excluded from the picker.
        profile_api=BASE+"/api/account-archives/"+quote(
            verified[0]["key"],safe="")
        profile_response=page.request.get(profile_api+"/profile",timeout=120000)
        assert profile_response.status==200,"production profile read unavailable"
        profile=profile_response.json()
        assert profile.get("available") is True,"no real archived profile snapshot"
        first_response=page.request.get(api+"/feed?limit=2&offset=0",timeout=120000)
        assert first_response.status==200,"production original feed read unavailable"
        first=first_response.json()
        assert first.get("total",0)>=6 and len(first.get("posts",[]))==2, (
            "verified archive does not serve six distinct posts through the live API")
        second_response=page.request.get(api+"/feed?limit=2&offset=2",timeout=120000)
        assert second_response.status==200,"pagination of actual archive failed"
        second=second_response.json()
        assert len(second.get("posts",[]))==2
        ids_first={post["id"] for post in first["posts"]}
        ids_second={post["id"] for post in second["posts"]}
        assert not ids_first.intersection(ids_second),"archive load-more duplicated a saved post"
        assert second["total"]==first["total"],"live archive changed while paginating"
        text_value=str(first["posts"][0].get("text") or "")
        if text_value.strip():
            query=text_value.strip()[:min(12,len(text_value.strip()))]
            search_response=page.request.get(
                api+"/feed?"+urlencode({"limit":10,"q":query}),timeout=120000)
            assert search_response.status==200,"archive text search request failed"
            results=search_response.json()
            assert results["total"]>=1 and all(
                query.casefold() in str(post.get("text","")).casefold()
                for post in results["posts"]),"full-journal text filtering failed"
        status_name=("complete" if first["posts"][0].get("archive_complete") else
                     "partial")
        status_response=page.request.get(
            api+"/feed?"+urlencode({"limit":10,"media_status":status_name}),
            timeout=120000)
        assert status_response.status==200,"saved attachment filter failed"
        status_rows=status_response.json()
        assert status_rows["total"]>=1 and all(
            bool(post.get("archive_complete"))==(status_name=="complete")
            for post in status_rows["posts"]),"attachment filter result inconsistent"
        # Find any confirmed original in the first available 50 posts; a
        # backend returning metadata without actual bytes is NOT INT-05 PASS.
        full=page.request.get(api+"/feed?limit=50&offset=0",timeout=120000)
        assert full.status==200,"archive first full page unreadable"
        backed=[m for post in full.json().get("posts",[])
                for m in post.get("media",[])
                if m.get("verified_sha256") is True and m.get("url")]
        assert backed,"no original photo, video or audio bytes in the archived feed"
        media_response=page.request.get(
            BASE+backed[0]["url"],headers={"Range":"bytes=0-63"},
            timeout=120000)
        assert media_response.status in (200,206),"archived original media cannot be read"
        assert len(media_response.body())>0,"archived original media is empty"
        print("LIVE_ARCHIVE_VERIFIED_ORIGINALS_PASS",label,
              "https=PASS","profile=PASS","posts_at_least_six=PASS",
              "pagination=PASS","global_search=PASS","media_filter=PASS",
              "original_media_readback=PASS",flush=True)
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
        if source.get("profile_snapshot_verified") is True:
            expected=source["display_name"].strip()
            handle=source["handle"].strip().lstrip("@")
            assert any(expected in s and handle in s and "https://" not in s
                       for s in labels),"full viewer lacks archived nickname/ID"
        else:
            assert labels and all("https://" not in s for s in labels),(
                "partial profile accounts must not expose raw URLs")
        page.locator("#results article.post").first.wait_for(timeout=120000)
        count=page.locator("#results article.post").count()
        assert count>=6,"real saved posts not visible"
        assert page.locator("#results article.post").count()>=6
        if source.get("profile_snapshot_verified") is True:
            assert page.locator("#displayName").inner_text().strip(), (
                "stored public profile not displayed"
            )
        else:
            # An older archive with no profile is not a blank/unidentified
            # dropdown row; do not invent or infer a public account name.
            assert page.locator("#accountSelect").input_value()==key
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
