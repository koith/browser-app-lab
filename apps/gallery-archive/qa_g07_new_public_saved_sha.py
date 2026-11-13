#!/usr/bin/env python3
"""G-07 acceptance: a newly acquired *actual byte file* survives Pages and SPA.

Run offline against PR checkout to prove source bytes, SHA, width/height,
no owner duplication and source-work identity. On postmerge, additionally
open the deployed Yui gallery in native Chromium/WebKit, read the exact
user-visible photo tile and decode its static original JPEG.
"""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
PHOTO_SHA='68ff6a9b92bd13e7a1def21ef2dfb42a28c7bf627d1a493164906107158dcc7b'
BASE='https://koith.github.io/browser-app-lab/apps/yui-gallery/'

def source_proof():
    path=ROOT/'apps/yui-gallery'
    saved=json.loads((path/'stored-albums.json').read_text())
    owner=json.loads((path/'owner-index.json').read_text())
    expected = {
        '68ff6a9b92bd13e7a1def21ef2dfb42a28c7bf627d1a493164906107158dcc7b': (467,234959,1366,2048),
        'c00059932bfcfd17c214d4dc8b462de4846cad8881bcebc2ac24f4feb31b8802': (468,325352,1365,2048),
    }
    verified = {}
    for sha, (number, size, width, height) in expected.items():
        local=[p for a in saved['albums'] if a['id']=='public-yui-sns' for p in a['images']
               if p['sha256']==sha]
        assert len(local)==1,('new individual photo not in exact recorded source album',sha)
        candidate=local[0]
        assert not any(t.get('sha256')==sha for a in owner['albums'] for t in a['images']), 'not new relative to owner catalog'
        file=(path/candidate['url']).resolve()
        assert file.is_relative_to((path/'stored-albums/public-yui-sns').resolve())
        raw=file.read_bytes()
        assert len(raw)==size==candidate['bytes'] and hashlib.sha256(raw).hexdigest()==sha
        with Image.open(file) as image:
            image.load()
            assert image.size==(width,height)==(candidate['width'],candidate['height'])
            assert image.format=='JPEG'
        assert candidate['number']==number,'public album photos must be append-only'
        verified[sha]=candidate
    expected_albums={'public-yui-sns':2,'artgravia-677-yui-public-samples':12,
                     'yui-meow-public-samples':6}
    total=0
    global_sha=set()
    for album in saved['albums']:
        if album['id'] not in expected_albums:continue
        assert len(album['images'])==expected_albums[album['id']],('unexpected count',album['id'])
        for item in album['images']:
            sha=item['sha256']
            assert sha not in global_sha,('duplicate SHA in new works',sha)
            assert not any(p['sha256']==sha for a in owner['albums'] for p in a['images'])
            global_sha.add(sha)
            file=(path/item['url']).resolve()
            assert file.is_relative_to((path/'stored-albums').resolve())
            assert file.is_file()
            raw=file.read_bytes()
            assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==sha
            with Image.open(file) as image:
                image.load()
                assert image.size==(item['width'],item['height'])
                assert image.format=='JPEG'
            total+=1
    assert total==20,('all 20 actual individual new public photo bytes required',total)
    print('G07_ACTUAL_NEW_20_SHA_ORIGINALS_VERIFIED',{ 'model':'yui',
        'albums':expected_albums,'bytes_sha_decoded':total},flush=True)
    p=verified[PHOTO_SHA]
    print('G07_REAL_PUBLIC_NEW_FILE_SHA_BYTES_PIXELS_PASS',json.dumps({
      'sha256':PHOTO_SHA,'bytes':p['bytes'],'width':p['width'],
      'height':p['height'],'album':'public-yui-sns','number':p['number']}),flush=True)
    return p

def live(browser_type,p):
    with sync_playwright() as pw:
        browser=getattr(pw,browser_type).launch()
        context=browser.new_context(viewport={'width':390,'height':844},
              is_mobile=True,has_touch=True)
        page=context.new_page()
        response=page.goto(BASE+'#album=public-yui-sns',wait_until='domcontentloaded',timeout=80000)
        assert response and response.status==200
        page.wait_for_function("""sha=>{
          const a=stored.find(x=>x.id==='public-yui-sns');
          return a&&a.images.some(p=>p.sha256===sha);
        }""",arg=PHOTO_SHA,timeout=60000)
        # The gallery appends 48 photo nodes per animation frame to keep
        # first paint fast. A 467th SNS photo is not in the DOM at the
        # instant stored[] is hydrated; wait for its real node rather than
        # treating progressive rendering as missing archive content.
        page.wait_for_function("""sha=>{
          const a=stored.find(x=>x.id==='public-yui-sns');
          const p=a?.images.find(x=>x.sha256===sha);
          return !!p&&[...document.querySelectorAll('#detailphotos .photo img')]
            .some(img=>(img.getAttribute('src')||'').includes(p.url));
        }""",arg=PHOTO_SHA,timeout=45000)
        evidence=page.evaluate("""sha=>{
          const a=stored.find(x=>x.id==='public-yui-sns');
          const p=a.images.find(x=>x.sha256===sha);
          const tile=[...document.querySelectorAll('#detailphotos .photo img')]
            .find(e=>(e.getAttribute('src')||'').includes(p.url));
          return {id:a.id,number:p.number,bytes:p.bytes,url:p.url,
                  tileInActualAlbumDetail:!!tile,
                  detailedPhotoCount:document.querySelectorAll('#detailphotos .photo').length};
        }""",PHOTO_SHA)
        assert evidence['url']==p['url'] and evidence['bytes']==p['bytes']
        assert evidence['tileInActualAlbumDetail'],evidence
        photo_path=BASE+p['url']
        actual=context.request.get(photo_path,timeout=45000)
        assert actual.status==200,(browser_type,'public SHA file GET',actual.status)
        assert len(actual.body())==p['bytes']
        assert hashlib.sha256(actual.body()).hexdigest()==PHOTO_SHA
        native=page.evaluate("""async url=>{
          const image=new Image();image.loading='eager';image.decoding='async';
          image.src=url;await image.decode();
          return {complete:image.complete,width:image.naturalWidth,height:image.naturalHeight};
        }""",photo_path)
        assert native=={'complete':True,'width':p['width'],'height':p['height']},native
        page.reload(wait_until='domcontentloaded',timeout=60000)
        page.wait_for_function("""sha=>{
          const a=stored.find(x=>x.id==='public-yui-sns');
          return a&&a.images.some(p=>p.sha256===sha);
        }""",arg=PHOTO_SHA,timeout=45000)
        print('G07_ACTUAL_NEW_PUBLIC_SAVED_PHOTO_LIVE_BROWSER_PASS',json.dumps({
          'browser':browser_type,'sha256':PHOTO_SHA,'nativeDecoded':native,
          'albumDetailTileExists':evidence['tileInActualAlbumDetail'],
          'actualBytesSHAverified':True,'reloadSourceRetained':True,
          'new_owner_private_original_not_claimed':True}),flush=True)
        browser.close()

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--browser',choices=['chromium','webkit'])
    args=a.parse_args()
    p=source_proof()
    if args.browser:live(args.browser,p)
