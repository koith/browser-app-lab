#!/usr/bin/env python3
"""Lossless full-image pHash-vs-dHash comparison for all Git-committed originals."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import json

from full_pixel_quality_ab import entries,choose_shard,ROOT


def compare(root,reports,out,shards=8):
    allphotos,scope=entries(root)
    expected={(p['model'],p['path_relative'],p['album'],p['number']) for p in allphotos}
    rows=[];reported=set();shard_ids=set()
    for path in Path(reports).glob('photo-pixel-*.json'):
        j=json.loads(path.read_text(encoding='utf-8'))
        ident=(j['model'],j['shard'])
        if ident in shard_ids:raise ValueError('duplicate_shard')
        if j.get('shards')!=shards:raise ValueError('wrong_shard_count')
        if j.get('actual_pixel_scan_complete') is not True:raise ValueError('incomplete_pixel_scan')
        shard_ids.add(ident)
        for r in j['records']:
            key=(r.get('model'),r.get('path'),r.get('album'),r.get('number'))
            if key in reported:raise ValueError('duplicate_photo')
            if key not in expected:raise ValueError('unexpected_photo')
            if choose_shard({'path_relative':r.get('path')},shards)!=j['shard']:raise ValueError('wrong_photo_shard')
            if r.get('model')!=j['model']:raise ValueError('wrong_photo_model')
            reported.add(key);rows.append(r)
    missing=expected-reported;unexpected=reported-expected
    expected_shards={(m,i) for m in ('yui','mimmi') for i in range(shards)}
    decoded=[r for r in rows if r['status']=='decoded_sha256_verified']
    found={}
    stats=Counter()
    groups=defaultdict(list)
    for i,r in enumerate(decoded):
        groups[r['sha256']].append(i)
    for a in range(len(decoded)):
        one=decoded[a]
        for b in range(a+1,len(decoded)):
            other=decoded[b]
            if one['sha256']==other['sha256']:
                stats['exact_sha_pairs']+=1
                continue
            # Characteristic 64-bit comparisons; reported as review-only
            # candidate pairs, never automatic identity determination.
            if min(one['width'],one['height'],other['width'],other['height'])<250:
                continue
            ratio=(one['width']/one['height'])/(other['width']/other['height'])
            if abs(ratio-1)>.04:continue
            d=(int(one['dhash64'],16)^int(other['dhash64'],16)).bit_count()
            p=(int(one['phash64'],16)^int(other['phash64'],16)).bit_count()
            isd=d<=5;isp=p<=8
            if isd:stats['dhash_candidates']+=1
            if isp:stats['phash_candidates']+=1
            if isd and isp:stats['both_candidates']+=1
            if isd and not isp:stats['dhash_only']+=1
            if isp and not isd:stats['phash_only']+=1
            if isd or isp:
                if one['album']!=other['album']:stats['cross_work_pairs']+=1
                if len(found)<500 and (isd != isp or d==0 or p==0):
                    key=(one['path'],other['path'])
                    found[key]={'model_pair':[one['model'],other['model']],
                        'path_a':one['path'],'path_b':other['path'],
                        'dhash_hamming':d,'phash_hamming':p,
                        'same_album':one['album']==other['album'],
                        'review_candidate_only':True}
    by_album=defaultdict(list)
    for r in decoded:by_album[(r['model'],r['album'])].append(r)
    quality_flags=[]
    for album,photos in by_album.items():
        vals=sorted(x['detail_index'] for x in photos)
        median=vals[len(vals)//2]
        for row in photos:
            suspect=(len(photos)>=6 and median>.08 and row['detail_index']<median*.42)
            sparse=(row['width']*row['height']>=2_000_000 and
                    row['encoded_bytes_per_pixel']<.04)
            if suspect or sparse:
                quality_flags.append({'model':row['model'],'album':row['album'],
                    'path':row['path'],'flags':(['relative_soft_detail'] if suspect else [])+
                    (['very_sparse_encoding'] if sparse else []),'pixel_recheck_only':True})
    summary={'owner_original_positions_metadata_only':scope['all_owner_original_positions'],
        'owner_albums':scope['owner_albums'],
        'committed_gallery_photo_records':len(expected),
        'actual_records_seen':len(rows),
        'physically_sha_and_pixel_verified':len(decoded),
        'decode_or_metadata_errors':dict(Counter(x['status'] for x in rows if x['status']!='decoded_sha256_verified')),
        'shards_expected':len(expected_shards),'shards_seen':len(shard_ids),
        'all_committed_photo_paths_accounted_for':
            not(missing or unexpected or expected_shards-shard_ids),
        'all_committed_photo_pixels_verified':len(decoded)==len(expected) and
            not(missing or unexpected or expected_shards-shard_ids),
        'owner_TeraBox_only_originals_actually_decoded':False,
        'duplicate_review_pair_counts':dict(stats),
        'pixel_quality_review_flags':len(quality_flags),
        'new_originals_stored':0,'gallery_images_added':0}
    report={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'summary':summary,'missing_records':[list(x) for x in sorted(missing)],
        'unexpected_records':[list(x) for x in sorted(unexpected)],
        'missing_shards':[list(x) for x in sorted(expected_shards-shard_ids)],
        'representative_disagreement_pairs':list(found.values()),
        'pixel_quality_review_candidates':quality_flags,
        'warning':'No automatic photo merging, watermark erasing, or replacing; private originals outside Git are not measured.'}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ALL_PHOTO_HASH_QUALITY_COMPARISON',json.dumps(summary,ensure_ascii=False),flush=True)
    if not summary['all_committed_photo_paths_accounted_for']:
        raise SystemExit('At least one committed file was not processed')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--report-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--shards',type=int,default=8)
    a=p.parse_args()
    compare(a.root,a.report_dir,a.out,a.shards)

if __name__=='__main__':main()
