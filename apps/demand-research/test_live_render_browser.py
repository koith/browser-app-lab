"""Read-only LIVE deployed Render smoke in real Chromium and mobile WebKit.

No private session, no account backup dispatch, no raw archived data.
"""
from playwright.sync_api import sync_playwright

BASE="https://intersection-originals-free.onrender.com/"

def exercise(browser,label):
    context=browser.new_context(viewport=(
        {"width":390,"height":844} if "webkit" in label else
        {"width":1200,"height":800}))
    page=context.new_page()
    errors=[]
    page.on("pageerror",lambda exc: errors.append(str(exc)))
    # First-time account-watch transfer redirects to GitHub Pages; skip the
    # migration attempt for this disposable synthetic browser only.
    page.add_init_script("""(() => {
      try {sessionStorage.setItem('intersection:watch-origin-migration-attempted:v1','1');}
      catch(e) {}
    })()""")
    try:
        page.goto(BASE+"?liveqa=20261111",wait_until="domcontentloaded",
                  timeout=85000)
        page.locator("#viewPosts").wait_for(state="visible",timeout=30000)
        assert page.title()=="INTERSECTION",page.title()
        assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
        assert page.locator("#postsView").is_visible()
        page.locator("#viewArchives").click()
        assert page.locator("#archivesView").is_visible()
        assert page.locator("#viewArchives").get_attribute("aria-selected")=="true"
        assert page.locator("#archiveModeAuto").inner_text()=="해시태그 자동 백업"
        assert page.locator("#archiveModeAccounts").inner_text()=="지정 계정 전체 기록"
        page.locator("#archiveModeAccounts").click()
        assert page.locator("#archiveAccountPicker").is_visible()
        assert page.locator("#archiveQuickSearch").is_visible()
        # Reload with ?tab=archives still in address MUST restore first tab.
        assert "tab=archives" in page.url,page.url
        page.reload(wait_until="domcontentloaded",timeout=85000)
        assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
        assert page.locator("#postsView").is_visible()
        assert page.locator("#archivesView").is_hidden()
        assert "tab=archives" not in page.url,page.url
        # New direct navigation is deliberately different from reload.
        page.goto(BASE+"?tab=archives&mode=auto",wait_until="domcontentloaded",
                  timeout=85000)
        assert page.locator("#viewArchives").get_attribute("aria-selected")=="true"
        assert page.locator("#archiveModeAuto").get_attribute("aria-selected")=="true"
        worker=page.request.get(BASE+"intersection-sw.js",timeout=35000)
        assert worker.status==200,worker.status
        # A rolling immutable shell version changes on each deployment.
        # Validate a versioned, public-only worker, not a stale release date.
        worker_source=worker.text()
        assert 'const PREFIX="intersection-public-shell-v1-";' in worker_source
        assert 'const VERSION="intersection-public-shell-v1-' in worker_source
        assert "const SCRIPT_PATHS=new Set(" in worker_source
        health=page.request.get(BASE+"health",timeout=35000)
        assert health.status==200 and health.json().get("alive") is True
        if "chromium" in label:
            # Reproduce the important user scenario: a previously opened
            # browser must show INTERSECTION's public app shell when the
            # sleeping free backend cannot answer a page refresh.
            installed=page.evaluate("""async () => {
                if (!('serviceWorker' in navigator)) return false;
                const worker=await navigator.serviceWorker.ready;
                return Boolean(worker.active);
            }""")
            assert installed,"live public-shell service worker never activated"
            context.set_offline(True)
            try:
                page.reload(wait_until="domcontentloaded",timeout=35000)
                assert page.title()=="INTERSECTION"
                assert page.locator("#viewPosts").is_visible()
                assert page.locator("#viewPosts").get_attribute("aria-selected")=="true"
                print("LIVE_RENDER_CACHED_SHELL_OFFLINE_PASS",label,
                      "offline_reload=posts","render_placeholder=no",flush=True)
            finally:
                context.set_offline(False)
        # Source hosts can reject browser CORS requests without breaking UI.
        # Report those separately, but require no local JavaScript crashes.
        blocked=[e for e in errors if "due to access control checks" in e]
        fatal=[e for e in errors if "due to access control checks" not in e]
        assert not fatal,fatal
        # Archive-overview once spawned an expensive remote root listing and
        # crashed the 512MiB instance tens of seconds after navigating.
        if "webkit" in label:
            page.wait_for_timeout(42000)
            subsequent=page.request.get(BASE+"health",timeout=35000)
            print("LIVE_RENDER_WEBKIT_POSTLOAD_HEALTH",subsequent.status,flush=True)
            assert subsequent.status==200 and subsequent.json().get("alive") is True
            accounts=page.request.get(BASE+"api/accounts/status",timeout=35000)
            assert accounts.status==200,accounts.status
        print("LIVE_INTERSECTION_RENDER_BROWSER_PASS",label,
              "reload_first_tab=yes","deep_link=yes","two_modes=yes",
              "worker_http_200=yes","health=yes",
              "external_access_denials="+str(len(blocked)),flush=True)
    finally:
        context.close()

if __name__=="__main__":
    with sync_playwright() as p:
        exercise(p.chromium.launch(headless=True),"chromium_desktop")
        exercise(p.webkit.launch(headless=True),"webkit_mobile")
