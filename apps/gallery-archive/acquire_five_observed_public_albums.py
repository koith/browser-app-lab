#!/usr/bin/env python3
"""Acquire only individually OBSERVED published public album photo URLs.

Does not enumerate or guess filenames, bypass access control, collect paid
files, or claim five complete paid photobooks from 12 public previews.
Uses the existing SHA, decode, visual dedupe and stored-albums publisher.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, UnidentifiedImageError
from publish_new_public_photos_to_pages import publish

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_SOURCE=ROOT/'apps/gallery-archive/five_public_observed_yui_20261116.json'
MAX_BYTES=16_000_000

def fetch_individual(client,url):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or parsed.hostname!='showartx.net'
            or parsed.port not in (None,443) or parsed.username
            or parsed.password or parsed.fragment
            or not parsed.path.startswith('/wp-content/uploads/')
            or not parsed.path.lower().endswith('.jpg')):
        raise ValueError('UNSAFE_NON_OBSERVED_PUBLIC_ASSET_ORIGIN')
    response=client.get(url,timeout=(8,25),allow_redirects=False,
                        headers={'Accept':'image/jpeg',
                                 'User-Agent':'PublicPhotobookBackup/1.0'})
    if response.status_code!=200:
        raise ValueError('PUBLIC_IMAGE_HTTP_'+str(response.status_code))
    if 'image/' not in response.headers.get('Content-Type','').lower():
        raise ValueError('PUBLIC_IMAGE_NOT_IMAGE_CONTENT')
    raw=response.content
    if not 20_000<=len(raw)<=MAX_BYTES:
        raise ValueError('PUBLIC_IMAGE_BYTE_LENGTH_REJECTED')
    return raw

def acquire(source=DEFAULT_SOURCE,root=ROOT,stage=None,client=None,max_photos=60):
    source=Path(source);root=Path(root);stage=Path(stage)
    doc=json.loads(source.read_text(encoding='utf-8'))
    if (doc.get('schema_version')!=1 or doc.get('model')!='yui'
            or len(doc.get('albums',[]))!=5 or not 1<=max_photos<=60):
        raise ValueError('WRONG_FIVE_PUBLIC_PREVIEW_INPUT')
    base=root/'apps/yui-gallery'
    registered=json.loads((base/'public-work-pages.json').read_text(encoding='utf-8'))
    known={a['id']:a for a in registered['albums']}
    client=client or requests.Session()
    results=[]
    remaining=max_photos
    for item in doc['albums']:
        aid=item['id']
        if (aid not in known or item['source']!=known[aid]['source']
                or len(item.get('public_image_observations',[]))!=12):
            raise ValueError('UNREVIEWED_OR_WRONG_PUBLIC_PREVIEW_EDITION')
        folder=stage/aid
        photo_rows=[]
        tried=0;failures=[]
        for index,asset in enumerate(item['public_image_observations'],1):
            if remaining<=0:break
            remaining-=1
            tried+=1
            url=asset['url']
            try:
                raw=fetch_individual(client,url)
                # decoded bytes are verified below before publication
            except TypeError:
                # Never mask failures with a fabricated staged file.
                raise
            except (requests.RequestException,ValueError,OSError) as e:
                failures.append({'position':index,'error':type(e).__name__,
                                 'detail':str(e)[:90]})
                continue
            dest=folder/'raw'/(str(index).zfill(3)+'.jpg')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw)
            try:
                with Image.open(dest) as image:
                    image.verify()
                with Image.open(dest) as image:
                    image.load()
                    width,height=image.size
                    if image.format!='JPEG' or min(width,height)<450:
                        raise ValueError('LOW_RESOLUTION_OR_WRONG_IMAGE_FORMAT')
            except (ValueError,UnidentifiedImageError,OSError):
                dest.unlink(missing_ok=True)
                failures.append({'position':index,'error':'INVALID_DECODED_IMAGE'})
                continue
            photo_rows.append({
                'number':index,'key':str(dest.relative_to(folder)),
                'sha256':hashlib.sha256(raw).hexdigest(),
                'bytes':len(raw),'width':width,'height':height,
                'source_url':url,
                'source_photo_number':asset['source_filename_number'],
                'numbering_provenance':'published_source_order'})
        metadata=folder/'metadata'
        metadata.mkdir(parents=True,exist_ok=True)
        (metadata/'catalog.json').write_text(json.dumps({
            'schema_version':1,'model':'yui','albums':[{
                'id':aid,'title':item['name'],'images':photo_rows
            }]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        pub=publish('yui',folder,root=root,budget=60_000_000,limit=60)
        results.append({
            'album_id':aid,'declared_full_photos':item['declared_publisher_photos'],
            'publicly_observed_photo_urls':len(item['public_image_observations']),
            'urls_attempted':tried,'valid_decoded_assets':len(photo_rows),
            'new_unique_gallery_photos':pub['new_sha_verified_originals'],
            'same_frame_duplicates':pub['same_frame_duplicate_SHA_files_skipped'],
            'quality_upgrades_still_deferred':pub['quality_upgrades_held_for_verified_replacement'],
            'failures':failures})
    report={'schema_version':1,'model':'yui',
            'scope':'public previews, never full paid editions',
            'albums_attempted':len(results),
            'new_gallery_photos':sum(x['new_unique_gallery_photos'] for x in results),
            'full_publisher_editions_completed':0,
            'results':results}
    stage.mkdir(parents=True,exist_ok=True)
    (stage/'five-public-photo-backfill-report.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('FIVE_ALBUMS_ACTUAL_PUBLIC_PHOTO_BACKFILL',
          json.dumps(report,ensure_ascii=False),flush=True)
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--stage',type=Path,required=True)
    parser.add_argument('--max-photos',type=int,default=60)
    a=parser.parse_args()
    report=acquire(a.source,a.root,a.stage,max_photos=a.max_photos)
    if report['new_gallery_photos']==0:
        print('NO_NEW_SHA_PHOTOS_CONFIRMED',flush=True)

if __name__=='__main__':
    main()
