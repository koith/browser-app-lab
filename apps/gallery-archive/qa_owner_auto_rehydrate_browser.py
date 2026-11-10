#!/usr/bin/env python3
"""Test automatic owner tile recovery after a genuine mocked 503->200 transition.

Only the candidate inline gallery HTML comes from the PR. All photo metadata
comes from the real Pages owner-index. The returned tiny synthetic PNG is a
mock for UI behavior and MUST NOT be mistaken for restored owner photos.
"""
import argparse
import io
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from PIL import Image
from playwright.sync_api import sync_playwright

TARGET={
    # Teddy Bear pages 1-10 have exact local copies: select an owner-only tile.
    "yui":[("teddy-bear97",13),("djawa-privaty-public-samples",0)],
    "mimmi":[("v2ph-actor-a8n8n85a",10),("v2ph-actor-zo5n754z",16)],
}
BASE="https://koith.github.io/browser-app-lab/apps"

def is_target_owner_media(url, model, album):
    # The restored production transport uses /api/v1/media/MODEL/ALBUM/...
    # while the legacy Render gateway used /api/MODEL/media/ALBUM/...
    # Match only the requested model and album; never weaken the 503->200 gate.
    path=urlsplit(url).path
    return (
        path.startswith(f"/api/v1/media/{model}/{album}/") or
        path.startswith(f"/api/{model}/media/{album}/") or
        path.startswith(f"/media/{album}/")
    )


def serve_candidate_owner_transport(page,model,root):
    # PR's gallery HTML calls the new .renew() API. The live Pages
    # owner-media.js and pages-client.mjs are intentionally still old, so
    # overlay BOTH candidate scripts; real catalog and Worker bytes stay live.
    owner=Path(f"apps/{model}-gallery/owner-media.js")
    module=Path("apps/gallery-archive/cloudflare-owner-gateway/pages-client.mjs")
    page.route(root+"owner-media.js",lambda route:route.fulfill(
        status=200,content_type="application/javascript",body=owner.read_bytes()))
    page.route(BASE+"/gallery-archive/cloudflare-owner-gateway/pages-client.mjs",
        lambda route:route.fulfill(status=200,content_type="application/javascript",
            body=module.read_bytes()))

def exercise(browser,model,album,index):
    ctx=browser.new_context(viewport={"width":390,"height":844},
            is_mobile=True,has_touch=True,service_workers="block",locale="ko-KR")
    page=ctx.new_page()
    root=f"{BASE}/{model}-gallery/"
    serve_candidate_owner_transport(page,model,root)
    html=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
    png=io.BytesIO()
    Image.new("RGB",(320,480),(30,60,120)).save(png,format="PNG")
    mock_bytes=png.getvalue()
    phase={"warm":False,"errors":0,"recoveries":0,"readiness":0,"unnecessary_catalog":0,
           "invalid_signed_queries":0}
    def mock_media(route):
        link=route.request.url
        if not is_target_owner_media(link,model,album):
            route.continue_()
            return
        # The current Worker refuses additional query arguments on signed
        # image routes. Never fake recovery for a URL production would reject.
        if urlsplit(link).path.startswith("/api/v1/media/"):
            keys=set(parse_qs(urlsplit(link).query,keep_blank_values=True))
            if keys!={"h","b","e","s"}:
                phase["invalid_signed_queries"]+=1
                route.fulfill(status=403,body="invalid signed URL arguments",
                    headers={"Cache-Control":"no-store"})
                return
        if phase["warm"] and "/original" in link:
            phase["recoveries"]+=1
            route.fulfill(status=200,body=mock_bytes,content_type="image/png",
                headers={"Access-Control-Allow-Origin":"https://koith.github.io"})
        else:
            phase["errors"]+=1
            route.fulfill(status=503,body="mock temporary owner 503",
                headers={"Access-Control-Allow-Origin":"https://koith.github.io",
                         "Cache-Control":"no-store"})
    def reject_global_poll(route):
        phase["readiness"]+=1
        route.fulfill(status=500,body="old global readiness endpoint must not gate an album")
    page.route(root,lambda route:route.fulfill(status=200,content_type="text/html",body=html))
    def reject_optional_catalog(route):
        phase["unnecessary_catalog"]+=1
        route.fulfill(status=503,body="static owner index should make this optional")
    page.route("**/api/catalog",reject_optional_catalog)
    page.route("**/api/yui/catalog",reject_optional_catalog)
    page.route("**/api/gallery-media-readiness",reject_global_poll)
    page.route("**/media/**",mock_media)
    try:
        response=page.goto(root+"#album="+album,wait_until="domcontentloaded",timeout=60000)
        assert response and response.status==200
        page.wait_for_function("""album=>typeof ownerRecoveryPending!=='undefined' &&
          stored.some(a=>a.id===album) &&
          document.querySelector('#detail')?.hidden===false
        """,arg=album,timeout=90000)
        photo=page.locator("#detailphotos .photo").nth(index)
        image=photo.locator("img")
        photo.scroll_into_view_if_needed(timeout=20000)
        page.wait_for_function("""()=>
          [...ownerRecoveryPending].some(im=>im.isConnected&&
            !!im.closest('#detailphotos')&&!!im.dataset.owner)
        """,timeout=45000)
        # The intersection observer can have multiple owner photos in flight;
        # a fixed grid index is not necessarily the image whose 503 queued a
        # retry. Prove restoration of the EXACT failed image, not a neighbor.
        retry_index=page.evaluate("""() => {
          const all=[...document.querySelectorAll('#detailphotos .photo img')];
          return all.findIndex(im=>ownerRecoveryPending.has(im)&&
            im.dataset.owner&&ownerRetryVisible(im));
        }""")
        assert retry_index>=0,(model,"no pending visible owner photo",phase)
        assert phase["errors"]>=1,(model,"mocked 503 not exercised",phase)
        # Backend becomes ready without a page refresh. The user refocuses
        # the existing tab and the same tile must repaint automatically.
        phase["warm"]=True
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        page.wait_for_function("""idx=>{
          const im=document.querySelectorAll('#detailphotos .photo img')[idx];
          return im && im.complete && im.naturalWidth===320 &&
                 im.naturalHeight===480 && !im.hidden &&
                 !im.closest('.photo')?.classList.contains('broken-source') &&
                 im.closest('.photo')?.dataset.imageState!=='failed';
        }""",arg=retry_index,timeout=30000)
        assert phase["recoveries"]>=1,(model,"no original retry after healthy status",phase)
        assert phase["invalid_signed_queries"]==0,(model,"tampered Cloudflare signed media URL",phase)
        assert phase["readiness"]==0,(model,"global readiness must not be polled",phase)
        assert phase["unnecessary_catalog"]==0,(model,"static owner manifest triggered optional Render catalog",phase)
        print("GALLERY_OWNER_AUTO_RECOVERY_503_TO_200_MOCK_UI_PASS",json.dumps({
            "model":model,"album":album,"browser":browser.browser_type.name,
            "verified_failed_owner_tile_index":retry_index,
            "original_mock_errors":phase["errors"],
            "unnecessary_global_readiness_polls":phase["readiness"],
            "unnecessary_remote_catalog_requests":phase["unnecessary_catalog"],
            "original_mock_recoveries":phase["recoveries"],
            "invalid_signed_queries":phase["invalid_signed_queries"],
            "same_page_no_reload":True,
            "real_owner_media_claimed":False,
            "real_iphone_hardware_claimed":False
        }),flush=True)
    finally:
        ctx.close()


def exercise_real_owner_cover_after_failure(browser,model,failure_mode):
    """Real Worker original, real DOM album cover; only initial transport failure is injected."""
    ctx=browser.new_context(viewport={"width":390,"height":844},
        is_mobile=True,has_touch=True,service_workers="block",locale="ko-KR")
    page=ctx.new_page()
    root=f"{BASE}/{model}-gallery/"
    serve_candidate_owner_transport(page,model,root)
    html=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
    state={"initial_503":0,"legacy_render_requests":0,"warm":False}
    def inject(route):
        if not state["warm"]:
            state["initial_503"]+=1
            route.fulfill(status=503,body="one controlled unavailable response",
                headers={"Access-Control-Allow-Origin":"https://koith.github.io",
                         "Cache-Control":"no-store"})
        else:
            route.continue_()
    def reject_old_render(route):
        state["legacy_render_requests"]+=1
        route.fulfill(status=503,body="retired Render origin is not a photo fallback")
    page.route(root,lambda route:route.fulfill(status=200,content_type="text/html",body=html))
    page.route("**/mimmi-private-gallery-free.onrender.com/**",reject_old_render)
    if failure_mode=="config503":
        page.route(root+"cloudflare-gateway.json",inject)
    elif failure_mode=="sign503":
        page.route("**/api/v1/sign",inject)
    else:
        raise ValueError(failure_mode)
    try:
        response=page.goto(root,wait_until="domcontentloaded",timeout=80000)
        assert response and response.status==200
        page.wait_for_function("""() => typeof ownerPhotoIndex!=='undefined' &&
          ownerPhotoIndex.size>0 && typeof observeOwner==='function' &&
          !!document.querySelector('#albumgrid button.album')""",timeout=80000)
        selected=page.evaluate("""() => {
          const cards=[...document.querySelectorAll('#albumgrid button.album')];
          for(const card of cards){
            let im=card.querySelector('img');
            if(!im)continue;
            if(!im.dataset.owner){
              const a=stored.find(x=>x.id===card.dataset.id);
              const photo=a&&photosFor(a).find(p=>p.ownerAlbum);
              if(!photo)continue;
              im.dataset.owner=photo.url;
              delete im.dataset.ownerVariant;
              im.removeAttribute('src');
            }
            if(im.getAttribute('src')){
              // Simulate an exact saved photo's failed local request; the
              // selected owner identity remains unchanged for its fallback.
              im.removeAttribute('src');
              delete im.dataset.ownerVariant;
            }
            const photo=ownerPhotoIndex.get(im.dataset.owner);
            if(!photo)continue;
            im.scrollIntoView({block:'center'});
            observeOwner();
            return {album:card.dataset.id,owner:im.dataset.owner,sha:photo.sha256};
          }
          return null;
        }""")
        assert selected,(model,'no existing owner image to test')
        page.wait_for_function("""sel => [...ownerRecoveryPending].some(im =>
           im.isConnected && !!im.closest('.album') &&
           im.dataset.owner===sel.owner && ownerRetryVisible(im))""",
           arg=selected,timeout=35000)
        assert state["initial_503"]>=1,(model,failure_mode,state)
        state["warm"]=True
        page.evaluate("window.dispatchEvent(new Event('focus'))")
        page.wait_for_function("""sel => {
          const img=[...document.querySelectorAll('#albumgrid button.album img')]
            .find(im=>im.dataset.owner===sel.owner);
          if(!img||!img.complete||img.hidden||img.naturalWidth<100)return false;
          const url=new URL(img.currentSrc||img.src,location.href);
          const photo=ownerPhotoIndex.get(sel.owner);
          return !!photo && url.hostname==='gallery-archive-free.gallery-9f7d03138f3f.workers.dev'
            && ['h','b','e','s'].every(key=>url.searchParams.has(key))
            && [...url.searchParams.keys()].length===4
            && [photo.sha256,photo.preview_sha256].includes(url.searchParams.get('h'))
            && !ownerRecoveryPending.has(img)
            && !img.closest('.album').classList.contains('broken-source');
        }""",arg=selected,timeout=45000)
        assert state["legacy_render_requests"]==0,(model,'retired Render fallback occurred',state)
        print('GALLERY_REAL_WORKER_ALBUM_COVER_RECOVERED_AFTER_INJECTED_503',json.dumps({
            "model":model,"browser":browser.browser_type.name,
            "failure_mode":failure_mode,"album":selected["album"],
            "first_requests_503":state["initial_503"],
            "original_SHA":selected["sha"][:12],
            "actual_cloudflare_native_decoded_cover":True,
            "real_iphone_hardware_tested":False,
            "legacy_render_requests":state["legacy_render_requests"]},sort_keys=True),flush=True)
    finally:
        ctx.close()



def exercise_real_pages_static_cover_after_two_503(browser,model):
    """Two simulated Pages 503s, third GET and decoded pixels from actual Pages."""
    import re
    import hashlib
    ctx=browser.new_context(viewport={"width":390,"height":844},
        is_mobile=True,has_touch=True,service_workers="block",locale="ko-KR")
    page=ctx.new_page()
    root=f"{BASE}/{model}-gallery/"
    serve_candidate_owner_transport(page,model,root)
    html=Path(f"apps/{model}-gallery/index.html").read_text(encoding="utf-8")
    matched=re.search(r'data-fast-sha="([a-f0-9]{64})".*?<img src="(stored-albums/[^"]+)"',
                      html,re.S)
    assert matched,(model,'no SHA-tagged first-paint cover to retry')
    sha,relative=matched.groups()
    state={"failed":0,"served_real":0,"queries":[]}
    def inject(route):
        url=urlsplit(route.request.url)
        if not url.path.endswith("/"+relative):
            route.continue_()
            return
        state["queries"].append(url.query)
        if state["failed"]<2:
            state["failed"]+=1
            route.fulfill(status=503,body="controlled local saved-cover 503",
                headers={"Cache-Control":"no-store"})
        else:
            state["served_real"]+=1
            route.continue_()
    page.route(root,lambda route:route.fulfill(status=200,content_type="text/html",body=html))
    page.route("**/stored-albums/**",inject)
    try:
        response=page.goto(root,wait_until="domcontentloaded",timeout=80000)
        assert response and response.status==200
        # A committed album cover can legitimately become lazy/offscreen after
        # hydration (especially 2-column mobile WebKit). A native browser will
        # not fetch its retried URL until it enters the viewport. Simulate
        # the real user scrolling to the affected album, rather than treating
        # an offscreen pending lazy image as a recovery failure.
        target=page.locator('#albumgrid img[src*="'+relative+'"]').first
        target.wait_for(state='attached',timeout=35000)
        target.scroll_into_view_if_needed(timeout=35000)
        try:
            page.wait_for_function("""relative => {
              const imgs=[...document.querySelectorAll('#albumgrid img')];
              return imgs.some(img => img.complete && img.naturalWidth>100 &&
                new URL(img.currentSrc||img.src,location.href).pathname.endsWith('/'+relative));
            }""",arg=relative,timeout=45000)
        except Exception:
            diagnosis=page.evaluate("""relative => ({
              galleryCards:document.querySelectorAll('#albumgrid .album').length,
              matchingImages:[...document.querySelectorAll('#albumgrid img')].filter(
                im => (im.currentSrc||im.src||'').includes(relative)).map(im=>({
                  src:im.getAttribute('src'),width:im.naturalWidth,
                  complete:im.complete,hidden:im.hidden,connected:im.isConnected,
                  broken:im.closest('.album')?.classList.contains('broken-source')})),
              pendingOwner:typeof ownerRecoveryPending!=='undefined'
                ? ownerRecoveryPending.size : null,
              loadState:document.readyState
            })""",relative)
            print('GALLERY_STATIC_503_RECOVERY_TIMEOUT_EVIDENCE',
                  json.dumps({'model':model,'browser':browser.browser_type.name,
                              'requests':state,'ui':diagnosis},sort_keys=True),flush=True)
            raise
        assert state["failed"]==2 and state["served_real"]>=1,state
        # Multiple first-paint <img> requests can independently hit the
        # unmodified URL before the error listener runs. What matters is that
        # a fresh same-origin gtry URL succeeded after both injected failures.
        assert any(re.fullmatch(r'gtry=[1-4]',q) for q in state["queries"]),(
            "No cache-busted same-origin Pages retry",state)
        assert len(set(state["queries"]))>=2,("Only cached 503 URL reused",state)
        actual=ctx.request.get(root+relative,timeout=45000)
        assert actual.status==200,(model,'real Pages committed cover unavailable',actual.status)
        assert hashlib.sha256(actual.body()).hexdigest()==sha,(model,'committed cover SHA changed')
        print('GALLERY_REAL_SAVED_PAGES_THUMBNAIL_RECOVERED_AFTER_TWO_503',json.dumps({
          "model":model,"browser":browser.browser_type.name,
          "real_image_SHA":sha[:12],"injected_HTTP_503":state["failed"],
          "separate_local_cache_keys":len(set(state["queries"])),
          "live_pages_file_sha_verified":True,
          "native_browser_image_decoded":True,
          "physical_iphone_hardware_tested":False},sort_keys=True),flush=True)
    finally:
        ctx.close()


if __name__=="__main__":
    assert is_target_owner_media("https://archive.example/api/v1/media/yui/teddy-bear97/13/original?h=x","yui","teddy-bear97")
    assert is_target_owner_media("https://archive.example/api/mimmi/media/v2ph-actor-a8n8n85a/11/original","mimmi","v2ph-actor-a8n8n85a")
    assert not is_target_owner_media("https://archive.example/api/v1/media/yui/other/13/original","yui","teddy-bear97")
    assert not is_target_owner_media("https://archive.example/api/v1/media/mimmi/teddy-bear97/13/original","yui","teddy-bear97")
    parser=argparse.ArgumentParser()
    parser.add_argument("--browser",choices=("chromium","webkit"),required=True)
    args=parser.parse_args()
    with sync_playwright() as pw:
        browser=getattr(pw,args.browser).launch(headless=True)
        try:
            for model in ("mimmi","yui"):
                for album,index in TARGET[model]:exercise(browser,model,album,index)
                for failure_mode in ("sign503","config503"):
                    exercise_real_owner_cover_after_failure(browser,model,failure_mode)
                exercise_real_pages_static_cover_after_two_503(browser,model)
        finally:
            browser.close()
