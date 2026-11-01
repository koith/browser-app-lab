#!/usr/bin/env python3
"""Sharded *entire-registered-scope* collection-engine comparison.

Every enumerated work/source/lead must yield a row, including unsupported,
HTTP blocked, no source, runner-budget-limited and model-attribution-uncertain.
This is a comparison only; source URLs are never archived by this script.
"""
from __future__ import annotations

import argparse
import ipaddress
from collections import Counter,deque
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
import sys
import time
from urllib.parse import urljoin,urlsplit,parse_qsl

import requests
from bs4 import BeautifulSoup
from collector_full_census import census,select
from collector_engines_ab import asset_group, verify_public
from direct_photo_pipeline import page_images,safe_page,MODEL_PATTERNS
from public_photo_archive import PublicSession, public_failure

GDL_PAGE_LIMIT=600
MAX_DOC_BYTES=6_000_000
SOURCE_ENS=['existing_scoped','scrapy_selectors','playwright_dom','gallery_dl','manifest_known']


def alternative_safe_photo(url):
    """Independent public-HTTPS image admission beyond the legacy host list."""
    try:
        p=urlsplit(url);host=(p.hostname or '').lower().rstrip('.')
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443):return False
        if not host or len(url)>2100 or p.fragment:return False
        if host in ('localhost','metadata.google.internal'):return False
        if any(host.endswith(s) for s in ('.localhost','.local','.internal','.test','.invalid')):return False
        try:
            ip=ipaddress.ip_address(host)
            if not ip.is_global:return False
        except ValueError:
            if '.' not in host:return False
        if not re.search(r'\.(?:jpe?g|png|webp)$',p.path,re.I):return False
        if re.search(r'logo|avatar|favicon|emoji|banner|placeholder|tracking',p.path,re.I):return False
        return True
    except (ValueError,TypeError):return False

def independent_scrapy_extract(raw,url,model):
    """Scrapy selectors without reusing our original photo-host exclusions."""
    from scrapy.http import HtmlResponse
    response=HtmlResponse(url=url,body=raw,encoding='utf-8')
    heading=' '.join(response.css('h1::text,title::text').getall())
    article=None
    for css in ('#powerbbsContent','.portfolio-content','.entry-content','article','main'):
        selections=response.css(css)
        if selections:
            article=selections[0];break
    if article is None:return [],'no_scoped_article'
    context=heading+' '+(' '.join(article.css('::text').getall()))
    if not MODEL_PATTERNS[model].search(context):return [],'missing_model_identity'
    images=[]
    for node in article.css('img,source'):
        if any(any(re.search(r'related|recommend|comment|advert|sidebar',item,re.I)
                   for item in ancestor.attrib.get('class','').split())
               for ancestor in node.root.iterancestors() if ancestor is not article.root):
            continue
        attrs=[]
        for k in ('data-full','data-original','data-large-file','data-src','data-lazy-src','src','srcset','data-srcset'):
            if node.attrib.get(k):attrs.append(node.attrib[k])
        anchor=node.xpath('ancestor::a[1]/@href').get()
        if anchor:attrs.append(anchor)
        for value in attrs:
            for segment in value.split(',') if ',' in value else (value,):
                u=urljoin(url,segment.strip().split()[0]) if segment.strip() else ''
                if alternative_safe_photo(u) and u not in images:images.append(u)
    return images,'independent_scrapy_selector'


def pagination_from_html(raw,url,work_root):
    """Follow only observed, same-work pagination; never manufacture photo paths."""
    here=urlsplit(url);base=urlsplit(work_root)
    if here.hostname!=base.hostname:return []
    page=BeautifulSoup(raw,'html.parser')
    found=[]
    for a in page.select('a[href]'):
        link=urljoin(url,a.get('href') or '')
        p=urlsplit(link)
        if p.scheme!='https' or p.hostname!=base.hostname or p.username or p.password or p.port not in (None,443):
            continue
        if link==url or link==work_root:continue
        label=a.get_text(' ',strip=True).casefold()
        rel=a.get('rel') or []
        if isinstance(rel,str):rel=rel.split()
        same=(p.path.rstrip('/')==base.path.rstrip('/') or
              p.path.rstrip('/').startswith(base.path.rstrip('/')+'/'))
        params=dict(parse_qsl(p.query))
        paged=bool(params.get('page','').isdigit() and 2<=int(params['page'])<=1000)
        suffix=bool(re.search(r'/page/[2-9][0-9]{0,2}/?$',p.path))
        if same and (paged or suffix) and (
                label.isdigit() or 'next' in label or 'older' in label
                or label in ('›','»','다음','下一页','次へ','→')
                or 'next' in rel):
            if link not in found:found.append(link)
    return found


class LiveBrowser:
    def __init__(self,enabled=True):
        self.enabled=enabled
        self.play=None;self.browser=None;self.page=None;self.reason=None
    def open(self):
        if not self.enabled:return
        if self.page:return
        try:
            from playwright.sync_api import sync_playwright
            self.play=sync_playwright().start()
            self.browser=self.play.chromium.launch(headless=True,args=['--disable-gpu'])
            self.page=self.browser.new_page()
        except Exception as exc:
            self.reason=type(exc).__name__;self.close()
    def extract(self,url,model):
        if not self.enabled:return [],'not_run'
        if not self.page:self.open()
        if not self.page:return [],'browser_unavailable_'+str(self.reason)
        try:
            response=self.page.goto(url,wait_until='domcontentloaded',timeout=16000)
            if response is None:return [],'no_response'
            if response.status>=400:return [],'http_'+str(response.status)
            self.page.evaluate('window.scrollBy(0,document.body.scrollHeight/2)')
            self.page.wait_for_timeout(250)
            raw=self.page.content().encode('utf-8')
            if urlsplit(url).hostname=='teapawt.net':
                urls,_,status=page_images(raw,url,model)
                return urls,'exact_author_'+status
            urls,status=scoped_generic_html(raw,url,model)
            return urls,status
        except Exception as exc:return [],'error_'+type(exc).__name__
    def close(self):
        if self.page:
            try:self.page.close()
            except Exception:pass
        if self.browser:
            try:self.browser.close()
            except Exception:pass
        if self.play:
            try:self.play.stop()
            except Exception:pass
        self.page=self.browser=self.play=None


def gallery_dl_work(url):
    """Try the genuine native extractor for each work, not pretend all sites fit."""
    p=urlsplit(url)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443):
        return [],'unapproved_url'
    args=[sys.executable,'-m','gallery_dl','-g','--range',
          '1-'+str(GDL_PAGE_LIMIT),'--',url]
    try:
        done=subprocess.run(args,capture_output=True,text=True,timeout=45)
        urls=list(dict.fromkeys(s.strip() for s in done.stdout.splitlines() if safe_photo(s.strip())))
        if done.returncode==64:return [],'unsupported_extractor'
        return urls[:GDL_PAGE_LIMIT],('ok' if done.returncode==0 else 'exit_'+str(done.returncode))
    except subprocess.TimeoutExpired:return [],'timeout_45s'
    except OSError as exc:return [],'runtime_'+type(exc).__name__


def make_status(row):
    return {'model':row['model'],'kind':row['kind'],'id':row['id'],'title':row.get('title'),
            'owner_registered':row.get('owner_registered',False),
            'owner_slots':row.get('owner_slots',0),'owner_distinct_sha':row.get('owner_distinct_sha',0),
            'initial_source_pages':len(row.get('urls',[])),
            'declared_direct_images':len(row.get('direct_image_urls',[])),
            'registered_page_attempts':0,'additional_pages_discovered':0,
            'http_statuses':{},'engine_page_statuses':{},'engine_photo_urls':{},
            'decoded_sha_by_engine':{},'candidate_asset_groups_by_engine':{},
            'extra_asset_groups_candidate_not_proven_distinct_cuts':0,
            'limits':[],'reason':None,'actual_public_image_downloads':0,
            'actual_public_images_decoded':0,'new_private_originals_stored':0,
            'new_gallery_photos_verified':0,'no_owner_mutation':True}


def inspect_work(row,client,browser,max_pages=500,max_images=650,
                 max_browser_pages=500,wall_seconds=240):
    result=make_status(row)
    initial=list(dict.fromkeys(u for u in row.get('urls',[]) if u.startswith('https://')))
    initial_direct=list(dict.fromkeys(u for u in row.get('direct_image_urls',[]) if safe_photo(u)))
    if not initial and not initial_direct:
        result['reason']='no_physical_public_source_registered' if row['kind']!='visual_lead' else 'title_only_search_needed'
        return result
    begun=time.monotonic()
    methods={e:[] for e in SOURCE_ENS}
    methods['manifest_known']=initial_direct
    statuses=Counter()
    engine_statuses=Counter()
    first_urls=initial[:]
    # A site-specific gallery-dl extractor may itself follow its album pages.
    if initial:
        gdl,gs=gallery_dl_work(initial[0])
        methods['gallery_dl'].extend(gdl)
        engine_statuses['gallery_dl:'+gs]+=1
        if len(gdl)>=GDL_PAGE_LIMIT:result['limits'].append('gallery_dl_range_limit')
    queue=deque(initial);visited=set();discovered=0;browser_visits=0
    blocked=set()
    # All explicit manifest URLs are in the queue, even on an unsupported host.
    # The limit is recorded as incomplete, never called a full sweep.
    while queue:
        if len(visited)>=max_pages:
            result['limits'].append('max_pages_per_target');break
        if time.monotonic()-begun>=wall_seconds:
            result['limits'].append('target_wall_time');break
        url=queue.popleft()
        if url in visited:continue
        visited.add(url)
        origin=urlsplit(url).hostname
        if origin in blocked:
            statuses['blocked_origin_skipped']+=1
            continue
        try:
            response=client.get(url)
            raw=response.content
            if len(raw)>MAX_DOC_BYTES:
                statuses['oversized_html']+=1
                continue
            if b'<html' not in raw[:2500].lower() and b'<!doctype' not in raw[:2500].lower():
                statuses['not_html']+=1
                continue
            statuses['http_200']+=1
        except Exception as exc:
            d=public_failure(exc)
            code=d.get('http_status')
            statuses['http_'+str(code) if code else d.get('cause','error')]+=1
            if code in (401,403,429,451):
                blocked.add(origin)
            continue
        # A legacy work-specific parser is only executable on its supported origins.
        next_pages=[]
        if safe_page(url):
            try:
                base,more,bs=page_images(raw,url,row['model'])
                methods['existing_scoped'].extend(u for u in base if safe_photo(u))
                next_pages.extend(more)
                engine_statuses['existing_scoped:'+bs]+=1
            except Exception as exc:engine_statuses['existing_scoped:'+type(exc).__name__]+=1
        else:engine_statuses['existing_scoped:unsupported_origin']+=1
        try:
            scrape,st=scoped_generic_html(raw,url,row['model'])
            methods['scrapy_selectors'].extend(u for u in scrape if safe_photo(u))
            engine_statuses['scrapy:'+st]+=1
        except Exception as exc:engine_statuses['scrapy:'+type(exc).__name__]+=1
        if browser_visits<max_browser_pages:
            urls,bs=browser.extract(url,row['model'])
            methods['playwright_dom'].extend(u for u in urls if safe_photo(u))
            engine_statuses['browser:'+bs]+=1
            browser_visits+=1
        else:
            if 'browser_page_budget' not in result['limits']:result['limits'].append('browser_page_budget')
        for link in pagination_from_html(raw,url,first_urls[0]):
            next_pages.append(link)
        for link in next_pages:
            if link not in visited and link not in queue and link.startswith('https://'):
                # Restrict auto-discovery to the exact original site's collection.
                p=urlsplit(link);q=urlsplit(first_urls[0])
                if p.hostname==q.hostname and p.username is None and p.password is None:
                    queue.append(link);discovered+=1
    result['registered_page_attempts']=len(visited)
    result['additional_pages_discovered']=discovered
    result['http_statuses']=dict(statuses)
    result['engine_page_statuses']=dict(engine_statuses)
    if queue:result['limits'].append('pending_page_queue_'+str(len(queue)))
    accepted={}
    for engine,urls in methods.items():
        items=list(dict.fromkeys(u for u in urls if safe_photo(u)))
        accepted[engine]=items
        result['engine_photo_urls'][engine]=len(items)
        result['candidate_asset_groups_by_engine'][engine]=len(set(asset_group(u) for u in items))
    # Images from multiple actors on public timelines are not independent model
    # evidence. The native parser and rendered author-scoped feed are safe;
    # generic Scrapy on a social timeline is quarantined as research-only.
    author_scope=all(u.split('/')[2]=='teapawt.net' for u in initial) and bool(initial)
    trusted=set(SOURCE_ENS)
    if author_scope:trusted.discard('scrapy_selectors')
    baseline=set(asset_group(u) for u in accepted['existing_scoped'])
    pool=set(asset_group(u) for k,urls in accepted.items() if k in trusted for u in urls)
    result['extra_asset_groups_candidate_not_proven_distinct_cuts']=len(pool-baseline)
    result['untrusted_social_generic_candidates']=len(accepted['scrapy_selectors']) if author_scope else 0
    result['candidate_distinct_assets_across_methods']=len(pool)
    # Stronger evidence: downloads actual decoded public image bytes, with
    # explicit failures/budgets; never infer physical private archive publication.
    # Verify URL-union, not only baseline, to avoid giving existing code an edge.
    image_urls=list(dict.fromkeys(u for k in ('existing_scoped','gallery_dl',
              'scrapy_selectors','playwright_dom','manifest_known')
              if k in trusted for u in accepted[k]))
    decoded_sha={k:set() for k in methods}
    by_url={}
    class PublicImageFetcher:
        def get(self,url,**_kwargs):
            # Reuse the same origin/robots/rate state as public page discovery.
            return client.get(url)
    image_fetcher=PublicImageFetcher()
    for url in image_urls:
        if result['actual_public_image_downloads']>=max_images:
            result['limits'].append('max_image_gets_per_target');break
        if time.monotonic()-begun>=wall_seconds:
            result['limits'].append('target_wall_time');break
        evidence=verify_public(image_fetcher,url)
        result['actual_public_image_downloads']+=1
        by_url[url]=evidence
    for engine,urls in accepted.items():
        for url in urls:
            d=by_url.get(url)
            if d and d.get('status')=='decoded_sha':
                decoded_sha[engine].add(d['sha256'])
    result['decoded_sha_by_engine']={k:len(v) for k,v in decoded_sha.items()}
    result['actual_public_images_decoded']=len({v['sha256'] for v in by_url.values()
                                                if v.get('status')=='decoded_sha'})
    result['public_image_failure_statuses']=dict(Counter(v.get('status','unknown')
                                              for v in by_url.values() if v.get('status')!='decoded_sha'))
    baseline_sha=decoded_sha['existing_scoped']
    verified_all=set().union(*(decoded_sha[e] for e in trusted))
    result['extra_decoded_sha_not_in_baseline']=len(verified_all-baseline_sha)
    result['unverified_image_urls']=max(0,len(image_urls)-len(by_url))
    result['no_auth_or_protected_retries']=True
    result['reason']='limited_incomplete' if result['limits'] else 'all_registered_pages_visited_within_public_access'
    return result


def audit(root,model,shard,shards,out,max_pages=500,max_images=650,
          browser_pages=500,wall_seconds=240):
    all_data=census(root)
    targets=select(all_data,model,shard,shards)
    session=PublicSession(delay=.1)
    browser=LiveBrowser(enabled=True)
    rows=[]
    try:
        for idx,row in enumerate(targets):
            try:
                result=inspect_work(row,session,browser,max_pages,max_images,
                                    browser_pages,wall_seconds)
            except Exception as exc:
                result=make_status(row)
                result['reason']='engine_exception_'+type(exc).__name__
            rows.append(result)
            print('EXHAUSTIVE_ENGINE_WORK',json.dumps({
                'i':idx+1,'total':len(targets),'model':model,'kind':row['kind'],'id':row['id'],
                'sources':result['initial_source_pages'],'pages':result['registered_page_attempts'],
                'engine_images':result['engine_photo_urls'],
                'decoded':result['actual_public_images_decoded'],
                'candidate_extras':result['extra_asset_groups_candidate_not_proven_distinct_cuts'],
                'reason':result['reason'],'limits':result['limits']},ensure_ascii=False),flush=True)
    finally:browser.close()
    summary={'target_count':len(targets),'targets_reported':len(rows),
             'model':model,'shard':shard,'shards':shards,
             'no_source':sum(r['reason'] in ('no_physical_public_source_registered',
                                            'title_only_search_needed') for r in rows),
             'limited_targets':sum(bool(r['limits']) for r in rows),
             'page_attempts':sum(r['registered_page_attempts'] for r in rows),
             'public_images_decoded_sum_not_deduplicated_across_works':
                sum(r['actual_public_images_decoded'] for r in rows),
             'candidate_unmatched_asset_groups_sum_not_proven_new':
                sum(r['extra_asset_groups_candidate_not_proven_distinct_cuts'] for r in rows),
             'new_private_originals_stored':0,'gallery_visible_photos_added':0,
             'all_registered_targets_accounted_for':len(rows)==len(targets),
             'complete_public_web_coverage_claimed':False}
    data={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
          'census_summary':all_data['summary'],'summary':summary,'targets':rows,
          'warning':'A/B research: alternate resized images, social embeds and blocked sources do not prove missing photo cuts. No owner-storage write.'}
    output=Path(out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('EXHAUSTIVE_ENGINE_SHARD_SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)
    if len(rows)!=len(targets):raise ValueError('missing_registered_target_result')
    return data


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--model',choices=['yui','mimmi'],required=True)
    ap.add_argument('--shard',type=int,required=True)
    ap.add_argument('--shards',type=int,default=8)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--max-pages',type=int,default=500)
    ap.add_argument('--max-images',type=int,default=650)
    ap.add_argument('--browser-pages',type=int,default=500)
    ap.add_argument('--work-seconds',type=int,default=240)
    args=ap.parse_args()
    if not 0<=args.shard<args.shards<=64:raise ValueError('invalid_shard_range')
    audit(args.root,args.model,args.shard,args.shards,args.out,
          args.max_pages,args.max_images,args.browser_pages,args.work_seconds)


if __name__=='__main__':main()
