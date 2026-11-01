#!/usr/bin/env python3
"""Lossless census of EVERY Yui/Mimmi source/work registered in this repository.

This census is the denominator for engine comparisons. Never silently drop
owner works without source links, unsupported host families, or research-only
album leads. Exact work IDs are not assumed to prove cross-site equivalence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]

INPUTS={
 'yui':('additional-source-albums.json','public-work-pages.json','stored-albums.json'),
 'mimmi':('official-previews.json','v2ph-actor-previews.json',
          'pixibb-public-previews.json','public-work-pages.json','stored-albums.json'),
}
MODELS=('yui','mimmi')


def load(root,path):
    return json.loads((root/path).read_text(encoding='utf-8'))


def safe_public_url(s):
    try:
        if not isinstance(s,str):return False
        u=urlsplit(s)
        return bool(u.scheme=='https' and u.hostname and not u.username and not u.password
                    and u.port in (None,443) and len(s)<2200)
    except ValueError:
        return False


def add_url(record,url,provenance,field='urls'):
    if not safe_public_url(url):
        record['rejected_url_fields']+=1
        return
    if url not in record[field]:
        record[field].append(url)
    if provenance not in record['manifest_sources']:
        record['manifest_sources'].append(provenance)


def census(root=ROOT):
    root=Path(root)
    works={}
    catalogues=[]
    visual_leads=[]
    social_sources=[]
    independent_sources=[]
    owner_counts={}
    for model in MODELS:
        base=root/'apps'/(model+'-gallery')
        owner=load(root,base.relative_to(root)/'owner-index.json')
        if owner.get('model')!=model:raise ValueError('owner_model_mismatch_'+model)
        owner_counts[model]={'registered_albums':len(owner['albums']),
                             'physical_originals_indexed':owner.get('physical_originals_indexed',0)}
        for album in owner['albums']:
            aid=album['id'];key=(model,aid)
            unique_sha={i['sha256'] for i in album.get('images',[])
                        if isinstance(i,dict) and i.get('sha256')}
            works[key]={'model':model,'id':aid,'title':album.get('title',aid),
                        'owner_registered':True,'owner_slots':len(album.get('images',[])),
                        'owner_distinct_sha':len(unique_sha),'urls':[],
                        'direct_image_urls':[],'manifest_sources':['owner-index.json'],
                        'rejected_url_fields':0,'metadata_sample_urls':0,
                        'advertised_max':None,'source_origin_types':[]}
        for name in INPUTS[model]:
            rel=base.relative_to(root)/name
            data=load(root,rel)
            for a in data.get('albums',[]):
                aid=a.get('id')
                if not isinstance(aid,str) or not aid:continue
                key=(model,aid)
                if key not in works:
                    works[key]={'model':model,'id':aid,'title':a.get('title') or aid,
                                'owner_registered':False,'owner_slots':0,
                                'owner_distinct_sha':0,'urls':[],'direct_image_urls':[],
                                'manifest_sources':[],'rejected_url_fields':0,
                                'metadata_sample_urls':0,'advertised_max':None,
                                'source_origin_types':[]}
                row=works[key]
                if not row.get('title') or row['title']==aid:
                    row['title']=a.get('title') or aid
                for page in [a.get('source'),*a.get('source_pages',[])]:
                    if page:add_url(row,page,name)
                observed=a.get('advertised_photos',a.get('source_claimed_total_edition_photos'))
                if type(observed) is int and observed>0:
                    row['advertised_max']=max(row['advertised_max'] or 0,observed)
                for sample in a.get('samples',[]) or []:
                    if isinstance(sample,dict) and safe_public_url(sample.get('url')):
                        add_url(row,sample['url'],name,'direct_image_urls')
                        row['metadata_sample_urls']+=1
                # Existing visual/photo evidence may include verified public image
                # URLs even where a source page has expired.
                for image in a.get('images',[]) or []:
                    if isinstance(image,dict):
                        u=image.get('url')
                        if safe_public_url(u):
                            add_url(row,u,name,'direct_image_urls')
                if name not in row['source_origin_types']:
                    row['source_origin_types'].append(name)
    registry=load(root,'apps/gallery-archive/global_source_registry.json')
    for source in registry['sources']:
        model=source.get('model')
        if model not in MODELS:raise ValueError('invalid_catalogue_model')
        url=source.get('url')
        catalogues.append({'kind':'catalogue','model':model,'id':source['id'],
                           'title':source.get('id'),'urls':[url] if safe_public_url(url) else [],
                           'mode':source.get('mode'),'tier':source.get('tier'),
                           'manifest_sources':['global_source_registry.json']})
    leads=load(root,'apps/gallery-archive/visual-work-leads.json')
    for v in leads['works']:
        visual_leads.append({'kind':'visual_lead','model':leads.get('model','yui'),
                             'id':v['key'],'title':v.get('title',v['key']),
                             'observed_items':v.get('observed_items'),
                             'urls':[],'manifest_sources':['visual-work-leads.json'],
                             'matching_work_ids_not_proven':True})
    bulk=load(root,'apps/gallery-archive/public_social_bulk_sources.json')
    for model in MODELS:
        for s in bulk.get(model,[]):
            url=s.get('url')
            social_sources.append({'kind':'social','model':model,'id':s['id'],
                                   'title':s.get('title') or s['id'],
                                   'urls':[url] if safe_public_url(url) else [],
                                   'account':s.get('account'),
                                   'manifest_sources':['public_social_bulk_sources.json']})
    independent=load(root,'apps/gallery-archive/independent_shoot_sources.json')
    for model in MODELS:
        for s in independent.get(model,{}).get('source_jobs',[]):
            url=s.get('url')
            independent_sources.append({'kind':'independent','model':model,'id':s['id'],
                                        'title':s.get('title') or s['id'],
                                        'urls':[url] if safe_public_url(url) else [],
                                        'required_mention':s.get('required_mention'),
                                        'author':s.get('author'),
                                        'direct_image_urls':[u for u in s.get('direct_public_images',[])
                                                             if safe_public_url(u)],
                                        'manifest_sources':['independent_shoot_sources.json']})
    works_list=[{'kind':'work',**row,'urls':sorted(row['urls']),
                 'direct_image_urls':sorted(row['direct_image_urls']),
                 'manifest_sources':sorted(row['manifest_sources'])}
                for row in works.values()]
    for entry in works_list:entry['source_page_count']=len(entry['urls'])
    all_targets=sorted(works_list+catalogues+visual_leads+social_sources+independent_sources,
                       key=lambda v:(v['model'],v['kind'],v['id']))
    keys=[(v['model'],v['kind'],v['id']) for v in all_targets]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate_census_target')
    owner_missing=[w for w in works_list if w['owner_registered'] and not w['urls']]
    summary={'owner':owner_counts,'distinct_work_ids_by_model':dict(Counter(w['model'] for w in works_list)),
             'source_page_urls_recorded':sum(len(w['urls']) for w in works_list),
             'manifest_direct_image_url_entries':sum(len(w['direct_image_urls']) for w in works_list),
             'owner_albums_without_any_source':len(owner_missing),
             'all_targets_by_kind':dict(Counter(w['kind'] for w in all_targets)),
             'total_targets':len(all_targets),
             'all_targets_have_unique_key':True,
             'research_leads_not_counted_as_archived_photos':True}
    return {'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
            'scope':'ALL owner-index albums plus ALL source/lead/social/independent/cross-site manifests',
            'completeness':'manifest_census_only_not_public_web_crawl_complete',
            'summary':summary,'targets':all_targets}


def shard_key(row,shards):
    raw=':'.join((row['model'],row['kind'],row['id']))
    return int.from_bytes(sha256(raw.encode('utf-8')).digest()[:8],'big')%shards


def select(census_data,model,shard,shards):
    if model not in MODELS or not 0<=shard<shards:raise ValueError('invalid_shard')
    return [t for t in census_data['targets']
            if t['model']==model and shard_key(t,shards)==shard]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--model',choices=['yui','mimmi'])
    ap.add_argument('--shard',type=int)
    ap.add_argument('--shards',type=int,default=8)
    args=ap.parse_args()
    all_data=census(args.root)
    if args.model:
        if args.shard is None:raise ValueError('shard_required_when_model_selected')
        rows=select(all_data,args.model,args.shard,args.shards)
        all_data['selected_target_count']=len(rows)
        all_data['selected_model']=args.model
        all_data['shard_index']=args.shard
        all_data['shard_count']=args.shards
        all_data['targets']=rows
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(all_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('FULL_GALLERY_CENSUS',json.dumps(all_data['summary'],ensure_ascii=False),flush=True)
    if args.model:print('CENSUS_SHARD',args.model,args.shard,'/',args.shards,'targets',len(rows),flush=True)


if __name__=='__main__':main()
