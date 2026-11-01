#!/usr/bin/env python3
"""Prove every registered work/source/lead yielded one report across shards.

Never convert search leads, resized URLs, denied sources or research downloads
into claims of private original acquisition or gallery completeness.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
from collector_full_census import census,ROOT

def aggregate(root,report_dir,out,expected_shards=12):
    reference=census(root)
    expected={(t['model'],t['kind'],t['id']):t for t in reference['targets']}
    files=sorted(Path(report_dir).glob('full-*-*.json'))
    actual={};shards=set();failed=[]
    for file in files:
        doc=json.loads(file.read_text(encoding='utf-8'))
        shard=(doc['summary']['model'],doc['summary']['shard'])
        if shard in shards:raise ValueError('duplicate_shard_'+str(shard))
        shards.add(shard)
        if doc['summary']['targets_reported']!=doc['summary']['target_count']:
            failed.append({'shard':shard,'reason':'target_count_mismatch'})
        for row in doc['targets']:
            key=(row['model'],row['kind'],row['id'])
            if key in actual:raise ValueError('same_target_in_multiple_shards_'+str(key))
            actual[key]=row
    missing=set(expected)-set(actual)
    unexpected=set(actual)-set(expected)
    all_needed={(m,i) for m in ('yui','mimmi') for i in range(expected_shards)}
    by_model=defaultdict(lambda:Counter())
    by_host=defaultdict(lambda:Counter())
    limited=[]
    result_rows=[]
    for key,row in sorted(actual.items()):
        model,kind,aid=key
        tally=by_model[model]
        tally['targets']+=1
        tally['registered_page_attempts']+=row.get('registered_page_attempts',0)
        tally['decoded_image_sha_work_sum_not_global_unique']+=row.get('actual_public_images_decoded',0)
        tally['extra_unmatched_asset_groups_research_only']+=row.get('extra_asset_groups_candidate_not_proven_distinct_cuts',0)
        tally['browser_page_200_or_parse_count']+=sum(v for k,v in row.get('engine_page_statuses',{}).items() if k.startswith('browser:') and 'http_403' not in k)
        if row.get('limits'):
            limited.append({'model':model,'kind':kind,'id':aid,'limits':row['limits']})
            tally['limited_targets']+=1
        if row.get('reason') in ('title_only_search_needed','no_physical_public_source_registered'):
            tally['targets_without_registered_source']+=1
        if row.get('reason','').startswith('engine_exception_'):
            tally['engine_exceptions']+=1
        origins={urlsplit(url).hostname for url in expected.get(key,{}).get('urls',[])
                 if urlsplit(url).hostname}
        for host in origins:
            by_host[host]['target_refs']+=1
            if row.get('actual_public_images_decoded',0):
                by_host[host]['targets_with_image_decode']+=1
            if row.get('limits'):by_host[host]['limited_target_refs']+=1
        result_rows.append({'model':model,'kind':kind,'id':aid,
            'owner_registered':row.get('owner_registered',False),
            'pages':row.get('registered_page_attempts',0),
            'candidate_assets':row.get('candidate_distinct_assets_across_methods',0),
            'extra_unmatched_asset_groups_not_proven_cuts':row.get('extra_asset_groups_candidate_not_proven_distinct_cuts',0),
            'decoded_sha':row.get('actual_public_images_decoded',0),
            'limit':row.get('limits',[]),'reason':row.get('reason'),
            'http_statuses':row.get('http_statuses',{})})
    report={
        'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'census_summary':reference['summary'],
        'registered_targets':len(expected),
        'reported_unique_targets':len(actual),
        'missing_target_keys':[list(k) for k in sorted(missing)],
        'unexpected_target_keys':[list(k) for k in sorted(unexpected)],
        'missing_shards':[list(k) for k in sorted(all_needed-shards)],
        'anomalies':failed,
        'exhaustive_registered_target_accounting':
           not (missing or unexpected or all_needed-shards or failed),
        'every_page_successfully_collected':False,
        'public_album_completeness_proven':False,
        'new_private_originals_stored':0,
        'gallery_visible_photos_added':0,
        'by_model':{k:dict(v) for k,v in by_model.items()},
        'by_public_source_host':{k:dict(v) for k,v in sorted(by_host.items())},
        'limited_targets':limited,
        'per_target':result_rows,
        'warning':'100% registry accounting ≠ 100% public photo acquisition. Limits and source errors must remain visible.'
    }
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('EXHAUSTIVE_GALLERY_COMPARE_AGGREGATE',json.dumps({
        k:report[k] for k in ('registered_targets','reported_unique_targets',
            'missing_shards','exhaustive_registered_target_accounting',
            'new_private_originals_stored','gallery_visible_photos_added')},ensure_ascii=False),flush=True)
    if not report['exhaustive_registered_target_accounting']:
        raise SystemExit('Incomplete registered target accounting: do not claim full census')
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--report-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--shards',type=int,default=12)
    a=p.parse_args()
    aggregate(a.root,a.report_dir,a.out,a.shards)

if __name__=='__main__':main()
