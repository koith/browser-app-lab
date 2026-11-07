#!/usr/bin/env python3
"""Test candidate Cloudflare gallery source on actual Pages origin and real Worker bytes.

The live page is not changed by this test: Playwright overlays checked-out JS
and enabled config in an ephemeral, clean browser context. A merged production
release must run a separate deployed-source acceptance test afterward.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://koith.github.io/browser-app-lab/apps/'
WORKER = 'https://gallery-archive-free.gallery-9f7d03138f3f.workers.dev'
TARGET = {
    'mimmi': ('mimmi-indie-sana-sopmod2-2019', 1),
    'yui': ('yuis-present33', 1),
}


def expected(model):
    owner = json.loads((ROOT / 'apps' / f'{model}-gallery' / 'owner-index.json').read_text())
    assert owner['model'] == model and owner['schema_version'] == 1
    album, number = TARGET[model]
    for a in owner['albums']:
        if a['id'] == album:
            for p in a['images']:
                if p['number'] == number:
                    return {**p, 'ownerAlbum': album}
    raise AssertionError('Verified original missing from local index')


def verify_bytes(raw, photo):
    assert len(raw) == photo['bytes'], 'original length mismatch'
    assert hashlib.sha256(raw).hexdigest() == photo['sha256'], 'original SHA mismatch'
    with Image.open(io.BytesIO(raw)) as im:
        assert im.size == (photo['width'], photo['height']), 'original pixel size mismatch'
        assert im.format in ('JPEG', 'PNG', 'WEBP'), 'original format mismatch'
        im.verify()
    with Image.open(io.BytesIO(raw)) as im:
        im.load()


def fulfill(name, mime):
    def perform(route):
        route.fulfill(status=200, content_type=mime, body=name.read_bytes())
    return perform


def exercise(browser, model, mobile):
    root = f'{BASE}{model}-gallery/'
    ctx = browser.new_context(
        viewport={'width': 390, 'height': 844} if mobile else {'width': 1280, 'height': 840},
        is_mobile=mobile, has_touch=mobile, service_workers='block',
        locale='ko-KR', user_agent=(
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 '
            '(KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1' if mobile else
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'))
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)[:200]))
    folder = ROOT / 'apps' / f'{model}-gallery'
    module = ROOT / 'apps/gallery-archive/cloudflare-owner-gateway/pages-client.mjs'
    photo = expected(model)
    try:
        # Test the actual live GitHub Pages HTML/owner index using the candidate
        # gallery transport and its explicit opt-in. Never alter the live site.
        page.route(root + 'owner-media.js', fulfill(folder / 'owner-media.js', 'application/javascript'))
        page.route(
            'https://koith.github.io/browser-app-lab/apps/gallery-archive/cloudflare-owner-gateway/pages-client.mjs',
            fulfill(module, 'application/javascript'))
        page.route(root + 'cloudflare-gateway.json',
            lambda route: route.fulfill(status=200, content_type='application/json',
                body=json.dumps({'enabled': True, 'endpoint': WORKER})))
        response = page.goto(root, wait_until='domcontentloaded', timeout=80000)
        assert response and response.status == 200, 'actual Pages HTML unavailable'
        bridge = 'MimmiPrivate' if model == 'mimmi' else 'YuiPrivate'
        page.wait_for_function('name => typeof window[name]?.asset === "function"', arg=bridge, timeout=35000)
        signed = page.evaluate('''async ({name, photo}) => {
            return await window[name].asset(photo, 'original')
        }''', {'name': bridge, 'photo': photo})
        assert isinstance(signed, str), 'bridge did not return signed media URL'
        parsed = urlsplit(signed)
        assert parsed.scheme == 'https' and parsed.netloc == urlsplit(WORKER).netloc
        assert parsed.path == f'/api/v1/media/{model}/{photo["ownerAlbum"]}/{photo["number"]}/original'
        assert parsed.query, 'signed photo URL missing signature'
        received = ctx.request.get(signed, timeout=45000,
            headers={'User-Agent': 'gallery-archive-replica-qa/1.0'})
        assert received.status == 200, f'Cloudflare original HTTP {received.status}'
        verify_bytes(received.body(), photo)

        # Independent native <img> decoding in actual engine, not Pillow alone.
        decoded = page.evaluate('''async ({url, width, height}) => {
            const im = document.createElement('img');
            im.id = 'qa-actual-cloudflare-original';
            im.src = url;
            im.style.cssText='position:fixed;top:0;left:0;width:180px;height:180px;z-index:100000';
            document.body.append(im);
            try {
                await Promise.race([im.decode(),
                  new Promise((_,reject)=>setTimeout(()=>reject(Error('native image decode timeout')),30000))]);
                return {width:im.naturalWidth,height:im.naturalHeight,complete:im.complete,
                  current:im.currentSrc};
            } finally {im.remove()}
        }''', {'url': signed, 'width': photo['width'], 'height': photo['height']})
        assert decoded['complete'] and (decoded['width'], decoded['height']) == (
            photo['width'], photo['height']), 'browser failed actual original decode'
        assert urlsplit(decoded['current']).netloc == urlsplit(WORKER).netloc

        # Real main gallery album/detail interaction, not only a synthetic image.
        page.wait_for_function('''() => typeof available === 'function'
            && typeof photosFor === 'function'
            && document.querySelectorAll('#albumgrid .album').length > 0''', timeout=60000)
        target = page.evaluate('''q => {
           for(const album of available()) {
             const photos = photosFor(album);
             const ix = photos.findIndex(p => p.ownerAlbum === q.ownerAlbum &&
                  (p.storageNumber ?? p.number) === q.number && p.sha256 === q.sha256);
             if(ix >= 0) return {album: album.id, index: ix};
           } return null;
        }''', photo)
        assert target, 'actual gallery missing verified owner album/photo'
        card = page.locator('#albumgrid .album[data-id="' + target['album'] + '"]')
        card.scroll_into_view_if_needed(timeout=35000)
        card.click(timeout=30000)
        page.wait_for_function('''a => !document.querySelector('#detail').hidden
          && document.querySelector('#detailphotos .photo[data-i="' + a.index + '"]')''',
          arg=target, timeout=45000)
        detail = page.locator('#detailphotos .photo[data-i="' + str(target['index']) + '"]')
        detail.scroll_into_view_if_needed(timeout=35000)
        detail.click(timeout=30000)
        page.wait_for_selector('#lightbox.open', timeout=35000)
        page.wait_for_function('''() => {
            const im=document.querySelector('#full');
            return !!im && im.complete && im.naturalWidth>0;
        }''', timeout=45000)
        print('CLOUDFLARE_CANDIDATE_REAL_BROWSER_PHOTO_PASS',
            json.dumps({'model': model, 'mobile': mobile, 'owner_album': photo['ownerAlbum'],
                'number': photo['number'], 'verified_sha_bytes_dimensions': True,
                'native_cloudflare_decode': True, 'album_and_lightbox_open': True,
                'lightbox_width': page.locator('#full').evaluate('im=>im.naturalWidth'),
                'page_errors': errors[:3]}, sort_keys=True), flush=True)
        assert not errors, ('JavaScript runtime errors', errors[:3])
    finally:
        ctx.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chromium', 'webkit'], required=True)
    args = parser.parse_args()
    with sync_playwright() as p:
        engine = getattr(p, args.browser)
        browser = engine.launch(headless=True)
        try:
            for model in ('mimmi', 'yui'):
                exercise(browser, model, mobile=args.browser == 'webkit')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
