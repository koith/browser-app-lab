#!/usr/bin/env python3
"""Decode every gallery image in its real lightbox, not just count DOM records.

--http-bridge is only for managed executors whose Chromium lacks the proxy CA;
Python requests still validates TLS. CI and production QA use direct browser TLS.
"""
import argparse
import asyncio
import hashlib
import json

from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright
import requests


async def run(args):
    results=[]
    async with async_playwright() as pw:
        browser=await getattr(pw,args.engine).launch()
        context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,accept_downloads=True)
        if args.http_bridge:
            async def bridge(route):
                def get():
                    r=requests.get(route.request.url,timeout=45,allow_redirects=False)
                    return r
                r=await asyncio.to_thread(get)
                headers={k:v for k,v in r.headers.items() if k.lower() not in ('content-encoding','content-length','transfer-encoding','connection')}
                await route.fulfill(status=r.status_code,headers=headers,body=r.content)
            await context.route('https://**/*',bridge)
        page=await context.new_page()
        errors=[]
        page.on('pageerror',lambda e: (errors.append(str(e)),print('BROWSER_JS_ERROR',str(e),flush=True)))
        await page.goto(args.base,wait_until='domcontentloaded')
        await page.wait_for_function("document.querySelector('#total').textContent.includes('albums')")
        version=await page.locator('#app-version').inner_text()
        box=await page.locator('#app-version').bounding_box()
        assert box['x']>190 and box['y']<25 and box['height']<18,box
        albums=await page.evaluate('available().map(a=>({id:a.id,images:validImages(a)}))')
        for album in albums:
            print('QA_ALBUM_BEGIN',album['id'],flush=True)
            await page.locator(f'.album[data-id="{album["id"]}"]').click()
            await page.locator('#detailphotos .photo').first.click()
            passed=0
            downloads=0
            for i,image in enumerate(album['images']):
                if i:
                    await page.locator('#next').click()
                await page.locator('#full').evaluate('(im)=>Promise.race([im.decode(),new Promise((_,reject)=>setTimeout(()=>reject(Error("Image decode timed out: "+im.src)),25000))])')
                dims=await page.locator('#full').evaluate('(im)=>[im.naturalWidth,im.naturalHeight]')
                assert dims==[image['width'],image['height']],(album['id'],i+1,dims)
                passed+=1
                if passed%10==0:print('DECODE_PROGRESS',album['id'],passed,flush=True)
                # Verify the exact linked bytes with same-origin fetch. Saving
                # uses the browser's native context menu, with no app download UI.
                linked=await page.locator('#original').get_attribute('href')
                assert linked==image['url'],(album['id'],i+1,linked,image['url'],await page.locator('#position').inner_text(),errors)
                if image['url'].startswith('stored-albums/'):
                    digest=await page.locator('#original').evaluate("async a=>{const r=await fetch(a.href);if(!r.ok)throw Error(r.status);const b=await r.arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('')}")
                    assert digest==image['sha256']
                    downloads+=1
            results.append({'id':album['id'],'decoded_lightbox':passed,'original_link_sha256_checks':downloads})
            print('GALLERY_REAL_DECODE',args.engine,results[-1],flush=True)
            await page.locator('#close').click()
            await page.locator('#back').click()
        await page.screenshot(path=str(args.out.with_suffix('.png')))
        assert not errors,errors
        await browser.close()
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'base':args.base,'engine':args.engine,
            'version':version,'viewport':[390,844],'iphone_real_device':False,
            'network':'TLS-verified requests bridge' if args.http_bridge else 'direct browser TLS',
            'private_cloud_verified':0,'albums':results,
            'decoded_image_entries':sum(r['decoded_lightbox'] for r in results),
            'browser_download_sha256_verified':0,
            'original_link_sha256_verified':sum(r['original_link_sha256_checks'] for r in results)}
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print('ALL_GALLERY_MEDIA_QA_PASS',report['decoded_image_entries'],report['original_link_sha256_verified'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',default='http://localhost:8765/')
    p.add_argument('--engine',choices=['chromium','webkit'],default='chromium')
    p.add_argument('--out',type=Path,default=Path('yui-gallery-qa.json'))
    p.add_argument('--http-bridge',action='store_true')
    asyncio.run(run(p.parse_args()))
