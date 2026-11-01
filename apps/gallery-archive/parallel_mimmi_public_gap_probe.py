#!/usr/bin/env python3
"""Independent, read-only SHA audit for actual public-source candidate bytes.

This audit never modifies owner metadata or private TeraBox. Call after
direct_photo_pipeline.py when another agent is working on the galleries.
"""
import argparse
import hashlib
import json
from pathlib import Path

def inspect(stage: Path, owner: Path) -> dict:
    report=json.loads((stage/'metadata/collection-audit.json').read_text())
    catalog=json.loads((stage/'metadata/catalog.json').read_text())
    published=json.loads(owner.read_text())
    if report.get('model')!='mimmi' or catalog.get('model')!='mimmi':
        raise ValueError('Wrong model or wrong output')
    published_shas={p['sha256'] for a in published['albums'] for p in a['images']}
    actual=set()
    parsed=[]
    for a in catalog['albums']:
        files=[]
        for p in a['images']:
            sha=p['sha256']
            if sha in published_shas:
                raise ValueError('Already published original was counted as new')
            if sha in actual:
                raise ValueError('Duplicated original within staged catalog')
            for name,expected in ((p['key'],sha),(p['preview'],p['preview_sha256'])):
                file=(stage/name).resolve()
                if not file.is_relative_to(stage.resolve()) or not file.is_file():
                    raise ValueError('Missing or unsafe staged path')
                digest=hashlib.sha256(file.read_bytes()).hexdigest()
                if digest!=expected:
                    raise ValueError('Photo bytes do not match actual full SHA-256')
            actual.add(sha)
            files.append({'number':p['number'],'sha256':sha,'bytes':p['bytes']})
        parsed.append({'album_id':a['id'],'files':files})
    if len(actual)!=report['new_local_individual_files']:
        raise ValueError('Audit file count mismatch')
    return {'new_sha_verified_individual_photos':len(actual),
            'existing_owner_unchanged':True,
            'remote_verified':False,
            'gallery_verified':False,
            'newly_staged_per_album':parsed,
            'reasons':[{ 'album_id':r['id'],
                         'source_candidates':r.get('published_image_candidates',0),
                         'individual_files_saved':r.get('individual_files_saved',0),
                         'failures':[{k:x.get(k) for k in ('reason','exception','http_status','cause','response_scope')}
                                     for x in r.get('failures',[])]}
                        for r in report.get('results',[])]}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',required=True,type=Path)
    parser.add_argument('--owner',required=True,type=Path)
    parser.add_argument('--audit',required=True,type=Path)
    args=parser.parse_args()
    result=inspect(args.stage,args.owner)
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PARALLEL_PUBLIC_ACTUAL_DOWNLOAD_AUDIT',json.dumps(result,ensure_ascii=False))
