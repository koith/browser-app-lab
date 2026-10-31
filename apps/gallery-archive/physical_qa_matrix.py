"""Partition exactly the new/changed immutable owner rows; omit empty models."""
import argparse
import json
from pathlib import Path
import re
import subprocess

import requests
from native_qa_checkpoint import changed_rows

BASELINE='9b38a8169240b8d084bf2e1f4f3f85e0ff644858'
MODELS=('yui','mimmi')
ROOT=Path(__file__).resolve().parents[2]


def matrix(counts):
    if set(counts)!=set(MODELS) or any(type(n) is not int or n<0 for n in counts.values()):
        raise ValueError('Exact nonnegative changed-row counts are required for both models')
    jobs=[]
    # Small cohorts run first. Each adjacent native browser pair tests the
    # same contiguous positions and shares the verified gateway cache.
    for model in sorted(MODELS,key=lambda m:(counts[m],m)):
        count=counts[model]
        if not count:continue
        shards=min(24,(count+19)//20)
        for shard in range(shards):
            for browser in ('chromium','webkit'):
                jobs.append({'model':model,'browser':browser,'shard':shard,'shards':shards})
    return jobs


def main():
    p=argparse.ArgumentParser();p.add_argument('--current-commit',required=True)
    p.add_argument('--github-output',type=Path,required=True);a=p.parse_args()
    if not re.fullmatch('[a-f0-9]{40}',a.current_commit):raise ValueError('Exact current commit required')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=a.current_commit:
        raise ValueError('Matrix checkout must be the exact current inventory snapshot')
    counts={}
    for model in MODELS:
        r=requests.get(f'https://raw.githubusercontent.com/koith/browser-app-lab/{BASELINE}/apps/{model}-gallery/owner-index.json',timeout=(12,45))
        r.raise_for_status();before=r.json()
        after=json.loads((ROOT/f'apps/{model}-gallery/owner-index.json').read_text())
        if before.get('model')!=model or after.get('model')!=model:raise ValueError('Wrong immutable inventory model')
        counts[model]=len(changed_rows(before,after))
    jobs=matrix(counts)
    # Keep the expression syntactically valid even when the whole browser job
    # is skipped by has_changes. This row never runs or produces QA evidence.
    valid=jobs or [{'model':'yui','browser':'chromium','shard':0,'shards':1}]
    with a.github_output.open('a') as output:
        output.write('matrix='+json.dumps({'include':valid},separators=(',',':'))+'\n')
        output.write('has_changes='+str(bool(jobs)).lower()+'\n')
        output.write('since_commit='+BASELINE+'\n')
    print('EXACT_NATIVE_PHOTO_QA_MATRIX',counts,'REAL_BROWSER_JOBS',len(jobs),flush=True)


if __name__=='__main__':main()
