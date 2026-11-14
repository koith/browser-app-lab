#!/usr/bin/env python3
"""G-07: publish *actual* verified downloaded public photo bytes from the
existing registered direct collector to free static Pages, never source URLs.

Source collector already enforces model/work/source identity and robots policy.
This layer independently checks immutable SHA, image decode, same-work scope,
global owner/local duplicates and files, then appends without overwriting.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_EXT = {'.jpg': 'JPEG','.jpeg': 'JPEG','.png': 'PNG','.webp': 'WEBP'}

def publish(model, stage, root=ROOT, budget=14_000_000, limit=18):
    assert model in ('mimmi','yui')
    base=Path(root)/'apps'/f'{model}-gallery'
    stage=Path(stage)
    owner=json.loads((base/'owner-index.json').read_text())
    old_path=base/'stored-albums.json'
    old=json.loads(old_path.read_text())
    registered=json.loads((base/'public-work-pages.json').read_text())
    ids={a['id'] for a in registered['albums']}
    existing_sha={p['sha256'] for a in owner['albums'] for p in a['images']}
    existing_sha.update(p['sha256'] for a in old['albums'] for p in a['images'])
    byid={a['id']:a for a in old['albums']}
    stage_doc=json.loads((stage/'metadata/catalog.json').read_text())
    if stage_doc.get('model')!=model:
        raise ValueError('wrong model staged')
    added=[];used=0
    for album in stage_doc.get('albums',[]):
        aid=album.get('id')
        if aid not in ids or not isinstance(aid,str) or not aid.replace('-','').isalnum():
            continue
        source=next(a for a in registered['albums'] if a['id']==aid)
        rec=byid.get(aid)
        if rec is None:
            rec={'id':aid,'title':source.get('title') or album.get('title') or aid,
                 'source':source.get('source',''),'status':'public_verified_local_orig_files',
                 'images':[]}
        for photo in album.get('images',[]):
            digest=photo.get('sha256')
            if not isinstance(digest,str) or len(digest)!=64 or digest in existing_sha:
                continue
            key=photo.get('key','')
            stage_file=(stage/key).resolve()
            if not str(stage_file).startswith(str(stage.resolve())+os.sep) or not stage_file.is_file():
                raise ValueError('missing confined staged image')
            raw=stage_file.read_bytes()
            if len(raw)!=photo.get('bytes') or hashlib.sha256(raw).hexdigest()!=digest:
                raise ValueError('staged original physical SHA mismatch')
            if len(raw)>64_000_000 or used+len(raw)>budget or len(added)>=limit:
                continue
            ext=stage_file.suffix.lower()
            if ext not in ALLOWED_EXT:continue
            with Image.open(stage_file) as im:
                im.verify()
            with Image.open(stage_file) as im:
                im.load()
                if im.format!=ALLOWED_EXT[ext] or im.size!=(photo['width'],photo['height']):
                    raise ValueError('staged source decoded image mismatch')
                if min(im.size)<300:continue
            rel=f'stored-albums/{aid}/{digest[:20]}{ext}'
            dest=base/rel
            if dest.exists() and dest.read_bytes()!=raw:
                raise ValueError('immutable Pages destination collision')
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():dest.write_bytes(raw)
            n=int(photo.get('number') or 0)
            occupied={int(p.get('number') or 0) for p in rec['images']}
            if n<1 or n in occupied:
                n=max(occupied|{0})+1
            # Preserve observed source-file numbering separately from our
            # immutable gallery slot. Losing this evidence prevents later
            # page-by-page missing-cut audits, and source sequence is never
            # represented as the publisher's original sequence.
            recorded={'number':n,'url':rel,
              'sha256':digest,'bytes':len(raw),'width':photo['width'],'height':photo['height'],
              'origin_page':source.get('source'),'source_url':photo.get('source_url',''),
              'quality':'direct_public_original_bytes_not_publisher_master_verified'}
            source_no=photo.get('source_photo_number')
            if type(source_no) is int and 1<=source_no<=25000:
                recorded['source_photo_number']=source_no
                recorded['source_numbering']='public_web_filename_not_publisher_original'
            provenance=photo.get('numbering_provenance')
            if provenance in {
                    'archive_append_order_not_publisher_number',
                    'published_source_order',
                    'official_source_unique_url_append_not_publisher_sequence',
                    'verified_creator_cached_public_feed_append'}:
                recorded['numbering_provenance']=provenance
            rec['images'].append(recorded)
            existing_sha.add(digest);added.append((aid,digest,len(raw)))
            used+=len(raw)
        if rec['images']:
            byid[aid]=rec
    if added:
        old['albums']=list(byid.values())
        old_path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    result={'model':model,'new_sha_verified_originals':len(added),
       'total_bytes_added':used,'sha_samples':[{'album':a,'sha256':s,'bytes':n} for a,s,n in added],
       'real_files_in_pages':bool(added),'private_terabox_readback_verified':False,
       'photo_source_fallback_prohibited':True}
    (stage/'metadata/pages-publication.json').write_text(json.dumps(result,indent=2)+'\n')
    print('G07_ACTUAL_NEW_PUBLIC_PAGES_STORED_SHA',json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--model',choices=['mimmi','yui'],required=True)
    a.add_argument('--stage',type=Path,required=True)
    a.add_argument('--budget',type=int,default=14000000)
    a.add_argument('--limit',type=int,default=18)
    v=a.parse_args()
    publish(v.model,v.stage,budget=v.budget,limit=v.limit)
