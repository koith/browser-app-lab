#!/usr/bin/env python3
"""Deterministic tests of lazy-load discovery and numbered pagination."""
import asyncio, hashlib, io, json
from PIL import Image
from playwright.async_api import async_playwright
from archive_engine import canonical,candidates,image_allowed,next_pages,inspect_page,discover,download

BASE='https://fixture.example/album'
HTML1="""<!doctype html><html><body>
<article class="entry-content" style="min-height:2200px">
  <img src="https://fixture.example/images/a.jpg">
  <img data-src="https://fixture.example/images/b.jpg" src="/fallback-placeholder.gif">
  <picture><source srcset="https://fixture.example/images/c.jpg 800w, https://fixture.example/images/c-large.jpg 1600w"></picture>
  <a rel="next" href="/album?page=2">2</a>
</article>
<script>window.addEventListener('scroll',()=>{if(scrollY>200&&!document.querySelector('#late')){const e=document.createElement('img');e.id='late';e.src='https://fixture.example/images/lazy.jpg';document.querySelector('article').appendChild(e)}});</script>
</body></html>"""
HTML2="""<!doctype html><html><body>
<article><img src="https://fixture.example/images/d.jpg"><img src="https://fixture.example/images/e.jpg"></article>
</body></html>"""
async def main():
    assert candidates('a.jpg 300w, b.jpg 1200w',BASE)[0].endswith('b.jpg')
    assert canonical('https://a.com/x.jpg?w=400&s=abc')=='https://a.com/x.jpg'
    assert image_allowed('https://img.fixture.example/a.jpg',['fixture.example'])
    assert not image_allowed('https://hostile.example/a.jpg',['fixture.example'])
    assert next_pages([{'url':BASE+'?page=2','text':'2','rel':''}],BASE,set())==[BASE+'?page=2']
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':900,'height':600},service_workers='block')
        async def router(route):
            u=route.request.url
            if 'page=2' in u:
                await route.fulfill(status=200,content_type='text/html',body=HTML2)
            elif u.endswith('/album'):
                await route.fulfill(status=200,content_type='text/html',body=HTML1)
            else:
                await route.fulfill(status=404,body='not found')
        await context.route('https://fixture.example/**',router)
        page=await context.new_page()
        a=await inspect_page(page,BASE,['fixture.example'],max_steps=18)
        assert len(a['images'])>=4,('first_page_images',a['images'])
        assert any('lazy.jpg' in x['url'] for x in a['images']), 'lazy scroll was not observed'
        assert any('c-large.jpg' in x['url'] for x in a['images']), 'responsive srcset largest candidate missing'
        assert any('?page=2' in x['url'] for x in a['page_links']), 'page 2 link missed'
        b=await inspect_page(page,BASE+'?page=2',['fixture.example'],max_steps=7)
        assert len(b['images'])==2,('second page',b['images'])
        assert len({v['url'] for v in a['images']+b['images']})>=6
        print('SELFTEST_PASS',json.dumps({'page1':len(a['images']),'page2':len(b['images']),
          'lazy_loaded':True,'responsive_srcset':True,'pagination':True}),flush=True)
        await browser.close()
if __name__=='__main__':
    asyncio.run(main())
