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
            photo_url=f"{url}/apps/{model}-gallery/"
            video_url=photo_url+"videos.html"
            page.goto(photo_url,wait_until="domcontentloaded")
            toggle=page.locator(".logo .mode-toggle")
            assert toggle.count()==1,(model,"photo toggle missing")
            assert toggle.inner_text()=="GALLERY"
            assert toggle.get_attribute("href")=="videos.html"
            assert page.locator('.mainnav a[href="videos.html"]').count()==0
            toggle.click()
            page.wait_for_url(video_url,timeout=15000)
            page.locator("#stats span").first.wait_for(timeout=15000)
            assert page.locator(".mode-toggle").inner_text()=="MOVIE"
            assert page.locator(".mode-toggle").get_attribute("href")=="./"
            assert page.locator(".card").count()==(1 if model=="yui" else 2)
            assert page.locator(".preview button").count()==0,"source-only cannot fake playable videos"
            assert "실제 파일 저장 0개" in page.locator("#stats").inner_text()
            assert page.locator("#player iframe").count()==0,"unrequested YouTube embed"
            page.locator(".mode-toggle").click()
            page.wait_for_url(photo_url,timeout=15000)
            assert page.locator(".mode-toggle").inner_text()=="GALLERY"
            print("GALLERY_MODE_TOGGLE_LOCAL_BROWSER_PASS",browser,model)
        ctx.close();driver.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=["chromium","webkit"],default="chromium")
    args=parser.parse_args()
    run(args.browser)
