#!/usr/bin/env python3
"""Actual Pages originals and UI; candidate evidence is never operational PASS."""
import argparse
import faulthandler
from collections import defaultdict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
from PIL import Image
from playwright.sync_api import sync_playwright
from pages_deployment_identity import validate as validate_deployment_identity

BASE='https://koith.github.io/browser-app-lab/apps'
ROOT=Path(__file__).resolve().parents[2]


def candidate_route(text,mime):
    def handle(route):route.fulfill(status=200,content_type=mime,body=text)
    return handle


def signature(p):return (p['sha256'],p['bytes'],p['width'],p['height'])


def cross_candidates(model):
    folder=ROOT/f'apps/{model}-gallery'
    physical=json.loads((folder/'stored-albums.json').read_text())
    owner=json.loads((folder/'owner-index.json').read_text())
    by_signature=defaultdict(list);by_url={}
    for album in physical['albums']:
        for photo in album['images']:
            if not re.fullmatch(r'stored-albums/'+re.escape(album['id'])+r'/[a-zA-Z0-9._-]+\.(?:jpe?g|png|webp|avif)',photo['url']):
                raise ValueError('Physical source is not an existing model-local Pages file')
            by_signature[signature(photo)].append((album['id'],photo))
            by_url[photo['url']]=photo
    candidates=[]
    for album in owner['albums']:
        for photo in album['images']:
            copies=by_signature.get(signature(photo),[])
            if copies and not any(aid==album['id'] for aid,_ in copies):
                candidates.append({'owner_album':album['id'],'owner_number':photo['number'],
                    **{k:photo[k] for k in ('sha256','bytes','width','height')}})
    if not candidates:raise ValueError('No actual cross-album owner originals were selected')
    return candidates,by_url


def exact_bytes(context,url,photo):
    r=context.request.get(url,timeout=45000)
    assert r.status==200,('actual image HTTP',r.status,url)
    raw=r.body()
    if hasattr(r,'dispose'):r.dispose()
    assert len(raw)==photo['bytes'] and hashlib.sha256(raw).hexdigest()==photo['sha256'],('actual image SHA/length',url)
    with Image.open(io.BytesIO(raw)) as image:image.verify()
    with Image.open(io.BytesIO(raw)) as image:
        image.load();assert image.size==(photo['width'],photo['height']),('actual image dimensions',url)
    return len(raw)


def deployed_sources(context,root,model):
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    stamp=context.request.get('https://koith.github.io/browser-app-lab/gallery-deployment.json',timeout=35000)
    assert stamp.status==200,'Actual Pages deployment source stamp is missing'
    validate_deployment_identity(stamp.body(),source)
    names=['index.html','saved-photo-union.js','owner-media.js','owner-index.json',
           'stored-albums.json','album-aliases.json']
    if model=='mimmi':names.append('album-grouping.js')
    result={}
    for name in names:
        r=context.request.get(root+name,timeout=35000)
        assert r.status==200,(model,name,'deployed source HTTP',r.status)
        expected=(ROOT/f'apps/{model}-gallery'/name).read_bytes()
        sha=hashlib.sha256(r.body()).hexdigest()
        assert sha==hashlib.sha256(expected).hexdigest(),(model,name,'deployed source differs from exact checkout')
        result[name]=sha
    return result


def scroll_to_real_card(locator):
    # Native QA timed out in WebKit's protocol preflight before scrolling.
    # Use the page's normal instant scroll. Native touch below independently
    # verifies the actual geometry/hit target; image checks remain unchanged.
    locator.evaluate("node=>node.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'})")
    locator.wait_for(state='visible',timeout=25000)
    assert locator.evaluate('''node=>{const r=node.getBoundingClientRect();
        return node.isConnected&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight}'''), 'Card is not visible after real scroll'


def native_touch(page,locator):
    """Real iPhone-style pointer input with explicit geometry/hit guards.

    Do not force clicks or call application handlers from JavaScript. Record
    three actual rendered bounds and require a stable, enabled, unobstructed
    touch target before sending the browser's native touchscreen event.
    """
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        state=locator.evaluate('''async node=>{
        const rect=()=>{const r=node.getBoundingClientRect();return [r.x,r.y,r.width,r.height]};
        const bounds=[rect()];
        for(let i=0;i<2;i++){await new Promise(resolve=>setTimeout(resolve,50));bounds.push(rect())}
        const last=bounds[2],x=last[0]+last[2]/2,y=last[1]+last[3]/2;
        const tolerance=.5/(devicePixelRatio||1),style=getComputedStyle(node),hit=document.elementFromPoint(x,y);
        return {bounds,x,y,tolerance,
            stable:bounds.every(b=>b.every((n,i)=>Math.abs(n-last[i])<=tolerance)),
            visible:node.isConnected&&last[2]>0&&last[3]>0&&x>=0&&x<innerWidth&&y>=0&&y<innerHeight&&
                style.visibility==='visible'&&style.display!=='none'&&style.pointerEvents!=='none',
            enabled:!node.matches(':disabled'),hit:!!hit&&(hit===node||node.contains(hit)),
            documentVisible:document.visibilityState==='visible'};
        }''')
        if all(state[k] for k in ('stable','visible','enabled','hit','documentVisible')):break
        # Like native actionability, wait for an in-flight history/viewport
        # restoration to settle. Keep the same 25s bound and all hit guards.
        if not state['visible']:
            locator.evaluate("node=>node.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'})")
    assert all(state[k] for k in ('stable','visible','enabled','hit','documentVisible')),('Native touch target is not actionable',state)
    page.touchscreen.tap(state['x'],state['y'])


def navigate_album(page,album):
    if page.locator('#lightbox.open').count():
        native_touch(page,page.locator('#close'))
        page.wait_for_selector('#lightbox.open',state='hidden',timeout=25000)
    if page.evaluate("id=>!document.querySelector('#detail').hidden && detailAlbum?.id===id",album):return
    if not page.locator('#detail').is_hidden():
        native_touch(page,page.locator('#back'))
        page.wait_for_selector('#detail',state='hidden',timeout=25000)
    card=page.locator('#albumgrid .album[data-id="'+album+'"]')
    scroll_to_real_card(card)
    native_touch(page,card)
    page.wait_for_function("id=>!document.querySelector('#detail').hidden && detailAlbum?.id===id",arg=album,timeout=25000)


def decoded(page,root,target):
    expected=root+target['url']
    page.wait_for_function('''wanted=>{
        const img=document.querySelector('#full');
        return document.querySelector('#lightbox.open') && img && img.complete &&
            img.naturalWidth>=160 && new URL(img.currentSrc||img.src,location.href).href===wanted;
    }''',arg=expected,timeout=45000)
    size=page.locator('#full').evaluate('im=>[im.naturalWidth,im.naturalHeight]')
    assert size==[target['width'],target['height']],('actual lightbox pixels',target,size)
    assert page.locator('#lightbox .version-chip').inner_text()==page.locator('#app-version').inner_text(), 'Viewer and main version labels differ'
    return expected


def open_photo(page,root,target):
    navigate_album(page,target['album'])
    page.wait_for_function('''q=>[...document.querySelectorAll('#detailphotos .photo')].some(n=>Number(n.dataset.i)===q)''',arg=target['index'],timeout=25000)
    card=page.locator('#detailphotos .photo[data-i="'+str(target['index'])+'"]')
    scroll_to_real_card(card)
    card.locator('img').wait_for(state='visible',timeout=25000)
    page.wait_for_function('''q=>{
        const image=document.querySelector('#detailphotos .photo[data-i="'+q.index+'"] img');
        return image?.complete && image.naturalWidth===q.width && image.naturalHeight===q.height &&
            new URL(image.currentSrc||image.src,location.href).href===q.url;
    }''',arg={**target,'url':root+target['url']},timeout=45000)
    # Lazy image loads and history restoration can change the viewport while
    # decoding. Reposition the actual decoded card before native touch.
    scroll_to_real_card(card)
    native_touch(page,card)
    decoded(page,root,target)


def select_representatives(targets,limit):
    grouped=defaultdict(list)
    for t in targets:grouped[t['album']].append(t)
    selected=[]
    while len(selected)<limit and any(grouped.values()):
        for key in grouped:
            if grouped[key] and len(selected)<limit:selected.append(grouped[key].pop(0))
    return selected


def inspect_covers(page):
    cards=page.locator('#albumgrid .album')
    for i in range(0,cards.count(),4):
        scroll_to_real_card(cards.nth(i))
        page.wait_for_timeout(120)
    page.wait_for_timeout(1500)
    return cover_snapshot(page)


def cover_snapshot(page):
    return page.evaluate('''()=>{
        const rows=[...document.querySelectorAll('#albumgrid .album')].map(card=>{
            const img=card.querySelector('img');return {album:card.dataset.id,
                decoded:!!img?.complete&&img.naturalWidth>0,
                failed:!!img?.complete&&!!img.src&&img.naturalWidth===0,
                pending:!img?.complete,width:img?.naturalWidth||0,height:img?.naturalHeight||0};});
        return {albums:rows.length,decoded:rows.filter(r=>r.decoded).length,
            failed:rows.filter(r=>r.failed).length,pending:rows.filter(r=>r.pending).length,rows};
    }''')


def denied_catalog_real_local_photos(browser,model,overlay):
    """Controlled transport failures, real unchanged Pages image bytes."""
    root=f'{BASE}/{model}-gallery/'
    context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,
        has_touch=True,service_workers='block')
    page=context.new_page();calls=[]
    page.on('request',lambda request:calls.append(request.url)
        if 'onrender.com/api/' in request.url and request.url.endswith('/catalog') else None)
    try:
        if overlay:
            for name in ['index.html','saved-photo-union.js']+(['album-grouping.js'] if model=='mimmi' else []):
                text=(ROOT/f'apps/{model}-gallery'/name).read_text()
                page.route(root if name=='index.html' else '**/'+name+'*',
                    candidate_route(text,'text/html' if name=='index.html' else 'application/javascript'))
        page.route('**/owner-index.json',lambda route:route.fulfill(status=403,body='controlled owner-index denial'))
        page.route('https://mimmi-private-gallery-free.onrender.com/**',
            lambda route:route.fulfill(status=503,body='controlled Render outage'))
        page.goto(root,wait_until='domcontentloaded',timeout=60000)
        page.wait_for_function('Array.isArray(stored)&&stored.length>0&&document.querySelectorAll("#albumgrid .album").length>0',timeout=45000)
        target=page.evaluate('''()=>{
            for(const a of stored){const p=photosFor(a),i=p.findIndex(q=>!q.ownerAlbum&&!q.vaultAlbum&&typeof q.url==='string'&&q.url.startsWith('stored-albums/'));
                if(i>=0)return {album:a.id,index:i,...p[i]};}return null;
        }''')
        assert target,'Real saved local photo lost when both catalogs fail'
        open_photo(page,root,target);exact_bytes(context,root+target['url'],target)
        assert not calls,('Pages attempted unavailable Render catalog after static manifest denial',calls)
        print('FAULT_INJECTED_CATALOG_DENIAL_REAL_PAGES_ORIGINAL_PASS',json.dumps({
            'model':model,'candidate_html':overlay,'controlled_owner_index_http':403,
            'controlled_render_http':503,'real_local_photo_decode_and_SHA':True,
            'render_catalog_requests':len(calls),'not_a_full_gallery_restoration':True}),flush=True)
    finally:context.close()


def transient_pages_real_local_photo(browser,model,overlay):
    """One controlled 503, followed by actual untouched Pages image bytes."""
    root=f'{BASE}/{model}-gallery/'
    context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,
        has_touch=True,service_workers='block')
    page=context.new_page();attempts=[]
    try:
        if overlay:
            for name in ['index.html','saved-photo-union.js']+(['album-grouping.js'] if model=='mimmi' else []):
                text=(ROOT/f'apps/{model}-gallery'/name).read_text()
                page.route(root if name=='index.html' else '**/'+name+'*',
                    candidate_route(text,'text/html' if name=='index.html' else 'application/javascript'))
        # Select a real non-cover BEFORE any navigation. Choosing a target
        # after loading allowed an in-flight/cached image to skip injection.
        folder=ROOT/f'apps/{model}-gallery'
        excluded=set()
        excluded.update(re.findall(r'data-fast-sha="([a-f0-9]{64})"',(folder/'index.html').read_text()))
        for name in ('stored-albums.json','owner-index.json'):
            for album in json.loads((folder/name).read_text())['albums']:
                if album.get('images'):excluded.add(album['images'][0]['sha256'])
        covers=json.loads((folder/'album-covers.json').read_text()).get('covers',{})
        excluded.update(p.get('sha256') for p in covers.values())
        candidates,physical=cross_candidates(model)
        selected=next((p for p in candidates if p['sha256'] not in excluded),None)
        assert selected,'No actual non-cover original for transient-failure test'
        paths=[path for path,p in physical.items() if signature(p)==signature(selected)]
        urls={root+path for path in paths}
        def first_failure(route):
            if route.request.url not in urls:route.continue_();return
            attempts.append(route.request.url)
            if len(attempts)==1:route.fulfill(status=503,body='controlled transient Pages failure')
            else:route.continue_()
        page.route('**/stored-albums/**',first_failure)
        page.goto(root,wait_until='domcontentloaded',timeout=60000)
        page.wait_for_function('Array.isArray(stored)&&stored.length>0&&ownerStored.length>0',timeout=45000)
        target=page.evaluate('''paths=>{
            for(const a of available()){const p=photosFor(a),i=p.findIndex(q=>
                !q.ownerAlbum&&!q.vaultAlbum&&paths.includes(q.url));
                if(i>=0)return {album:a.id,index:i,...p[i]};}return null;
        }''',paths)
        assert target,'Selected real non-cover original missing from composed gallery'
        url=root+target['url']
        open_photo(page,root,target)
        retry_count=page.locator('#detailphotos .photo[data-i="'+str(target['index'])+'"] img').evaluate(
            'img=>committedImageRetries.get(img)?.attempts||0')
        assert retry_count==1 and 2<=len(attempts)<=3,('Transient photo retry was missing or repeated unnecessarily',retry_count,len(attempts))
        exact_bytes(context,url,target)
        print('FAULT_INJECTED_TRANSIENT_PAGES_REAL_ORIGINAL_PASS',json.dumps({
            'model':model,'candidate_html':overlay,'controlled_initial_http':503,
            'real_Pages_followup_SHA_and_decoded_pixels':True,'automatic_grid_retries':retry_count,
            'browser_image_requests_including_lightbox':len(attempts),'full_gallery_P0_restored':False}),flush=True)
    finally:context.close()


def exercise(browser,model,overlay,limit=12):
    root=f'{BASE}/{model}-gallery/'
    source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    relevant=[f'apps/{model}-gallery','apps/gallery-archive/qa_cross_album_pages_live.py']
    diff=subprocess.run(['git','diff','--quiet','HEAD','--',*relevant],cwd=ROOT)
    if diff.returncode not in (0,1):raise ValueError('Cannot establish exact checked-out source state')
    dirty=diff.returncode!=0
    if not overlay:assert not dirty,'Operational QA requires committed exact checked-out source'
    print('ACTUAL_PAGES_MODEL_BEGIN',model,'CANDIDATE' if overlay else 'EXACT_DEPLOYED_SOURCE',flush=True)
    context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2,
        is_mobile=True,has_touch=True,locale='ko-KR',service_workers='block')
    page=context.new_page();exceptions=[];failures=[];catalog_calls=[];console_errors=[]
    page.on('pageerror',lambda e:exceptions.append(str(e)[:300]))
    page.on('console',lambda message:console_errors.append(message.text[:350]) if message.type=='error' else None)
    page.on('requestfailed',lambda request:failures.append({'url':request.url,'failure':request.failure}))
    page.on('response',lambda r:failures.append({'url':r.url,'status':r.status}) if r.status>=400 else None)
    page.on('request',lambda r:catalog_calls.append(r.url) if 'onrender.com/api/' in r.url and r.url.endswith('/catalog') else None)
    if overlay:
        for name in ['index.html','saved-photo-union.js']+(['album-grouping.js'] if model=='mimmi' else []):
            text=(ROOT/f'apps/{model}-gallery'/name).read_text()
            pattern=root if name=='index.html' else '**/'+name+'*'
            mime='text/html' if name=='index.html' else 'application/javascript'
            page.route(pattern,candidate_route(text,mime))
    try:
        source_proof={} if overlay else deployed_sources(context,root,model)
        response=page.goto(root,wait_until='domcontentloaded',timeout=60000)
        assert response and response.status==200
        page.bring_to_front()
        page.wait_for_function("Array.isArray(stored)&&stored.length>0&&document.querySelectorAll('#albumgrid .album').length>0",timeout=80000)
        composed_rows=page.evaluate('available().reduce((n,a)=>n+photosFor(a).length,0)')
        cover_observation=inspect_covers(page)
        public_album_ids=page.evaluate('''()=>available().filter(a=>photosFor(a).some(p=>
            !p.ownerAlbum&&!p.vaultAlbum&&typeof p.url==='string'&&p.url.startsWith('stored-albums/'))).map(a=>a.id)''')
        public_cover_proofs=[]
        for album_id in public_album_ids:
            # WebKit may defer offscreen loading. Inspect the real card in
            # the viewport rather than waiting for offscreen lazy images.
            card=page.locator('#albumgrid .album[data-id="'+album_id+'"]')
            scroll_to_real_card(card)
            page.wait_for_function('''id=>{
                const image=document.querySelector('#albumgrid .album[data-id="'+id+'"] img');
                return image?.complete&&image.naturalWidth>0&&new URL(image.currentSrc||image.src,location.href).pathname.includes('/stored-albums/');
            }''',arg=album_id,timeout=45000)
            public_cover_proofs.append({'album':album_id,**card.locator('img').evaluate('''image=>({
                url:new URL(image.currentSrc||image.src,location.href).href,
                width:image.naturalWidth,height:image.naturalHeight})''')})
        cover_observation=cover_snapshot(page)
        candidates,physical=cross_candidates(model)
        for cover in public_cover_proofs:
            assert cover['url'].startswith(root),'Cover left the actual model gallery'
            file=physical.get(cover['url'][len(root):])
            assert file and (cover['width'],cover['height'])==(file['width'],file['height']),('Actual cover pixels differ from stored original',cover)
        print('ACTUAL_CROSS_OWNER_ROWS_SELECTED',model,len(candidates),flush=True)
        mapped=page.evaluate('''rows=>rows.map(row=>{
            const id=canonicalId(row.owner_album),a=stored.find(a=>a.id===id);
            if(!a)return null;
            const photos=photosFor(a),i=photos.findIndex(p=>p.sha256===row.sha256 && p.bytes===row.bytes &&
                p.width===row.width && p.height===row.height && typeof p.url==='string' &&
                p.url.startsWith('stored-albums/') && !p.ownerAlbum && !p.vaultAlbum);
            return i<0?null:{album:a.id,index:i,url:photos[i].url,sha256:photos[i].sha256,
                bytes:photos[i].bytes,width:photos[i].width,height:photos[i].height};
        })''',candidates)
        assert len(mapped)==len(candidates) and all(mapped),(model,'actual cross-album owner original missing from final composed gallery',sum(p is None for p in mapped))
        targets=[];seen=set()
        for photo in mapped:
            assert photo['url'] in physical and signature(photo)==signature(physical[photo['url']]),'Not an exact physical stored original'
            key=(photo['album'],photo['sha256'])
            if key not in seen:seen.add(key);targets.append(photo)
        checked_urls=set();byte_count=0
        for photo in targets:
            if photo['url'] not in checked_urls:
                byte_count+=exact_bytes(context,root+photo['url'],photo);checked_urls.add(photo['url'])
                if len(checked_urls)%50==0:print('REAL_PAGES_CROSS_FILE_INTEGRITY_PROGRESS',model,len(checked_urls),flush=True)
        selected=select_representatives(targets,len(targets) if model=='yui' else limit)
        viewed=[]
        for target in selected:
            print('ACTUAL_UI_PHOTO_BEGIN',model,target['album'],target['index'],flush=True)
            open_photo(page,root,target)
            exact_bytes(context,root+target['url'],target)
            viewed.append({'album':target['album'],'sha256':target['sha256'],'width':target['width'],'height':target['height']})
            native_touch(page,page.locator('#close'))
            # closeViewer uses asynchronous history.back(). Waiting here is
            # essential: reopening an album earlier races the old popstate.
            page.wait_for_selector('#lightbox.open',state='hidden',timeout=25000)
            page.wait_for_function('''id=>!document.querySelector('#detail').hidden && detailAlbum?.id===id && !history.state?.photo''',arg=target['album'],timeout=25000)
        # Test next/previous on adjacent REAL local originals, independently
        # of whether a collapsed owner alias retained the marker property.
        pair=page.evaluate('''()=>{
            for(const a of stored){const p=photosFor(a);
                for(let i=0;i<p.length-1;i++)if([p[i],p[i+1]].every(q=>!q.ownerAlbum&&!q.vaultAlbum&&typeof q.url==='string'&&q.url.startsWith('stored-albums/')))
                    return [i,i+1].map(j=>({album:a.id,index:j,url:p[j].url,sha256:p[j].sha256,bytes:p[j].bytes,width:p[j].width,height:p[j].height}));}
            return null;
        }''')
        assert pair,(model,'no actual adjacent local originals for navigation')
        open_photo(page,root,pair[0]);native_touch(page,page.locator('#next'));decoded(page,root,pair[1]);exact_bytes(context,root+pair[1]['url'],pair[1])
        native_touch(page,page.locator('#prev'));decoded(page,root,pair[0]);native_touch(page,page.locator('#close'))
        page.wait_for_selector('#lightbox.open',state='hidden',timeout=25000)
        native_touch(page,page.locator('#back'));page.wait_for_selector('#detail',state='hidden',timeout=25000)
        page.reload(wait_until='domcontentloaded',timeout=60000)
        page.wait_for_function("Array.isArray(stored)&&stored.length>0&&document.querySelectorAll('#albumgrid .album').length>0",timeout=45000)
        if not overlay:assert source_proof==deployed_sources(context,root,model)
        assert not exceptions,(model,'unhandled JS errors',exceptions)
        assert not catalog_calls,(model,'unnecessary Render catalog request',catalog_calls)
        print('CANDIDATE_CROSS_ALBUM_PHOTO_CHECK_PASS' if overlay else 'DEPLOYED_CROSS_ALBUM_PHOTO_CHECK_PASS',json.dumps({
            'model':model,'candidate_html':overlay,'operational_source_verified':not overlay and not dirty,
            'source_commit':None if dirty else source_head,'checked_out_base_commit':source_head,
            'uncommitted_candidate_source':dirty,'version':page.locator('#app-version').inner_text(),
            'source_asset_sha256':source_proof,'cross_owner_rows':len(candidates),
            'composed_photo_rows_not_a_viewing_count':composed_rows,
            'all_cross_owner_rows_have_exact_local_routes':len(mapped),
            'independent_real_file_SHA_bytes_pixels':len(checked_urls),'independent_read_bytes':byte_count,
            'actual_browser_lightbox_photos':len(viewed),'viewed':viewed,
            'next_previous_close_back_reload':True,'unhandled_js_errors':exceptions,
            'unnecessary_render_catalog_requests':catalog_calls,
            'all_album_cover_observation':cover_observation,
            'all_albums_with_public_original_have_decoded_covers':len(public_album_ids),
            'verified_public_covers':public_cover_proofs,
            'console_errors':console_errors[:30],
            'remaining_http_failures':failures[:30],'full_gallery_P0_restored':False,
            'iphone_hardware':False},sort_keys=True),flush=True)
    except Exception:
        print('ACTUAL_PAGES_FAILURE_STATE',json.dumps({'model':model,'url':page.url,
            'unhandled_js_errors':exceptions,'http_failures':failures[-15:],
            'cover_observation':cover_snapshot(page),
            'ui':page.evaluate("()=>({lightbox:document.querySelector('#lightbox')?.className,detailHidden:document.querySelector('#detail')?.hidden,scroll:scrollY,route:history.state})")}),flush=True)
        raise
    finally:context.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--browser',choices=('chromium','webkit'),required=True)
    p.add_argument('--candidate-html',action='store_true');p.add_argument('--max-browser-photos',type=int,default=12)
    args=p.parse_args()
    if not 12<=args.max_browser_photos<=500:raise SystemExit('Browser sample must retain at least twelve actual originals per model')
    # Preserve the real call stack if a native driver stops responding.
    # This diagnostic does not extend the operation or job deadlines.
    faulthandler.dump_traceback_later(60,repeat=True)
    with sync_playwright() as pw:
        proxy=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        browser=getattr(pw,args.browser).launch(headless=True,**({'proxy':{'server':proxy}} if proxy else {}))
        try:
            for model in ('mimmi','yui'):
                exercise(browser,model,args.candidate_html,args.max_browser_photos)
                denied_catalog_real_local_photos(browser,model,args.candidate_html)
                transient_pages_real_local_photo(browser,model,args.candidate_html)
        finally:browser.close()
