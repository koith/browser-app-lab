#!/usr/bin/env python3
"""Pre-deploy actual WebKit/Chromium Service Worker photo-cache 200->503 test.

Serve the candidate worker at localhost with an independent CORS gateway.
This never opens or copies private photographs; test fixture is synthetic.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
IMAGE = io.BytesIO()
Image.new("RGB", (48, 64), color=(30, 76, 112)).save(IMAGE, format="PNG")
PIXELS = IMAGE.getvalue()
SHA = hashlib.sha256(PIXELS).hexdigest()
GALLERY = "http://127.0.0.1:8765"
GATEWAY = "http://127.0.0.1:8766"
PRODUCTION = "https://mimmi-private-gallery-free.onrender.com"


def make_server(kind: str, model: str, state: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if kind == "gallery":
                if self.path == "/apps/" + model + "-gallery/":
                    body = b"<!doctype html><meta charset=utf-8><title>Owner device cache acceptance</title><body></body>"
                    mime = "text/html"
                elif self.path == "/apps/" + model + "-gallery/gallery-cover-sw.js":
                    source = (ROOT / ("apps/" + model + "-gallery/gallery-cover-sw.js")).read_text()
                    assert source.count(PRODUCTION) == 1
                    body = source.replace(PRODUCTION, GATEWAY).encode()
                    mime = "text/javascript"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            state["requests"] += 1
            if (self.path != ("/api/" + ("yui/" if model == "yui" else "") +
                    "media/known-album/1/original?v=" + SHA)):
                self.send_error(404)
                return
            status = 503 if state["offline"] else 200
            body = b'{"detail":"provider_denial"}' if state["offline"] else PIXELS
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", GALLERY)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "application/json" if state["offline"] else "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", choices=("chromium", "webkit"), required=True)
    ap.add_argument("--model", choices=("mimmi", "yui"), required=True)
    args = ap.parse_args()
    state = {"offline": False, "requests": 0}
    servers = [
        ThreadingHTTPServer(("127.0.0.1", 8765), make_server("gallery", args.model, state)),
        ThreadingHTTPServer(("127.0.0.1", 8766), make_server("gateway", args.model, state))
    ]
    threads = [Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    try:
        with sync_playwright() as p:
            # Real Safari keeps an on-device browser profile. Playwright's
            # default ephemeral/incognito profile can clear CacheStorage
            # between reloads, causing a false negative for persistence.
            profile = TemporaryDirectory(prefix="gallery-persistent-sw-")
            context = getattr(p, args.browser).launch_persistent_context(
                profile.name, headless=True,
                viewport={"width": 390, "height": 844},
                is_mobile=True, has_touch=True, service_workers="allow"
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                console_errors = []
                page.on("pageerror", lambda e: console_errors.append(str(e)))
                page.goto(GALLERY + "/apps/" + args.model + "-gallery/",
                          wait_until="domcontentloaded")
                page.evaluate("""async () => {
                    await navigator.serviceWorker.register('./gallery-cover-sw.js', {scope: './'});
                    await navigator.serviceWorker.ready;
                }""")
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function("() => !!navigator.serviceWorker.controller",
                                       timeout=40000)
                image_url = (GATEWAY + "/api/" + ("yui/" if args.model == "yui" else "") +
                             "media/known-album/1/original?v=" + SHA)
                def decode():
                    return page.evaluate("""(url) => new Promise(resolve => {
                        const image = new Image();
                        image.onload = () => resolve({loaded: true, width: image.naturalWidth});
                        image.onerror = () => resolve({loaded: false, width: image.naturalWidth});
                        image.src = url;
                        document.body.appendChild(image);
                    })""", image_url)
                first = decode()
                assert first == {"loaded": True, "width": 48}, first
                assert state["requests"] == 1, state
                page.wait_for_function("""async () => {
                    const names = await caches.keys();
                    if (!names.some(name => name.endsWith('-owner-verified-photos-v1'))) return false;
                    const cache = await caches.open(
                        names.find(name => name.endsWith('-owner-verified-photos-v1')));
                    const keys = await cache.keys();
                    return keys.length === 1;
                }""", timeout=15000)
                before_cache = page.evaluate("""async () => {
                    const names=await caches.keys();
                    const result=[];
                    for(const name of names){
                        const storage=await caches.open(name);
                        result.push({name,urls:(await storage.keys()).map(x=>x.url)});
                    }
                    return {origin:location.origin,result};
                }""")
                state["offline"] = True
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function("() => !!navigator.serviceWorker.controller",
                                       timeout=40000)
                second = decode()
                if second != {"loaded": True, "width": 48}:
                    info=page.evaluate("""async (url) => {
                        const c=await caches.open('"""
                        + args.model + """-owner-verified-photos-v1');
                        const keys=await c.keys();
                        const allNames=await caches.keys();
                        const cached=await c.match(url);
                        const bytes=cached?await cached.clone().arrayBuffer():null;
                        return {
                            controller:navigator.serviceWorker.controller?.scriptURL,
                            allNames:allNames,
                            origin:location.origin,
                            keys:keys.map(x=>x.url),
                            cached:cached?{type:cached.type,status:cached.status,
                                length:bytes.byteLength,mime:cached.headers.get('content-type'),
                                prefix:[...new Uint8Array(bytes.slice(0,8))]}:null
                        };
                    }""",image_url)
                    print("OFFLINE_IMAGE_CACHE_DIAGNOSTIC",json.dumps({
                        "model":args.model,"browser":args.browser,
                        "server_requests":state["requests"],"second":second,
                        "before_cache":before_cache,"cache":info,"errors":console_errors
                    }),flush=True)
                assert second == {"loaded": True, "width": 48}, second
                assert state["requests"] == 1, (
                    "Browser unexpectedly attempted failed provider after exact SHA cache warm",
                    state
                )
                assert not console_errors, console_errors
                print("DEVICE_ORIGINAL_CACHE_REAL_BROWSER_200_TO_503_PASS", json.dumps({
                    "browser": args.browser,
                    "model": args.model,
                    "initial_verified_image_decoded": True,
                    "backend_after_refresh": 503,
                    "same_image_still_decodes_on_reload": True,
                    "backend_requests": state["requests"],
                    "real_iphone_hardware": False,
                    "real_owner_bytes": False
                }), flush=True)
            finally:
                context.close()
                profile.cleanup()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
