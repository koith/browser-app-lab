"""Exercise browser history, fixed controls, aligned thumbnails and native gestures."""
import argparse,asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

async def run(args):
 async with async_playwright() as pw:
  browser=await getattr(pw,args.engine).launch()
  context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
  page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(args.base,wait_until='domcontentloaded');await page.locator('.album[data-id="v04"]').wait_for()
  assert await page.locator('h1,.eyebrow').count()==0
  assert await page.locator('#zoom,#download,.lightbottom').count()==0
  await page.locator('.album[data-id="v04"]').click()
  await page.locator('#detail').wait_for(state='visible')
  first=await page.locator('#detailphotos .photo').nth(0).bounding_box();second=await page.locator('#detailphotos .photo').nth(1).bounding_box()
  assert abs(first['y']-second['y'])<1,(first,second)
  assert second['x']>first['x'] and first['width']>150
  back=await page.locator('#back').bounding_box()
  await page.screenshot(path=str(args.out.with_suffix('.album.png')))
  await page.locator('#detailphotos .photo').first.click()
  await page.locator('#full').evaluate('(im)=>im.decode()')
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
   const fire=(type,points,changed=points)=>{const e=new TouchEvent(type,{bubbles:true,cancelable:true,touches:points.map((p,i)=>new Touch({identifier:i,target:im,clientX:p[0],clientY:p[1]})),changedTouches:changed.map((p,i)=>new Touch({identifier:i,target:im,clientX:p[0],clientY:p[1]}))});return im.dispatchEvent(e)&&!e.defaultPrevented};
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
  await page.goto(args.base+'#v04',wait_until='domcontentloaded');await page.locator('#detail').wait_for(state='visible')
  await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
  assert not errors,errors
  result={'engine':args.engine,'viewport':[390,844],'history_back_forward':True,'root_can_leave':True,'fixed_back_close':True,'aligned_two_columns':True,'native_contextmenu_allowed':True,'emulated_browser_zoom_scale':pinch,'physical_pinch_verified':False,'multitouch_and_edge_not_intercepted':True,'iphone_real_device':False}
  args.out.write_text(json.dumps(result,indent=2)+'\n');print('MOBILE_NAVIGATION_QA_PASS',json.dumps(result),flush=True)
  await browser.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://localhost:8765/');p.add_argument('--engine',choices=['chromium','webkit'],default='chromium');p.add_argument('--out',type=Path,default=Path('yui-navigation-qa.json'));asyncio.run(run(p.parse_args()))
