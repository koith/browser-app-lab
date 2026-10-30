"""Native owner-image/browser fixture; real server integrity is tested separately."""
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
             'bytes':len(photo),'sha256':digest if n==1 else 'f'*64} for n in (1,2)]
    catalog={'schema_version':1,'model':'yui','albums':[{'id':'owner-test','title':'Owner fixture','images':images}]}
    async with async_playwright() as pw:
        browser=await getattr(pw,args.engine).launch()
        context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,accept_downloads=True)
        async def respond(route):
            headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'Authorization','Access-Control-Allow-Methods':'GET, OPTIONS'}
            if route.request.method=='OPTIONS':return await route.fulfill(status=204,headers=headers)
            assert 'fixture-secret' not in route.request.url
            if route.request.url.endswith('/api/yui/catalog'):
                assert route.request.headers.get('authorization')=='Bearer fixture-secret'
                await route.fulfill(json=catalog,headers=headers)
            elif '/1/original' in route.request.url or '/api/cover/' in route.request.url:
                assert not route.request.headers.get('authorization'),'Native image URL must not contain browser secrets'
                await route.fulfill(body=photo,content_type='image/jpeg',headers=headers)
            else:
                # The production gateway rejects SHA-mismatched bytes *before*
                # returning an image. A native img cannot attach a bearer header
                # or independently report a JavaScript SHA exception.
                await route.fulfill(status=502,json={'detail':'Cloud media SHA-256 integrity check failed'},headers=headers)
        await context.route('https://owner.example/**',respond)
        await context.route('**/owner-index.json',lambda route:route.fulfill(
            json={'schema_version':1,'model':'yui','albums':[]}))
        await context.add_init_script("sessionStorage.setItem('yui-owner-session',JSON.stringify({api:'https://owner.example',token:'fixture-secret'}))")
        page=await context.new_page();await page.goto(origin,wait_until='domcontentloaded')
        await page.locator('.album[data-id="owner-test"]').click()
        await page.locator('#detailphotos .photo').first.click()
        await page.wait_for_function("document.querySelector('#full').naturalWidth===640")
        assert await page.locator('#original').get_attribute('href') is not None
        actual=await page.locator('#original').evaluate("async a=>{const b=await(await fetch(a.href)).arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('')}")
        assert actual==digest
        await page.locator('#next').click()
        await page.wait_for_function("document.querySelector('#media-status').textContent.includes('사진')")
        assert await page.locator('#full').evaluate('im=>im.naturalWidth')==0,'Rejected corrupt cloud bytes rendered'
        assert await page.evaluate("localStorage.getItem('yui-owner-session')") is None
        await browser.close()
    server.shutdown();server.server_close()
    print('OWNER_NATIVE_IMAGE_FIXTURE_ORIGINAL_SHA_AND_SERVER_REJECTION_PASS',args.engine,flush=True)

if __name__=='__main__':asyncio.run(main())
