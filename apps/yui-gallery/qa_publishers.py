"""Mobile publisher/logo browsing and Back/Forward through real gallery routes."""
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
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto(args.base, wait_until='domcontentloaded')
        await page.wait_for_function('history.state?.yui')
        baseline = await page.evaluate('JSON.stringify(available().map(a=>[a.id,validImages(a).map(p=>[p.number,p.sha256,p.url])]))')
        await page.locator('[data-filter="publishers"]').click()
        await page.locator('#publishergrid').wait_for(state='visible')
        count = await page.locator('#publishergrid .publisher').count()
        assert count >= 8, count
        assert await page.locator('.publisher[data-publisher="public"]').count() == 1
        assert await page.locator('.publisher[data-publisher="unknown"]').count() == 1
        logos = page.locator('#publishergrid img')
        logo_checks = 0
        for i in range(await logos.count()):
            await decode_image(logos.nth(i))
            assert await logos.nth(i).evaluate('(im)=>im.naturalWidth>0&&im.naturalHeight>0')
            logo_checks += 1
        publisher_counts = await page.locator('.publisher[data-publisher="ctee"]').inner_text()
        assert '등록 7' in publisher_counts, publisher_counts
        await page.locator('.publisher[data-publisher="sweetbox"]').click()
        assert await page.locator('#albumname').inner_text() == 'SWEETBOX'
        assert await page.locator('#albumgrid .album').count() >= 8
        assert await page.evaluate("document.body.classList.contains('publisher-view')")
        await page.locator('.album[data-id="teddy-bear97"]').click()
        assert await page.locator('#detailphotos .photo').count() == 97
        photo = page.locator('#detailphotos .photo').filter(has=page.locator('img[src^="stored-albums/"]')).first
        await photo.click()
        await decode_image(page.locator('#full'))
        await page.go_back()
        await page.locator('#lightbox').wait_for(state='hidden')
        await page.go_back()
        await page.locator('#publishergrid').wait_for(state='hidden')
        assert await page.locator('#albumname').inner_text() == 'SWEETBOX'
        await page.go_back()
        await page.locator('#publishergrid').wait_for(state='visible')
        await page.go_forward()
        await page.wait_for_function("activePublisher==='sweetbox'")
        await page.locator('#search-toggle').click()
        await page.locator('#search').fill('Teddy')
        await page.locator('#search-form button[type=submit]').click()
        await page.locator('#search-dialog').wait_for(state='hidden')
        assert await page.locator('#albumgrid .album').count() == 1
        await page.locator('#search-toggle').click()
        await page.locator('#search').fill('')
        await page.locator('#search-close').click()
        await page.locator('#search-dialog').wait_for(state='hidden')
        assert await page.evaluate('JSON.stringify(available().map(a=>[a.id,validImages(a).map(p=>[p.number,p.sha256,p.url])]))') == baseline
        await page.goto(args.base+'#view=publishers&publisher=sweetbox', wait_until='domcontentloaded')
        await page.reload(wait_until='domcontentloaded')
        await page.wait_for_function("activePublisher==='sweetbox'")
        await page.locator('#back').click()
        await page.locator('#publishergrid').wait_for(state='visible')
        assert not errors, errors
        await page.screenshot(path=str(args.out.with_suffix('.png')))
        await browser.close()
    report = {'engine': args.engine, 'publisher_categories': count, 'logo_images_decoded': logo_checks,
              'history_publisher_album_photo_back_forward': True, 'publisher_deep_link_back': True,
              'publisher_search': True, 'all_photo_order_urls_sha256_unchanged': True,
              'physical_iphone_verified': False, 'errors': errors}
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print('PUBLISHER_MOBILE_BROWSE_QA_PASS', json.dumps(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://localhost:8765/')
    p.add_argument('--engine', choices=['chromium', 'webkit'], default='chromium')
    p.add_argument('--out', type=Path, default=Path('yui-publishers.json'))
    p.add_argument('--http-bridge', action='store_true')
    asyncio.run(run(p.parse_args()))
