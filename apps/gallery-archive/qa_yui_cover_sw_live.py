#!/usr/bin/env python3
"""Live Pages registration check. Does not certify upstream image availability."""
import argparse, json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL="https://koith.github.io/browser-app-lab/apps/yui-gallery/"
PATH="/browser-app-lab/apps/yui-gallery/"
def run(browser):
    ctx=browser.new_context(viewport={"width":390,"height":844},
        is_mobile=True,has_touch=True,service_workers="allow")
    page=ctx.new_page()
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)[:160]))
    try:
        response=page.goto(URL,wait_until="domcontentloaded",timeout=60000)
        assert response and response.status==200
        # navigator.serviceWorker.ready resolves only after an active worker exists.
        # Do NOT use an async function in wait_for_function: the Promise itself
        # can be truthy before resolving to false, yielding a bogus false handle.
        data=page.evaluate("""async () => {
          if(!navigator.serviceWorker)throw new Error('Service worker unavailable');
          const registration=await Promise.race([
            navigator.serviceWorker.ready,
            new Promise((_,reject)=>setTimeout(
              ()=>reject(new Error('Timed out awaiting active service worker')),45000))
          ]);
          return {scope:registration.scope,script:registration.active?.scriptURL||null};
        }""")
        assert data["script"],("missing active script",data)
        assert urlparse(data["scope"]).path==PATH,data
        assert urlparse(data["script"]).path==PATH+"gallery-cover-sw.js",data
        page.reload(wait_until="domcontentloaded",timeout=60000)
        page.wait_for_function("() => !!navigator.serviceWorker?.controller",timeout=40000)
        control=page.evaluate("() => navigator.serviceWorker.controller.scriptURL")
        assert urlparse(control).path==PATH+"gallery-cover-sw.js",control
        assert not errors,errors
        print("YUI_LIVE_PAGES_COVER_CACHE_SCOPE_PASS",json.dumps({
          "browser":browser.browser_type.name,"controlled_after_reload":True,
          "cached_provider_403_as_photo":False,"provider_originals_repaired":False}),flush=True)
    finally:
        ctx.close()
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--browser",choices=["chromium","webkit"],required=True)
    args=ap.parse_args()
    with sync_playwright() as p:
        browser=getattr(p,args.browser).launch(headless=True)
        try:run(browser)
        finally:browser.close()
