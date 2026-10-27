"""Exercise browser history, fixed controls, aligned thumbnails and native gestures."""
import argparse,asyncio,json
import requests
from pathlib import Path
from playwright.async_api import async_playwright

async def run(args):
 async with async_playwright() as pw:
  browser=await getattr(pw,args.engine).launch()
  context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  if args.http_bridge:
   async def bridge(route):
    r=await asyncio.to_thread(lambda:requests.get(route.request.url,timeout=45,allow_redirects=False))
    headers={k:v for k,v in r.headers.items() if k.lower() not in ('content-encoding','content-length','transfer-encoding','connection')}
    await route.fulfill(status=r.status_code,headers=headers,body=r.content)
   await context.route('https://**/*',bridge)
  page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(args.base,wait_until='domcontentloaded');await page.locator('.album[data-id="teddy-bear97"]').wait_for()
  cover=page.locator('.album[data-id="teddy-bear97"]');card=await cover.bounding_box()
  # Same card width and columns; half of the previous portrait 3:4 height.
  assert abs(card['height']-card['width']*2/3)<1,card
  pub=await cover.locator('.publisher-sticker').bounding_box();edition=await cover.locator('.edition-sticker').bounding_box();quantity=await cover.locator('.album-count').bounding_box()
  assert pub['x']<edition['x'] and abs(pub['y']-edition['y'])<1
  assert quantity['y']>=pub['y']+pub['height'] and quantity['x']==pub['x']
  assert await cover.locator('.publisher-sticker').inner_text()=='SWEETBOX'
  assert await cover.locator('.edition-sticker').inner_text()=='웹판'
  assert await page.locator('.album[data-id="green91"] .edition-sticker').inner_text()=='AI 보정판'
  assert await page.locator('h1,.eyebrow').count()==0
  assert await page.locator('#zoom,#download,.lightbottom').count()==0
  assert await page.locator('.album[data-id="v04"]').count()==0
  assert await page.locator('.album[data-id="cn-miaohuaying"]').count()==0
  assert await page.locator('.album[data-id="sexiest18"]').count()==0
  assert not await page.locator('#search').is_visible()
  header=await page.locator('.topbar').bounding_box()
  assert header['height']<75,'Collapsed search still consumes a second header row'
  await page.locator('#search-toggle').click();await page.locator('#search-dialog').wait_for(state='visible')
  assert await page.locator('#search').evaluate('e=>e===document.activeElement')
  await page.locator('#search').fill('Teddy Bear')
  assert await page.locator('#albumgrid .album').count()==1
  await page.go_back();await page.locator('#search-dialog').wait_for(state='hidden')
  assert await page.locator('#albumgrid .album').count()==1
  await page.go_forward();await page.locator('#search-dialog').wait_for(state='visible')
  await page.locator('#search').fill('');await page.keyboard.press('Escape');await page.locator('#search-dialog').wait_for(state='hidden')
  await page.locator('#search-toggle').click();await page.locator('#search').fill('Teddy Bear');await page.locator('#search').press('Enter')
  await page.locator('#search-dialog').wait_for(state='hidden')
  await page.locator('#search-toggle').click();await page.locator('#search').fill('');await page.locator('#search-close').click()
  await page.locator('#search-dialog').wait_for(state='hidden')
  await page.locator('.album[data-id="teddy-bear97"]').click()
  await page.locator('#detail').wait_for(state='visible')
  first=await page.locator('#detailphotos .photo').nth(0).bounding_box();second=await page.locator('#detailphotos .photo').nth(1).bounding_box()
  assert abs(first['y']-second['y'])<1,(first,second)
  assert second['x']>first['x'] and first['width']>150
  assert abs(first['height']-first['width']*1.5)<1,'In-album photo grid changed dimensions'
  back=await page.locator('#back').bounding_box()
  await page.screenshot(path=str(args.out.with_suffix('.album.png')))
  await page.locator('#detailphotos .photo').first.click()
  await page.locator('#full').evaluate('(im)=>im.decode()')
  # Safari limits history writes. Hundreds of rapid changes must still render.
  await page.evaluate('for(let n=0;n<250;n++)step(1)')
  await page.locator('#full').evaluate('(im)=>im.decode()')
  assert (await page.locator('#position').inner_text()).startswith('57 / 97')
  close=await page.locator('#close').bounding_box()
  assert abs(back['x']-close['x'])<1 and abs(back['y']-close['y'])<1,(back,close)
  full=await page.locator('#full').bounding_box();link=await page.locator('#original').bounding_box()
  assert link['x']>=full['x'] and link['x']+link['width']<=full['x']+full['width']+1
  assert link['y']>=full['y'] and link['y']+link['height']<=full['y']+full['height']+1
  assert await page.locator('#full').evaluate("im=>{const e=new MouseEvent('contextmenu',{bubbles:true,cancelable:true});return im.dispatchEvent(e)&&!e.defaultPrevented}")
  pinch=False
  if args.engine=='chromium':
   client=await context.new_cdp_session(page)
   # Headless Chrome cannot deliver the OS pinch recognizer reliably.
   # Emulate browser viewport magnification and ensure app handlers allow it.
   assert await page.locator('#full').evaluate("im=>getComputedStyle(im).touchAction")== 'auto'
   assert await page.locator('meta[name=viewport]').get_attribute('content') == 'width=device-width,initial-scale=1,viewport-fit=cover'
   await client.send('Emulation.setPageScaleFactor',{'pageScaleFactor':2})
   await page.wait_for_function('visualViewport.scale>1.3')
   pinch=await page.evaluate('visualViewport.scale')
   await client.send('Emulation.setPageScaleFactor',{'pageScaleFactor':1})
  # Multi-touch and edge swipes must never turn the page or cancel native input.
  before=await page.locator('#position').inner_text()
  allowed=await page.locator('#full').evaluate('''im=>{
   const fire=(type,points,changed=points)=>{const e=new Event(type,{bubbles:true,cancelable:true});const touches=ps=>ps.map((p,i)=>({identifier:i,target:im,clientX:p[0],clientY:p[1]}));Object.defineProperties(e,{touches:{value:touches(points)},changedTouches:{value:touches(changed)}});return im.dispatchEvent(e)&&!e.defaultPrevented};
   return [fire('touchstart',[[150,300],[250,300]]),fire('touchend',[[300,300]],[[50,300]]),fire('touchend',[],[[300,300]]),fire('touchstart',[[5,300]]),fire('touchend',[],[[200,300]])].every(Boolean)
  }''')
  assert allowed and before==await page.locator('#position').inner_text()
  await page.screenshot(path=str(args.out.with_suffix('.viewer.png')))
  await page.go_back();await page.locator('#lightbox').wait_for(state='hidden')
  assert await page.locator('#detail').is_visible()
  await page.go_forward();await page.locator('#lightbox').wait_for(state='visible')
  await page.locator('#close').click();await page.locator('#lightbox').wait_for(state='hidden')
  await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
  await page.go_forward();await page.locator('#detail').wait_for(state='visible')
  await page.go_back();await page.locator('#browse').wait_for(state='visible')
  # No history trap at the gallery root: browser Back can leave this app.
  await page.goto('about:blank');await page.goto(args.base,wait_until='domcontentloaded')
  await page.wait_for_function("history.state?.yui")
  await page.go_back();assert page.url=='about:blank',page.url
  # Direct album links still have a working in-app back button.
  for alias,canonical,count in [('v04','teddy-bear97',97),('v12','kuro-yui58',58),('v15','dec2023-199',199)]:
   await page.goto(args.base+'#'+alias,wait_until='domcontentloaded')
   # Loading a deep link starts the app; a same-document hash change does not.
   await page.reload(wait_until='domcontentloaded');await page.locator('#detail').wait_for(state='visible')
   assert await page.locator('#detailphotos .photo').count()==count
   assert canonical in page.url
  await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
  await page.locator('[data-filter="all"]').click()
  assert await page.locator('.album[data-id="sexiest18"]').count()==0
  for aid in ['kuro-yui58','yui-vol2-42','yui-vol3-106','blackroom145','dec2023-199','pussylet41-82','artgravia663-ai32']:
   card=page.locator('.album[data-id="'+aid+'"]');assert await card.count()==1
   assert '미수집' not in await card.inner_text()
  await page.locator('.album[data-id="yui-vol2-42"]').click();await page.locator('#detail').wait_for(state='visible')
  assert await page.locator('#detailphotos .photo').count()==42
  await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
  # A cached or concurrent manifest must not bring a user-excluded model back.
  excluded=json.loads(Path(__file__).with_name('identity-exclusions.json').read_text())
  stale={'albums':[{'id':'sexiest18','title':'Excluded stale fixture','status':'verified_collected_individual_files_source_hosted_online_view','images':[]},
                   {'id':'renamed-excluded-fixture','title':'Renamed stale fixture','status':'verified_collected_individual_files_source_hosted_online_view','images':[{'sha256':excluded['excluded_image_sha256'][-1]}]}]}
  await context.route('**/additional-source-albums.json',lambda route:route.fulfill(json=stale))
  await page.reload(wait_until='domcontentloaded');await page.wait_for_function('history.state?.yui')
  assert await page.evaluate("stored.every(a=>!['sexiest18','renamed-excluded-fixture'].includes(a.id))")
  await page.locator('[data-filter="all"]').click()
  assert await page.locator('.album[data-id="sexiest18"],.album[data-id="renamed-excluded-fixture"]').count()==0
  assert not errors,errors
  result={'engine':args.engine,'viewport':[390,844],'history_back_forward':True,'rapid_photo_changes':250,'root_can_leave':True,'fixed_back_close':True,'aligned_two_columns':True,'album_card_height_halved':True,'publisher_count_edition_stickers':True,'detail_photo_grid_unchanged':True,'collapsed_search_popup_back_forward_escape_submit_close':True,'stale_wrong_model_manifest_blocked':True,'native_contextmenu_allowed':True,'emulated_browser_zoom_scale':pinch,'physical_pinch_verified':False,'multitouch_and_edge_not_intercepted':True,'iphone_real_device':False}
  args.out.write_text(json.dumps(result,indent=2)+'\n');print('MOBILE_NAVIGATION_QA_PASS',json.dumps(result),flush=True)
  await browser.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://localhost:8765/');p.add_argument('--engine',choices=['chromium','webkit'],default='chromium');p.add_argument('--http-bridge',action='store_true');p.add_argument('--out',type=Path,default=Path('yui-navigation-qa.json'));asyncio.run(run(p.parse_args()))
