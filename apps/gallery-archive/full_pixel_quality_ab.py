#!/usr/bin/env python3
"""Every physically committed Yui/Mimmi gallery image: independent pHash vs dHash.

The owner private TeraBox originals have only metadata in Git. Do not claim
their pixels were measured unless their actual file bytes are present here.
This is a quality/duplicate evidence audit, never automatic image replacement.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[2]


def entries(root=ROOT):
    root=Path(root)
    photos=[];total_owner=0;owner_albums=0
    for model in ('yui','mimmi'):
        base=root/'apps'/(model+'-gallery')
        owner=json.loads((base/'owner-index.json').read_text(encoding='utf-8'))
        total_owner+=int(owner.get('physical_originals_indexed',0))
        owner_albums+=len(owner.get('albums',[]))
        data=json.loads((base/'stored-albums.json').read_text(encoding='utf-8'))
        for a in data.get('albums',[]):
            for photo in a.get('images',[]):
                rel=photo.get('url','')
                if not isinstance(rel,str) or not rel.startswith('stored-albums/') or '..' in rel.split('/'):
                    continue
                path=base/rel
                photos.append({'model':model,'album':a['id'],'path':path,
                               'path_relative':str(path.relative_to(root)),
                               'number':photo.get('number'),
                               'claimed_sha':photo.get('sha256'),
                               'claimed_width':photo.get('width'),
                               'claimed_height':photo.get('height')})
    return photos,{'all_owner_original_positions':total_owner,'owner_albums':owner_albums,
                   'repo_committed_photo_rows':len(photos)}


def choose_shard(row,shards):
    digest=sha256(row['path_relative'].encode()).digest()
    return int.from_bytes(digest[:8],'big')%shards


def scan_photo(row):
    # The aggregator imports entries/choose_shard but never opens pixels.
    # Pillow/imagehash are needed only in shard scan workers.
    from PIL import Image, ImageOps
    import imagehash
    path=row['path'];root=ROOT.resolve()
    if not path.resolve().is_relative_to(root) or not path.is_file() or path.is_symlink():
        return {'status':'missing_file','path':row['path_relative']}
    try:
        import audit_stored_image_quality
        raw=path.read_bytes()
        digest=sha256(raw).hexdigest()
        with Image.open(path) as im:
            im.load()
            orientation=ImageOps.exif_transpose(im).convert('RGB')
            actual_size=[im.width,im.height]
            dhash=imagehash.dhash(orientation,hash_size=8)
            phash=imagehash.phash(orientation,hash_size=8)
        detail=audit_stored_image_quality.metric(path)
        issues=[]
        if digest!=row['claimed_sha']:issues.append('sha256_differs_from_manifest')
        if actual_size!=[row['claimed_width'],row['claimed_height']]:
            issues.append('dimensions_differ_from_manifest')
        return {'status':'decoded_sha256_verified' if not issues else 'metadata_disagreement',
                'model':row['model'],'album':row['album'],
                'path':row['path_relative'],'number':row['number'],
                'sha256':digest,'dhash64':str(dhash),'phash64':str(phash),
                'file_bytes':len(raw),'width':im.width,'height':im.height,
                'detail_index':detail['center_detail_index'],
                'encoded_bytes_per_pixel':round(len(raw)/(im.width*im.height),5),
                'review_flags':issues}
    except Exception as exc:
        return {'status':'decode_error_'+type(exc).__name__,
                'path':row['path_relative'],'model':row['model'],'album':row['album']}


def run(root,out,model,shard,shards):
    photos,scope=entries(root)
    assigned=[x for x in photos if x['model']==model and choose_shard(x,shards)==shard]
    results=[scan_photo(x) for x in assigned]
    tally=Counter(x['status'] for x in results)
    findings={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'model':model,'shard':shard,'shards':shards,'scope':scope,
        'expected_photo_rows':len(assigned),'reported_photo_rows':len(results),
        'metadata_or_decode_statuses':dict(tally),
        'actual_pixel_scan_complete':len(assigned)==len(results) and
               not any(x['status']!='decoded_sha256_verified' for x in results),
        'owner_private_originals_pixel_inspected':False,
        'owner_private_originals_not_in_repo_not_scored':True,
        'auto_deleted_or_replaced_files':0,'records':results}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(findings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PHOTO_PIXEL_ALL_SHARD',json.dumps({
        'model':model,'shard':shard,'tested':len(results),'statuses':dict(tally),
        'repo_photo_rows':scope['repo_committed_photo_rows']},ensure_ascii=False),flush=True)
    return findings


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--model',choices=['yui','mimmi'],required=True)
    ap.add_argument('--shard',type=int,required=True)
    ap.add_argument('--shards',type=int,default=8)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if not 1<=a.shards<=32 or not 0<=a.shard<a.shards:raise ValueError('invalid_shard')
    run(a.root,a.out,a.model,a.shard,a.shards)

if __name__=='__main__':main()
