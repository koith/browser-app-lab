#!/usr/bin/env python3
"""Collect REAL, distinct, decoded photos for all registered Mimmi/Yui public works.

Only public HTML and image URLs that existing direct_photo_pipeline validates:
no paid media, authentication bypass, Cloudflare rereads, ZIPs or synthetic rows.
Stages are persistent for the job; publication can be safely replayed onto an
updated GitHub main without re-downloading upstream images.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/'apps/gallery-archive'
PRIORITY={
 'mimmi':(
  'djawa-pop-kitty-party','djawa-nikke-yuni',
  'djawa-janus-scary-lantern-night','djawa-rudy2-codename-wolfgirl',
  'djawa-twin-bunnies-affair','djawa-my-summer-vacation-vol-5',
 ),
 'yui':(
  'yui-meow-public-samples','artgravia-677-yui-public-samples',
  'crazygiant-player5-public','djawa-privaty-public-samples',
  'yui-summer-public-samples',
 ),
}


def work_batches(model, run_number, base=ROOT, batch_size=7):
    """Always prioritize low-inventory works; rotate remaining full corpus."""
    if model not in PRIORITY or batch_size<1:
        raise ValueError('INVALID_COLLECTION_MODEL_OR_BATCH')
    path=Path(base)/f'apps/{model}-gallery/public-work-pages.json'
    registry=json.loads(path.read_text(encoding='utf-8'))
    works=registry.get('albums')
    if not isinstance(works,list) or not works:
        raise ValueError('PUBLIC_SOURCE_REGISTRY_MISSING')
    all_ids=[a['id'] for a in works]
    if len(all_ids)!=len(set(all_ids)):
        raise ValueError('DUPLICATE_PUBLIC_WORK_IDS')
    priority=[aid for aid in PRIORITY[model] if aid in all_ids]
    rest=[aid for aid in all_ids if aid not in priority]
    if rest:
        offset=((max(run_number,1)-1)*batch_size)%len(rest)
        rest=rest[offset:]+rest[:offset]
    # Keep priority works in a separate, longer-pagination batch.
    return ([priority] if priority else []) + [
        rest[i:i+batch_size] for i in range(0,len(rest),batch_size)
    ]


def execute(args):
    batches=work_batches(args.model,args.run_number,ROOT,args.batch_size)
    stage=Path(args.stage).resolve()
    if args.plan_only:
        print('GALLERY_MISSING_FULL_PLAN',json.dumps({
          'model':args.model,'registered_work_count':sum(map(len,batches)),
          'priority_count':len(batches[0]) if batches else 0,
          'batches':batches},ensure_ascii=False),flush=True)
        return 0
    stage.mkdir(parents=True,exist_ok=True)
    source_evidence=Path(args.source_evidence).resolve() if args.source_evidence else None
    reports=[]
    collected=0
    for index,ids in enumerate(batches):
        target=stage/('batch-'+str(index).zfill(2))
        catalog=target/'metadata/catalog.json'
        command=[sys.executable,str(ARCHIVE/'direct_photo_pipeline.py'),
          '--model',args.model,'--owner',f'apps/{args.model}-gallery/owner-index.json',
          '--out',str(target),'--max-new',str(args.max_per_batch),
          '--max-pages',str(5 if index==0 else 3),
          '--page-cycle',str(args.run_number),'--render-budget','0',
          '--reviewed-source-only']
        if source_evidence and source_evidence.is_file():
            command.extend(['--reverse-evidence',str(source_evidence)])
        if index==0 and args.alternate_priority:
            command.append('--alternative-engines')
        for aid in ids:
            command.extend(['--album-id',aid])
        print('FULL_COLLECTION_BATCH_START',args.model,index,'work_count',len(ids),flush=True)
        result=subprocess.run(command,cwd=ROOT,timeout=args.batch_timeout,check=False)
        row={'batch':index,'works':ids,'collector_returncode':result.returncode,
             'new_sha_verified_originals':0,'total_bytes_added':0}
        if result.returncode==0 and catalog.is_file():
            try:
                proc=subprocess.run([sys.executable,str(ARCHIVE/'publish_new_public_photos_to_pages.py'),
                    '--model',args.model,'--stage',str(target),
                    '--limit',str(args.max_per_batch),'--budget',str(args.bytes_per_batch)],
                    cwd=ROOT,timeout=180,check=False)
                row['publisher_returncode']=proc.returncode
                if proc.returncode==0:
                    publication=json.loads((target/'metadata/pages-publication.json').read_text())
                    row['new_sha_verified_originals']=publication['new_sha_verified_originals']
                    row['total_bytes_added']=publication['total_bytes_added']
                    collected+=row['new_sha_verified_originals']
            except (ValueError,OSError,subprocess.TimeoutExpired) as error:
                row['publication_error']=type(error).__name__
        reports.append(row)
        print('FULL_COLLECTION_BATCH_RESULT',json.dumps(row,ensure_ascii=False),flush=True)
    report={'model':args.model,'registered_works_visited':sum(map(len,batches)),
            'batches':reports,'new_local_verified_SHA':collected,
            'new_remote_SHA_readback_verified':0,
            'new_public_Pages_verified':0,
            'scope':'public_authenticated-free_only',
            'state':'LOCAL_PUBLICATION_STAGED_NOT_DEPLOYED'}
    (stage/'full-collection-summary.json').write_text(
       json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('FULL_COLLECTION_MODEL_RESULT',json.dumps(report,ensure_ascii=False),flush=True)
    if not any(x['collector_returncode']==0 for x in reports):
        return 2
    if any(x.get('publisher_returncode',0)!=0 for x in reports):
        return 3
    return 0


def replay(model,stage,max_per_batch,bytes_per_batch):
    from publish_new_public_photos_to_pages import publish
    stage=Path(stage)
    count=0
    for folder in sorted(stage.glob('batch-*')):
        if not (folder/'metadata/catalog.json').is_file():
            continue
        doc=publish(model,folder,root=ROOT,budget=bytes_per_batch,limit=max_per_batch)
        count+=doc['new_sha_verified_originals']
    print('FULL_COLLECTION_REBASED_MAIN_NEW_SHA',model,count,flush=True)
    return count


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',choices=tuple(PRIORITY),required=True)
    p.add_argument('--run-number',type=int,default=1)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--source-evidence',type=Path)
    p.add_argument('--batch-size',type=int,default=7)
    p.add_argument('--max-per-batch',type=int,default=48)
    p.add_argument('--bytes-per-batch',type=int,default=36000000)
    p.add_argument('--batch-timeout',type=int,default=1200)
    p.add_argument('--alternate-priority',action='store_true')
    p.add_argument('--plan-only',action='store_true')
    p.add_argument('--replay-only',action='store_true')
    a=p.parse_args()
    if (not 1<=a.batch_size<=20 or not 1<=a.max_per_batch<=90 or
            not 1000000<=a.bytes_per_batch<=80000000 or
            not 60<=a.batch_timeout<=2000 or a.run_number<0):
        raise SystemExit('INVALID_SAFE_COLLECTION_BOUNDS')
    if a.replay_only:
        replay(a.model,a.stage,a.max_per_batch,a.bytes_per_batch)
        return
    sys.exit(execute(a))


if __name__=='__main__':
    main()
