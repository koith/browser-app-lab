#!/usr/bin/env python3
"""Decode every image through the gallery in a bounded number of browser tabs.

--http-bridge is for managed executors missing the proxy CA in Chromium;
requests still verifies TLS. CI uses direct browser TLS.
"""
import argparse,asyncio,json
from datetime import datetime,timezone
from pathlib import Path
from playwright.async_api import async_playwright
from browser_http_bridge import fulfill_verified_request
from browser_image_checks import decode_image, SourceViewPacer

async def static_owner_fixture(route):
 await route.fulfill(content_type='application/json',body='{"schema_version":1,"model":"yui","albums":[]}')

async def static_gateway_fixture(route):
 await route.fulfill(status=503,body='Static individual-file unit scope; deployed owner media is tested separately')

async def isolate_static_scope(context):
 await context.route('**/owner-index.json',static_owner_fixture)
 await context.route('https://mimmi-private-gallery-free.onrender.com/**',static_gateway_fixture)

async def run(args):
 results=[];errors=[];decode_retries=[];local_verified=set();semaphore=asyncio.Semaphore(args.workers);source_pacer=SourceViewPacer()
 async with async_playwright() as pw:
  browser=await getattr(pw,args.engine).launch()
  context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  if args.http_bridge:
   bridge=fulfill_verified_request
   await context.route('https://**/*',bridge)
  if args.public_pages_files:await isolate_static_scope(context)
  page=await context.new_page();await page.goto(args.base,wait_until='domcontentloaded')
  await page.wait_for_function("document.querySelector('#total').textContent.includes('albums')")
  version=await page.locator('#app-version').inner_text();box=await page.locator('#app-version').bounding_box()
  assert box['x']>190 and box['y']<25 and box['height']<18,box
  albums=await page.evaluate('''async onlyPublic=>Promise.all(available().map(async a=>{
   const photos=validImages(a).map((p,i)=>({...p,grid_index:i})).filter(p=>!onlyPublic||p.url?.startsWith('stored-albums/'));
   return {id:a.id,images:await Promise.all(photos.map(async p=>({...p,url:p.ownerAlbum?await YuiPrivate.asset(p):p.url})))};
  })).then(rows=>rows.filter(a=>a.images.length))''',args.public_pages_files)
  if args.album:
   requested=set(args.album);albums=[a for a in albums if a['id'] in requested]
   assert {a['id'] for a in albums}==requested,'Requested album missing from actual gallery'
  if args.photo_selection:
   choices=json.loads(args.photo_selection.read_text())
   selected={a['id']:{p['number'] for p in a['replacements']} for a in choices['albums']}
   albums=[{**a,'images':[{**p,'grid_index':i} for i,p in enumerate(a['images']) if p['number'] in selected.get(a['id'],set())]} for a in albums if a['id'] in selected]
   assert {a['id'] for a in albums}==set(selected),'Selected work missing from actual gallery'
   assert all({p['number'] for p in a['images']}==selected[a['id']] for a in albums),'Selected photographs missing from actual gallery'
  await page.screenshot(path=str(args.out.with_suffix('.png')));await context.close()
  async def check(album):
   async with semaphore:
    # Release an album's decoded images and pending connections before the
    # next album. Thousands of files must not accumulate in one WebKit cache.
    album_context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    if args.http_bridge:await album_context.route('https://**/*',bridge)
    if args.public_pages_files:await isolate_static_scope(album_context)
    page=await album_context.new_page();js_errors=[]
    page.on('pageerror',lambda e:(js_errors.append(str(e)),print('BROWSER_JS_ERROR',album['id'],str(e),flush=True)))
    passed=0;hashes=0
    try:
     await page.goto(args.base,wait_until='domcontentloaded')
     await page.locator(f'.album[data-id="{album["id"]}"]').click()
     print('QA_ALBUM_BEGIN',album['id'],flush=True)
     for i,image in enumerate(album['images']):
      # Collection succeeded at 1s spacing; avoid synthetic bursts of CDN views.
      # Image decode timeout, URL, dimensions, SHA and total count stay unchanged.
      await source_pacer.wait(image['url'])
      grid_index=image.get('grid_index',i)
      if i and grid_index==album['images'][i-1].get('grid_index',i-1)+1:
       await page.locator('#next').click()
      else:
       if i:
        await page.locator('#close').click();await page.locator('#lightbox').wait_for(state='hidden')
       await page.locator('#detailphotos .photo').nth(grid_index).click()
      retries=await decode_image(page.locator('#full'))
      if retries:
       decode_retries.append({'id':album['id'],'number':image.get('number',i+1),'retries':retries})
       print('IMAGE_TRANSPORT_RETRY',album['id'],image.get('number',i+1),retries,flush=True)
      dims=await page.locator('#full').evaluate('(im)=>[im.naturalWidth,im.naturalHeight]')
      linked=await page.locator('#original').get_attribute('href')
      assert dims==[image['width'],image['height']],(album['id'],i+1,dims)
      assert linked==image['url'],(album['id'],i+1,linked,image['url'],await page.locator('#position').inner_text(),js_errors)
      orientation=await page.locator('#full').evaluate('''im=>{
       const r=im.getBoundingClientRect(),frame=im.parentElement.getBoundingClientRect();
       const transform=getComputedStyle(im).transform,m=new DOMMatrix(transform);
       return {transform,a:m.a,b:m.b,c:m.c,d:m.d,width:r.width,height:r.height,
        contained:r.left>=frame.left-1&&r.top>=frame.top-1&&r.right<=frame.right+1&&r.bottom<=frame.bottom+1,
        onScreen:r.left>=-1&&r.right<=innerWidth+1&&r.top>=64&&r.bottom<=innerHeight+1};
      }''')
      angle=image.get('display_rotation',0)
      if angle:
       sign=1 if angle==90 else -1
       assert abs(orientation['a'])<.001 and abs(orientation['d'])<.001 and abs(orientation['b']-sign)<.001 and abs(orientation['c']+sign)<.001,(album['id'],i+1,orientation)
       assert orientation['contained'] and orientation['onScreen'],(album['id'],i+1,orientation)
       assert abs(orientation['width']/orientation['height']-image['height']/image['width'])<.001
      else:
       assert orientation['transform']=='none',(album['id'],i+1,'previous photo rotation not cleared',orientation)
      passed+=1
      if passed%25==0:print('DECODE_PROGRESS',album['id'],passed,flush=True)
      if image['url'].startswith('stored-albums/'):
       digest=await page.locator('#original').evaluate("async a=>{const r=await fetch(a.href);if(!r.ok)throw Error(r.status);const b=await r.arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('')}")
       assert digest==image['sha256'];hashes+=1;local_verified.add(digest)
     await page.locator('#close').click();await page.locator('#lightbox').wait_for(state='hidden')
     await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
     assert not js_errors,js_errors
    except Exception as exc:
     errors.append({'id':album['id'],'decoded_before_failure':passed,'error':str(exc),'page_errors':js_errors})
    finally:
     result={'id':album['id'],'decoded_lightbox':passed,'original_link_sha256_checks':hashes}
     results.append(result);print('GALLERY_REAL_DECODE',args.engine,result,flush=True);await album_context.close()
  await asyncio.gather(*(check(a) for a in albums));await browser.close()
 report={'checked_at':datetime.now(timezone.utc).isoformat(),'base':args.base,'scope':'public_pages_files' if args.public_pages_files else 'selected_photographs' if args.photo_selection else 'selected_albums' if args.album else 'full_gallery','requested_album_ids':args.album,'engine':args.engine,'version':version,'viewport':[390,844],'iphone_real_device':False,'network':'TLS-verified requests bridge' if args.http_bridge else 'direct browser TLS','static_owner_fixture':args.public_pages_files,'private_cloud_verified':0,'albums':results,'decoded_image_entries':sum(r['decoded_lightbox'] for r in results),'browser_download_sha256_verified':0,'original_link_sha256_verified':sum(r['original_link_sha256_checks'] for r in results),'unique_original_link_sha256_verified':len(local_verified),'errors':errors}
 report['image_decode_retries']=decode_retries
 report['source_view_interval_seconds']={'cdn.imgcup.com':source_pacer.interval}
 report['paced_source_views']=source_pacer.views
 args.out.write_text(json.dumps(report,indent=2)+'\n')
 assert not errors,errors
 assert report['decoded_image_entries']==sum(len(a['images']) for a in albums)
 print('PUBLIC_PAGES_FILE_VIEWER_QA_PASS' if args.public_pages_files else 'SELECTED_GALLERY_MEDIA_QA_PASS' if args.album or args.photo_selection else 'ALL_GALLERY_MEDIA_QA_PASS',report['decoded_image_entries'],report['original_link_sha256_verified'],flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',default='http://localhost:8765/');p.add_argument('--engine',choices=['chromium','webkit'],default='chromium');p.add_argument('--out',type=Path,default=Path('yui-gallery-qa.json'));p.add_argument('--http-bridge',action='store_true');p.add_argument('--album',action='append',help='Verify selected acquired work IDs; omit for full gallery');p.add_argument('--photo-selection',type=Path,help='Check only explicitly selected replacement numbers; default still checks the full gallery');p.add_argument('--workers',type=int,choices=range(1,4),default=3);p.add_argument('--public-pages-files',action='store_true',help='CI scope: every physically published Pages file; private originals have separate deployed SHA QA');asyncio.run(run(p.parse_args()))
