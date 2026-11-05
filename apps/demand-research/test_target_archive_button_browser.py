"""Desktop Chromium + mobile WebKit QA of the actual backup button.

Tests both real modes without external accounts or GitHub credentials:
public Pages opens the owner-authenticated workflow for manual dispatch, and
private gateway submits a same-origin queued request. No backup is claimed
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


def verify(browser_type,kind,width,height):
    browser=browser_type.launch(headless=True)
    try:
        for private in (False,True):
            page=browser.new_page(viewport={"width":width,"height":height})
            errors=[]
            status_queries=[]
            dispatched=[]
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
                if (parsed.hostname=="github.com" and
                    path=="/koith/browser-app-lab/actions/workflows/intersection-target-account-bundle.yml"):
                    route.fulfill(status=200,content_type="text/html",
                                  body='<html><body><p id="workflow-reached">Owner workflow</p></body></html>')
                elif path=="/browser-app-lab/apps/demand-research/":
                    route.fulfill(status=200,content_type="text/html; charset=utf-8",
                                  body=HTML)
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
                                  body='{"accepted":true,"state":"QUEUED_NOT_VERIFIED"}')
                else:
                    route.abort()
            page.route("**/*",route_it)
            response=page.goto(PAGE,wait_until="domcontentloaded",timeout=30000)
            assert response and response.status==200
            page.wait_for_function("""() => {
              const status=document.getElementById("targetArchiveStatus").textContent;
              return status.includes("공개 페이지")||
                     status.includes("개인용 보관 서버 연결됨");
            }""")
            assert len(status_queries)==1
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
                page.wait_for_function(
                    """() => document.getElementById("targetArchiveStatus").textContent.includes("대기 중")""")
                assert dispatched==[{
                    "payload":{"platform":"bluesky","account":
                               "https://bsky.app/profile/qa-example.bsky.social"},
                    "intent":"selected-public-account-v1"
                }]
                assert "원격 저장 성공은 아직 확인되지" in page.locator(
                    "#targetArchiveStatus").inner_text()
                assert page.locator("#targetArchiveAccount").input_value()==""
                assert button.is_enabled(),"cleared account should explain missing input"
                button.click()
                assert "먼저 공개 SNS 계정" in page.locator("#targetArchiveStatus").inner_text()
            else:
                assert button.inner_text()=="GitHub에서 백업 실행"
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
                page.wait_for_url(
                    "https://github.com/koith/browser-app-lab/actions/workflows/"
                    "intersection-target-account-bundle.yml",timeout=12000)
                assert page.locator("#workflow-reached").is_visible()
                assert clipboard_events==[
                    "QA_COPIED:https://bsky.app/profile/qa-example.bsky.social"]
                assert not dispatched,"public Pages must not falsely claim queued work"
            assert not errors,errors
            assert page.evaluate(
                "document.documentElement.scrollWidth<=window.innerWidth+2")
            print("TARGET_BACKUP_BUTTON_BROWSER_PASS",kind,
                  "private" if private else "public_pages",
                  "valid_control_and_dispatch=YES")
            page.close()
    finally:
        browser.close()


if __name__=="__main__":
    with sync_playwright() as p:
        verify(p.chromium,"desktop-chromium",1200,800)
        verify(p.webkit,"mobile-webkit",390,844)
