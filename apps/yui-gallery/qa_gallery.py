#!/usr/bin/env python3
"""Decode every image through the gallery in a bounded number of browser tabs.

--http-bridge is for managed executors missing the proxy CA in Chromium;
requests still verifies TLS. CI uses direct browser TLS.
"""
import argparse,asyncio,json
from datetime import datetime,timezone
from pathlib import Path
from playwright.async_api import async_playwright
import requests

async def run(args):
 results=[];errors=[];semaphore=asyncio.Semaphore(args.workers)
 async with async_playwright() as pw:
  browser=await getattr(pw,args.engine).launch()
  context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  if args.http_bridge:
   async def bridge(route):
    r=await asyncio.to_thread(lambda:requests.get(route.request.url,timeout=45,allow_redirects=False))
    headers={k:v for k,v in r.headers.items() if k.lower() not in ('content-encoding','content-length','transfer-encoding','connection')}
    await route.fulfill(status=r.status_code,headers=headers,body=r.content)
   await context.route('https://**/*',bridge)
  page=await context.new_page();await page.goto(args.base,wait_until='domcontentloaded')
  await page.wait_for_function("document.querySelector('#total').textContent.includes('albums')")
  version=await page.locator('#app-version').inner_text();box=await page.locator('#app-version').bounding_box()
  assert box['x']>190 and box['y']<25 and box['height']<18,box
  albums=await page.evaluate('available().map(a=>({id:a.id,images:validImages(a)}))')
  await page.screenshot(path=str(args.out.with_suffix('.png')));await page.close()
  async def check(album):
   async with semaphore:
    page=await context.new_page();js_errors=[]
    page.on('pageerror',lambda e:(js_errors.append(str(e)),print('BROWSER_JS_ERROR',album['id'],str(e),flush=True)))
    passed=0;hashes=0
    try:
     await page.goto(args.base,wait_until='domcontentloaded')
     await page.locator(f'.album[data-id="{album["id"]}"]').click()
     await page.locator('#detailphotos .photo').first.click()
     print('QA_ALBUM_BEGIN',album['id'],flush=True)
     for i,image in enumerate(album['images']):
      if i:await page.locator('#next').click()
      await page.locator('#full').evaluate('(im)=>Promise.race([im.decode(),new Promise((_,reject)=>setTimeout(()=>reject(Error("Image decode timed out: "+im.src)),25000))])')
      dims=await page.locator('#full').evaluate('(im)=>[im.naturalWidth,im.naturalHeight]')
      linked=await page.locator('#original').get_attribute('href')
      assert dims==[image['width'],image['height']],(album['id'],i+1,dims)
      assert linked==image['url'],(album['id'],i+1,linked,image['url'],await page.locator('#position').inner_text(),js_errors)
      passed+=1
      if passed%25==0:print('DECODE_PROGRESS',album['id'],passed,flush=True)
      if image['url'].startswith('stored-albums/'):
       digest=await page.locator('#original').evaluate("async a=>{const r=await fetch(a.href);if(!r.ok)throw Error(r.status);const b=await r.arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('')}")
       assert digest==image['sha256'];hashes+=1
     await page.locator('#close').click();await page.locator('#lightbox').wait_for(state='hidden')
     await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
     assert not js_errors,js_errors
    except Exception as exc:
     errors.append({'id':album['id'],'decoded_before_failure':passed,'error':str(exc),'page_errors':js_errors})
    finally:
     result={'id':album['id'],'decoded_lightbox':passed,'original_link_sha256_checks':hashes}
     results.append(result);print('GALLERY_REAL_DECODE',args.engine,result,flush=True);await page.close()
  await asyncio.gather(*(check(a) for a in albums));await browser.close()
 report={'checked_at':datetime.now(timezone.utc).isoformat(),'base':args.base,'engine':args.engine,'version':version,'viewport':[390,844],'iphone_real_device':False,'network':'TLS-verified requests bridge' if args.http_bridge else 'direct browser TLS','private_cloud_verified':0,'albums':results,'decoded_image_entries':sum(r['decoded_lightbox'] for r in results),'browser_download_sha256_verified':0,'original_link_sha256_verified':sum(r['original_link_sha256_checks'] for r in results),'errors':errors}
 args.out.write_text(json.dumps(report,indent=2)+'\n')
 assert not errors,errors
 assert report['decoded_image_entries']==sum(len(a['images']) for a in albums)
 print('ALL_GALLERY_MEDIA_QA_PASS',report['decoded_image_entries'],report['original_link_sha256_verified'],flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',default='http://localhost:8765/');p.add_argument('--engine',choices=['chromium','webkit'],default='chromium');p.add_argument('--out',type=Path,default=Path('yui-gallery-qa.json'));p.add_argument('--http-bridge',action='store_true');p.add_argument('--workers',type=int,choices=range(1,4),default=3);asyncio.run(run(p.parse_args()))
