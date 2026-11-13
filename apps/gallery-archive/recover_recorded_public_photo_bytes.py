#!/usr/bin/env python3
"""Physically recover source-observed, exact-SHA-pinned Mimmi public JPEGs.

The saved official/V2PH manifests contain byte SHA + dimensions recorded from
real previous public-photo GETs. Recover only those exact unmodified image
bytes, in the right edition, without needing a fresh search/site workaround.
A URL list, plausible photo, watermark re-encode or new SHA is NOT archival
proof. Respect robots, hard HTTP denials, source labels and existing originals.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/yui-gallery'))
from public_photo_archive import PublicSession
from official_sample_recovery import _publisher_page, _publisher_photo

SHA=re.compile(r'^[0-9a-f]{64}$')
ID=re.compile(r'^[a-z0-9][a-z0-9-]{1,100}$')
V2PH_SRC=re.compile(r'^/album/[a-z0-9]{8,16}\.html$',re.I)
V2PH_JPG=re.compile(r'^/photos/[A-Za-z0-9_-]{8,80}\.(?:jpe?g|png|webp)$',re.I)

def validated(row, kind, source):
    if not isinstance(row,dict):
        return False
    url=row.get('url')
    sha=row.get('sha256')
    if not isinstance(url,str) or not isinstance(sha,str) or not SHA.fullmatch(sha):
        return False
    if type(row.get('bytes')) is not int or not 4500<=row['bytes']<=12_000_000:
        return False
    if any(type(row.get(k)) is not int or not 280<=row[k]<=12000 for k in ('width','height')):
        return False
    p=urlsplit(url)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or p.query or p.fragment:
        return False
    if kind=='official':
        return _publisher_page(source) and _publisher_photo(url)
    s=urlsplit(source)
    return bool(s.scheme=='https' and s.hostname in ('www.v2ph.com','v2ph.com')
        and not s.query and not s.fragment and V2PH_SRC.fullmatch(s.path)
        and p.hostname=='cdn.v2ph.com' and V2PH_JPG.fullmatch(p.path))

def candidates(base, kinds, saved_sha):
    groups=[]
    for kind,filename in (('official','official-previews.json'),('v2ph','v2ph-actor-previews.json')):
        if kind not in kinds:
            continue
        document=json.loads((base/filename).read_text(encoding='utf-8'))
        for album in document['albums']:
            aid,source=album.get('id'),album.get('source')
            if not isinstance(aid,str) or not ID.fullmatch(aid) or not isinstance(source,str):
                continue
            grouped={}
            for row in album.get('samples',[]):
                if not validated(row,kind,source):
                    continue
                if row['sha256'] in saved_sha:
                    continue
                grouped.setdefault(row['url'],{})[row['sha256']]=row
            for url,variants in grouped.items():
                groups.append({'kind':kind,'id':aid,'title':album.get('title') or aid,
                  'origin_page':source,'url':url,'variants':list(variants.values())})
    return groups

def decode(raw):
    with Image.open(BytesIO(raw)) as img:
        img.verify()
    with Image.open(BytesIO(raw)) as img:
        img.load()
        return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                'width':img.width,'height':img.height,
                'extension':{'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(img.format)}

def recover(root=ROOT,kind='both',max_new=80,max_bytes=75_000_000,client=None):
    root=Path(root);base=root/'apps/mimmi-gallery'
    owner=json.loads((base/'owner-index.json').read_text(encoding='utf-8'))
    oldpath=base/'stored-albums.json';stored=json.loads(oldpath.read_text(encoding='utf-8'))
    if owner.get('model')!='mimmi' or stored.get('model')!='mimmi':
        raise ValueError('Source owner/storage model mismatch')
    saved_sha={p['sha256'] for a in owner['albums'] for p in a.get('images',[])}
    saved_sha.update(p['sha256'] for a in stored['albums'] for p in a.get('images',[]))
    albums={a['id']:a for a in stored['albums']}
    kinds={'official','v2ph'} if kind=='both' else {kind}
    work=candidates(base,kinds,saved_sha)
    # Prioritize editions with an actual missing SHA in the historic manifest;
    # avoid re-downloading any URL for a work already completely SHA covered.
    http=client or PublicSession(delay=.35)
    stats=Counter()
    errors=[]
    additions=[];used=0
    for i,item in enumerate(work,1):
        if len(additions)>=max_new or used>=max_bytes:
            break
        sha_variants={v['sha256']:v for v in item['variants'] if v['sha256'] not in saved_sha}
        if not sha_variants:
            stats['now_already_present']+=1;continue
        stats['attempted_urls']+=1
        try:
            raw=http.get(item['url']).content
            meta=decode(raw)
            if not meta['extension'] or meta['sha256'] not in sha_variants:
                stats['not_historical_sha']+=1
                continue
            old=sha_variants[meta['sha256']]
            if any(meta[k]!=old[k] for k in ('bytes','width','height')):
                stats['checksum_or_dimensions_changed']+=1
                continue
            if meta['sha256'] in saved_sha:
                stats['now_already_present']+=1
                continue
            if used+meta['bytes']>max_bytes:
                stats['budget_skipped']+=1
                continue
            aid=item['id']
            rec=albums.get(aid)
            if rec is None:
                rec={'id':aid,'title':item['title'],'source':item['origin_page'],
                     'status':'public_verified_local_orig_files','images':[]}
                albums[aid]=rec
            occupied={p['number'] for p in rec['images']}
            number=max(occupied|{0})+1
            rel=f"stored-albums/{aid}/{meta['sha256'][:20]}.{meta['extension']}"
            dest=(base/rel).resolve()
            if not dest.is_relative_to(base.resolve()):
                raise ValueError('Invalid photo destination')
            if dest.exists():
                if dest.read_bytes()!=raw:
                    raise ValueError('Immutable SHA file collision')
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(raw)
            rec['images'].append({'number':number,'url':rel,'sha256':meta['sha256'],
               'bytes':meta['bytes'],'width':meta['width'],'height':meta['height'],
               'origin_page':item['origin_page'],'source_url':item['url'],
               'quality':'historically_sha_pinned_public_bytes_not_paid_master',
               'numbering_provenance':'observed_public_source_photo_not_publisher_master'})
            saved_sha.add(meta['sha256']);used+=meta['bytes']
            additions.append({'album':aid,'sha256':meta['sha256'],
                              'bytes':meta['bytes'],'url':rel,'source_kind':item['kind']})
            stats['new_real_files']+=1
        except Exception as exc:
            key=type(exc).__name__
            stats['failed_'+key]+=1
            if len(errors)<35:
                errors.append({'album':item['id'],'source_kind':item['kind'],
                    'url':item['url'],'error_type':key,'detail':str(exc)[:140]})
        if i%30==0:
            print('MIMMI_RECORDED_PUBLIC_PHYSICAL_PROGRESS',i,'/',len(work),
                  'new',len(additions),'bytes',used,flush=True)
    if additions:
        stored['albums']=list(albums.values())
        stored['updated']=datetime.now(timezone.utc).isoformat()
        if type(stored.get('physical_verified_image_count')) is int:
            stored['physical_verified_image_count']=sum(len(a['images']) for a in stored['albums'])
        oldpath.write_text(json.dumps(stored,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'kind':kind,'candidate_historic_source_urls':len(work),
      'real_physical_new_sha':len(additions),'real_bytes_added':used,
      'not_publisher_master':True,'not_full_collection':True,
      'source_and_sha_validated':True,'statistics':dict(stats),
      'files':additions,'errors':errors}
    path=root/'.gallery-public-recovery-report.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('MIMMI_RECORDED_REAL_PHYSICAL_SHA_PAGES_REPORT',
          json.dumps(report,ensure_ascii=False),flush=True)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--kind',choices=['official','v2ph','both'],default='both')
    p.add_argument('--max-new',type=int,default=80)
    p.add_argument('--max-bytes',type=int,default=75000000)
    a=p.parse_args()
    if not 1<=a.max_new<=300 or not 1_000_000<=a.max_bytes<=250_000_000:
        raise ValueError('Invalid bounded photo budget')
    recover(a.root,a.kind,a.max_new,a.max_bytes)

if __name__=='__main__':
    main()
