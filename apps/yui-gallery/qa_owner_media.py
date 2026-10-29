"""Browser integration fixture; proves owner auth/byte checks, NOT a live cloud."""
import asyncio,hashlib,io,json,tempfile,threading,functools
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright

async def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--engine',default='chromium');args=parser.parse_args()
    handler=functools.partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin='http://localhost:'+str(server.server_port)
    data=io.BytesIO();Image.new('RGB',(640,960),(30,40,50)).save(data,'JPEG');photo=data.getvalue()
    digest=hashlib.sha256(photo).hexdigest()
    images=[{'number':n,'key':f'originals/owner-test/{n}.jpg','width':640,'height':960,
             'bytes':len(photo),'sha256':digest} for n in (1,2)]
    catalog={'schema_version':1,'albums':[{'id':'owner-test','title':'Owner fixture','images':images}]}
    async with async_playwright() as pw:
        browser=await getattr(pw,args.engine).launch()
        context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,accept_downloads=True)
        async def respond(route):
            headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'Authorization','Access-Control-Allow-Methods':'GET, OPTIONS'}
            if route.request.method=='OPTIONS':return await route.fulfill(status=204,headers=headers)
            assert route.request.headers.get('authorization')=='Bearer fixture-secret'
            assert 'fixture-secret' not in route.request.url
            if route.request.url.endswith('/api/yui/catalog'):
                await route.fulfill(json=catalog,headers=headers)
            elif '/1/original' in route.request.url:
                await route.fulfill(body=photo,content_type='image/jpeg',headers=headers)
            else:
                await route.fulfill(body=b'X'*len(photo),content_type='image/jpeg',headers=headers)
        await context.route('https://owner.example/**',respond)
        await context.add_init_script("sessionStorage.setItem('yui-owner-session',JSON.stringify({api:'https://owner.example',token:'fixture-secret'}))")
        page=await context.new_page();await page.goto(origin,wait_until='domcontentloaded')
        await page.locator('.album[data-id="owner-test"]').click()
        await page.locator('#detailphotos .photo').first.click()
        await page.wait_for_function("document.querySelector('#full').naturalWidth===640")
        assert await page.locator('#original').get_attribute('href') is not None
        actual=await page.locator('#original').evaluate("async a=>{const b=await(await fetch(a.href)).arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('')}")
        assert actual==digest
        await page.locator('#next').click()
        await page.wait_for_function("document.querySelector('#media-status').textContent.includes('SHA-256')")
        assert await page.locator('#full').get_attribute('src') is None,'Corrupt cloud bytes rendered'
        assert await page.evaluate("localStorage.getItem('yui-owner-session')") is None
        await browser.close()
    print('OWNER_MAIN_GALLERY_FIXTURE_AUTH_ORIGINAL_LINK_AND_CORRUPTION_PASS',args.engine,flush=True)

if __name__=='__main__':asyncio.run(main())
