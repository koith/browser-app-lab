"""Public source identity for the actual Pages artifact, never archive metadata."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

REPO='koith/browser-app-lab'

def identity(commit,run_id,repository=REPO):
    if not isinstance(commit,str) or not re.fullmatch('[a-f0-9]{40}',commit):
        raise ValueError('Exact source commit required')
    if type(run_id) is not int or run_id<1 or repository!=REPO:
        raise ValueError('Invalid trusted Pages deployment identity')
    return {'schema_version':1,'repository':repository,'source_commit':commit,'workflow_run_id':run_id}

def validate(raw,expected_commit):
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('schema_version')!=1:
        raise ValueError('Missing actual Pages deployment identity')
    checked=identity(data.get('source_commit'),data.get('workflow_run_id'),data.get('repository'))
    if checked['source_commit']!=expected_commit:
        raise ValueError('Operating Pages deployment is not the exact checked-out source commit')
    return checked

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',type=Path,required=True);args=p.parse_args()
    source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if source!=os.environ.get('GITHUB_SHA'):raise ValueError('Artifact checkout differs from triggering source commit')
    stamp=identity(source,int(os.environ['GITHUB_RUN_ID']),os.environ['GITHUB_REPOSITORY'])
    args.write.write_text(json.dumps(stamp,sort_keys=True)+'\n')
    print('PAGES_EXACT_SOURCE_STAMP_WRITTEN',source,stamp['workflow_run_id'],flush=True)
