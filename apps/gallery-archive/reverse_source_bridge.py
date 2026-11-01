"""Convert prior image-first search results to *unverified* public work pages.

No photo URL is treated as a saved picture here. Downstream must independently
fetch the actual page, establish work/person attribution, decode image bytes,
verify SHA and read back private owner storage before publishing.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from public_work_photo_extractor import ordinary_public_https_image

WORK_ID=re.compile(r'[a-z0-9][a-z0-9-]{1,100}\Z')


def public_page(url):
    # Use the URL validator for HTTPS + non-private host, but do not require
    # image extensions. Source links come from recorded reverse-search hits.
    return ordinary_public_https_image(url,url) if isinstance(url,str) else None


def collect_evidence(directory,model,owner_ids,max_pages_per_work=40):
    sources=defaultdict(list)
    names={}
    search_counts={'shards':0,'photo_seed_rows':0,'title_leads':0,
                   'identity_supported_source_page_hits':0,
                   'named_title_page_hits':0}
    seen_files=set()
    for p in sorted(Path(directory).rglob('reverse-full-*.json')):
        doc=json.loads(p.read_text(encoding='utf-8'))
        if doc.get('summary',{}).get('model')!=model:
            continue
        key=(doc['summary']['model'],doc['summary']['shard'])
        if key in seen_files:
            raise ValueError('duplicate_reverse_shard')
        seen_files.add(key)
        search_counts['shards']+=1
        for item in doc.get('photo_seeds',[]):
            aid=item.get('album_id')
            if aid not in owner_ids:
                continue
            search_counts['photo_seed_rows']+=1
            names[aid]=item.get('album_title') or aid
            for page in item.get('candidates',[]):
                if not page.get('identity_hint'):
                    continue
                url=public_page(page.get('url'))
                if not url:
                    continue
                search_counts['identity_supported_source_page_hits']+=1
                if url not in sources[aid] and len(sources[aid])<max_pages_per_work:
                    sources[aid].append(url)
        for item in doc.get('title_leads',[]):
            aid=item.get('id')
            if not isinstance(aid,str) or not WORK_ID.fullmatch(aid):
                continue
            search_counts['title_leads']+=1
            names[aid]=item.get('title') or aid
            for page in item.get('candidate_pages',[]):
                url=public_page(page.get('url') if isinstance(page,dict) else None)
                if not url:
                    continue
                search_counts['named_title_page_hits']+=1
                if url not in sources[aid] and len(sources[aid])<max_pages_per_work:
                    sources[aid].append(url)
    rows=[{'id':aid,'title':names.get(aid) or aid,'urls':urls,
           'owner_registered':aid in owner_ids,
           'provenance':'public_reverse_search_page_unverified'}
          for aid,urls in sorted(sources.items()) if urls]
    return {'model':model,'status':'unverified_reverse_source_pages_not_photo_files',
            'counts':{**search_counts,'registered_source_targets':len(rows),
                      'unverified_unique_page_links':sum(len(r['urls']) for r in rows)},
            'targets':rows}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dir',type=Path,required=True)
    ap.add_argument('--model',choices=['yui','mimmi'],required=True)
    ap.add_argument('--owner',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    owner=json.loads(a.owner.read_text(encoding='utf-8'))
    if owner.get('model')!=a.model:
        raise ValueError('owner_model_mismatch')
    ids={row['id'] for row in owner['albums']}
    report=collect_evidence(a.dir,a.model,ids)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('IMAGE_FIRST_PUBLIC_SOURCE_RECOVERY',a.model,report['counts'],flush=True)


if __name__=='__main__':
    main()
