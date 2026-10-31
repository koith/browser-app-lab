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
import re
import requests

from playwright.async_api import async_playwright,Error as PlaywrightError

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/yui-gallery'))
from browser_http_bridge import fulfill_verified_request

SITE='https://koith.github.io/browser-app-lab/apps'


async def current_card(page,selector,click=False):
    # The background owner catalog replaces album cards after first paint.
    # Refetch detached WebKit nodes, retaining the same action/image deadline.
    deadline=time.monotonic()+30
    while True:
        try:
            locator=page.locator(selector)
            await locator.scroll_into_view_if_needed(timeout=4000)
            if click:await page.locator(selector).click(timeout=4000)
            return
        except PlaywrightError as error:
            if time.monotonic()>=deadline or not any(word in str(error).lower() for word in ('not attached','detached','not stable')):raise
            await asyncio.sleep(.15)


async def run(args):
    document=json.loads(args.selection.read_text())
    selected=document['selection'][args.model]
    resumed={}
    if args.since_commit:
        if not re.fullmatch('[a-f0-9]{40}',args.since_commit):raise ValueError('Exact baseline commit required')
        def owner(ref):
            url=f'https://raw.githubusercontent.com/koith/browser-app-lab/{ref}/apps/{args.model}-gallery/owner-index.json'
            r=requests.get(url,timeout=(12,45));r.raise_for_status();d=r.json()
            if d.get('model')!=args.model:raise ValueError('Wrong model in deployed comparison')
            return d
        before=await asyncio.to_thread(owner,args.since_commit)
        after=await asyncio.to_thread(owner,args.current_commit or 'main')
        old={(a['id'],p['number']):p['sha256'] for a in before['albums'] for p in a['images']}
        selected=[{'id':a['id'],'images':[p for p in a['images'] if old.get((a['id'],p['number']))!=p['sha256']]} for a in after['albums']]
        selected=[a for a in selected if a['images']]
        if args.checkpoint:
            from native_qa_checkpoint import resume_keys
            raw=args.checkpoint.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=args.checkpoint_sha:
                raise ValueError('Checkpoint was not independently verified by the prerequisite job')
            resumed=resume_keys(json.loads(raw),before,after,args.model,args.browser,args.since_commit)
    all_selected=sum(len(a['images']) for a in selected)
    html=(ROOT/'apps'/(args.model+'-gallery')/'index.html').read_text()
    expected_version=re.search(r'id="app-version"[^>]*>([^<]+)',html).group(1)
    version_numbers=lambda value:tuple(int(n) for n in re.findall(r'\d+',value))
    offset=0;sharded=[]
    for album in selected:
        images=[]
        for photo in album['images']:
            if offset%args.shards==args.shard:images.append(photo)
            offset+=1
        if images:sharded.append({**album,'images':images})
    selected=sharded
    report={'model':args.model,'browser':args.browser,'real_iphone_device':False,
            'deployed_url':f'{SITE}/{args.model}-gallery/',
            'TLS_verified_bridge':args.http_bridge,'photos':[],'page_errors':[],
            'resumed_photos':[],
            'since_commit':args.since_commit,'all_new_or_upgraded_rows':all_selected,
            'current_owner_index_ref':args.current_commit or 'main',
            'shard':args.shard,'shards':args.shards}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if not selected:
        report['no_selected_new_photographs']=True
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('NO_NEW_PHOTOGRAPHS_IN_THIS_SHARD',args.model,args.shard,flush=True)
        return
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
                routes=await page.evaluate('''selection=>selection.flatMap(a=>a.images.map(p=>{
                    let work=stored.find(w=>validImages(w).some(q=>q.ownerAlbum===a.id&&
                        (q.storageNumber??q.number)===p.number&&q.sha256===p.sha256));
                    let q=work&&validImages(work).find(q=>q.ownerAlbum===a.id&&
                        (q.storageNumber??q.number)===p.number&&q.sha256===p.sha256);
                    let identical=false;
                    if(!q){work=stored.find(w=>w.id===canonicalId(a.id)&&validImages(w).some(q=>q.sha256===p.sha256));
                        q=work&&validImages(work).find(q=>q.sha256===p.sha256);identical=!!q;}
                    return q?{...p,physical_album:a.id,gallery_album:work.id,
                        display_number:q.number,byte_identical_existing_display:identical}:null;
                }))''',selected)
                present=all(routes)
                version=await page.locator('#app-version').inner_text()
                duplicates=await page.evaluate('''()=>stored.reduce((n,a)=>{
                    const sha=validImages(a).map(p=>p.sha256);return n+sha.length-new Set(sha).size},0)''')
                if present and version_numbers(version)>=version_numbers(expected_version) and not duplicates:break
                if time.monotonic()>=deadline:raise AssertionError('Exact newly stored SHA not in deployed gallery')
                await asyncio.sleep(3)
            report['version']=await page.locator('#app-version').inner_text()
            report['work_counts']=await page.evaluate('''()=>stored.map(a=>({id:a.id,
                images_count:validImages(a).length,distinct_sha:new Set(validImages(a).map(p=>p.sha256)).size}))''')
            report['inventory']=await page.evaluate('''()=>({albums:stored.length,
                displayed:stored.reduce((n,a)=>n+validImages(a).length,0),
                distinct_sha:new Set(stored.flatMap(a=>validImages(a).map(p=>p.sha256))).size,
                owner_rows:ownerStored.reduce((n,a)=>n+validImages(a).length,0)})''')
            routed={}
            for photo in routes:
                proof=resumed.get((photo['physical_album'],photo['number']))
                if proof:
                    report['resumed_photos'].append({'album':photo['physical_album'],'number':photo['number'],
                        'prior_successful_native_job':proof,'current_gallery_exact_SHA_route_verified':True})
                else:routed.setdefault(photo['gallery_album'],[]).append(photo)
            selected=[{'id':aid,'images':photos} for aid,photos in routed.items()]
            for album in selected:
                aid=album['id'];card=f'#albumgrid .album[data-id="{aid}"]'
                await current_card(page,card)
                await page.wait_for_function('''id=>{const im=document.querySelector('#albumgrid [data-id="'+id+'"] img');
                    return im?.complete&&im.naturalWidth>=160}''',arg=aid,timeout=105000)
                await current_card(page,card,click=True);await page.locator('#detail').wait_for(state='visible')
                for expected in album['images']:
                    number=expected['number']
                    position=await page.evaluate('''([id,n,sha])=>photosFor(stored.find(a=>a.id===id))
                        .findIndex(p=>p.number===n&&p.sha256===sha)''',[aid,expected['display_number'],expected['sha256']])
                    assert position>=0,(aid,number,'saved slot missing')
                    photo=page.locator(f'#detailphotos .photo[data-i="{position}"]')
                    await current_card(page,f'#detailphotos .photo[data-i="{position}"]')
                    await page.wait_for_function('''i=>{const im=document.querySelector('#detailphotos .photo[data-i="'+i+'"] img');
                        return im?.complete&&im.naturalWidth>=160}''',arg=position,timeout=105000)
                    await current_card(page,f'#detailphotos .photo[data-i="{position}"]',click=True)
                    await page.locator('#lightbox').wait_for(state='visible')
                    await page.wait_for_function('''()=>{const im=document.querySelector('#full');
                        return im?.complete&&im.naturalWidth>=160}''',timeout=105000)
                    size=await page.locator('#full').evaluate('im=>[im.naturalWidth,im.naturalHeight]')
                    assert size==[expected['width'],expected['height']],(aid,number,size)
                    original=await page.locator('#original').get_attribute('href')
                    assert original and '/api/' in original,(aid,number,'not owner storage media')
                    # Use the actual photo-open control. WebKit ignores the
                    # download attribute across origins and can show an image
                    # inline despite Content-Disposition. In the original tab,
                    # native image saving is same-origin; verify that real path.
                    async with page.expect_popup(timeout=105000) as opened:
                        await page.locator('#original').click()
                    original_page=await opened.value
                    await original_page.wait_for_load_state('domcontentloaded',timeout=105000)
                    await original_page.wait_for_function('''()=>{const im=document.images[0];
                        return im?.complete&&im.naturalWidth>=160}''',timeout=105000)
                    tab_size=await original_page.locator('img').first.evaluate('im=>[im.naturalWidth,im.naturalHeight]')
                    assert tab_size==[expected['width'],expected['height']],(aid,number,'original tab',tab_size)
                    # Chromium already supports this attachment from the
                    # gallery; preserve its verified path. WebKit needs the
                    # same-origin image tab for its native download attribute.
                    download_page=original_page if args.browser=='webkit' else page
                    await download_page.bring_to_front()
                    diagnostic={'album':aid,'number':number,'browser':args.browser,'responses':[]}
                    def attachment_response(response,item=diagnostic):
                        if 'download=true' in response.url:
                            item['responses'].append({'status':response.status,
                                'content_type':response.headers.get('content-type'),
                                'attachment':response.headers.get('content-disposition','').lower().startswith('attachment;')})
                    download_page.on('response',attachment_response)
                    download_url=original+('&' if '?' in original else '?')+'download=true'
                    received=asyncio.get_running_loop().create_future()
                    def exact_download(download):
                        # WebKit can attribute an image-tab download to its
                        # opener. Require the actual event for this exact URL
                        # from either of the two real pages, then check bytes.
                        if download.url==download_url and not received.done():received.set_result(download)
                    event_pages={page,original_page}
                    for source_page in event_pages:source_page.on('download',exact_download)
                    await download_page.evaluate('''url=>{const a=document.createElement('a');
                            a.id='qa-original-download';a.textContent='검증용 원본 저장';
                            a.style='position:fixed;top:80px;left:12px;z-index:999999';
                            a.href=url+(url.includes('?')?'&':'?')+'download=true';a.download='photo';
                            document.body.append(a)}''',original)
                    try:
                        await download_page.locator('#qa-original-download').click()
                        download=await asyncio.wait_for(received,timeout=105)
                        path=await download.path();raw=Path(path).read_bytes()
                    except Exception:
                        report['failed_download']=diagnostic
                        raise
                    finally:
                        download_page.remove_listener('response',attachment_response)
                        for source_page in event_pages:source_page.remove_listener('download',exact_download)
                    assert len(raw)==expected['bytes'],(aid,number,'download length mismatch')
                    assert hashlib.sha256(raw).hexdigest()==expected['sha256'],(aid,number,'download SHA mismatch')
                    if not download_page.is_closed():await download_page.locator('#qa-original-download').evaluate('a=>a.remove()')
                    if not original_page.is_closed():await original_page.close()
                    await page.bring_to_front()
                    report['photos'].append({'album':expected['physical_album'],'number':number,'dimensions':size,
                        'gallery_album':aid,'display_number':expected['display_number'],
                        'byte_identical_existing_display':expected['byte_identical_existing_display'],
                        'thumbnail_decoded':True,'lightbox_decoded':True,'original_tab_decoded':True,
                        'download_event_page':'original_tab' if download.page==original_page else 'gallery',
                        'download_sha256_verified':True})
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


def parse_cli(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',choices=['mimmi','yui'],required=True)
    parser.add_argument('--browser',choices=['chromium','webkit'],required=True)
    parser.add_argument('--selection',type=Path,default=Path(__file__).parent/'verification/new-physical-photos-2026-10-30.json')
    parser.add_argument('--http-bridge',action='store_true')
    parser.add_argument('--since-commit',help='Exact public owner-index baseline; verify every changed/new SHA since it')
    parser.add_argument('--current-commit',help='Pin the current owner-index snapshot for consistent matrix coverage')
    parser.add_argument('--checkpoint',type=Path,help='Previously successful native jobs, verified by prerequisite CI')
    parser.add_argument('--checkpoint-sha',help='Exact checkpoint digest emitted by independent source-job verification')
    parser.add_argument('--shard',type=int,default=0)
    parser.add_argument('--shards',type=int,default=1)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.current_commit and not args.since_commit:parser.error('Current snapshot requires an exact baseline')
    for ref in [args.since_commit,args.current_commit]:
        if ref is not None and not re.fullmatch('[a-f0-9]{40}',ref):parser.error('Exact owner-index commit required')
    if bool(args.checkpoint)!=bool(args.checkpoint_sha) or (args.checkpoint and not args.since_commit):
        parser.error('A checkpoint requires its independent digest and exact baseline')
    if args.checkpoint_sha and not re.fullmatch('[a-f0-9]{64}',args.checkpoint_sha):
        parser.error('Invalid independently verified checkpoint digest')
    if not 1<=args.shards<=24 or not 0<=args.shard<args.shards:parser.error('Invalid bounded QA shard')
    return args


if __name__=='__main__':
    asyncio.run(run(parse_cli()))
