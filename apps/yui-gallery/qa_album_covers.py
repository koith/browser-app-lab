"""Verify covers fill their cards and keep reviewed face regions visible."""
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from browser_http_bridge import fulfill_verified_request
from browser_image_checks import decode_image


async def run(args):
    async with async_playwright() as pw:
        browser = await getattr(pw, args.engine).launch()
        context = await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        if args.http_bridge:
            bridge = fulfill_verified_request
            await context.route('https://**/*', bridge)
        page = await context.new_page()
        await page.goto(args.base, wait_until='domcontentloaded')
        await page.wait_for_function("document.querySelector('#total').textContent.includes('albums')")
        configured = await page.evaluate('albumCovers')
        count = await page.locator('#albumgrid .album').count()
        assert count == len(configured), (count, len(configured))
        if args.album:
            requested = set(args.album)
            assert requested <= set(configured), 'Requested cover is missing from actual gallery'
            configured = {aid: meta for aid, meta in configured.items() if aid in requested}
        results = []
        for aid, meta in configured.items():
            print('COVER_QA_BEGIN', aid, flush=True)
            card = page.locator('.album[data-id="'+aid+'"]')
            image = card.locator('img')
            # Scrolling a static card does not require the image's hover
            # transition to satisfy WebKit actionability/stability checks.
            await card.evaluate('(card)=>card.scrollIntoView({block:"center"})')
            retries = await decode_image(image)
            dims = await image.evaluate('(im)=>[im.naturalWidth,im.naturalHeight]')
            assert dims == [meta['width'], meta['height']], (aid, dims)
            selected = await page.evaluate('(id)=>{const a=available().find(a=>a.id===id);return validImages(a).find(p=>p.sha256===albumCovers[id].sha256)}', aid)
            assert selected and await image.get_attribute('src') == selected['url']
            geometry = await image.evaluate('''(im)=>{
              const style=getComputedStyle(im),r=im.getBoundingClientRect();
              const clip=im.closest('.album').getBoundingClientRect();
              return {x:r.x,y:r.y,width:r.width,height:r.height,clip:{x:clip.x,y:clip.y,width:clip.width,height:clip.height},fit:style.objectFit,position:style.objectPosition.split(' ').map(parseFloat)}
            }''')
            width, height = geometry['width'], geometry['height']
            assert geometry['fit'] == 'cover', (aid, 'Thumbnail must fill the card', geometry)
            scale = max(width/dims[0], height/dims[1])
            ox = (dims[0]*scale-width)*geometry['position'][0]/100
            oy = (dims[1]*scale-height)*geometry['position'][1]/100
            x, y, w, h = meta['face']
            bounds = [x*scale-ox, y*scale-oy, (x+w)*scale-ox, (y+h)*scale-oy]
            clip = geometry['clip']
            content = [geometry['x']-ox, geometry['y']-oy,
                       geometry['x']-ox+dims[0]*scale, geometry['y']-oy+dims[1]*scale]
            assert content[0] <= clip['x']+1 and content[1] <= clip['y']+1 and content[2] >= clip['x']+clip['width']-1 and content[3] >= clip['y']+clip['height']-1, (aid, 'Thumbnail has letterbox gaps', content, clip)
            visible = [bounds[0]+geometry['x']-clip['x'], bounds[1]+geometry['y']-clip['y'],
                       bounds[2]+geometry['x']-clip['x'], bounds[3]+geometry['y']-clip['y']]
            assert visible[0] >= -1 and visible[1] >= -1 and visible[2] <= clip['width']+1 and visible[3] <= clip['height']+1, (aid, visible, geometry)
            title_color = await card.locator('.name').evaluate('e=>getComputedStyle(e).color')
            assert title_color.startswith('rgba(') and float(title_color.split(',')[-1].rstrip(') ')) <= .65, title_color
            results.append({'id': aid, 'photo': meta['number'], 'face_region_inside_card': True, 'card_filled_without_letterboxing': True, 'fit': geometry['fit'], 'image_decode_retries': retries})
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
    parser.add_argument('--album', action='append', help='Check selected acquired covers; omit to verify every cover')
    parser.add_argument('--out', type=Path, default=Path('yui-covers-qa.json'))
    asyncio.run(run(parser.parse_args()))
