"""Verify actual cover images keep their reviewed face regions in the card."""
import argparse
import asyncio
import json
from pathlib import Path

import requests
from playwright.async_api import async_playwright


async def run(args):
    async with async_playwright() as pw:
        browser = await getattr(pw, args.engine).launch()
        context = await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        if args.http_bridge:
            async def bridge(route):
                response = await asyncio.to_thread(lambda: requests.get(route.request.url, timeout=45, allow_redirects=False))
                headers = {k: v for k, v in response.headers.items()
                           if k.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'connection')}
                await route.fulfill(status=response.status_code, headers=headers, body=response.content)
            await context.route('https://**/*', bridge)
        page = await context.new_page()
        await page.goto(args.base, wait_until='domcontentloaded')
        await page.wait_for_function("document.querySelector('#total').textContent.includes('albums')")
        configured = await page.evaluate('albumCovers')
        count = await page.locator('#albumgrid .album').count()
        assert count == len(configured), (count, len(configured))
        results = []
        for aid, meta in configured.items():
            card = page.locator('.album[data-id="'+aid+'"]')
            image = card.locator('img')
            await image.scroll_into_view_if_needed()
            await image.evaluate('(im)=>im.decode()')
            dims = await image.evaluate('(im)=>[im.naturalWidth,im.naturalHeight]')
            assert dims == [meta['width'], meta['height']], (aid, dims)
            selected = await page.evaluate('(id)=>{const a=available().find(a=>a.id===id);return validImages(a).find(p=>p.sha256===albumCovers[id].sha256)}', aid)
            assert selected and await image.get_attribute('src') == selected['url']
            geometry = await image.evaluate('''(im)=>{
              const style=getComputedStyle(im),r=im.getBoundingClientRect();
              return {width:r.width,height:r.height,fit:style.objectFit,position:style.objectPosition.split(' ').map(parseFloat)}
            }''')
            width, height = geometry['width'], geometry['height']
            scale = (min if geometry['fit'] == 'contain' else max)(width/dims[0], height/dims[1])
            ox = (dims[0]*scale-width)*geometry['position'][0]/100
            oy = (dims[1]*scale-height)*geometry['position'][1]/100
            x, y, w, h = meta['face']
            bounds = [x*scale-ox, y*scale-oy, (x+w)*scale-ox, (y+h)*scale-oy]
            assert bounds[0] >= -1 and bounds[1] >= -1 and bounds[2] <= width+1 and bounds[3] <= height+1, (aid, bounds, geometry)
            title_color = await card.locator('.name').evaluate('e=>getComputedStyle(e).color')
            assert title_color.startswith('rgba(') and float(title_color.split(',')[-1].rstrip(') ')) <= .65, title_color
            results.append({'id': aid, 'photo': meta['number'], 'face_region_inside_card': True, 'fit': geometry['fit']})
        teddy = page.locator('.album[data-id="teddy-bear97"]')
        assert 'SWEETBOX' not in await teddy.locator('.name').inner_text()
        assert await teddy.locator('.publisher-sticker').inner_text() == 'SWEETBOX'
        before = await page.evaluate("photosFor(available().find(a=>a.id==='teddy-bear97')).map(p=>p.url)")
        await teddy.click()
        assert before == await page.locator('#detailphotos img').evaluate_all('images=>images.map(im=>im.getAttribute("src"))')
        await page.locator('#back').click()
        await page.locator('#browse').wait_for(state='visible')
        await page.evaluate('scrollTo(0,0)')
        await page.screenshot(path=str(args.out.with_suffix('.png')), full_page=True)
        report = {'engine': args.engine, 'base': args.base, 'version': await page.locator('#app-version').inner_text(),
                  'verified_cover_count': len(results), 'covers': results, 'title_translucency_verified': True,
                  'publisher_removed_only_from_cover_title': True, 'detail_image_order_and_urls_unchanged': True,
                  'not_identity_recognition': True, 'iphone_real_device': False}
        args.out.write_text(json.dumps(report, indent=2)+'\n')
        print('FACE_VISIBLE_COVERS_QA_PASS', len(results), 'TITLE_AND_DETAIL_ORDER_PASS', flush=True)
        await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://localhost:8765/')
    parser.add_argument('--engine', choices=['chromium', 'webkit'], default='chromium')
    parser.add_argument('--http-bridge', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('yui-covers-qa.json'))
    asyncio.run(run(parser.parse_args()))
