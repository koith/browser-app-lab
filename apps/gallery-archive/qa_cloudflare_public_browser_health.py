"""Read-only real-browser probe of the already-created public Worker; no secrets."""
import argparse
import asyncio
import json
from playwright.async_api import async_playwright

URL = "https://gallery-archive-free.gallery-9f7d03138f3f.workers.dev/api/v1/health"

async def verify(engine):
    async with async_playwright() as pw:
        browser = await getattr(pw, engine).launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            response = await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            status = response.status if response else 0
            ctype = response.headers.get("content-type", "") if response else ""
            if status != 200:
                print("GALLERY_REAL_WORKER_BROWSER_HEALTH", engine,
                      "http", status, "content_type",
                      "JSON" if "json" in ctype else "HTML" if "html" in ctype else "OTHER",
                      flush=True)
                raise AssertionError("REAL_WORKER_NOT_HEALTHY_IN_" + engine.upper())
            body = await response.json()
            if (not isinstance(body, dict) or
                body.get("transport") != "cloudflare-bound-assets" or
                not isinstance(body.get("source_commit"), str) or
                len(body["source_commit"]) != 40):
                raise AssertionError("WORKER_HEALTH_SCHEMA_MISMATCH")
            print("GALLERY_REAL_WORKER_BROWSER_HEALTH", engine,
                  "http", status, "expected_transport", True, flush=True)
        finally:
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("webkit", "chromium"), required=True)
    options = parser.parse_args()
    asyncio.run(verify(options.browser))
