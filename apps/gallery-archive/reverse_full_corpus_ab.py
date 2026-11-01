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
    root=Path(root)
    rows=[]
    model_totals={}
    for model in ('yui','mimmi'):
        base=root/'apps'/(model+'-gallery')
        owner=json.loads((base/'owner-index.json').read_text(encoding='utf-8'))
        pub=json.loads((base/'stored-albums.json').read_text(encoding='utf-8'))
        by_id={a['id']:a for a in pub.get('albums',[])}
        albums=owner.get('albums',[])
        model_totals[model]=len(albums)
        for a in albums:
            aid=a['id']
            originals=list({p['sha256']:p for p in a.get('images',[])
                            if SHA.fullmatch(str(p.get('sha256','')))
                            and isinstance(p.get('number'),int) and p['number']>0
                            and p.get('bytes',0)>1024}.values())
            static=list({p['sha256']:p for p in by_id.get(aid,{}).get('images',[])
                         if SHA.fullmatch(str(p.get('sha256',''))) and
                         str(p.get('url','')).startswith('stored-albums/') and
                         '..' not in str(p.get('url','')).split('/')}.values())
            refs=static or originals
            indices=list(dict.fromkeys((0,len(refs)//2,len(refs)-1))) if refs else []
            for i in indices:
                p=refs[i];digest=p['sha256']
                if static:
                    url=BASE+'/'+model+'-gallery/'+quote(p['url'],safe='/')
                    kind='already_committed_public_image'
                else:
                    url=(COVER+'/'+model+'/'+quote(aid,safe='')+'/'+str(p['number'])+
                         '?v='+str(p.get('preview_sha256') or digest)[:24])
                    kind='first_party_cover_of_owner_original'
                rows.append({'model':model,'album_id':aid,'album_title':a.get('title',aid),
                             'owner_sha256':digest,'owner_photo_count':len(originals),
                             'seed_position':i,'public_image_url':url,'seed_kind':kind,
                             'ai_derived_seed':bool(re.search(r'AI Enhanced|AI 보정|ai32',a.get('title',''),re.I))})
    if len({(x['model'],x['album_id'],x['owner_sha256']) for x in rows})!=len(rows):
        raise ValueError('same_photo_seed_counted_twice')
    return {'owner_albums_by_model':model_totals,'seeds':rows}


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
                sum(albums['owner_albums_by_model'].values())-
                len({(x['model'],x['album_id']) for x in albums['seeds']}),
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
        'title_leads':titles,'scope':'all owner cover positions + all title leads, no sampled albums',
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
