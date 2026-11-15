#!/usr/bin/env python3
"""Mobile Back regression: previously decoded thumbnail DOM and scroll survive.

Exercise real client-side routing in both galleries. This intentionally does
not rely on remote providers decoding owner images: preserving the original
<img> identity is required regardless of network availability.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def check(browser, model, base):
    context = browser.new_context(
        viewport={'width': 390, 'height': 844},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        locale='ko-KR',
    )
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)[:240]))
    try:
        response = page.goto(f'{base}/{model}-gallery/', wait_until='domcontentloaded', timeout=60000)
        assert response and response.status == 200, (model, 'HTTP_GALLERY_FAILURE')
        page.wait_for_function("""() => typeof available === 'function'
          && document.querySelector('#browse')?.hidden === false
          && document.querySelectorAll('#albumgrid [data-id]').length > 4
          && available().some(a => validImages(a).length >= 2)
        """, timeout=85000)

        # Select a gallery whose detail contains multiple thumbnails. Prefer a
        # card below the fold to prove that the album-grid scroll also survives.
        target = page.evaluate("""() => {
          const cards=[...document.querySelectorAll('#albumgrid [data-id]')];
          const suitable=cards.map((c,i)=>({
            id:c.dataset.id,index:i,
            count:validImages(stored.find(a=>a.id===c.dataset.id)||{}).length
          })).filter(x=>x.count>=2);
          const selected=suitable.find(x=>x.index>9&&x.count>=16)
            ||suitable.find(x=>x.index>9)||suitable[0];
          if(!selected)throw Error('NO_VIEWABLE_ALBUM');
          const card=cards[selected.index];
          window.__thumbnailBackWitness={
            albumCard:card, albumImage:card.querySelector('img'),
            albumGrid:document.querySelector('#albumgrid'),
            albumCount:cards.length
          };
          return selected;
        }""")
        page.locator('#albumgrid [data-id="'+target['id']+'"]').scroll_into_view_if_needed()
        page.evaluate("""() => {
          window.__thumbnailBackWitness.browseScroll=scrollY;
        }""")
        page.locator('#albumgrid [data-id="'+target['id']+'"]').click()
        page.wait_for_function("""id => !document.querySelector('#detail').hidden
          && detailAlbum?.id===id && document.querySelectorAll('#detailphotos .photo').length>=2
        """, arg=target['id'], timeout=25000)
        # Wait until the progressive first batch is mounted; store its real DOM,
        # not a copied HTML string that could hide a destructive re-render.
        page.evaluate("""() => {
          const nodes=[...document.querySelectorAll('#detailphotos .photo')];
          window.__thumbnailBackWitness.detailGrid=document.querySelector('#detailphotos');
          window.__thumbnailBackWitness.detailImage=nodes[0].querySelector('img');
          window.__thumbnailBackWitness.detailPhoto=nodes[0];
          window.__thumbnailBackWitness.detailCount=nodes.length;
        }""")
        open_index=min(target['count']-1, 16)
        page.locator('#detailphotos .photo').nth(open_index).scroll_into_view_if_needed()
        page.evaluate("""() => {
          window.__thumbnailBackWitness.detailScroll=scrollY;
        }""")
        page.locator('#detailphotos .photo').nth(open_index).click()
        page.wait_for_function("""() => !!document.querySelector('#lightbox.open')
          && !!history.state?.photo && history.state.depth===2
        """, timeout=20000)

        # Back 1: lightbox -> same already-mounted detail thumbnails.
        page.go_back(wait_until='domcontentloaded', timeout=30000)
        page.wait_for_function("""() => history.state?.depth===1
          && !document.querySelector('#lightbox.open')
          && document.querySelector('#detail').hidden===false
        """, timeout=20000)
        page.wait_for_function("""() =>
          Math.abs(scrollY-window.__thumbnailBackWitness.detailScroll)<=40
        """, timeout=12000)
        detail = page.evaluate("""() => {
          const w=window.__thumbnailBackWitness;
          return {
            gridSame:document.querySelector('#detailphotos')===w.detailGrid,
            photoSame:document.querySelector('#detailphotos .photo')===w.detailPhoto,
            imageSame:document.querySelector('#detailphotos .photo img')===w.detailImage,
            count:document.querySelectorAll('#detailphotos .photo').length,
            scroll:scrollY
          };
        }""")
        assert detail['gridSame'] and detail['photoSame'] and detail['imageSame'], (model, 'DETAIL_THUMBNAIL_REPLACED', detail)
        assert detail['count'] >= page.evaluate('window.__thumbnailBackWitness.detailCount'), (model, 'DETAIL_LIST_LOST', detail)

        # Back 2: detail -> same already-mounted album-cover thumbnails.
        page.go_back(wait_until='domcontentloaded', timeout=30000)
        page.wait_for_function("""() => history.state?.depth===0
          && document.querySelector('#browse').hidden===false
          && document.querySelector('#detail').hidden===true
        """, timeout=20000)
        page.wait_for_function("""() =>
          Math.abs(scrollY-window.__thumbnailBackWitness.browseScroll)<=40
        """, timeout=12000)
        browse=page.evaluate("""() => {
          const w=window.__thumbnailBackWitness;
          const selected=document.querySelector('#albumgrid [data-id="'+w.albumCard.dataset.id+'"]');
          return {
            gridSame:document.querySelector('#albumgrid')===w.albumGrid,
            cardSame:selected===w.albumCard,
            imageSame:selected?.querySelector('img')===w.albumImage,
            count:document.querySelectorAll('#albumgrid [data-id]').length,
            scroll:scrollY
          };
        }""")
        assert browse['gridSame'] and browse['cardSame'] and browse['imageSame'], (model, 'ALBUM_COVER_REPLACED', browse)
        assert browse['count']==page.evaluate('window.__thumbnailBackWitness.albumCount'), (model,'ALBUM_LIST_CHANGED',browse)

        # Forward is still navigable: the optimization must not break the URLs.
        page.go_forward(wait_until='domcontentloaded',timeout=30000)
        page.wait_for_function("""id => history.state?.depth===1 && !document.querySelector('#detail').hidden
          && detailAlbum?.id===id
        """,arg=target['id'],timeout=20000)
        assert not errors, (model, 'JAVASCRIPT_ERRORS', errors)
        print('THUMBNAIL_BACK_DOM_REUSE_PASS', model, browser.browser_type.name,
              {'album':target['id'],'photos':target['count'],
               'detail_img_reused':True,'album_img_reused':True,
               'detail_scroll':detail['scroll'],'album_scroll':browse['scroll']},flush=True)
    finally:
        context.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser',choices=('chromium','webkit'),default='chromium')
    parser.add_argument('--deployed',action='store_true')
    args=parser.parse_args()
    server=None
    if args.deployed:
        base='https://koith.github.io/browser-app-lab/apps'
    else:
        handler=partial(QuietHandler,directory=str(ROOT / 'apps'))
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser=getattr(p,args.browser).launch(headless=True)
            try:
                for model in ('mimmi','yui'):
                    check(browser,model,base)
            finally:
                browser.close()
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__=='__main__':
    main()
