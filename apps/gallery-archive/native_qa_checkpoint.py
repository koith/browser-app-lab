"""Resume exact previously opened bytes only after checking successful Actions logs.

Interrupted/failed jobs never establish a checkpoint. A whole-model original and
preview metadata fingerprint must still match; new/changed bytes are retested.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import requests

REPO='koith/browser-app-lab'
WORKFLOW='.github/workflows/gallery-newly-stored-photo-qa.yml'
SHA=re.compile('[a-f0-9]{40}\\Z')
FLAGS=('thumbnail_decoded','lightbox_decoded','original_tab_decoded','download_sha256_verified')


def metadata_fingerprint(owner):
    # Shard membership depends on order. Equal sets in a different order must
    # never transfer successful photo positions to different photographs.
    rows=[(a['id'],p['number'],p['sha256'],p['bytes'],p['width'],p['height'],
        bool(p.get('preview')),p.get('preview_sha256'),p.get('display_rotation'))
        for a in owner['albums'] for p in a['images']]
    return hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()


def changed_rows(before,after):
    old={(a['id'],p['number']):p['sha256'] for a in before['albums'] for p in a['images']}
    return [(a['id'],p) for a in after['albums'] for p in a['images']
            if old.get((a['id'],p['number']))!=p['sha256']]


def in_partition(index,total,shard,shards,partition):
    if partition=='modulo':return index%shards==shard
    if partition=='contiguous':return total*shard//shards<=index<total*(shard+1)//shards
    raise ValueError('Unknown exact-photo partition')


def report_from_logs(text):
    marker='DEPLOYED_PHYSICAL_PHOTOS_QA_PASS '
    lines=[line.split(marker,1)[1] for line in text.splitlines() if marker+'{' in line]
    if len(lines)!=1:raise ValueError('No single completed native browser report')
    return json.loads(lines[0])


def verify(document,fetch):
    source=document['source_owner_index_ref'];baseline=document['baseline_owner_index_ref']
    if (document.get('schema_version')!=1 or not SHA.fullmatch(source) or not SHA.fullmatch(baseline)
            or type(document.get('source_run_id')) is not int or document['source_run_id']<=0
            or not 1<=len(document.get('jobs',[]))<=100):raise ValueError('Invalid checkpoint scope')
    runs={};models={};seen=set();ids=set()
    for evidence in document['jobs']:
        jid=evidence['job_id'];model=evidence['model'];browser=evidence['browser']
        shard=evidence['shard'];shards=evidence['shards']
        if (jid in ids or model not in ('mimmi','yui') or browser not in ('chromium','webkit')
                or type(shard) is not int or type(shards) is not int
                or not 1<=shards<=24 or not 0<=shard<shards):raise ValueError('Invalid checkpoint job')
        run_id=evidence.get('source_run_id',document['source_run_id'])
        job_source=evidence.get('source_owner_index_ref',source)
        partition=evidence.get('partition','modulo')
        if (type(run_id) is not int or run_id<=0 or not SHA.fullmatch(job_source)
                or partition not in ('modulo','contiguous')):raise ValueError('Invalid completed source scope')
        scope=(run_id,job_source)
        if scope not in runs:
            if len(runs)>=4:raise ValueError('Checkpoint source workflow bound exceeded')
            run=fetch(f'/actions/runs/{run_id}')
            if (run.get('head_sha')!=job_source or run.get('head_branch')!='main'
                    or run.get('head_repository',{}).get('full_name')!=REPO
                    or run.get('path')!=WORKFLOW):raise ValueError('Wrong source workflow or source commit')
            jobs=fetch(f'/actions/runs/{run_id}/jobs?per_page=100')
            if jobs['total_count']>100:raise ValueError('Checkpoint job list requires explicit pagination')
            runs[scope]={j['id']:j for j in jobs['jobs']}
        ids.add(jid);job=runs[scope].get(jid,{})
        if (job.get('status')!='completed' or job.get('conclusion')!='success'
                or not job.get('name','').startswith('actual-deployed-originals (')):
            raise ValueError('Unfinished or failed job cannot establish photo success')
        model_scope=(job_source,model)
        if model_scope not in models:
            before=fetch(f'raw:{baseline}:{model}');after=fetch(f'raw:{job_source}:{model}')
            if before.get('model')!=model or after.get('model')!=model:
                raise ValueError('Wrong model in source metadata')
            if metadata_fingerprint(after)!=document['source_indices_fingerprint'].get(model):
                raise ValueError('Checkpoint source metadata changed')
            models[model_scope]=(after,changed_rows(before,after))
        after,changes=models[model_scope]
        expected={(aid,p['number']):p for i,(aid,p) in enumerate(changes)
                  if in_partition(i,len(changes),shard,shards,partition)}
        report=report_from_logs(fetch(f'/actions/jobs/{jid}/logs',text=True))
        if (report.get('model')!=model or report.get('browser')!=browser
                or report.get('current_owner_index_ref')!=job_source or report.get('since_commit')!=baseline
                or report.get('partition','modulo')!=partition
                or report.get('shard')!=shard or report.get('shards')!=shards
                or report.get('success') is not True or report.get('reload_pass') is not True
                or report.get('TLS_verified_bridge') is not False or report.get('page_errors')!=[]
                or report.get('all_new_or_upgraded_rows')!=len(changes)
                or report.get('inventory',{}).get('owner_rows')!=sum(len(a['images']) for a in after['albums'])):
            raise ValueError('Incomplete, bridged or different native photo evidence')
        actual=set()
        for photo in report['photos']:
            key=(photo['album'],photo['number']);p=expected.get(key)
            unique=(model,browser,*key)
            if (not p or key in actual or unique in seen or not all(photo.get(f) is True for f in FLAGS)
                    or photo.get('dimensions')!=[p['width'],p['height']]):
                raise ValueError('Unverified, repeated or changed checkpoint photo')
            actual.add(key);seen.add(unique)
        if actual!=set(expected):raise ValueError('Partial shard cannot establish success')
    return len(seen)


def resume_keys(document,before,after,model,browser,baseline):
    if (baseline!=document['baseline_owner_index_ref'] or
            metadata_fingerprint(after)!=document['source_indices_fingerprint'].get(model)):
        return {}
    changes=changed_rows(before,after);out={}
    for job in document['jobs']:
        if job['model']!=model or job['browser']!=browser:continue
        for i,(aid,p) in enumerate(changes):
            if in_partition(i,len(changes),job['shard'],job['shards'],job.get('partition','modulo')):
                out[(aid,p['number'])]=job['job_id']
    return out


def github_fetch(path,text=False):
    headers={'Accept':'application/vnd.github+json'}
    if os.environ.get('GH_TOKEN'):headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    if path.startswith('raw:'):
        _,ref,model=path.split(':')
        url=f'https://raw.githubusercontent.com/{REPO}/{ref}/apps/{model}-gallery/owner-index.json'
        headers={}
    else:url=f'https://api.github.com/repos/{REPO}'+path
    try:
        response=requests.get(url,headers=headers,timeout=(12,45));response.raise_for_status()
        return response.text if text else response.json()
    except requests.RequestException:
        # Do not expose signed log-download URLs or authorization headers.
        raise ValueError('Cannot independently read public native QA evidence') from None


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--github-output',type=Path,required=True);a=p.parse_args()
    raw=a.checkpoint.read_bytes();count=verify(json.loads(raw),github_fetch)
    with a.github_output.open('a') as out:out.write('checkpoint_sha='+hashlib.sha256(raw).hexdigest()+'\n')
    print('INDEPENDENT_NATIVE_JOB_CHECKPOINT_VERIFIED',count,'photo_browser_checks',flush=True)
