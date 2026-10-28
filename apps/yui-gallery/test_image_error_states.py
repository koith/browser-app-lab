"""Exercise real gallery error events with local 451/503 HTTP fixtures.

No external photograph is requested and fixture decodes are not acquisition or
actual-gallery photograph verification counts.
"""
import argparse
import asyncio
import io
import json
import threading
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright


async def run(engine):
    root = Path(__file__).parent
    manifests = {a['id']:a for name in ('source-viewer-albums.json','additional-source-albums.json')
                 for a in json.loads((root/name).read_text())['albums']}
    athletic, wet = manifests['athletic-club104'], manifests['wet-yui80']
    denied = {athletic['images'][i]['url'] for i in (1, 3)}
    transient = wet['images'][0]['url']
    counts = Counter()
    raw = io.BytesIO()
    Image.new('RGB', (64, 96), '#456789').save(raw, 'PNG')

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as pw:
            browser = await getattr(pw, engine).launch()
            page = await browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            async def external(route):
                url = route.request.url
                counts[url] += 1
                if url in denied:
                    await route.fulfill(status=451, content_type='text/html', body='Unavailable For Legal Reasons')
                elif url == transient and counts[url] == 1:
                    await route.fulfill(status=503, body='Temporary failure')
                elif route.request.resource_type == 'image':
                    await route.fulfill(status=200, content_type='image/png', body=raw.getvalue())
                else:
                    await route.abort()

            await page.route('https://**/*', external)
            await page.goto(f'http://127.0.0.1:{server.server_port}/')
            await page.wait_for_function('history.state?.yui')
            await page.locator('.album[data-id="athletic-club104"]').click()
            await page.wait_for_function("document.querySelectorAll('#detailphotos .photo[data-image-state=failed]').length===2")
            assert await page.locator('#detail-media-status').inner_text() == '2장 연결 실패 · 사진을 누르면 출처 확인 가능'
            cards = page.locator('#detailphotos .photo')
            first, second = await cards.nth(0).bounding_box(), await cards.nth(1).bounding_box()
            assert abs(first['y']-second['y']) < 1 and abs(first['height']-second['height']) < 1
            assert await cards.nth(1).locator('img').evaluate('im=>getComputedStyle(im).visibility') == 'hidden'
            assert await cards.nth(0).locator('img').evaluate('im=>im.naturalWidth') == 64
            before = {url:counts[url] for url in denied}
            await page.wait_for_timeout(500)
            assert before == {url:counts[url] for url in denied}, 'Denied URLs automatically retried'
            await cards.nth(1).click()
            assert 'HTTP 451' in await page.locator('#media-status').inner_text()
            assert await page.locator('#original').get_attribute('href') == athletic['images'][1]['url']
            assert await page.locator('#full').get_attribute('src') is None
            await page.wait_for_timeout(200)
            assert before == {url:counts[url] for url in denied}, 'Viewer re-requested failed reported origin'
            await page.locator('#prev').click()
            await page.wait_for_function('document.querySelector("#full").naturalWidth===64')
            assert await page.locator('.media-frame').get_attribute('data-image-state') is None
            assert await page.locator('#media-status').inner_text() == ''
            assert await page.locator('#original').get_attribute('href') == athletic['images'][0]['url']
            assert await page.locator('#full').evaluate('im=>getComputedStyle(im).touchAction') == 'auto'
            await page.go_back()
            await page.locator('#lightbox').wait_for(state='hidden')
            await page.locator('#back').click()
            await page.locator('.album[data-id="wet-yui80"]').click()
            await page.wait_for_function("document.querySelector('#detailphotos .photo').dataset.imageState==='failed'")
            assert await page.evaluate('imageFailureText('+json.dumps(transient)+').includes("451")') is False
            await page.locator('#detailphotos .photo').first.click()
            await page.wait_for_function('document.querySelector("#full").naturalWidth===64')
            assert await page.locator('.media-frame').get_attribute('data-image-state') is None
            assert await page.locator('#original').get_attribute('href') == transient
            assert not errors, errors
            await browser.close()
        print('IMAGE_FAILURE_451_503_NATIVE_NAVIGATION_FIXTURE_PASS', engine,
              'actual_external_photo_requests=0', 'actual_gallery_photographs_verified=0', flush=True)
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['chromium','webkit'], default='chromium')
    asyncio.run(run(parser.parse_args().engine))
