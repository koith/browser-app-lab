"""Work/edition coverage, explicit numbering evidence, aliases and missing frames.

Stored metadata, distinct SHA bytes, source candidates and publisher totals are
separate measurements. Title normalization suggests review; it NEVER merges sets.
"""
import argparse
from collections import defaultdict
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urlsplit

SOURCE_FILES = {
    'mimmi': ['source-viewer-albums.json','official-previews.json','v2ph-actor-previews.json',
              'v2ph-public-previews.json','pixibb-public-previews.json','xiutu-public-previews.json',
              'gumroad-public-previews.json','social-public-previews.json','research-catalogue.json','public-work-pages.json'],
    'yui': ['source-viewer-albums.json','additional-source-albums.json','publisher-catalogue.json',
            'public-album-candidates.json','research-sources.json'],
}


def title_key(title):
    value=unicodedata.normalize('NFKC',html.unescape(str(title))).casefold()
    value=re.sub(r'\s*[-–—]?\s*page\s+\d+\s*$','',value)
    value=re.sub(r'\[(?:djawa(?: photo)?|creamsoda|sweetbox|artgravia)\]',' ',value)
    return re.sub(r'[^\w]+',' ',value,flags=re.UNICODE).strip()


def ranges(numbers):
    values=sorted(set(numbers));out=[]
    for n in values:
        if out and n==out[-1][1]+1:out[-1][1]=n
        else:out.append([n,n])
    return out


def canonical(aid,aliases):
    visited=set()
    while aid in aliases:
        if aid in visited:raise ValueError('Cyclic album alias')
        visited.add(aid);aid=aliases[aid]
    return aid


def publisher(record):
    value=record.get('publisher') or record.get('title','')
    for brand in ['DJAWA','CreamSoda','SWEETBOX','ArtGravia','MilkyBomb','PUSSYLET','Yo-U','MOVIE FANTASY']:
        if brand.casefold() in str(value).casefold():return brand
    return record.get('publisher') or None


def total_evidence(a,filename):
    source=a.get('source') or a.get('url')
    official=(urlsplit(str(source)).hostname or '').lower() in ('djawaphoto.com','www.djawaphoto.com')
    out=[]
    for field in ('advertised_photos','expected','photos'):
        n=a.get(field)
        if type(n) is int and 1<=n<=25000:
            out.append({'total':n,'field':field,'source':source,'document':filename,
                        'kind':'publisher_advertised' if official else 'web_edition_claim'})
    return out


def build(root,model,owner=None,gallery=None):
    base=Path(root)/'apps'/(model+'-gallery')
    public=json.loads((base/'stored-albums.json').read_text())
    if owner is None:owner=json.loads((base/'owner-index.json').read_text())
    if owner.get('model')!=model:raise ValueError('Owner inventory model mismatch')
    alias_path=base/'album-aliases.json'
    aliases=json.loads(alias_path.read_text()).get('aliases',{}) if alias_path.exists() else {}
    for aid in aliases:canonical(aid,aliases)
    records=defaultdict(list);saved=defaultdict(list);public_rows=defaultdict(list)
    for kind,document in [('owner',owner),('public',public)]:
        if document.get('model',model)!=model:raise ValueError('Stored model mismatch')
        for a in document.get('albums',[]):
            aid=canonical(a['id'],aliases)
            records[aid].append((kind,a));(saved if kind=='owner' else public_rows)[aid].extend(a.get('images',[]))
    for filename in SOURCE_FILES[model]:
        path=base/filename
        if not path.exists():continue
        document=json.loads(path.read_text())
        for a in document.get('albums',document.get('works',[])):
            if not isinstance(a,dict):continue
            aid=a.get('id')
            if not aid:
                # Keep previously unindexed works, but do not guess an owner ID.
                source=a.get('source') or a.get('url')
                if not source:continue
                import hashlib
                aid='catalogue-'+hashlib.sha256(str(source).encode()).hexdigest()[:16]
            records[canonical(aid,aliases)].append((filename,a))
    visible={a['id']:a for a in (gallery or {}).get('albums',[])}
    global_sha=defaultdict(set)
    for aid,photos in saved.items():
        for p in photos:global_sha[p['sha256']].add(aid)
    result=[];titles=defaultdict(list)
    for aid,group in sorted(records.items()):
        owned=saved[aid];pub=public_rows[aid]
        hashes={p['sha256'] for p in owned+pub if p.get('sha256')}
        positions={p['number'] for p in owned if type(p.get('number')) is int}
        proposals=[];evidence=[];sources=set();names=[];candidates=[];source_numbers=set();anchors=set();anchor_sources=defaultdict(set)
        for filename,a in group:
            if a.get('title') and a['title'] not in names:names.append(a['title'])
            if a.get('source') or a.get('url'):sources.add(a.get('source') or a.get('url'))
            proposals.extend(total_evidence(a,filename))
            if filename in ('owner','public'):continue
            for p in a.get('samples') or a.get('images') or []:
                n=p.get('number');sha=p.get('sha256')
                if type(n) is int and n>0:
                    source_numbers.add(n)
                    if any(q.get('number')==n and q.get('sha256')==sha for q in owned):
                        anchors.add((n,sha));anchor_sources[(filename,a.get('source') or a.get('url'))].add((n,sha))
                if sha and sha not in hashes and p.get('url'):
                    candidates.append({'number':n,'url':p['url'],'historical_sha256':sha,'source_document':filename,
                                       'occupied_owner_number':n in positions,'downloaded_this_run':False})
        unique={(p['total'],p['kind'],p['source']):p for p in proposals};evidence=list(unique.values())
        publisher_totals={e['total'] for e in evidence if e['kind']=='publisher_advertised'}
        web_totals={e['total'] for e in evidence if e['kind']=='web_edition_claim'}
        selected=publisher_totals or web_totals
        expected=next(iter(selected)) if len(selected)==1 else None
        numbering_verified=(len(owned)==len(positions)==len({p['sha256'] for p in owned}) and
            not publisher_totals and len(web_totals)==1 and
            any(len(anchor_sources.get((e['document'],e['source']),set()))>=3
                for e in evidence if e['kind']=='web_edition_claim'))
        missing=sorted(set(range(1,expected+1))-positions) if expected and numbering_verified else None
        shared=defaultdict(int)
        for sha in hashes:
            for other in global_sha.get(sha,set())-{aid}:shared[other]+=1
        name=next((a.get('title') for kind,a in group if kind=='owner' and a.get('title')),names[0] if names else aid)
        titles[title_key(name)].append(aid)
        result.append({'id':aid,'model':model,'title':name,'title_variants':names,
            'publisher':next((publisher(a) for _,a in group if publisher(a)),None),'sources':sorted(sources),
            'known_total':expected,'total_evidence':evidence,'conflicting_totals':len(selected)>1,
            'owner_stored_rows':len(owned),'owner_distinct_sha256':len({p['sha256'] for p in owned}),
            'stored_numbers':sorted(positions),'public_stored_rows':len(pub),
            'gallery_displayed_rows':visible.get(aid,{}).get('images_count') if gallery is not None else None,
            'count_gap_against_declared_total':max(0,expected-len({p['sha256'] for p in owned})) if expected else None,
            'numbering_identity_verified':numbering_verified,'missing_photo_numbers':missing,
            'missing_photo_number_ranges':ranges(missing) if missing is not None else None,
            'known_source_numbers_not_in_owner':sorted(source_numbers-positions),
            'aliases':[k for k in aliases if canonical(k,aliases)==aid],
            'shared_exact_sha_with_other_ids':dict(shared),'public_candidates':list({p['url']:p for p in candidates}.values()),
            'download_failures':[],'completeness':'unknown_or_partial'})
    return {'schema_version':1,'model':model,'owner_rows':sum(len(a.get('images',[])) for a in owner['albums']),
        'owner_albums':sum(bool(a.get('images')) for a in owner['albums']),
        'owner_unique_sha256':len(global_sha),'gallery_measurement_supplied':gallery is not None,
        'raw_albums_10_or_fewer':sum(0<len(a.get('images',[]))<=10 for a in owner['albums']),
        'confirmed_missing_number_count':sum(len(a['missing_photo_numbers'] or []) for a in result),
        'unknown_numbering_album_count':sum(a['missing_photo_numbers'] is None for a in result),
        'same_normalized_title_review_only':[{'title_key':k,'ids':v} for k,v in titles.items() if len(v)>1],
        'albums':result}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--owner-dir',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    output={}
    for model in ('mimmi','yui'):
        file=a.owner_dir/(model+'.json') if a.owner_dir else None
        output[model]=build(a.root,model,json.loads(file.read_text()) if file and file.exists() else None)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print('WORK_COVERAGE_MATRIX_WRITTEN',{m:{k:v for k,v in d.items() if k not in ('albums','same_normalized_title_review_only')} for m,d in output.items()})
