"""Public deployment smoke test; isolated Chromium, never touches real user records.
Run: python tests/public_smoke.py https://.../ (install playwright + chromium).
This deliberately fails closed when navigation, manifest or expected app selectors fail.
"""
import json, os, sys
from playwright.sync_api import sync_playwright
url=sys.argv[1]
with sync_playwright() as p:
    options={"headless":True}
    if os.path.exists("/usr/bin/chromium"):
        options.update(executable_path="/usr/bin/chromium",args=["--no-sandbox"])
    b=p.chromium.launch(**options)
    print("Chromium",b.version,flush=True)
    c=b.new_context(viewport={"width":1280,"height":800},accept_downloads=True)
    page=c.new_page()
    response=page.goto(url,timeout=12000)
    assert response and response.status==200, "public page must return HTTP 200"
    page.locator("nav").wait_for()
    page.locator("main h1").wait_for()
    assert "Türkçe 120" in page.title()
    data=page.evaluate("""async () => {const r=await fetch('RELEASE_MANIFEST.json',{cache:'no-store'}); if(!r.ok) throw Error(r.status); return r.json()}""")
    published=set(data["publishedDayIds"])
    page.locator('nav [data-tab="course"]').click()
    for day in range(1,8):
        page.locator(f'button[data-day="{day}"]').click()
        visible=page.locator("#quiz").count()>0
        assert visible==(f"D{day:03d}" in published),f"day {day}: manifest/quiz mismatch"
    print(json.dumps({"status":response.status,"title":page.title(),"approved":sorted(published),"render":"pass","first_week_access_gate":"pass"},ensure_ascii=False))
    b.close()
