"""CC BY 4.0 published expert-product ratings, NOT consumer demand or SNS.
Official dataset: https://verdict-reviews.com/data/ . No article/media crawling
or person-account correlation. Only independently published numerical scores
are included in the conservative mean; model-inferred scores are excluded.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from datetime import date
import hashlib
import io
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SOURCE = 'https://verdict-reviews.com/data/'
RATINGS_URL = 'https://verdict-reviews.com/dataset/ratings.csv'
PRODUCTS_URL = 'https://verdict-reviews.com/dataset/products.csv'
LICENSE = 'CC BY 4.0'
MAX_INPUT_BYTES = 3_000_000
RATING_COLUMNS = ['product_slug','category_slug','publisher','review_url','value','max',
                  'normalized_5pt','source','publisher_stated','outlet_publishes_scores']
PRODUCT_COLUMNS = ['category_slug','category_name','product_slug','product_name','brand',
                   'rank','rating','rating_count','review_count','first_published','last_updated','product_url']
CATEGORIES = {
    'robot-vacuums': '로봇청소기',
    'wireless-earbuds': '무선 이어폰',
    '4k-monitors': '4K 모니터',
    'coffee-grinders-under-200': '커피 그라인더',
    'espresso-machines-under-500': '에스프레소 머신',
    'full-frame-mirrorless-cameras': '미러리스 카메라',
    'standing-desks': '스탠딩 데스크',
}

def _read_csv(raw: bytes, columns: list[str]) -> list[dict]:
    if not isinstance(raw, bytes) or not raw or len(raw)>MAX_INPUT_BYTES:
        raise ValueError('invalid or oversized source CSV')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
        if reader.fieldnames!=columns: raise ValueError('unexpected CSV schema')
        records=[]
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('malformed CSV row')
            records.append(row)
            if len(records)>25000: raise ValueError('unexpected CSV size')
        return records
    except UnicodeError as e: raise ValueError('invalid CSV encoding') from e

def _source_url(raw: str, *, on_dataset=False) -> str:
    if not isinstance(raw,str) or len(raw)>1024: return ''
    try:
        p=urlsplit(raw)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.port: return ''
        if on_dataset and p.hostname.lower()!='verdict-reviews.com': return ''
        return raw
    except ValueError: return ''

def _score(raw: str) -> float|None:
    try:
        v=float(raw)
        return v if math.isfinite(v) and 0<v<=5 else None
    except (TypeError,ValueError): return None

def compile_report(ratings_csv:bytes, products_csv:bytes, *, as_of:str) -> dict:
    try: as_of=date.fromisoformat(as_of).isoformat()
    except (TypeError,ValueError): raise ValueError('invalid as-of date')
    ratings=_read_csv(ratings_csv,RATING_COLUMNS)
    products=_read_csv(products_csv,PRODUCT_COLUMNS)
    if len(ratings)<1000 or len(products)<100:
        raise ValueError('canonical source seems incomplete; fail closed')
    selected={}
    for row in products:
        cat=row['category_slug']
        if cat not in CATEGORIES: continue
        slug=row['product_slug'];key=(cat,slug)
        if key in selected: raise ValueError('ambiguous category/product key')
        if len(slug)>120 or len(row['product_name'])>180:
            raise ValueError('unexpected product field length')
        if not _source_url(row['product_url'],on_dataset=True):
            raise ValueError('invalid product source link')
        selected[key]=row
    if not selected: raise ValueError('no supported ordinary-product categories')
    joined=defaultdict(list);seen=set();duplicate_source_rows=0
    for row in ratings:
        key=(row['category_slug'],row['product_slug'])
        if key not in selected: continue
        url=_source_url(row['review_url'])
        if not url: continue
        id_=(key,url)
        if id_ in seen:
            duplicate_source_rows+=1
            continue
        seen.add(id_);joined[key].append(row)
    output=[]
    category_metrics=defaultdict(lambda:dict(products=0,reviews=0,published_scores=0))
    for key,product in sorted(selected.items()):
        cat,slug=key;items=joined.get(key,[])
        scores=[];inferred=0;unscored=0;urls=[]
        for row in items:
            score=_score(row['normalized_5pt'])
            if row['publisher_stated'].lower()=='true' and score is not None:
                scores.append(score)
                if len(urls)<3:urls.append(row['review_url'])
            elif score is None:unscored+=1
            else:inferred+=1
        mean=round(sum(scores)/len(scores),3) if scores else None
        output.append(dict(category=cat,category_name=CATEGORIES[cat],
            product_id=slug,name=product['product_name'],
            product_url=product['product_url'],publication_reviews=len(items),
            publisher_stated_scores=len(scores),inferred_scores_excluded=inferred,
            unscored_reviews=unscored,publisher_stated_mean_5pt=mean,
            sample_review_urls=urls))
        c=category_metrics[cat];c['products']+=1;c['reviews']+=len(items)
        c['published_scores']+=len(scores)
    output.sort(key=lambda p:(-p['publisher_stated_scores'],p['category'],p['product_id']))
    categories=[dict(id=k,name=CATEGORIES[k],**category_metrics[k])
                for k in CATEGORIES if k in category_metrics]
    return {'schema_version':1,'dataset':{
        'kind':'real_editorial_product_ratings',
        'name':'Verdict Cross-Publication Product Review Ratings',
        'is_real_data':True,'is_consumer_demand':False,'is_current_sales':False,
        'as_of':as_of,'source_url':SOURCE,'license':LICENSE,
        'citation':'Verdict Cross-Publication Product Review Ratings (Michael Hunter, 2026)',
        'ratings_csv_sha256':hashlib.sha256(ratings_csv).hexdigest(),
        'products_csv_sha256':hashlib.sha256(products_csv).hexdigest(),
        'same_person_inferred':False,'existing_sns_pipeline_connected':False,
        'method':'Only outlet-published scores are used for the conservative average.'
    },'summary':{
        'source_ratings_rows':len(ratings),'source_products_rows':len(products),
        'selected_categories':len(categories),'selected_products':len(output),
        'selected_review_links':sum(x['publication_reviews'] for x in output),
        'publisher_stated_scores':sum(x['publisher_stated_scores'] for x in output),
        'inferred_scores_excluded':sum(x['inferred_scores_excluded'] for x in output),
        'unscored_reviews':sum(x['unscored_reviews'] for x in output),
        'duplicate_source_rows':duplicate_source_rows
    },'categories':categories,'products':output,'warnings':[
        'Editorial ratings are not buyer interest, sales, or independent consumers.',
        'Review syndication across different domains may remain undetected.',
        'Published scores are a selected subset; missing and model-derived scores are excluded.',
        'Dates of source reviews are not inferred from product update dates.'
    ]}

def fetch_source(url:str)->bytes:
    if url not in (RATINGS_URL,PRODUCTS_URL):
        raise ValueError('download URL not allowlisted')
    req=Request(url,headers={'User-Agent':'INTERSECTION-OpenData/1.0',
                             'Accept':'text/csv','Accept-Encoding':'identity'})
    with urlopen(req,timeout=25) as response:
        if response.status!=200 or response.geturl()!=url:
            raise ValueError('unexpected source response or redirect')
        raw=response.read(MAX_INPUT_BYTES+1)
    if not raw or len(raw)>MAX_INPUT_BYTES:
        raise ValueError('source bytes outside bounds')
    return raw

def main(argv=None):
    p=argparse.ArgumentParser(description='CC BY 4.0 expert-product evidence')
    p.add_argument('--ratings-file',type=Path)
    p.add_argument('--products-file',type=Path)
    p.add_argument('--as-of',required=True)
    p.add_argument('--output',type=Path,required=True)
    opt=p.parse_args(argv)
    if bool(opt.ratings_file)!=bool(opt.products_file):
        p.error('both offline CSV files are required together')
    a=opt.ratings_file.read_bytes() if opt.ratings_file else fetch_source(RATINGS_URL)
    b=opt.products_file.read_bytes() if opt.products_file else fetch_source(PRODUCTS_URL)
    report=compile_report(a,b,as_of=opt.as_of)
    opt.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=opt.output.with_name(opt.output.name+'.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,opt.output)
    print(json.dumps({'source_rows':report['summary']['source_ratings_rows'],
                      'products':report['summary']['selected_products'],
                      'published_scores':report['summary']['publisher_stated_scores'],
                      'output':str(opt.output)}))

if __name__=='__main__':
    main()
