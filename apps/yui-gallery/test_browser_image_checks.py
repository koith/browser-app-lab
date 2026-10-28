"""Real HTTP fault: recover once without changing URL; persistent faults fail."""
import argparse
import asyncio
import io
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image
from playwright.async_api import Error, async_playwright

from browser_image_checks import decode_image, SourceViewPacer


async def run(engine):
    data = io.BytesIO()
    Image.new('RGB', (64, 96), '#456789').save(data, 'PNG')
    raw, requests = data.getvalue(), {'/transient.png': 0, '/broken.png': 0, '/paced-1.png': 0, '/paced-2.png': 0}
    paced_arrivals = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path in requests:
                requests[self.path] += 1
                if self.path.startswith('/paced-'):
                    paced_arrivals.append(time.monotonic())
                valid = self.path.startswith('/paced-') or (self.path == '/transient.png' and requests[self.path] > 1)
                body = raw if valid else b''
                self.send_response(200 if valid else 503)
                self.send_header('Content-Type', 'image/png')
            else:
                body = b'<!doctype html><img id="photo" alt="test fixture">'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        async with async_playwright() as pw:
            browser = await getattr(pw, engine).launch()
            page = await browser.new_page()
            base = 'http://127.0.0.1:'+str(server.server_port)
            await page.goto(base)
            image = page.locator('#photo')
            url = base+'/transient.png'
            await image.evaluate('(im,url)=>im.src=url', url)
            assert await decode_image(image, timeout_ms=2000) == 1
            assert requests['/transient.png'] == 2
            assert await image.get_attribute('src') == url
            assert await image.evaluate('(im)=>[im.naturalWidth,im.naturalHeight]') == [64, 96]
            url = base+'/broken.png'
            await image.evaluate('(im,url)=>im.src=url', url)
            try:
                await decode_image(image, timeout_ms=2000)
            except Error:
                pass
            else:
                raise AssertionError('Persistent image failure was hidden')
            assert requests['/broken.png'] == 2
            assert await image.get_attribute('src') == url
            pacer = SourceViewPacer(interval=.1, hosts=('127.0.0.1',))
            for n in range(1, 3):
                url = base+f'/paced-{n}.png'
                await pacer.wait(url)
                await image.evaluate('(im,url)=>{im.removeAttribute("src");im.src=url}', url)
                await decode_image(image, timeout_ms=2000)
                assert await image.get_attribute('src') == url
                assert await image.evaluate('(im)=>[im.naturalWidth,im.naturalHeight]') == [64, 96]
            await pacer.wait('https://unpaced.example.org/photo.png')
            assert requests['/paced-1.png']+requests['/paced-2.png'] == pacer.views == 2
            assert paced_arrivals[1]-paced_arrivals[0] >= .075, paced_arrivals
            await browser.close()
        print('DIRECT_SOURCE_VIEW_PACING_NO_URL_OR_IMAGE_CHANGE_PASS', engine, flush=True)
        print('REAL_HTTP_IMAGE_RETRY_AND_PERSISTENT_FAILURE_BOUND_PASS', engine, flush=True)
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['chromium', 'webkit'], default='chromium')
    asyncio.run(run(parser.parse_args().engine))
