#!/usr/bin/env python3
"""Reject claimed full reverse-image audits when any owner seed/title is missing."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
from reverse_full_corpus_ab import full_census,partition,ROOT


def merge(root,dir,out,shards=8):
    baseline=full_census(root)
    all_seeds={(r['model'],r['album_id'],r['owner_sha256'],r['seed_position'])
               for r in baseline['seeds']}
    all_titles={(r['model'],r['id']) for r in baseline['title_leads']}
    recorded_seeds=set();recorded_titles=set();seen_shards=set();summary=Counter()
    engine_statuses=Counter();candidates={}
    for p in sorted(Path(dir).glob('reverse-full-*.json')):
        d=json.loads(p.read_text(encoding='utf-8'))
        shard=(d['summary']['model'],d['summary']['shard'])
        if shard in seen_shards:raise ValueError('duplicate_shard_'+str(shard))
        seen_shards.add(shard)
        for r in d['photo_seeds']:
            k=(r['model'],r['album_id'],r['owner_sha256'],r['seed_position'])
            if k in recorded_seeds:raise ValueError('duplicate_seed_'+str(k))
            recorded_seeds.add(k)
            summary['queried_seeds']+=1
            summary['total_candidate_links_before_identity_review']+=r['candidate_source_urls']
            summary['identity_supported_links_before_dedup']+=r['approved_candidate_source_urls']
            for engine,details in r['engines'].items():
                engine_statuses[engine+':'+str(details)[:100]]+=1
            for item in r.get('candidates',[]):
                if item.get('identity_hint') and item.get('url'):
                    candidates[item['url']]=candidates.get(item['url'],0)+1
        for t in d['title_leads']:
            k=(d['summary']['model'],t['id'])
            if k in recorded_titles:raise ValueError('duplicate_title_'+str(k))
            recorded_titles.add(k)
            summary['queried_title_leads']+=1
            summary['title_candidate_links_before_dedup']+=t['candidate_count']
            for item in t.get('candidate_pages',[]):
                if item.get('url'):candidates[item['url']]=candidates.get(item['url'],0)+1
    expected_shards={(model,i) for model in ('yui','mimmi') for i in range(shards)}
    missing_seeds=sorted(all_seeds-recorded_seeds)
    missing_titles=sorted(all_titles-recorded_titles)
    unknown=(recorded_seeds-all_seeds,recorded_titles-all_titles)
    report={
        'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'owner_corpus':baseline['summary'],
        'expected_shards':len(expected_shards),'shards_completed':len(seen_shards),
        'missing_shards':[list(x) for x in sorted(expected_shards-seen_shards)],
        'missing_owner_photo_seeds':[list(x) for x in missing_seeds],
        'missing_title_leads':[list(x) for x in missing_titles],
        'unknown_seed_count':len(unknown[0]),'unknown_title_count':len(unknown[1]),
        'exhaustive_registered_seed_and_title_coverage':
            not (missing_seeds or missing_titles or unknown[0] or unknown[1] or expected_shards-seen_shards),
        'counts':dict(summary),
        'unique_candidate_source_pages_not_decoded':len(candidates),
        'engine_status_counts':dict(engine_statuses),
        'new_private_originals_saved':0,'gallery_photos_added':0,
        'not_claimed':'search candidate pages are not image files, completeness or verified visual matches'}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('REVERSE_FULL_ALL_SUMMARY',json.dumps({k:report[k] for k in
        ('expected_shards','shards_completed','exhaustive_registered_seed_and_title_coverage',
         'counts','unique_candidate_source_pages_not_decoded')},ensure_ascii=False),flush=True)
    if not report['exhaustive_registered_seed_and_title_coverage']:
        raise SystemExit('At least one owner seed, title or shard was not queried')
    return report


if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--root',type=Path,default=ROOT)
    a.add_argument('--dir',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--shards',type=int,default=8)
    args=a.parse_args()
    merge(args.root,args.dir,args.out,args.shards)
