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
P0_TARGETS = {
    'mimmi': ['mimmi-indie-sana-sopmod2-2019', 'djawa-pop-kitty-party', 'djawa-rei-beyond-the-heart', 'v2ph-azur-lane-tashkent'],
    'yui': ['yuis-present33', 'teddy-bear97', 'athletic-club104', 'djawa-privaty-public-samples'],
}


def expected(model, album_override=None):
    owner = json.loads((ROOT / 'apps' / f'{model}-gallery' / 'owner-index.json').read_text())
    assert owner['model'] == model and owner['schema_version'] == 1
    album, number = (album_override, {'v2ph-azur-lane-tashkent': 11, 'djawa-privaty-public-samples': 8, 'public-yui-sns': 465}.get(album_override, 1)) if album_override else TARGET[model]
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


def exercise(browser, model, mobile, deployed=False, album_override=None):
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
    config_path = folder / 'cloudflare-gateway.json'
    config = json.loads(config_path.read_text())
    assert config == {'enabled': True, 'endpoint': WORKER}, 'Cloudflare gallery not explicitly enabled'
    photo = expected(model, album_override)
    try:
        # Test the actual live GitHub Pages HTML/owner index using the candidate
        # gallery transport and its explicit opt-in. Never alter the live site.
        if not deployed:
            page.route(root + 'owner-media.js', fulfill(folder / 'owner-media.js', 'application/javascript'))
            page.route(
                'https://koith.github.io/browser-app-lab/apps/gallery-archive/cloudflare-owner-gateway/pages-client.mjs',
                fulfill(module, 'application/javascript'))
            page.route(root + 'cloudflare-gateway.json',
                fulfill(config_path, 'application/json'))
        else:
            # Require the actual published bytes, not an overlay. Fail closed if
            # Pages is still serving an older Render-only bundle.
            from time import monotonic, sleep
            deadline = monotonic() + 360
            paths = {
                root + 'owner-media.js': folder / 'owner-media.js',
                root + 'cloudflare-gateway.json': config_path,
                'https://koith.github.io/browser-app-lab/apps/gallery-archive/cloudflare-owner-gateway/pages-client.mjs': module,
            }
            mismatched = []
            while monotonic() < deadline:
                mismatched.clear()
                for address, expected_file in paths.items():
                    try:
                        response = ctx.request.get(address, timeout=25000,
                            headers={'Cache-Control': 'no-cache'})
                        if response.status != 200 or response.body() != expected_file.read_bytes():
                            mismatched.append(address.split('/')[-1])
                    except Exception:
                        mismatched.append(address.split('/')[-1])
                if not mismatched:
                    break
                sleep(8)
            assert not mismatched, ('PAGES_EXACT_GALLERY_RELEASE_NOT_VISIBLE', model, mismatched)
            print('DEPLOYED_PAGES_EXACT_CLOUDFLARE_SOURCE_PASS', model, flush=True)
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

        if deployed and model == 'yui' and album_override == 'public-yui-sns':
            # The 11 NEW originals are distinct published owner catalog slots,
            # not an older preview or a third-party hotlink. Assert every byte
            # in the actual LIVE Worker and native browser, plus presence in
            # the actual gallery's available photo union. No sample-only PASS.
            owner = json.loads((folder / 'owner-index.json').read_text())
            sns = next(a for a in owner['albums'] if a['id'] == 'public-yui-sns')
            fresh = [dict(p, ownerAlbum='public-yui-sns') for p in sns['images']
                     if 455 <= p['number'] <= 465]
            assert [p['number'] for p in fresh] == list(range(455, 466)), (
                'EXPECTED_11_NEW_OWNER_SNS_ROWS_MISSING', [p['number'] for p in fresh])
            page.wait_for_function("() => typeof available==='function' && typeof photosFor==='function'")
            for row in fresh:
                # Actual on-screen gallery state, NOT owner metadata alone.
                visible = page.evaluate("""photo => {
                    const album=available().find(a=>a.id==='public-yui-sns');
                    return !!album && photosFor(album).some(p=>p.sha256===photo.sha256 &&
                      p.bytes===photo.bytes && p.width===photo.width && p.height===photo.height);
                }""", row)
                assert visible, ('NEW_YUI_OWNER_PHOTO_ABSENT_FROM_PAGES_GALLERY', row['number'])
                url = page.evaluate("""async photo =>
                    await window.YuiPrivate.asset(photo,'original')""", row)
                assert urlsplit(url).netloc == urlsplit(WORKER).netloc
                r = ctx.request.get(url, timeout=45000,
                    headers={'User-Agent': 'gallery-archive-replica-qa/1.0'})
                assert r.status == 200, ('NEW_YUI_LIVE_ORIGINAL_HTTP', row['number'], r.status)
                verify_bytes(r.body(), row)
                pixels = page.evaluate("""async url => {
                    const im=new Image();im.src=url;
                    await Promise.race([im.decode(),new Promise((_,reject)=>
                      setTimeout(()=>reject(Error('native image timeout')),30000))]);
                    return [im.naturalWidth,im.naturalHeight];
                }""", url)
                assert pixels == [row['width'],row['height']], (
                    'NEW_YUI_NATIVE_BROWSER_PHOTO_DECODE',row['number'],pixels)
                print('YUI_NEW_SNS_OWNER_ORIGINAL_LIVE_GALLERY_PIXELS_PASS',
                      row['number'], row['sha256'][:12], flush=True)
            print('YUI_NEW_SNS_ALL_11_LIVE_SHA_NATIVE_BROWSER_DECODE_PASS',
                  browser.browser_type.name, flush=True)

        # G-11: reproduce one browser-native transient sign/CORS network failure
        # while the second request, signed original bytes and native image
        # decoding come from the LIVE Cloudflare Worker, not synthetic photos.
        # Separate gateway instance avoids any pre-existing album-cover cache.
        if album_override is None or album_override == P0_TARGETS[model][0]:
            restored = page.evaluate("""async ({model,photo,endpoint}) => {
              const mod=await import('../gallery-archive/cloudflare-owner-gateway/pages-client.mjs');
              let requests=0,failures=0;
              const client=mod.pagesGateway({endpoint,model,fetcher:async(url,opts)=>{
                requests++;
                if(requests===1){
                  failures++;
                  throw new TypeError('controlled one-shot browser network interruption');
                }
                return fetch(url,opts);
              }});
              const [one,two]=await Promise.all([
                client.asset(photo,'original'),client.asset(photo,'cover')]);
              return {requests,failures,url:one,identical:one===two};
            }""", {"model": model, "photo": photo, "endpoint": WORKER})
            assert restored['requests']==2 and restored['failures']==1 and restored['identical'], (
                'TRANSIENT_SIGN_RETRY_NOT_BOUNDED', model, restored)
            resume_url=restored['url']
            assert urlsplit(resume_url).netloc == urlsplit(WORKER).netloc
            assert urlsplit(resume_url).path == (
                f'/api/v1/media/{model}/{photo["ownerAlbum"]}/{photo["number"]}/original')
            original_response=ctx.request.get(resume_url,timeout=45000,
                headers={'User-Agent':'gallery-archive-replica-qa/1.0'})
            assert original_response.status==200
            verify_bytes(original_response.body(),photo)
            dimensions=page.evaluate("""async url => {
              const image=new Image();image.src=url;
              await Promise.race([image.decode(),
                new Promise((_,reject)=>setTimeout(()=>reject(Error('decode timeout')),30000))]);
              return [image.naturalWidth,image.naturalHeight];
            }""",resume_url)
            assert dimensions==[photo['width'],photo['height']], dimensions
            print('LIVE_WORKER_BROWSER_TRANSIENT_SIGN_RETRY_EXACT_ORIGINAL_PASS',
                json.dumps({'model':model,'browser':browser.browser_type.name,
                  'deployed':deployed,'sign_calls':restored['requests'],
                  'simulated_network_failures':restored['failures'],
                  'actual_worker_original_sha_bytes_pixels':True,
                  'native_browser_photo_decode':True,
                  'physical_iphone_hardware':False},
                  sort_keys=True),flush=True)

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

        # Production union may substitute an exact SHA+length+pixel local copy
        # for a remotely addressed owner photo. This is the SAME photo, not a
        # missing owner original. Never require p.ownerAlbum for such local
        # replacements: SavedGalleryPhotoUnion.preferPhysical removes that
        # marker deliberately. The visible album and exact file identity must
        # still match; a hash match in an unrelated album is not enough.
        locate = """q => {
          if (typeof available !== 'function' || typeof photosFor !== 'function')
            return false;
          for (const album of available()) {
            const photos = photosFor(album);
            const index = photos.findIndex(p =>
              p.sha256 === q.sha256 && p.bytes === q.bytes &&
              p.width === q.width && p.height === q.height &&
              ((p.ownerAlbum === q.ownerAlbum &&
                (p.storageNumber ?? p.number) === q.number) ||
               (!p.ownerAlbum && album.id === q.ownerAlbum)));
            if (index >= 0) return {album: album.id, index};
          }
          return false;
        }"""
        try:
            target = page.wait_for_function(locate, arg=photo, timeout=60000).json_value()
        except Exception:
            # Evidence is diagnostic only. A missing gallery photo still fails
            # the gate even if the Worker serves the raw original correctly.
            diagnostics = page.evaluate("""q => ({
              albumPresent: typeof available === 'function' &&
                available().some(a => a.id === q.ownerAlbum),
              albumPhotos: typeof available === 'function' &&
                available().filter(a=>a.id===q.ownerAlbum)
                  .map(a=>({id:a.id,count:photosFor(a).length,
                     matchingSha:photosFor(a).filter(p=>p.sha256===q.sha256)
                       .map(p=>({number:p.number,storageNumber:p.storageNumber,
                                 local:!!p.shaPinnedLocalCopy,hasOwner:!!p.ownerAlbum}))})),
              totalAlbums: typeof available==='function' ? available().length : -1
            })""", photo)
            print('GALLERY_EXACT_PHOTO_NOT_VISIBLE',
                  json.dumps({'model': model, 'album': photo['ownerAlbum'],
                              'number': photo['number'], 'details': diagnostics},
                             sort_keys=True), flush=True)
            raise
        assert target and target['album'], 'actual gallery missing exact stored photo'
        card = page.locator('#albumgrid .album[data-id="' + target['album'] + '"]')
        card.scroll_into_view_if_needed(timeout=35000)
        if deployed and album_override:
            cover = card.locator('img').first
            page.wait_for_function("""id => {
              const image=document.querySelector('#albumgrid .album[data-id="'+id+'"] img');
              return !!image && image.complete && image.naturalWidth>=160;
            }""", arg=target['album'], timeout=45000)
            cover_host = cover.evaluate("""im=>{
              try{return new URL(im.currentSrc||im.src,location.href).hostname}catch{return ''}
            }""")
            assert cover_host in ('koith.github.io', 'gallery-archive-free.gallery-9f7d03138f3f.workers.dev'), (
                'COVER_NOT_SELF_HOSTED', model, target['album'], cover_host)
        card.click(timeout=30000)
        page.wait_for_function('''a => !document.querySelector('#detail').hidden
          && document.querySelector('#detailphotos .photo[data-i="' + a.index + '"]')''',
          arg=target, timeout=45000)
        if deployed and album_override in ('v2ph-azur-lane-tashkent', 'djawa-privaty-public-samples'):
            expected_tiles = {'v2ph-azur-lane-tashkent': 69,
                              'djawa-privaty-public-samples': 30}[album_override]
            # Actual gallery appends the first 48 tiles synchronously, then
            # appends the remaining unique saved photos on the next animation
            # frame. Check complete population before testing native pixels.
            page.wait_for_function("""n =>
                document.querySelectorAll('#detailphotos .photo').length===n
            """, arg=expected_tiles, timeout=20000)
            tiles = page.locator('#detailphotos .photo')
            assert tiles.count() == expected_tiles, ('SCREENSHOT_ALBUM_TILE_COUNT', model,
                                                       album_override, tiles.count())
            for tile_index in range(expected_tiles):
                tile = tiles.nth(tile_index)
                tile.scroll_into_view_if_needed(timeout=30000)
                page.wait_for_function("""i => {
                    const tile=document.querySelector('#detailphotos .photo[data-i="'+i+'"]');
                    const im=tile?.querySelector('img');
                    return !!im && im.complete && im.naturalWidth>=160 &&
                        tile.dataset.imageState!=='failed';
                }""", arg=tile_index, timeout=35000)
            print('CLOUDFLARE_DEPLOYED_SCREENSHOT_ALBUM_ALL_TILES_DECODED',
                  model, album_override, expected_tiles, flush=True)
        detail = page.locator('#detailphotos .photo[data-i="' + str(target['index']) + '"]')
        detail.scroll_into_view_if_needed(timeout=35000)
        detail.click(timeout=30000)
        page.wait_for_selector('#lightbox.open', timeout=35000)
        page.wait_for_function('''() => {
            const im=document.querySelector('#full');
            return !!im && im.complete && im.naturalWidth>0;
        }''', timeout=45000)
        print('CLOUDFLARE_'+('DEPLOYED' if deployed else 'CANDIDATE')+'_REAL_BROWSER_PHOTO_PASS',
            json.dumps({'model': model, 'mobile': mobile, 'owner_album': photo['ownerAlbum'],
                'number': photo['number'], 'verified_sha_bytes_dimensions': True,
                'native_cloudflare_decode': True, 'album_and_lightbox_open': True,
                'lightbox_width': page.locator('#full').evaluate('im=>im.naturalWidth'),
                'page_errors': errors[:3]}, sort_keys=True), flush=True)
        assert not errors, ('JavaScript runtime errors', errors[:3])
        if deployed and album_override:
            page.locator('#close').click(timeout=10000)
            page.reload(wait_until='domcontentloaded', timeout=45000)
            page.wait_for_function("""id => {
              const album=document.querySelector('#albumgrid .album[data-id="'+id+'"]');
              return !!album && !!album.querySelector('img');
            }""", arg=target['album'], timeout=45000)
            print('CLOUDFLARE_DEPLOYED_ALBUM_RELOAD_PASS', model, album_override, flush=True)
    finally:
        ctx.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=['chromium', 'webkit'], required=True)
    parser.add_argument('--deployed', action='store_true',
                        help='no page interception: require real public Pages code and photos')
    parser.add_argument('--new-yui-11', action='store_true',
                        help='require all eleven newly stored owner originals 455..465 in actual deployed Pages and Cloudflare')
    parser.add_argument('--all-p0', action='store_true',
                        help='verify eight priority real owner albums including screenshot failures after complete remote replica')
    args = parser.parse_args()
    with sync_playwright() as p:
        engine = getattr(p, args.browser)
        browser = engine.launch(headless=True)
        try:
            for model in ('mimmi', 'yui'):
                selections = P0_TARGETS[model] if args.all_p0 else [None]
                if args.new_yui_11:
                    assert args.deployed and args.all_p0, 'new owner acceptance requires exact published Pages'
                    if model == 'yui':
                        selections = list(selections) + ['public-yui-sns']
                for album in selections:
                    exercise(browser, model, mobile=args.browser == 'webkit',
                             deployed=args.deployed, album_override=album)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
