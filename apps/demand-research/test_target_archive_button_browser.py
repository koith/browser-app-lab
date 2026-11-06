"""Desktop Chromium + mobile WebKit QA of the actual backup button.

Tests both modes without external account credentials:
public Pages probes the dedicated private gateway only on a backup click and
falls back to the existing GitHub workflow when it is offline. Private gateway
submits a same-origin queued request. No backup is claimed
complete unless remotely verified by the separate operator workflow.
"""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
SOURCE=(ROOT/"index.html").read_text(encoding="utf-8")
start=SOURCE.index('<section id="targetArchivePanel"')
end=SOURCE.index("</section>",start)+len("</section>")
HTML=('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<script src="target_archive_client.js" defer></script></head><body>'+
      SOURCE[start:end]+'</body></html>')
PAGE="https://koith.github.io/browser-app-lab/apps/demand-research/"
PRIVATE="https://intersection-originals-free.onrender.com/"


def verify(browser_type,kind,width,height):
    browser=browser_type.launch(headless=True)
    try:
        for private,backend_available in ((False,False),(False,True),(True,True)):
            page=browser.new_page(viewport={"width":width,"height":height})
            errors=[]
            status_queries=[]
            health_queries=[]
            dispatched=[]
            job_reads=[]
            clipboard_events=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.on("console",lambda entry:clipboard_events.append(entry.text) if entry.text.startswith("QA_COPIED:") else None)
            page.add_init_script("""
window.__qaCopied=[];
Object.defineProperty(navigator,"clipboard",{
  configurable:true,value:{writeText:(value)=>{
    window.__qaCopied.push(value);
    console.log("QA_COPIED:"+value);
    return Promise.resolve();
  }}
});
""")
            def route_it(route):
                from urllib.parse import urlsplit
                parsed=urlsplit(route.request.url)
                path=parsed.path
                if path=="/browser-app-lab/apps/demand-research/" or (
                    parsed.hostname=="intersection-originals-free.onrender.com" and path=="/"):
                    route.fulfill(status=200,content_type="text/html; charset=utf-8",body=HTML)
                elif (parsed.hostname=="github.com" and
                      path=="/koith/browser-app-lab/actions/workflows/intersection-target-account-bundle.yml"):
                    route.fulfill(status=200,content_type="text/html",
                                  body='<html><body><p id="workflow-reached">Owner workflow</p></body></html>')
                elif parsed.hostname=="intersection-originals-free.onrender.com" and path=="/ready":
                    health_queries.append(1)
                    if backend_available:
                        route.fulfill(status=200,content_type="application/json",
                                      headers={"Access-Control-Allow-Origin":"https://koith.github.io"},
                                      body='{"ready":true}')
                    else:
                        route.fulfill(status=404,content_type="application/json",
                                      headers={"Access-Control-Allow-Origin":"https://koith.github.io"},
                                      body='{"error":"not deployed"}')
                elif path.endswith("/target_archive_client.js"):
                    route.fulfill(status=200,content_type="text/javascript",
                                  body=(ROOT/"target_archive_client.js").read_text("utf-8"))
                elif path=="/api/target-archive/status":
                    status_queries.append(1)
                    if private:
                        route.fulfill(status=200,content_type="application/json",
                                      body=json.dumps({"enabled":True}))
                    else:
                        route.fulfill(status=404,content_type="application/json",
                                      body='{"error":"not on static Pages"}')
                elif path=="/api/target-archive/start":
                    dispatched.append({
                        "payload":route.request.post_data_json,
                        "intent":route.request.headers.get("x-archive-intent")
                    })
                    route.fulfill(status=202,content_type="application/json",
                                  body=json.dumps({"accepted":True,"state":"QUEUED_NOT_VERIFIED",
                                                   "run_id":41999000001,
                                                   "receipt":"synthetic-signed-receipt-for-browser-QA"}))
                elif path.startswith("/api/target-archive/jobs/41999000001"):
                    job_reads.append(route.request.url)
                    route.fulfill(status=200,content_type="application/json",
                                  body=json.dumps({"run_id":41999000001,
                                    "state":"REMOTE_VERIFIED","remote_verified":True,
                                    "posts":6,"objects":42,
                                    "account_key":"bluesky-"+"a"*40}))
                elif path=="/api/account-archives":
                    route.fulfill(status=200,content_type="application/json",
                                  body=json.dumps({"accounts":[{
                                    "key":"bluesky-"+"a"*40,"platform":"bluesky",
                                    "profile_url":"https://bsky.app/profile/qa-example.bsky.social",
                                    "backup_kind":"terabox_zip_sha_verified",
                                    "posts_verified_in_bundle":6}]}))
                else:
                    route.abort()
            page.route("**/*",route_it)
            response=page.goto(PRIVATE if private else PAGE,
                               wait_until="domcontentloaded",timeout=30000)
            assert response and response.status==200
            page.wait_for_function("""() => {
              const status=document.getElementById("targetArchiveStatus").textContent;
              return status.includes("계정을 지정하고")||
                     status.includes("연결됨 · 계정 주소");
            }""")
            assert len(status_queries)==1
            assert not health_queries,"page load must not wake a sleeping Render server"
            button=page.locator("#targetArchiveSubmit")
            assert button.is_enabled(),"empty account must still allow helpful feedback"
            button.click()
            assert "먼저 공개 SNS 계정" in page.locator("#targetArchiveStatus").inner_text()
            assert page.locator("#targetArchiveAccount").evaluate("(el)=>document.activeElement===el")
            assert page.locator("#targetArchiveAccount").get_attribute("aria-invalid")=="true"
            page.locator("#targetArchiveAccount").fill("javascript:untrusted")
            button.click()
            assert page.locator("#targetArchiveAccount").get_attribute("aria-invalid")=="true"
            assert not dispatched,"invalid account must never schedule a backup"
            page.locator("#targetArchiveAccount").fill(
                "https://bsky.app/profile/qa-example.bsky.social")
            assert button.is_enabled(),"valid public account must enable button"
            if private:
                assert button.inner_text()=="테라박스 백업 시작"
                button.click()
                page.locator("#targetArchiveJobStatus[data-state=verified]").wait_for(
                    state="visible",timeout=15000)
                assert dispatched==[{
                    "payload":{"platform":"bluesky","account":
                               "https://bsky.app/profile/qa-example.bsky.social"},
                    "intent":"selected-public-account-v1"
                }]
                assert "게시글 6건" in page.locator("#targetArchiveJobStatus").inner_text()
                assert page.locator("#targetArchiveAccount").input_value()==(
                    "https://bsky.app/profile/qa-example.bsky.social")
                assert len(job_reads)>=1
                assert "receipt=synthetic-signed-receipt" in job_reads[0]
                page.locator("#targetArchiveLibrary").wait_for(
                    state="visible",timeout=10000)
                saved=page.locator("#targetArchiveLibraryRows a").first
                assert saved.get_attribute("href")==(
                    "?tab=archives&account=bluesky-"+"a"*40)
                assert button.is_enabled(),"verified backup should not lock the button"
            else:
                assert button.inner_text()=="백업 시작"
                page.locator("#targetArchivePlatform").select_option("mastodon")
                page.locator("#targetArchiveAccount").fill("qa@example.social")
                assert button.is_enabled()
                page.locator("#targetArchiveAccount").fill("qa@localhost")
                button.click()
                assert "먼저 공개 SNS 계정" in page.locator("#targetArchiveStatus").inner_text()
                assert not dispatched
                page.locator("#targetArchivePlatform").select_option("bluesky")
                page.locator("#targetArchiveAccount").fill(
                    "https://bsky.app/profile/qa-example.bsky.social")
                button.click()
                if backend_available:
                    page.wait_for_url(lambda url:url.startswith(PRIVATE),timeout=12000)
                    assert not dispatched,"cross-origin navigation must not schedule a backup"
                    page.locator("#targetArchiveAccount").wait_for(state="visible")
                    assert page.locator("#targetArchiveAccount").input_value()==(
                        "https://bsky.app/profile/qa-example.bsky.social")
                    assert page.locator("#targetArchiveSubmit").inner_text()=="인증 후 백업 시작"
                    assert "archive_account" not in page.url,"account URL must be cleared once restored"
                else:
                    page.wait_for_url(
                        "https://github.com/koith/browser-app-lab/actions/workflows/"
                        "intersection-target-account-bundle.yml",timeout=12000)
                    assert page.locator("#workflow-reached").is_visible()
                    assert not dispatched,"fallback must not claim a queued backup"
                assert len(health_queries)==1,"one availability probe per click"
            assert not errors,errors
            assert page.evaluate(
                "document.documentElement.scrollWidth<=window.innerWidth+2")
            print("TARGET_BACKUP_BUTTON_BROWSER_PASS",kind,
                  "private" if private else ("public_ready" if backend_available else "public_fallback"),
                  "valid_control_and_dispatch=YES")
            page.close()
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        verify(p.chromium,"desktop-chromium",1200,800)
        verify(p.webkit,"mobile-webkit",390,844)
