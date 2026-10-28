"""Real browser/HTTP fixture verifies request fidelity in the local TLS bridge."""
import argparse
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.async_api import async_playwright

from browser_http_bridge import fulfill_verified_request


async def run(engine):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            raw = b'<!doctype html><title>Public fixture</title>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            seen.append({'method': self.command, 'agent': self.headers.get('User-Agent'),
                         'test': self.headers.get('X-Archive-Test'),
                         'body': self.rfile.read(int(self.headers['Content-Length'])).decode()})
            raw = json.dumps({'accepted': True}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        async with async_playwright() as pw:
            browser = await getattr(pw, engine).launch()
            context = await browser.new_context()
            await context.route('http://127.0.0.1:**/*', fulfill_verified_request)
            page = await context.new_page()
            await page.goto('http://127.0.0.1:'+str(server.server_port))
            agent = await page.evaluate('navigator.userAgent')
            result = await page.evaluate("""async()=>{
                const response=await fetch('/public-api',{method:'POST',
                  headers:{'X-Archive-Test':'preserved'},body:'ordinary-public-request'});
                return response.json();
            }""")
            assert result == {'accepted': True}
            assert seen == [{'method': 'POST', 'agent': agent, 'test': 'preserved',
                             'body': 'ordinary-public-request'}], seen
            await browser.close()
        print('REAL_BROWSER_REQUEST_METHOD_HEADERS_BODY_PRESERVED_PASS', engine, flush=True)
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', choices=['chromium', 'webkit'], default='chromium')
    asyncio.run(run(p.parse_args().engine))
