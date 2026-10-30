"""Exercise real gallery failures with local 451/503 fixtures, never a source hotlink."""
import argparse
import asyncio
import json
import threading
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright


async def run(engine):
    root = Path(__file__).parent
    data = json.loads((root/'stored-albums.json').read_text())
    album = next(a for a in data['albums'] if len(a['images']) >= 3)
    images = album['images'][:3]
    denied, transient = images[1]['url'], images[2]['url']
    counts = Counter()
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as pw:
            browser = await getattr(pw, engine).launch()
            page = await browser.new_page(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
            errors,external = [],[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: external.append(r.url) if r.resource_type == 'image' and not r.url.startswith(f'http://127.0.0.1:{server.server_port}/') else None)
            async def fixtures(route):
                url = route.request.url
                counts[url] += 1
                if url.endswith('/'+denied):
                    await route.fulfill(status=451, content_type='text/html', body='Denied fixture')
                elif url.endswith('/'+transient) and counts[url] == 1:
                    await route.fulfill(status=503, body='Retry fixture')
                else:
                    await route.continue_()
            # This fault-injection fixture is deliberately local-only. Real
            # owner media is separately exercised by deployed exact-SHA QA.
            await page.route('**/owner-index.json',lambda route:route.fulfill(
                content_type='application/json',body=json.dumps({'schema_version':1,'model':'yui','albums':[]})))
            await page.route('https://mimmi-private-gallery-free.onrender.com/**',lambda route:route.fulfill(status=503,body='Local fault fixture'))
            await page.route('**/stored-albums/**', fixtures)
            await page.goto(f'http://127.0.0.1:{server.server_port}/')
            await page.wait_for_function("document.querySelector('#total').textContent.includes('albums')")
            assert await page.locator('#inventory').inner_text() == str(sum(len(a['images']) for a in data['albums']))+'장 · 실제 저장본'
            await page.locator(f'.album[data-id="{album["id"]}"]').click()
            await page.wait_for_function("document.querySelectorAll('#detailphotos .photo[data-image-state=failed]').length>=1")
            cards = page.locator('#detailphotos .photo')
            assert await cards.nth(1).get_attribute('data-image-state') == 'failed'
            assert '저장 파일' in await page.locator('#detail-media-status').inner_text()
            await cards.nth(1).click()
            await page.wait_for_function("document.querySelector('#media-status').textContent.includes('저장된 사진')")
            assert await page.locator('#original').get_attribute('href') == denied
            assert not external and not errors,(external,errors)
            await browser.close()
        print('STORED_MEDIA_451_503_ERROR_FIXTURE_PASS',engine,'source_hotlink_requests=0',flush=True)
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['chromium','webkit'], default='chromium')
    asyncio.run(run(parser.parse_args().engine))
