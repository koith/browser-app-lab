"""Decode and download the exact newly stored bytes through deployed galleries.

No mocked media, owner cookies, synthetic pass, weakened SHA, or longer image
deadline. A TLS-verifying transport bridge is optional only for managed local QA.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/yui-gallery'))
from browser_http_bridge import fulfill_verified_request

SITE='https://koith.github.io/browser-app-lab/apps'


async def run(args):
    document=json.loads(args.selection.read_text())
    selected=document['selection'][args.model]
    if not selected:raise ValueError('No exact stored photographs selected')
    report={'model':args.model,'browser':args.browser,'real_iphone_device':False,
            'deployed_url':f'{SITE}/{args.model}-gallery/',
            'TLS_verified_bridge':args.http_bridge,'photos':[],'page_errors':[]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as pw:
        browser=await getattr(pw,args.browser).launch()
        context=await browser.new_context(viewport={'width':390,'height':844},
            device_scale_factor=2,is_mobile=True,has_touch=True,locale='ko-KR',accept_downloads=True)
        if args.http_bridge:await context.route('https://**/*',fulfill_verified_request)
        page=await context.new_page()
        page.on('pageerror',lambda error:report['page_errors'].append(str(error)[:220]))
        try:
            # Pages deployment may finish after metadata publication. Poll only
            # its public ledger, never pretend an old deployment is current.
            deadline=time.monotonic()+300
            while True:
                await page.goto(report['deployed_url'],wait_until='domcontentloaded',timeout=60000)
                await page.wait_for_function('typeof stored!=="undefined" && stored.length>0',timeout=45000)
                present=await page.evaluate('''selection=>selection.every(a=>{
                    const saved=stored.find(x=>x.id===a.id);
                    return !!saved && a.images.every(p=>validImages(saved).some(q=>q.number===p.number&&q.sha256===p.sha256));
                })''',selected)
                if present:break
                if time.monotonic()>=deadline:raise AssertionError('Exact newly stored SHA not in deployed gallery')
                await asyncio.sleep(3)
            report['version']=await page.locator('#app-version').inner_text()
            report['inventory']=await page.evaluate('''()=>({albums:stored.length,
                displayed:stored.reduce((n,a)=>n+validImages(a).length,0),
                distinct_sha:new Set(stored.flatMap(a=>validImages(a).map(p=>p.sha256))).size,
                owner_rows:ownerStored.reduce((n,a)=>n+validImages(a).length,0)})''')
            for album in selected:
                aid=album['id'];card=page.locator(f'#albumgrid .album[data-id="{aid}"]')
                await card.scroll_into_view_if_needed()
                await page.wait_for_function('''id=>{const im=document.querySelector('#albumgrid [data-id="'+id+'"] img');
                    return im?.complete&&im.naturalWidth>=160}''',arg=aid,timeout=105000)
                await card.click();await page.locator('#detail').wait_for(state='visible')
                for expected in album['images']:
                    number=expected['number']
                    position=await page.evaluate('''([id,n])=>photosFor(stored.find(a=>a.id===id))
                        .findIndex(p=>p.number===n)''',[aid,number])
                    assert position>=0,(aid,number,'saved slot missing')
                    photo=page.locator(f'#detailphotos .photo[data-i="{position}"]')
                    await photo.scroll_into_view_if_needed()
                    await page.wait_for_function('''i=>{const im=document.querySelector('#detailphotos .photo[data-i="'+i+'"] img');
                        return im?.complete&&im.naturalWidth>=160}''',arg=position,timeout=105000)
                    await photo.click();await page.locator('#lightbox').wait_for(state='visible')
                    await page.wait_for_function('''()=>{const im=document.querySelector('#full');
                        return im?.complete&&im.naturalWidth>=160}''',timeout=105000)
                    size=await page.locator('#full').evaluate('im=>[im.naturalWidth,im.naturalHeight]')
                    assert size==[expected['width'],expected['height']],(aid,number,size)
                    original=await page.locator('#original').get_attribute('href')
                    assert original and '/api/' in original,(aid,number,'not owner storage media')
                    async with page.expect_download(timeout=105000) as pending:
                        await page.evaluate('''url=>{const a=document.createElement('a');
                            a.href=url+(url.includes('?')?'&':'?')+'download=true';a.download='photo';
                            document.body.append(a);a.click();a.remove()}''',original)
                    download=await pending.value
                    path=await download.path();raw=Path(path).read_bytes()
                    assert len(raw)==expected['bytes'],(aid,number,'download length mismatch')
                    assert hashlib.sha256(raw).hexdigest()==expected['sha256'],(aid,number,'download SHA mismatch')
                    report['photos'].append({'album':aid,'number':number,'dimensions':size,
                        'thumbnail_decoded':True,'lightbox_decoded':True,'download_sha256_verified':True})
                    print('DEPLOYED_EXACT_ORIGINAL_PASS',args.model,args.browser,aid,number,flush=True)
                    if len(report['photos'])==1:await page.screenshot(path=str(args.out.with_suffix('.png')))
                    await page.locator('#close').click();await page.locator('#lightbox').wait_for(state='hidden')
                await page.locator('#back').click();await page.locator('#browse').wait_for(state='visible')
            await page.reload(wait_until='domcontentloaded')
            await page.wait_for_function('document.querySelectorAll("#albumgrid .album").length>0',timeout=45000)
            assert not report['page_errors'],report['page_errors']
            report['reload_pass']=True;report['success']=True
        finally:
            args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            await context.close();await browser.close()
    assert len(report['photos'])==sum(len(a['images']) for a in selected)
    print('DEPLOYED_PHYSICAL_PHOTOS_QA_PASS',json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',choices=['mimmi','yui'],required=True)
    parser.add_argument('--browser',choices=['chromium','webkit'],required=True)
    parser.add_argument('--selection',type=Path,default=Path(__file__).parent/'verification/new-physical-photos-2026-10-30.json')
    parser.add_argument('--http-bridge',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    asyncio.run(run(parser.parse_args()))
