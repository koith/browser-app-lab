#!/usr/bin/env python3
"""Fair same-page A/B: existing scoped parser vs combined open-source engines.

Do not publish any photo found by this benchmark. Fetch-and-decode evidence is
separate from true owner-storage SHA readback and actual gallery visibility.
Never use credentials, guess photo URLs, bypass access checks, or count links as images.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urljoin,urlsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/gallery-archive'))
from direct_photo_pipeline import page_images, safe_page, inspect, MODEL_PATTERNS
from collect_private_batch import allowed_url

SOURCES=[
    {'model':'yui','work':'djawa-privaty','page':'https://djawaphoto.com/portfolio/nikke-privaty-sharp-lesson/'},
    {'model':'mimmi','work':'djawa-summer-2','page':'https://djawaphoto.com/portfolio/in-the-summer-sunshine-part-2/'},
    {'model':'yui','work':'artgravia-677-alt','page':'https://www.nicesss.com/archives/mij/artgravia/469248.html'},
    {'model':'yui','work':'artgravia-693','page':'https://showartx.net/artgravia-vol-693-yui/'},
    {'model':'mimmi','work':'shypetal-summer-5','page':'https://www.shypetal.com/albums/mimmimimmi-djawa-photo-my-summer-vacation-vol/'},
    {'model':'mimmi','work':'pixibb-my-small-bird','page':'https://sexy.pixibb.com/mimmi-vol-2-my-small-bird-135-photos-sexy-girl/'},
    {'model':'mimmi','work':'v2ph-public','page':'https://www.v2ph.com/album/a54385nz.html'},
    # Same verified creator handle via the existing public mirror vs a native
    # gallery-dl supported Twitter/X extractor. Cross-origin, reported separately.
    {'model':'yui','work':'sns-yui-cross-platform','page':'https://teapawt.net/super_yuisan',
     'gallery_dl_source':'https://x.com/super_yuisan'},
    {'model':'mimmi','work':'sns-mimmi-cross-platform','page':'https://teapawt.net/Mimmi_official',
     'gallery_dl_source':'https://x.com/Mimmi_official'},
]
MAX_IMG_GET=90
MAX_URLS_PER_ENGINE=90


def asset_group(url):
    """An image resize is a rendition, never a new photo cut by itself."""
    p=urlsplit(url)
    path=re.sub(r'-\d{2,5}x\d{2,5}(?=\.(?:jpe?g|webp|png)$)','',p.path,flags=re.I)
    return (p.hostname or '',path)


def safe_photo(raw):
    try:
        p=urlsplit(raw)
        approved,_=allowed_url(raw)
        if p.hostname in ('djawaphoto.com','www.djawaphoto.com') and not p.path.startswith('/wp-content/uploads/'):
            return False
        return bool(approved and re.search(r'\.(?:jpe?g|webp|png)$',p.path,re.I)
                    and not re.search(r'(?:logo|avatar|favicon|emoji|banner|tracking|placeholder)',p.path,re.I))
    except (ValueError,TypeError):return False


def scoped_generic_html(raw,page,model):
    """Real Scrapy selector engine over a public GET (different from the baseline)."""
    from scrapy.http import HtmlResponse
    response=HtmlResponse(url=page,body=raw,encoding='utf-8')
    heading=' '.join(response.css('h1::text,title::text').getall())
    article=None
    for css in ('#powerbbsContent','.portfolio-content','.entry-content','article','main'):
        selected=response.css(css)
        if selected:
            article=selected[0]
            break
    if article is None:return [],'no_article'
    identity=heading+' '+(' '.join(article.css('::text').getall()))
    if not MODEL_PATTERNS[model].search(identity):return [],'no_model_context'
    candidates=[]
    for node in article.css('img,source'):
        # Do not inherit outer BODY class, e.g. body.sidebar-right.
        bad=False
        for ancestor in node.root.iterancestors():
            if ancestor is article.root:break
            if any(re.search(r'related|recommend|comment|sidebar|advert',c,re.I)
                   for c in ancestor.attrib.get('class','').split()):
                bad=True
                break
        if bad:continue
        attrs=[node.attrib.get(k) for k in (
            'data-original','data-full','data-large-file','data-src',
            'data-lazy-src','src','srcset','data-srcset') if node.attrib.get(k)]
        anchor=node.xpath('ancestor::a[1]/@href').get()
        if anchor:attrs.append(anchor)
        for attr in attrs:
            for part in attr.split(',') if ',' in attr else [attr]:
                u=urljoin(page,part.strip().split()[0]) if part.strip() else ''
                if safe_photo(u) and u not in candidates:candidates.append(u)
    return candidates[:120],'scrapy_article_selector'


def gdl_extract(page,limit=120):
    """Run real gallery-dl extractor with no cookies and no archive mutation."""
    args=[sys.executable,'-m','gallery_dl','-g','--range','1-40','--',page]
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=24)
        urls=[]
        for line in p.stdout.splitlines():
            u=line.strip()
            if safe_photo(u) and u not in urls:urls.append(u)
        return urls[:limit],{'returncode':p.returncode,
            'stderr':p.stderr[-500:],'engine':'gallery-dl real CLI'}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return [],{'error':type(exc).__name__,'engine':'gallery-dl real CLI'}


def browser_extract(page,model,enabled=False):
    if not enabled:return [],{'status':'disabled'}
    try:from playwright.sync_api import sync_playwright
    except ImportError:return [],{'status':'not_installed'}
    result=[]
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True,args=['--disable-gpu'])
            ctx=browser.new_context()
            tab=ctx.new_page()
            response=tab.goto(page,wait_until='domcontentloaded',timeout=12000)
            if not response or response.status>=400:
                ctx.close();browser.close()
                return [],{'http':response.status if response else None}
            for _ in range(2):
                tab.evaluate('window.scrollBy(0, document.body.scrollHeight/2)')
                tab.wait_for_timeout(500)
            raw=tab.content().encode('utf-8')
            result,status=scoped_generic_html(raw,page,model)
            ctx.close();browser.close()
            return result,{'http':response.status,'selector_status':status}
    except Exception as exc:
        return [],{'error':type(exc).__name__+':'+str(exc)[:110]}


def verify_public(session,url):
    """Measure only actual downloaded and decoded public bytes."""
    try:
        r=session.get(url,timeout=(8,18),allow_redirects=False)
        if r.status_code!=200:return {'status':'http_'+str(r.status_code)}
        p,_,_=inspect(r.content)
        return {'status':'decoded_sha','sha256':p['sha256'],'bytes':p['bytes'],
                'width':p['width'],'height':p['height']}
    except (requests.RequestException,OSError,ValueError,Image.DecompressionBombError) as exc:
        return {'status':type(exc).__name__}


def compare(source,session,use_browser=True,limit=MAX_IMG_GET):
    page=source['page'];model=source['model']
    result={**source,'engines':{},'public_decoded_by_engine':{},
            'baseline_unique_sha':0,'ensemble_unique_sha':0,
            'additional_unique_sha':0,'extra_urls_not_stored':[]}
    if not safe_page(page):
        result['error']='page_not_on_current_approved_host_list';return result
    try:
        response=session.get(page,timeout=(8,18),allow_redirects=False)
        if response.status_code!=200:
            result['error']='http_'+str(response.status_code)
            # Still test the independent gallery-dl extraction to see its behavior.
            raw=b''
        else:raw=response.content
    except requests.RequestException as exc:
        result['error']=type(exc).__name__;raw=b''
    if raw:
        base,more,status=page_images(raw,page,model)
        generic,genstatus=scoped_generic_html(raw,page,model)
    else:base,more,status,generic,genstatus=[],[],'unavailable',[],'unavailable'
    gdl,gdl_status=gdl_extract(source.get('gallery_dl_source') or page)
    gdl_status['comparison_origin']='same_creator_cross_platform' if source.get('gallery_dl_source') else 'same_public_work_page'
    browser,browser_status=browser_extract(page,model,use_browser)
    proposals={'existing_scoped_parser':base,'scrapy_style_generic_article':generic,
               'gallery_dl_native':gdl,'playwright_rendered_article':browser}
    result['engines']={
        'existing_scoped_parser':{'urls':len(base),'status':status,'more_pages':len(more)},
        'scrapy_style_generic_article':{'urls':len(generic),'status':genstatus},
        'gallery_dl_native':{'urls':len(gdl),**gdl_status},
        'playwright_rendered_article':{'urls':len(browser),**browser_status},
    }
    verdict={};checked=0
    for engine,urls in proposals.items():
        for u in dict.fromkeys(urls[:MAX_URLS_PER_ENGINE]):
            if not safe_photo(u):continue
            if u in verdict:continue
            if checked>=limit:
                verdict[u]={'status':'budget_exhausted'};continue
            verdict[u]=verify_public(session,u)
            checked+=1
    engine_shas={}
    for engine,urls in proposals.items():
        hashes={verdict[u]['sha256'] for u in urls if u in verdict and verdict[u]['status']=='decoded_sha'}
        engine_shas[engine]=hashes
        result['public_decoded_by_engine'][engine]=len(hashes)
        result['engines'][engine]['unverified_or_failed_urls']=len(urls)-sum(1 for u in urls if u in verdict and verdict[u]['status']=='decoded_sha')
    base_set=engine_shas['existing_scoped_parser']
    combined=set().union(*engine_shas.values())
    result['baseline_unique_sha']=len(base_set)
    result['ensemble_unique_sha']=len(combined)
    result['additional_unique_sha']=len(combined-base_set)
    # SHA catches byte equality, NOT different-sized versions of one photo.
    # Compare native original vs generated WordPress resize variants by asset
    # identity. Distinct unmatched URLs remain candidates, not proven cuts.
    baseline_assets={asset_group(u) for u in proposals['existing_scoped_parser']
                     if u in verdict and verdict[u]['status']=='decoded_sha'}
    combined_assets={asset_group(u) for urls in proposals.values() for u in urls
                     if u in verdict and verdict[u]['status']=='decoded_sha'}
    result['baseline_distinct_asset_groups']=len(baseline_assets)
    result['ensemble_distinct_asset_groups']=len(combined_assets)
    result['additional_unmatched_asset_groups']=len(combined_assets-baseline_assets)
    result['extra_sha_of_existing_asset_renditions']=len({
        verdict[u]['sha256'] for engine,urls in proposals.items()
        if engine!='existing_scoped_parser'
        for u in urls if u in verdict and verdict[u]['status']=='decoded_sha'
        and verdict[u]['sha256'] not in base_set and asset_group(u) in baseline_assets
    })
    result['unmatched_group_example_paths']=[path for _,path in
        sorted(combined_assets-baseline_assets)[:15]]
    result['candidate_urls_seen']=len(verdict)
    result['actual_image_gets']=checked
    for engine,urls in proposals.items():
        if engine=='existing_scoped_parser':continue
        for u in urls:
            if u in verdict and verdict[u]['status']=='decoded_sha' and verdict[u]['sha256'] not in base_set:
                result['extra_urls_not_stored'].append({'engine':engine,'url':u,'sha256':verdict[u]['sha256']})
    result['extra_urls_not_stored']=list({d['sha256']:d for d in result['extra_urls_not_stored']}.values())[:60]
    return result


def run(out,use_browser=True,selection=None):
    session=requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; GalleryPublicEngineAB/1.0)',
                            'Accept':'text/html,image/webp,image/avif,image/jpeg,image/png,*/*'})
    rows=[]
    for source in SOURCES:
        if selection and source['work'] not in selection:continue
        row=compare(source,session,use_browser)
        print('PUBLIC_ENGINE_AB',json.dumps({k:v for k,v in row.items() if k!='extra_urls_not_stored'},ensure_ascii=False),flush=True)
        rows.append(row)
    report={
        'schema_version':1,
        'assessment':'public_decode_evidence_only_not_private_storage_or_gallery',
        'engines':['existing_scoped_parser','scrapy_style_generic_article','gallery_dl_native','playwright_rendered_article'],
        'works':rows,
        'totals':{'works_compared':len(rows),
            'baseline_public_unique_sha_sum':sum(r['baseline_unique_sha'] for r in rows),
            'ensemble_public_unique_sha_sum':sum(r['ensemble_unique_sha'] for r in rows),
            'additional_public_unique_sha_sum':sum(r['additional_unique_sha'] for r in rows),
            'additional_unmatched_asset_groups_sum':sum(r['additional_unmatched_asset_groups'] for r in rows),
            'extra_sha_of_existing_asset_renditions_sum':sum(r['extra_sha_of_existing_asset_renditions'] for r in rows)},
        'limits':{'max_verified_downloads_per_page':MAX_IMG_GET,
                  'max_urls_per_engine':MAX_URLS_PER_ENGINE,
                  'no_auth_no_paid_endpoints':True,
                  'no_collection_upload_or_gallery_publication':True}
    }
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PUBLIC_ENGINE_AB_TOTAL',json.dumps(report['totals']),flush=True)
    return report


if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--no-browser',action='store_true')
    a.add_argument('--work',action='append')
    args=a.parse_args()
    run(args.out,use_browser=not args.no_browser,selection=set(args.work or []))
