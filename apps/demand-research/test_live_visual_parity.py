"""Compare ACTUAL public SNS screen pixels against the SAME source account's
owner-only archived viewer at identical browser viewport and device pixel ratio.

Screenshots exist ONLY in process memory; do not upload original/user images
to a public repository, run logs or artifacts. This is a fail-closed acceptance
test, NOT a screenshot mock and NOT a claim of visual fidelity.

No login, raw user text, account key, media, screenshot or auth value is
printed. Dynamic source changes and inaccessible source UI count as UNVERIFIED.
"""
from __future__ import annotations

import io
import json
import math
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import ipaddress
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright, Error as BrowserError

BASE="https://intersection-originals-free.onrender.com"
VIEWPORTS=((390,844),(1280,800))
TIMEOUT_MS=85000
MAX_ACCOUNT_CANDIDATES=5


def owner_get(path,timeout=90):
    req=Request(BASE+path,headers={
        "Accept":"application/json",
        "User-Agent":"intersection-private-pixel-parity-gate/1.0"})
    with urlopen(req,timeout=timeout) as response:
        if response.status!=200:
            raise RuntimeError("archived original API did not return 200")
        return json.loads(response.read(4_000_000))


def choose_provider_accounts():
    index=owner_get("/api/account-archives",timeout=150)
    rows=index.get("accounts") or []
    selected={}
    for provider in ("bluesky","mastodon"):
        possible=[row for row in rows if (
            isinstance(row,dict) and row.get("platform")==provider
            and str(row.get("key","")).startswith(provider+"-"))]
        for row in possible[:MAX_ACCOUNT_CANDIDATES]:
            try:
                profile=owner_get("/api/account-archives/"+row["key"]+"/profile",
                                  timeout=120)
            except (HTTPError,URLError,TimeoutError,ValueError,RuntimeError):
                continue
            source=profile.get("profile_url") or row.get("profile_url")
            # Do not permit an archive API to point the browser at internal
            # hosts. Mastodon HTTPS source was independently checked by
            # source registration; never accept non-HTTPS.
            if (profile.get("available") is not True or
                    not isinstance(source,str) or len(source)>600 or
                    not profile.get("handle")):
                continue
            try:
                parsed=urlsplit(source)
                host=parsed.hostname or ""
                if (parsed.scheme!="https" or parsed.port not in (None,443)
                        or parsed.username or parsed.password or parsed.fragment):
                    continue
                if provider=="bluesky":
                    if host!="bsky.app" or not parsed.path.startswith("/profile/"):
                        continue
                else:
                    identity=str(profile.get("identity") or "")
                    expected_host=identity.rsplit(":",1)[0]
                    if host!=expected_host or not host or host.endswith(
                            (".local",".internal",".localhost")):
                        continue
                try:
                    ipaddress.ip_address(host)
                    continue
                except ValueError:
                    pass
            except ValueError:
                continue
            selected[provider]=(row["key"],source,profile)
            break
    return selected


def capture(page,url,selector=None):
    response=page.goto(url,wait_until="domcontentloaded",timeout=TIMEOUT_MS)
    if response is None or response.status>=400:
        raise RuntimeError("reference or archived page HTTP error")
    if selector:
        page.locator(selector).wait_for(state="visible",timeout=TIMEOUT_MS)
    page.wait_for_timeout(1200)
    page.evaluate("window.scrollTo(0,0)")
    return page.screenshot(full_page=False,animations="disabled",timeout=TIMEOUT_MS)


def diff_pixels(source_bytes,archive_bytes):
    reference=Image.open(io.BytesIO(source_bytes)).convert("RGB")
    candidate=Image.open(io.BytesIO(archive_bytes)).convert("RGB")
    if reference.size!=candidate.size:
        raise ValueError("reference and candidate pixel dimensions disagree")
    absolute=ImageChops.difference(reference,candidate)
    hist=absolute.convert("L").histogram()
    equal=hist[0]
    n=reference.width*reference.height
    mae=sum(ImageStat.Stat(absolute).mean)/3
    return {"equal_pixel_percent":round(100.0*equal/n,5),
            "mismatch_pixel_percent":round(100.0*(n-equal)/n,5),
            "rgb_mae":round(mae,5),
            "exactly_identical":equal==n,
            "pixels":n}


def measure_source_geometry(page,profile):
    """Keep public source pixels private; log only dimensionless UI geometry."""
    return page.evaluate("""(identity) => {
      const dims=el=>{
        const r=el.getBoundingClientRect();
        return {x:Math.round(r.x),y:Math.round(r.y),
                w:Math.round(r.width),h:Math.round(r.height)};
      };
      const visible=el=>{
        const r=el.getBoundingClientRect();
        return r.width>0 && r.height>0 && r.bottom>0 &&
               r.top<window.innerHeight;
      };
      const host=identity.handle.replace(/^@/, "").toLowerCase();
      const name=identity.name.toLowerCase();
      const textNodes=[...document.querySelectorAll('span,div,h1,h2,h3')].slice(0,18000)
        .filter(el=>el.children.length===0 && visible(el));
      const byText=(needle)=>textNodes
        .filter(el=>(el.textContent||'').trim().toLowerCase()===needle)
        .slice(0,8).map(dims);
      const imageRects=[...document.querySelectorAll('img')].slice(0,1000)
        .filter(el=>visible(el)).map(el=>({...dims(el)}));
      const candidates=[...document.querySelectorAll('*')].slice(0,12000)
        .filter(el=> {
          const r=el.getBoundingClientRect();
          return r.width>=250 && r.height>=65 && r.height<=250 &&
                 r.top>=0 && r.top<500;
        })
        .filter(el=>getComputedStyle(el).backgroundImage!=='none')
        .slice(0,8).map(dims);
      const tabs=[...document.querySelectorAll('[role=tab]')].slice(0,12)
        .filter(visible).map(dims);
      return {handle:byText(host).slice(0,3),
              name:byText(name).slice(0,3),
              profileImages:imageRects.filter(r=>r.w>=50&&r.h>=50&&
                 r.w<=180&&r.h<=180&&r.y<500).slice(0,6),
              wideImages:imageRects.filter(r=>r.w>=250&&r.h>=65&&
                 r.h<=300&&r.y<500).slice(0,6),
              coverBackgrounds:candidates,
              tabs:tabs.slice(0,8)};
    }""",{"handle":str(profile.get("handle") or ""),
            "name":str(profile.get("display_name") or "")})


def per_band_errors(source_bytes,archive_bytes):
    source=Image.open(io.BytesIO(source_bytes)).convert("RGB")
    archived=Image.open(io.BytesIO(archive_bytes)).convert("RGB")
    rows=[]
    for top in range(0,min(source.height,archived.height),100):
        bottom=min(source.height,archived.height,top+100)
        lhs=io.BytesIO();rhs=io.BytesIO()
        source.crop((0,top,source.width,bottom)).save(lhs,format="PNG")
        archived.crop((0,top,archived.width,bottom)).save(rhs,format="PNG")
        mismatch=diff_pixels(lhs.getvalue(),rhs.getvalue())
        rows.append({"top":top,"bottom":bottom,
                     "exact_percent":mismatch["equal_pixel_percent"],
                     "rgb_mae":mismatch["rgb_mae"]})
    return rows


def compare_one(browser,provider,key,source_url,profile,width,height):
    context=browser.new_context(
        viewport={"width":width,"height":height},device_scale_factor=1,
        locale="ko-KR",reduced_motion="reduce",
        color_scheme="dark" if provider=="mastodon" else "light",
        is_mobile=width<600,has_touch=width<600)
    try:
        source=context.new_page()
        reference_bytes=capture(source,source_url)
        visible=(source.locator("body").inner_text(timeout=12000) or "").lower()
        handle=str(profile.get("handle") or "").lower().lstrip("@")
        # An error splash or login page is not a valid pixel reference.
        if not handle or handle not in visible:
            return {"status":"SOURCE_NOT_COMPARABLE"}
        source_boxes=measure_source_geometry(source,profile)
        archived=context.new_page()
        candidate_url=BASE+"/account-archive?embedded=1&account="+key
        candidate_bytes=capture(archived,candidate_url,selector="#displayName")
        archived.wait_for_function(
            "() => {const name=document.getElementById('displayName')?.textContent||'';"
            "return name && !name.includes('불러오는') &&"
            " !name.includes('미확인') && !name.includes('선택하세요');}",
            timeout=TIMEOUT_MS)
        archived.wait_for_timeout(1200)
        candidate_bytes=archived.screenshot(full_page=False,animations="disabled")
        body=(archived.locator("#handle").inner_text(timeout=12000) or "").lower()
        if handle not in body:
            return {"status":"ARCHIVED_SOURCE_IDENTITY_NOT_MATCHED"}
        metrics=diff_pixels(reference_bytes,candidate_bytes)
        metrics["source_geometry"]=source_boxes
        metrics["vertical_error_bands"]=per_band_errors(reference_bytes,candidate_bytes)
        metrics["status"]="PIXEL_IDENTICAL" if metrics["exactly_identical"] else "PIXEL_DIFFERENT"
        # Expected source geometry varies by actual provider version.
        # Record only the archive-side measured bounding boxes, no text.
        metrics["archive_geometry"]={}
        for label,selector in (("banner","#cover"),("avatar","#avatar"),
                               ("name","#displayName"),("bio","#biography"),
                               ("tabs",".tabs")):
            box=archived.locator(selector).bounding_box()
            if box:
                metrics["archive_geometry"][label]={
                    "x":round(box["x"],1),"y":round(box["y"],1),
                    "w":round(box["width"],1),"h":round(box["height"],1)}
        return metrics
    except (BrowserError,HTTPError,URLError,RuntimeError,TimeoutError,ValueError):
        return {"status":"REFERENCE_OR_VIEWER_NOT_VERIFIED"}
    finally:
        context.close()


def main():
    status={"comparison_type":"actual_source_vs_owner_verified_archive",
            "same_account_required":True,"screenshots_persisted":False,
            "pass_condition":"100% exact pixel equality AND both providers verified",
            "results":[]}
    try:
        selected=choose_provider_accounts()
    except (HTTPError,URLError,TimeoutError,ValueError,RuntimeError):
        print("PIXEL_PARITY_RESULT "+json.dumps({
            **status,"overall":"UNVERIFIED_ARCHIVE_INVENTORY"},sort_keys=True))
        return 2
    with sync_playwright() as playwright:
        for provider in ("bluesky","mastodon"):
            if provider not in selected:
                status["results"].append({"provider":provider,
                    "status":"NO_VERIFIED_ACCOUNT_REFERENCE"})
                continue
            key,source_url,profile=selected[provider]
            for engine in ("chromium","webkit"):
                browser=getattr(playwright,engine).launch(headless=True)
                try:
                    for width,height in VIEWPORTS:
                        metrics=compare_one(browser,provider,key,source_url,
                                            profile,width,height)
                        status["results"].append({"provider":provider,
                            "browser":engine,"viewport":str(width)+"x"+str(height),
                            **metrics})
                finally:
                    browser.close()
    passed=(len(status["results"])==8 and all(
        row.get("status")=="PIXEL_IDENTICAL" for row in status["results"]))
    status["overall"]="VERIFIED_PIXEL_IDENTICAL" if passed else "NOT_PIXEL_IDENTICAL"
    print("PIXEL_PARITY_RESULT "+json.dumps(
        status,ensure_ascii=False,sort_keys=True))
    # A browser smoke test is not a pixel-parity test: strict by design.
    return 0 if passed else 1


if __name__=="__main__":
    raise SystemExit(main())
