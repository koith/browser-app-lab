#!/usr/bin/env python3
"""A real deployed Pages first-paint test with the Render gateway DISABLED.

The gallery must show its complete physically saved album catalog (not the
misleading 10-photo public-only samples) without needing an API cold start.
This tests saved photo *metadata*, NOT original media binary delivery; the
regular deployed-browser QA independently opens real thumbnails and originals.
"""
from __future__ import annotations
import argparse
import json
from playwright.sync_api import sync_playwright

BASE = "https://koith.github.io/browser-app-lab/apps"
MODELS = {
  "yui": {"owner": 2999,"minimum_visible":2999,"min_albums":30,
          "checks": [("teddy-bear97",97),("athletic-club104",104)]},
  "mimmi": {"owner":3168,"minimum_visible":3150,"min_albums":65,
            "checks":[("v2ph-actor-a8856noa",91),
                      ("v2ph-azur-lane-tashkent",59),
                      ("djawa-rudy2-codename-wolfgirl-9b4e68",201),
                      ("djawa-nikke-alice",170),
                      ("djawa-your-fishe-gawr-gura",123)]},
}

def inspect(browser,model,spec):
    ctx=browser.new_context(viewport={"width":390,"height":844},
                            is_mobile=True,has_touch=True,locale="ko-KR")
    page=ctx.new_page()
    page.route("**/*onrender.com/**",lambda route:route.abort("blockedbyclient"))
    try:
        for round in range(2):
            response=page.goto(f"{BASE}/{model}-gallery/",wait_until="domcontentloaded",timeout=45000)
            assert response.status==200,response.status
            assert page.url.startswith(f"{BASE}/{model}-gallery/")
            page.wait_for_function("""([expected,minimum])=>{
                if(typeof stored==='undefined'||!Array.isArray(stored))return false;
                const owner=stored.reduce((n,a)=>n+(a.images||[]).filter(p=>p.ownerAlbum).length,0);
                const all=stored.reduce((n,a)=>n+(a.images||[]).length,0);
                return owner>=expected && all>=minimum;
            }""",arg=[spec["owner"],spec["minimum_visible"]],timeout=45000)
            info=page.evaluate("""()=>({
               albums:stored.length,
               visible:stored.reduce((n,a)=>n+(a.images||[]).length,0),
               owner:stored.reduce((n,a)=>n+(a.images||[]).filter(p=>p.ownerAlbum).length,0),
               perAlbum:Object.fromEntries(stored.map(a=>[a.id,(a.images||[]).length])),
               inventory:document.querySelector('#inventory')?.textContent,
            })""")
            assert info["albums"]>=spec["min_albums"],(model,info["albums"])
            assert "실제 저장본" in info["inventory"],(model,info["inventory"])
            for aid,minimum in spec["checks"]:
                assert info["perAlbum"].get(aid,0)>=minimum,(model,aid,info["perAlbum"].get(aid,0))
            assert page.locator("#albumgrid .album").count()>=spec["min_albums"]
            print("COMPLETE_GALLERY_INDEX_IMMEDIATE_WITHOUT_RENDER_PASS",
                  json.dumps({"model":model,"round":round+1,
                              "album_count":info["albums"],
                              "indexed_real_photos":info["visible"],
                              "private_sha_verified_photos":info["owner"],
                              "expected_complete_works":spec["checks"]},
                             ensure_ascii=False),flush=True)
        return True
    finally:
        ctx.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--browser",choices=("chromium","webkit"),default="chromium")
    a=p.parse_args()
    with sync_playwright() as playwright:
        b=getattr(playwright,a.browser).launch(headless=True)
        try:
            for model,spec in MODELS.items():
                inspect(b,model,spec)
        finally:
            b.close()
    print("BOTH_YUI_MIMMI_FULL_FIRST_PAINT_GALLERIES_PASS",a.browser,flush=True)

if __name__=="__main__":
    main()
