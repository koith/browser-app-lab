#!/usr/bin/env python3
"""Archive only image URLs actually observed on the ordinary public album page.

This is not a guessed CDN spider, a login bypass, or a gallery hotlink.
Direct publicly exposed image links were individually observed on
https://www.v2ph.com/album/axm7n43z.html (the accessible first page).
All bytes are decoded and globally deduplicated against the actual index.
The output remains an unpublished private-owner stage until cloud SHA audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import requests
from direct_photo_pipeline import inspect,atomic_bytes

MODEL='mimmi'
ALBUM='v2ph-actor-axm7n43z'
PUBLIC_SOURCE='https://www.v2ph.com/album/axm7n43z.html'
# Only ten distinct photos shown on its publicly visible first page;
# no fabricated page/sequence, access cookies, offsets or API guessing.
OBSERVED_PUBLIC_IMAGE_URLS=[
    'https://cdn.v2ph.com/photos/OTWu16__bs8dZxAq.jpg',
    'https://cdn.v2ph.com/photos/suEjkb2eNsi0Ql6y.jpg',
    'https://cdn.v2ph.com/photos/3y-jKW-LxqjMdydq.jpg',
    'https://cdn.v2ph.com/photos/cfMGYeXHrXNjFiO-.jpg',
    'https://cdn.v2ph.com/photos/fQOi-MIMVaR8OopH.jpg',
    'https://cdn.v2ph.com/photos/6AXKji4xYUJ4Lpfu.jpg',
    'https://cdn.v2ph.com/photos/X5TQQ4H-PVUYhLp-.jpg',
    'https://cdn.v2ph.com/photos/Rd00siaZLUSxmwDj.jpg',
    'https://cdn.v2ph.com/photos/DS_yUpyIO5uxxXNQ.jpg',
    'https://cdn.v2ph.com/photos/qX9Zx6hDsibPdTz1.jpg',
]

def acquire(owner_path:Path,public_path:Path,out:Path,client=None):
    owner=json.loads(owner_path.read_text())
    public=json.loads(public_path.read_text())
    assert owner['schema_version']==1 and owner['model']==MODEL
    assert public['model']==MODEL
    allhashes={p['sha256'] for a in owner['albums'] for p in a['images']}
    allhashes.update(p['sha256'] for a in public['albums'] for p in a['images'])
    seen_in={}
    for album in owner['albums']:
        for p in album['images']:
            seen_in.setdefault(p['sha256'],set()).add('owner:'+album['id'])
    for album in public['albums']:
        for p in album['images']:
            seen_in.setdefault(p['sha256'],set()).add('pages:'+album['id'])
    current=next((a for a in owner['albums'] if a['id']==ALBUM),None)
    oldcount=len(current['images']) if current else 0
    occupied={p['number'] for p in current['images']} if current else set()
    next_number=max(occupied,default=0)+1
    assert len(set(OBSERVED_PUBLIC_IMAGE_URLS))==len(OBSERVED_PUBLIC_IMAGE_URLS)==10
    for url in OBSERVED_PUBLIC_IMAGE_URLS:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname!='cdn.v2ph.com' or not re.fullmatch(
                r'/photos/[a-zA-Z0-9_-]{16}\.jpg',parsed.path) or parsed.query or parsed.fragment:
            raise ValueError('Source URL outside observed public media scope')
    client=client or requests.Session()
    seen=set(allhashes);images=[];failure_types=[];duplicates=0
    out.mkdir(parents=True,exist_ok=True)
    for position,url in enumerate(OBSERVED_PUBLIC_IMAGE_URLS,1):
        try:
            response=client.get(url,timeout=(9,25),allow_redirects=False)
            if response.status_code in (401,403,429,451):
                failure_types.append({'position':position,'cause':'remote_access_denied','http':response.status_code})
                break
            if response.status_code!=200 or not 5000<=len(response.content)<=24_000_000:
                failure_types.append({'position':position,'cause':'invalid_public_media_response','http':response.status_code})
                continue
            if not response.headers.get('Content-Type','').lower().startswith('image/'):
                failure_types.append({'position':position,'cause':'unexpected_content_type'})
                continue
            raw=response.content
            meta,preview,fmt=inspect(raw)
            digest=meta['sha256']
            if digest in seen:
                duplicates+=1
                print('OBSERVED_PUBLIC_PHOTO_ALREADY_STORED',position,'sha',digest[:16], 'albums',','.join(sorted(seen_in.get(digest,[]))),flush=True)
                continue
            seen.add(digest)
            n=next_number
            next_number+=1
            prefix=f'{n:05d}-{digest[:16]}'
            key=f'originals/{ALBUM}/{prefix}.{meta.pop("extension")}'
            prev=f'previews/{ALBUM}/{prefix}.webp'
            atomic_bytes(out/key,raw)
            atomic_bytes(out/prev,preview)
            images.append({**meta,'number':n,'key':key,'preview':prev,
                           'preview_sha256':hashlib.sha256(preview).hexdigest(),
                           'preview_bytes':len(preview),
                           'published_public_page_position':position,
                           'numbering_provenance':'archive_append_order_not_publisher_number'})
            print('OBSERVED_PUBLIC_PHOTO_REAL_BYTES_SAVED',position,n,len(raw),digest[:16],flush=True)
        except (requests.RequestException,OSError,ValueError) as exc:
            failure_types.append({'position':position,'cause':type(exc).__name__})
    metadata=out/'metadata'
    metadata.mkdir(parents=True,exist_ok=True)
    catalog={'schema_version':1,'model':MODEL,'storage':'owner-private-terabox-sha-verified-bytes',
             'albums':[{'id':ALBUM,'title':current.get('title') if current else '[DJAWA] Mimmi - Sukajan Gal',
                        'publisher':'DJAWA','expected':177,'complete':False,'images':images}] if images else []}
    (metadata/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    audit={'model':MODEL,'source':PUBLIC_SOURCE,'album':ALBUM,
           'existing_album_owner_rows':oldcount,'first_page_links_observed':len(OBSERVED_PUBLIC_IMAGE_URLS),
           'downloaded_new_this_invocation':len(images),'new_local_individual_files':len(images),
           'duplicate_sha_skipped':duplicates,
           'remote_verified_files':0,'gallery_open_verified_files':0,'failures':failure_types,
           'results':[{'id':ALBUM,'pages':1,'published_image_candidates':10,
                       'individual_files_saved':len(images),'failures':failure_types}]}
    (metadata/'collection-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print('INDEPENDENT_OBSERVED_SOURCE_FILES_DECODED',len(images),'FAILURES',len(failure_types),flush=True)
    return audit

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--owner',type=Path,required=True)
    p.add_argument('--public',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    acquire(a.owner,a.public,a.out)
