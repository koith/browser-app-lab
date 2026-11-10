#!/usr/bin/env python3
"""Read-only exact SHA/byte/pixel verification of the deployed Cloudflare owner archive."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://gallery-archive-free.gallery-9f7d03138f3f.workers.dev'
MIN_COUNTS = {'mimmi': 4660, 'yui': 3077}
# Before the Mimmi owner index gained 2 physical rows on 2026-11-11.
MIMMI_PRE_INCREMENT = 'b57ecc91bb5b0053046e764335bac1e60a1e4f1a'
TARGETS = {('mimmi','djawa-asuna-the-maid',4), ('mimmi','djawa-asuna-the-maid',5),
           ('mimmi','mimmi-indie-sana-sopmod2-2019',1), ('yui','yuis-present33',1)}
SCREENSHOT_ALBUMS = {('mimmi','v2ph-azur-lane-tashkent'):69,
                     ('yui','djawa-privaty-public-samples'):30}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def read(method, url, body=None):
    headers={'User-Agent':'gallery-archive-replica-qa/1.0'}
    if method == 'POST':
        headers.update({'Origin':'https://koith.github.io','Content-Type':'application/json'})
    req=Request(url, method=method, data=body, headers=headers)
    try:
        with build_opener(NoRedirect()).open(req,timeout=40) as r:
            return r.status, r.geturl(), r.read(8_000_001), r.headers.get('content-type','')
    except HTTPError as e:
        return e.code, e.url, e.read(2048), e.headers.get('content-type','')

def read_reliably(method,url,body=None):
    for attempt in range(5):
        try:
            code,returned,raw,mime=read(method,url,body)
            if code==200 and returned==url:
                return raw,mime
            edge_1042=code==404 and b'error code: 1042' in raw.lower()
            if (edge_1042 or code in (429,500,502,503,504)) and attempt<4:
                time.sleep((1,2,3,5)[attempt])
                continue
            if edge_1042:
                raise ValueError('EDGE_ROUTE_1042')
            if code==404 and b'PHOTO_NOT_MIRRORED' in raw:
                raise ValueError('ACTUAL_PHOTO_NOT_MIRRORED')
            raise ValueError('HTTP_'+str(code))
        except (URLError, OSError, TimeoutError):
            if attempt==4:
                raise ValueError('NETWORK_EXHAUSTED') from None
            time.sleep((1,2,3,5)[attempt])
    raise ValueError('UNKNOWN_REMOTE_ERROR')

def indexed():
    result=[]
    for model,min_count in MIN_COUNTS.items():
        p=ROOT/'apps'/(model+'-gallery')/'owner-index.json'
        index=json.loads(p.read_text())
        assert index['model']==model and index['schema_version']==1
        unique=set()
        for a in index['albums']:
            screenshot_expected = SCREENSHOT_ALBUMS.get((model,a['id']))
            if screenshot_expected is not None:
                assert len(a['images']) == screenshot_expected, ('SCREENSHOT_ALBUM_SIZE',model,a['id'])
            for photo in a['images']:
                key=(a['id'],photo['number'])
                assert key not in unique
                unique.add(key)
                result.append((model,a['id'],photo))
        assert len(unique)>=min_count, ('OWNER_INDEX_BELOW_VERIFIED_FLOOR',model,len(unique),min_count)
    return result

def recent_mimmi(all_items):
    """Require actual new original bytes, not merely increased public count.

    Compare exact album/number/SHA to public metadata from immediately
    before the two new Mimmi rows. Neither endpoint contains secret URLs.
    """
    previous_url = (
        'https://raw.githubusercontent.com/koith/browser-app-lab/'
        f'{MIMMI_PRE_INCREMENT}/apps/mimmi-gallery/owner-index.json'
    )
    raw, _ = read_reliably('GET', previous_url)
    before = json.loads(raw)
    assert before.get('model') == 'mimmi' and before.get('physical_originals_indexed') == 4658, (
        'UNEXPECTED_PRE_INCREMENT_BASELINE'
    )
    old = {(album['id'], p['number']): p['sha256']
           for album in before['albums'] for p in album['images']}
    old_hashes = set(old.values())
    delta = [item for item in all_items if item[0] == 'mimmi'
             and old.get((item[1], item[2]['number'])) != item[2]['sha256']]
    assert len(delta) >= 2, ('NEW_MIMMI_RECORDS_NOT_PRESENT', len(delta))
    assert all(item[2]['sha256'] not in old_hashes for item in delta), (
        'NEW_MIMMI_ROW_REUSES_OLD_EXACT_SHA'
    )
    assert len({item[2]['sha256'] for item in delta}) == len(delta), (
        'NEW_MIMMI_ROWS_ARE_NOT_UNIQUE_PHOTOS'
    )
    print('G03_MIMMI_NEW_PHYSICAL_RECORDS_TO_REMOTE_VERIFY', len(delta), flush=True)
    return delta


def check(item):
    model,album,p=item
    payload=json.dumps({'model':model,'album':album,'number':p['number'],
                        'variant':'original','sha256':p['sha256']}).encode()
    response,mime=read_reliably('POST',BASE+'/api/v1/sign',payload)
    if 'json' not in mime.lower():
        raise ValueError('SIGN_RESPONSE_NOT_JSON')
    sign=json.loads(response)
    uri=sign['url']
    u=urlsplit(uri)
    expected='/api/v1/media/'+model+'/'+album+'/'+str(p['number'])+'/original'
    if u.scheme!='https' or u.netloc!=urlsplit(BASE).netloc or u.path!=expected:
        raise ValueError('SIGNED_URL_NOT_OWNER_ENDPOINT')
    if sign['sha256']!=p['sha256'] or sign['bytes']!=p['bytes']:
        raise ValueError('SIGNED_HASH_OR_LENGTH_MISMATCH')
    raw,mime=read_reliably('GET',uri)
    if len(raw)!=p['bytes'] or hashlib.sha256(raw).hexdigest()!=p['sha256']:
        raise ValueError('EXACT_ORIGINAL_BYTES_MISMATCH')
    with Image.open(io.BytesIO(raw)) as im:
        if im.size!=(p['width'],p['height']) or im.format not in ('JPEG','PNG','WEBP'):
            raise ValueError('IMAGE_DIMENSIONS_OR_FORMAT_MISMATCH')
        im.verify()
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
    return model

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scope',choices=('targeted','recent','all'),default='targeted')
    args=parser.parse_args()
    h,_=read_reliably('GET',BASE+'/api/v1/health')
    health=json.loads(h)
    assert health['transport']=='cloudflare-bound-assets'
    print('LIVE_WORKER_SOURCE',health.get('source_commit'),flush=True)
    all_items=indexed()
    if args.scope == 'all':
        items = all_items
    elif args.scope == 'recent':
        items = recent_mimmi(all_items)
    else:
        items = [
            item for item in all_items if ((item[0],item[1],item[2]['number']) in TARGETS
            or (item[0],item[1]) in SCREENSHOT_ALBUMS)
        ]
    if args.scope=='targeted':
        assert len(items)==len(TARGETS)+sum(SCREENSHOT_ALBUMS.values()), 'INCIDENT_TARGET_COVERAGE'
    passed={'mimmi':0,'yui':0}
    failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(check,item) for item in items]
        for n,(item,future) in enumerate(zip(items,futures),1):
            try:
                passed[future.result()]+=1
            except Exception as e:
                failures.append({'model':item[0],'album':item[1],
                                 'number':item[2]['number'],'reason':str(e)[:80]})
            if n%1000==0 or n==len(items):
                print('ACTUAL_CLOUDFLARE_PROGRESS',n,'/',len(items),flush=True)
    result={'scope':args.scope,'requested':len(items),'passed':passed,
            'failed':len(failures),'failures_first_20':failures[:20],
            'new_uploads':0,'billing_changed':0}
    print('ACTUAL_CLOUDFLARE_SHA_BYTES_PIXELS',json.dumps(result,sort_keys=True),flush=True)
    expected = {model: sum(item[0] == model for item in all_items)
                for model in MIN_COUNTS}
    if failures or (args.scope=='all' and passed!=expected) or (
        args.scope=='recent' and passed['mimmi']!=len(items)
    ):
        raise SystemExit(1)

if __name__=='__main__':
    main()
