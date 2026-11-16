#!/usr/bin/env python3
"""Search ALL registered owner-album photo-seed positions + ALL missing-title leads.

This is a real public reverse-search comparison, not image archiving. Search
results never become gallery photos; user-owned private originals never upload.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.parse import quote

import requests
from reverse_image_discovery import (
    multi_search,lens_query,tineye_query,identity_supported
)
from reverse_image_sweep import search_one as yandex_site_search
from visual_work_discovery import search_one as title_search

ROOT=Path(__file__).resolve().parents[2]
BASE='https://koith.github.io/browser-app-lab/apps'
COVER='https://mimmi-private-gallery-free.onrender.com/api/cover'
SHA=re.compile('^[a-f0-9]{64}$')


def all_album_seeds(root=ROOT):
    """Include the entire public/owner SHA union, not three sample covers."""
    from reverse_seed_priority import seeds as every_photo_seed
    root=Path(root)
    rows=[]
    model_totals={}
    owner_album_keys=set()
    for model in ('yui','mimmi'):
        owner=json.loads((root/'apps'/f'{model}-gallery'/'owner-index.json')
                         .read_text(encoding='utf-8'))
        albums=owner.get('albums',[])
        model_totals[model]=len(albums)
        owner_album_keys.update((model,a['id']) for a in albums)
    positions={}
    for p in every_photo_seed(root/'apps', all_cuts=True):
        key=(p['model'],p['album_id'])
        i=positions.get(key,0)
        positions[key]=i+1
        rows.append({'model':p['model'],'album_id':p['album_id'],
            'album_title':p['album_title'],'owner_sha256':p['photo_sha256'],
            'owner_photo_count':p['owner_saved_count'],
            'seed_position':i,'public_image_url':p['public_image_url'],
            'seed_kind':p.get('seed_kind'),
            'ai_derived_seed':bool(re.search(r'AI Enhanced|AI 보정|ai32',
                                           p.get('album_title',''),re.I))})
    if len({(x['model'],x['album_id'],x['owner_sha256']) for x in rows})!=len(rows):
        raise ValueError('same_photo_seed_counted_twice')
    seeded={(x['model'],x['album_id']) for x in rows}
    return {'owner_albums_by_model':model_totals,'seeds':rows,
            'owner_albums_without_photo_seed':len(owner_album_keys-seeded),
            'owner_album_ids':len(owner_album_keys)}


def all_title_leads(root=ROOT):
    p=Path(root)/'apps/gallery-archive/visual-work-leads.json'
    d=json.loads(p.read_text(encoding='utf-8'))
    return [{'model':d.get('model','yui'),'id':x['key'],'title':x.get('title'),
             'lead':x} for x in d['works']]


def partition(row,shards):
    key=':'.join(str(row[k]) for k in ('model','album_id','owner_sha256')) if 'owner_sha256' in row \
        else ':'.join(str(row[k]) for k in ('model','id'))
    return int.from_bytes(sha256(key.encode()).digest()[:8],'big')%shards


def full_census(root=ROOT):
    albums=all_album_seeds(root)
    leads=all_title_leads(root)
    summary={'owner_albums_by_model':albums['owner_albums_by_model'],
             'all_public_reverse_photo_seeds':len(albums['seeds']),
             'unique_albums_with_seeds':len({(x['model'],x['album_id']) for x in albums['seeds']}),
             'missing_owner_albums_without_photo_seed':
                albums['owner_albums_without_photo_seed'],
             'all_title_work_leads':len(leads)}
    return {'summary':summary,'seeds':albums['seeds'],'title_leads':leads}


def search_image(row,session):
    url=row['public_image_url'];result={**row,'engines':{},'candidates':[],
        'candidate_source_urls':0,'approved_candidate_source_urls':0,
        'new_originals_stored':0,'new_gallery_photos':0}
    found={}
    tests=(
        ('multi_yandex_bing',lambda:multi_search(session,url)),
        ('lens_public',lambda:lens_query(session,url)),
        ('tineye_public',lambda:tineye_query(session,url)),
        ('yandex_sites',lambda:yandex_site_search(
            {'model':row['model'],'album_id':row['album_id'],
             'album_title':row['album_title'],'photo_sha256':row['owner_sha256'],
             'public_image_url':url,'owner_saved_count':row['owner_photo_count']},session)),
    )
    for engine,call in tests:
        try:
            outcome=call()
            result['engines'][engine]=outcome.get('engine_statuses',
                outcome.get('search_status',outcome.get('status','unknown')))
            links=outcome.get('links',outcome.get('candidate_pages',[])) or []
            for lead in links:
                if not isinstance(lead,dict):continue
                dest=lead.get('url')
                if not isinstance(dest,str) or not dest.startswith('https://'):continue
                if dest not in found:
                    identity=identity_supported(
                        {'model':row['model'],'album_title':row['album_title']},
                        {'url':dest,'label':str(lead.get('label',''))})
                    found[dest]={'url':dest,'label':str(lead.get('label',''))[:120],
                                 'identity_hint':identity,'engine_tags':[engine]}
                else:
                    found[dest]['engine_tags'].append(engine)
        except Exception as exc:
            result['engines'][engine]={'error':type(exc).__name__}
    result['candidate_source_urls']=len(found)
    result['approved_candidate_source_urls']=sum(bool(t['identity_hint']) for t in found.values())
    # Do not publish raw source URLs to a user-visible gallery; research evidence.
    result['candidates']=list(found.values())[:125]
    return result


def audit(root,model,shard,shards,out,delay=.5):
    census=full_census(root)
    images=[x for x in census['seeds'] if x['model']==model and partition(x,shards)==shard]
    leads=[x for x in census['title_leads'] if x['model']==model and partition(x,shards)==shard]
    session=requests.Session()
    session.headers.update({'User-Agent':'PersonalGallerySourceResearch/1.0','Accept':'text/html'})
    results=[];titles=[]
    for i,row in enumerate(images):
        r=search_image(row,session)
        results.append(r)
        print('REVERSE_ALL_SEED',json.dumps({
            'model':model,'i':i+1,'count':len(images),'id':row['album_id'],
            'positions':row['seed_position'],'sources':r['candidate_source_urls'],
            'identity_supported':r['approved_candidate_source_urls'],
            'engine_statuses':r['engines']},ensure_ascii=False),flush=True)
        if delay:time.sleep(delay)
    for lead in leads:
        try:
            outcome=title_search(session,lead['lead'],max_queries=3)
            items=outcome.get('candidate_pages',[])
            titles.append({'id':lead['id'],'title':lead['title'],
                 'attempts':outcome.get('attempts',[]),
                 'candidate_pages':items,'candidate_count':len(items)})
        except Exception as e:
            titles.append({'id':lead['id'],'title':lead['title'],
                           'error':type(e).__name__,'candidate_pages':[],'candidate_count':0})
    summary={'model':model,'shard':shard,'shards':shards,
        'photo_seed_count':len(images),'image_seeds_reported':len(results),
        'title_lead_count':len(leads),'title_leads_reported':len(titles),
        'reverse_candidate_source_urls_sum_not_global_unique':
            sum(r['candidate_source_urls'] for r in results),
        'identity_supported_urls_sum_not_global_unique':
            sum(r['approved_candidate_source_urls'] for r in results),
        'title_candidate_page_count':sum(t['candidate_count'] for t in titles),
        'all_selected_seeds_accounted_for':len(results)==len(images) and len(titles)==len(leads),
        'new_originals_stored':0,'gallery_visible_photos_added':0}
    report={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'full_census_summary':census['summary'],'summary':summary,'photo_seeds':results,
        'title_leads':titles,'scope':'full distinct owner+public SHA union and title leads, no sampled images',
        'warning':'Search hits are candidate pages, not decoded, stored or proven identity photos.'}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('REVERSE_ALL_SHARD_TOTAL',json.dumps(summary,ensure_ascii=False),flush=True)
    if not summary['all_selected_seeds_accounted_for']:raise ValueError('incomplete_search_shard')
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--model',choices=['yui','mimmi'],required=True)
    ap.add_argument('--shard',type=int,required=True)
    ap.add_argument('--shards',type=int,default=8)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--delay',type=float,default=.5)
    a=ap.parse_args()
    if not 1<=a.shards<=32 or not 0<=a.shard<a.shards:raise ValueError('invalid_shard')
    audit(a.root,a.model,a.shard,a.shards,a.out,a.delay)

if __name__=='__main__':main()
