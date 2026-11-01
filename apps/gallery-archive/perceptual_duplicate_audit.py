#!/usr/bin/env python3
"""Hydrus-inspired, review-only near-duplicate evidence for staged originals.

No file deletion, replacement, album merging, upload, or gallery publication.
A 64-bit difference hash is only a candidate generator, not proof of identity.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from PIL import Image, ImageOps, ImageStat, ImageChops

FORMATS={'.jpg','.jpeg','.png','.webp'}
MAX_BYTES=32_000_000
MAX_FILES=1500


def scan_image(raw):
    if len(raw)>MAX_BYTES:raise ValueError('oversize_image')
    with Image.open(BytesIO(raw)) as src:
        src.load()
        im=ImageOps.exif_transpose(src).convert('RGB')
    if min(im.size)<96:raise ValueError('too_small_for_perceptual_comparison')
    gray=ImageOps.grayscale(im).resize((9,8),Image.Resampling.LANCZOS)
    v=list(gray.getdata());bits=0
    for y in range(8):
        for x in range(8):
            bits=(bits<<1)|(v[y*9+x]>v[y*9+x+1])
    return {'sha256':sha256(raw).hexdigest(),'width':im.width,'height':im.height,
            'dhash64':f'{bits:016x}','thumb':im.resize((48,48),Image.Resampling.LANCZOS)}


def candidate_relation(a,b):
    if a['sha256']==b['sha256']:return 'same_sha256',0,0.0
    if abs((a['width']/a['height'])/(b['width']/b['height'])-1)>0.025:
        return None,None,None
    distance=(int(a['dhash64'],16)^int(b['dhash64'],16)).bit_count()
    if distance>5:return None,distance,None
    mean=max(ImageStat.Stat(ImageChops.difference(a['thumb'],b['thumb'])).mean)
    if distance<=3 and mean<=8.0:
        return 'perceptually_similar_review',distance,round(mean,3)
    if distance<=5 and mean<=15.0:
        return 'weak_visual_candidate_review',distance,round(mean,3)
    return None,distance,round(mean,3)


def scan_stage(stage,max_files=MAX_FILES):
    stage=Path(stage).resolve()
    orig=stage/'originals'
    if not 1<=max_files<=MAX_FILES:raise ValueError('max_files_out_of_range')
    result={'schema_version':1,'method':'dhash64_plus_same_scale_rgb',
            'mode':'evidence_only_no_gallery_mutation','files_scanned':0,
            'files_skipped':0,'review_pairs':[],'pairs_omitted':0}
    if not orig.is_dir():return result
    paths=sorted(p for p in orig.rglob('*') if p.is_file() and p.suffix.lower() in FORMATS)
    if len(paths)>max_files:raise ValueError('unbounded_stage_images')
    rows=[]
    for p in paths:
        if p.is_symlink() or not p.resolve().is_relative_to(orig.resolve()):
            result['files_skipped']+=1
            continue
        try:
            if p.stat().st_size>MAX_BYTES:raise ValueError('oversize_image')
            row=scan_image(p.read_bytes())
            rows.append({**row,'path':str(p.relative_to(stage)),
                         'work_id':p.relative_to(orig).parts[0]})
        except (ValueError,OSError,Image.DecompressionBombError):
            result['files_skipped']+=1
    result['files_scanned']=len(rows)
    groups=defaultdict(list)
    for i,row in enumerate(rows):groups[row['sha256']].append(i)
    pairs=[]
    for group in groups.values():
        for j in group[1:]:
            a,b=rows[group[0]],rows[j]
            pairs.append({'a':a['path'],'b':b['path'],'type':'same_sha256',
                          'cross_work_review':a['work_id']!=b['work_id'],
                          'hamming':0,'mean_rgb_difference':0.0})
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if a['sha256']==b['sha256']:continue
            relation,distance,diff=candidate_relation(a,b)
            if relation:
                pairs.append({'a':a['path'],'b':b['path'],'type':relation,
                              'cross_work_review':a['work_id']!=b['work_id'],
                              'hamming':distance,'mean_rgb_difference':diff})
    result['review_pairs']=pairs[:2000]
    result['pairs_omitted']=max(0,len(pairs)-2000)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--stage',type=Path,required=True)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--max-files',type=int,default=MAX_FILES)
    args=ap.parse_args()
    data=scan_stage(args.stage,args.max_files)
    target=args.out or args.stage/'metadata'/'perceptual-duplicate-evidence.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PHOTO_PERCEPTUAL_AUDIT',json.dumps({
        'files_scanned':data['files_scanned'],'review_pairs':len(data['review_pairs']),
        'files_skipped':data['files_skipped'],'mode':data['mode']}))


if __name__=='__main__':main()
