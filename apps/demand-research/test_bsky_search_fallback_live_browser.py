"""Real-browser external provider smoke for source-verified public feed fallback.

Tests source-URL discovery and exact official AppView hydration. Never logs
authors, post text, URIs or media; no accounts are modified or tracked.
No mock results are used for this test.
"""
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT=Path(__file__).resolve().parent
SCRIPT=(ROOT/"bsky_search_fallback.js").read_text(encoding="utf-8")
ORIGIN="https://intersection-originals-free.onrender.com/__fallback_qa__"


def run(engine,name,timeout_ms=65000):
    browser=engine.launch(headless=True)
    try:
        page=browser.new_page(viewport={"width":390 if name=="webkit" else 1200,"height":844})
        # A local synthetic shell on a real same-origin URL; all search and
        # official hydration requests must be actual HTTPS network calls.
        page.route(ORIGIN,lambda route:route.fulfill(status=200,content_type="text/html",
            body="""<!doctype html><html><head><meta charset="utf-8"></head><body>
              <h1>Bluesky public source hydration QA</h1>
              <script>
              window.__fallbackStats=[];
              window.__fallbackAccepted=[];
              window.INTERSECTION_PUBLIC_SEARCH_DOWN="HTTP 500";
              window.INTERSECTION_publicFeedRange=()=>({
                fromMs:Date.now()-30*86400000,
                toMs:Date.now()+86400000,run:1
              });
              window.INTERSECTION_searchFallbackStatus=s=>window.__fallbackStats.push({
                state:s.state,pages:s.pages,verified:s.verified,
                checked:s.checked,providerFailures:s.providerFailures
              });
              window.INTERSECTION_receiveLiveBskyPost=p=>{
                if(!p||!/^at:\/\/did:(plc|web):/.test(String(p.uri||""))||
                    typeof p.record?.text!=="string"||!p.record.text.includes("뒷계")&&
                    !p.record.text.includes("섹트")&&!p.record.text.includes("섹블")&&
                    !p.record.text.includes("일탈계"))return false;
                window.__fallbackAccepted.push(p.uri);
                return true;
              };
              </script></body></html>"""))
        errors=[]
        page.on("pageerror",lambda error:errors.append(type(error).__name__))
        page.goto(ORIGIN,wait_until="domcontentloaded",timeout=20000)
        page.add_script_tag(content=SCRIPT)
        try:
            page.wait_for_function("window.__fallbackAccepted?.length>0",timeout=timeout_ms)
        except PWTimeout:
            stats=page.evaluate("window.__fallbackStats?.slice(-3)||[]")
            raise AssertionError("No source-verified public fallback post in real "+
                                 name+" browser; aggregate statuses: "+json.dumps(stats))
        counts=page.evaluate("""() => ({
          verified:window.__fallbackAccepted.length,
          last:window.__fallbackStats.slice(-1)[0],
          states:window.__fallbackStats.map(s=>s.state)
        })""")
        page.evaluate("window.INTERSECTION_stopSearchFallback?.()")
        assert counts["verified"]>0,counts
        assert not errors,errors
        print("PUBLIC_MARKDOWN_OFFICIAL_HYDRATION_LIVE_PASS",name,
              json.dumps(counts,ensure_ascii=False),flush=True)
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        run(p.chromium,"chromium")
        run(p.webkit,"webkit")
