#!/usr/bin/env python3
"""Actual local Chromium/WebKit gallery-video UX smoke. No fake video-byte success."""
import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

@contextmanager
def serve():
    srv=ThreadingHTTPServer(("127.0.0.1",0),partial(SimpleHTTPRequestHandler,directory=str(ROOT)))
    thread=threading.Thread(target=srv.serve_forever,daemon=True)
    thread.start()
    try:yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:srv.shutdown();thread.join(timeout=3)

def run(browser):
    with serve() as url, sync_playwright() as pw:
        driver=getattr(pw,browser).launch(headless=True)
        ctx=driver.new_context(viewport={"width":390,"height":844},is_mobile=True,
                               has_touch=True,device_scale_factor=3)
        page=ctx.new_page()
        for model in ("yui","mimmi"):
            page.goto(f"{url}/apps/{model}-gallery/videos.html",wait_until="domcontentloaded")
            page.locator("#stats span").first.wait_for(timeout=15000)
            title=page.title()
            assert "동영상" in title,(model,title)
            assert page.locator(".card").count()==(16 if model=="yui" else 3),model
            assert page.locator('nav a[aria-current="page"]').count()==1
            if model=="yui":
                assert page.locator(".preview button").count()==16
                page.locator(".preview button").first.click()
                assert page.locator("#modal").is_visible()
                src=page.locator("#player iframe").get_attribute("src")
                assert src.startswith("https://www.youtube-nocookie.com/embed/eOS8yoH1178"),src
                page.locator("#close").click()
                assert not page.locator("#modal").is_visible()
                assert page.locator("#player iframe").count()==0
                page.locator(".preview button").nth(2).click()
                assert page.locator("#modal").is_visible()
                assert "manpeace.org/data/video/202512/" in page.locator("#player video").get_attribute("src")
                page.locator("#close").click()
                assert page.locator("#player video").count()==0
            else:
                assert page.locator(".preview button").count()==1
                assert "실제 파일 저장 0개" in page.locator("#stats").inner_text()
                page.locator(".preview button").first.click()
                assert page.locator("#modal").is_visible()
                assert "www.instagram.com/reel/DF74hk7zBqf/embed/" in page.locator("#player iframe").get_attribute("src")
                page.locator("#close").click()
                assert page.locator("#player iframe").count()==0
            print("GALLERY_VIDEO_LOCAL_BROWSER_PASS",browser,model)
        ctx.close();driver.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=["chromium","webkit"],default="chromium")
    args=parser.parse_args()
    run(args.browser)
