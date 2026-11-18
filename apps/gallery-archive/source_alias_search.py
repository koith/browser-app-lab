#!/usr/bin/env python3
"""Search proven multilingual/partial spellings and visit SAME-WORK public HTML source pages.

Discovered URLs are only candidate research evidence until the existing decoder,
SHA dedupe, protected-source check, remote readback and gallery browser QA pass.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlencode
import requests
from bs4 import BeautifulSoup
from public_work_photo_extractor import ordinary_public_https_image
from source_name_ledger import LEDGER, queries, safe_url, key
from visual_work_discovery import ENGINES, hits_from_html

HEADERS={"User-Agent":"PersonalPublicPhotoSourceResearch/1.0","Accept":"text/html"}
EXCLUDE=("captcha","challenge","login","signin","password","verify-you-are-human")
MODELS={
    "mimmi":re.compile(r"mimmi|밈미|mimmissu17",re.I),
    "yui":re.compile(r"(?<![a-z])yui(?![a-z])|심유이|심혜성|ゆい|沈慧圣|super_yuisan",re.I)
}
IDENTITIES={
    "mimmi:djawa-pop-kitty-party":("pop","kitty","party"),
    "mimmi:djawa-nikke-yuni":("nikke","yuni"),
    "mimmi:djawa-janus-scary-lantern-night":("janus","scary","lantern","night"),
    "mimmi:djawa-rudy2-codename-wolfgirl":("codename","wolfgirl"),
    "mimmi:djawa-twin-bunnies-affair":("twin","bunnies","affair"),
    "yui:yui-meow-public-samples":("yui","meow"),
    "yui:artgravia-677-yui-public-samples":("artgravia","677","yui"),
    "yui:crazygiant-player5-public":("crazy","giant","player","5")
}
SEARCH_MAX_BYTES=2_000_000

def hydrate_all_registered_works(db, model, root=None):
    """Extend source-name discovery from eight manually seeded works to ALL
    known registered model+edition records. No invented URLs or actor identity.
    """
    root=Path(root or Path(__file__).resolve().parents[2])
    manifest=root/'apps'/f'{model}-gallery'/'public-work-pages.json'
    doc=json.loads(manifest.read_text(encoding='utf-8'))
    rows=doc.get('albums',[])
    if not isinstance(rows,list):
        raise ValueError('SOURCE_WORK_REGISTRY_INVALID')
    count=0
    for record in rows:
        aid=record.get('id')
        title=record.get('title')
        page=record.get('source')
        if not (isinstance(aid,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid)
                and isinstance(title,str) and len(title.strip())>=3
                and isinstance(page,str) and safe_url(page)):
            continue
        work=f'{model}:{aid}'
        if work not in db['works']:
            db['works'][work]=[{'name':title,'source':page,
                               'proof':'registered_existing_work_title'}]
            count+=1
        if work not in IDENTITIES:
            pieces=re.findall(r'[a-z0-9가-힣]{2,}',key(title))
            generic={'mimmi','yui','sim','public','sample','samples',
                     'photo','photos','cosplay','gallery','vol','djawa',
                     'artgravia','official','the','and','preview',
                     '공개','사진','미리보기','화보','공개본','심유이','심혜성',
                     '유이','공식','원본','이미지','샘플'}
            distinctive=tuple(dict.fromkeys(x for x in pieces if x not in generic))
            # Require at least one edition marker. A generic person-only source
            # is not evidence of belonging to a particular photobook.
            if distinctive:
                IDENTITIES[work]=distinctive
    # An owner archive can contain many works absent from the smaller list
    # of currently approved public sources. Its independently catalogued
    # edition title is still useful for finding (but not automatically
    # downloading) exact-work source pages.
    owner_manifest=root/'apps'/f'{model}-gallery'/'owner-index.json'
    if owner_manifest.is_file():
        owner_doc=json.loads(owner_manifest.read_text(encoding='utf-8'))
        if owner_doc.get('model')!=model:
            raise ValueError('OWNER_SOURCE_TITLE_MODEL_MISMATCH')
        for row in owner_doc.get('albums',[]):
            aid=row.get('id')
            title=row.get('title')
            if not (isinstance(aid,str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid)
                    and isinstance(title,str) and len(title.strip())>=4
                    and isinstance(row.get('images'),list) and row['images']):
                continue
            if re.search(r'AI Enhanced|AI 보정|미분류|unclassified',title,re.I):
                continue
            work=f'{model}:{aid}'
            if work in db['works']:
                continue
            generic={'mimmi','yui','sim','public','sample','samples','photo','photos',
                     'cosplay','gallery','vol','djawa','artgravia','official',
                     'the','and','preview','공개','사진','미리보기','화보','공개본',
                     '심유이','심혜성','유이','공식','원본','이미지','샘플'}
            pieces=re.findall(r'[a-z0-9가-힣]{2,}',key(title))
            distinctive=tuple(dict.fromkeys(t for t in pieces if t not in generic))
            if not distinctive:continue
            db['works'][work]=[{'name':title,'proof':'owner_catalog_work_title'}]
            if work not in IDENTITIES:IDENTITIES[work]=distinctive
            count+=1
    return count


def https_page(url):
    # Reverse search returns untrusted public page hints. Never request a
    # private/local/cloud-metadata host; reuse the existing public-origin
    # guard also used by image discovery and physical collection.
    if not safe_url(url) or ordinary_public_https_image(url,url) is None:return False
    p=urlsplit(url)
    return (not any(s in p.path.lower() for s in EXCLUDE) and
            not re.search(r"\.(?:zip|rar|7z|pdf|exe|jpe?g|png|webp)(?:$|/)",p.path,re.I))

def exact_work_in_text(work,text):
    words=IDENTITIES.get(work)
    if not words:return False
    text=key(text)
    # Same edition, not a neighboring volume or generic person-only source.
    return all(bool(re.search(r"(?<!\w)"+re.escape(w)+r"(?!\w)",text)) for w in words)

def page_matches(work,heading,context):
    model=work.split(":",1)[0]
    if not exact_work_in_text(work,heading):return False
    # An ambiguous Yui alone never establishes identity without the exact
    # work/volume and an explicit matching name in document text.
    if not MODELS[model].search(context):return False
    if model=="mimmi" and not re.search(r"djawa|mimmi|밈미",context,re.I):return False
    return True

def load_html(session,url,timeout=12):
    if not https_page(url):return None,"unsafe"
    try:
        r=session.get(url,headers=HEADERS,timeout=(7,timeout),allow_redirects=False)
        if r.status_code!=200:return None,"http_"+str(r.status_code)
        if "html" not in r.headers.get("Content-Type","").lower():return None,"not_html"
        if len(r.content)>SEARCH_MAX_BYTES:return None,"oversized"
        if re.search(r"captcha|are you human|unusual traffic",r.text[:12000],re.I):
            return None,"access_boundary"
        return r.text,"ok"
    except requests.RequestException as exc:
        return None,type(exc).__name__

def source_headings(html):
    soup=BeautifulSoup(html[:SEARCH_MAX_BYTES],"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    headlines=[x.get_text(" ",strip=True) for x in soup.select("h1,h2")[:8]]
    # A genuine public article may publish its exact edition only in the
    # HTML Open Graph / Twitter metadata; get_text() on <meta> is empty.
    # Use those observed fields, then still require independently matching
    # model+edition and page-scoped photos before staging any file.
    meta_titles=[x.get("content") or "" for x in soup.select(
        'meta[property="og:title"],meta[name="twitter:title"]')[:4]]
    meta_descriptions=[x.get("content") or "" for x in soup.select(
        'meta[property="og:description"],meta[name="description"]')[:4]]
    heads=" ".join([title]+headlines+meta_titles)
    context=" ".join([soup.get_text(" ",strip=True),*meta_titles,
                      *meta_descriptions])[:3000]
    return heads,context

def rotated_work_scope(work_ids, offset, per_work, work_budget):
    """Cover different work IDs every run, rather than shift by only ONE work.

    Workflow passes offset=run_number*per_work. Previously a 16-work budget
    shifted the window by one work per run: many albums were never inspected
    during an otherwise exhaustive 8,000-frame visual search campaign.
    """
    if not isinstance(offset,int) or offset<0 or not 1<=per_work<=6 or not 1<=work_budget<=80:
        raise ValueError('INVALID_PUBLIC_SOURCE_SCOPE')
    if not work_ids:
        return []
    budget=min(work_budget,len(work_ids))
    start=((offset//per_work)*budget)%len(work_ids)
    return [work_ids[(start+i)%len(work_ids)] for i in range(budget)]


def rotated_site_scope(hosts,offset,per_work,budget=2):
    if offset<0 or per_work<1 or budget<1:
        raise ValueError('INVALID_PUBLIC_CROSS_SITE_SCOPE')
    domains=sorted(set(hosts))
    if not domains:
        return []
    start=(offset//per_work)%len(domains)
    return [domains[(start+i)%len(domains)]
            for i in range(min(budget,len(domains)))]


def crawl_names(db,model,offset=0,per_work=3,max_pages=12,session=None,delay=.5,work_budget=None):
    session=session or requests.Session()
    results=[]
    visited_urls=set()
    hosts=set()
    status=Counter()
    work_ids=[x for x in db["works"] if x.startswith(model+":")]
    # Search different named works in successive runs. Every reverse-photo
    # result still enters independent same-work verification below.
    if work_budget is not None:
        if not 1<=work_budget<=80:
            raise ValueError('INVALID_NAME_WORK_BUDGET')
        work_ids=rotated_work_scope(work_ids,offset,per_work,work_budget)
    per_album_pages=max(1,max_pages//max(1,len(work_ids)))
    for work in work_ids:
        checked_this_work=0
        album=work.split(":",1)[1]
        terms=queries(db,model,album)
        if not terms:continue
        # Persistent external workflow-run number rotates the spelling candidates.
        selected=[terms[((offset//max(1,per_work))+i)%len(terms)] for i in range(min(per_work,len(terms)))]
        approved=[]
        observed=[]
        for term in selected:
            for engine,(endpoint,parameter) in ENGINES.items():
                html,state=load_html(session,endpoint+"?"+urlencode({parameter:term}))
                status["search_"+state]+=1
                if html is None:continue
                for result in hits_from_html(html,engine):
                    url=result["url"]
                    # A publisher page can appear as a hit for several
                    # editions. Rejecting it for work A must not prevent
                    # re-checking it for work B. De-duplicate within EACH
                    # work, not across the entire model catalog.
                    if (work,url) in visited_urls or not https_page(url):continue
                    # URL candidates cannot pass merely on a search title; open source.
                    # Search engines frequently use translated, shortened or
                    # generic card titles. Inspect a bounded *actual article*
                    # before dismissing the lead; never use snippets as identity
                    # proof and never import a neighboring model's images.
                    if checked_this_work>=per_album_pages:break
                    visited_urls.add((work,url))
                    checked_this_work+=1
                    source_html,state=load_html(session,url)
                    status["source_"+state]+=1
                    if source_html is None:continue
                    heading,context=source_headings(source_html)
                    if not page_matches(work,heading,context):continue
                    approved.append(url)
                    hosts.add(urlsplit(url).hostname)
                    observed.append({"album_id":album,"model":model,
                                     "name":heading[:220],"source":url,
                                     "proof":"unique_named_work_page_model_and_edition"})
                if checked_this_work>=per_album_pages:break
                if delay:time.sleep(delay)
            if checked_this_work>=per_album_pages:break
        results.append({"id":album,"title":db["works"][work][0]["name"],
                        "urls":list(dict.fromkeys(approved)),
                        "observations":observed,"query_count":len(selected)})
    # Every newly useful site is searched again for both tracked models.
    # This second pass is bounded and rotates through ALL observed model names.
    cross_site=[]
    cross_budget=16
    # The former sorted(hosts)[:2] permanently ignored every other
    # discovered source domain. Rotate the two-site budget by run number
    # so that all new sites receive a same-work cross-model check eventually.
    domains=sorted(hosts)
    rotated=rotated_site_scope(domains,offset,per_work,budget=2)
    for site in rotated:
        for other_model,names in db["model_names"].items():
            for identity in names:
                if cross_budget<=0:break
                cross_budget-=1
                site_query='site:'+site+' "'+identity["name"]+'"'
                search_html,state=load_html(session,ENGINES["bing"][0]+"?"+urlencode({"q":site_query}))
                status["site_"+state]+=1
                if search_html is None:continue
                for hit in hits_from_html(search_html,"bing")[:8]:
                    target=hit["url"]
                    if not https_page(target) or urlsplit(target).hostname!=site:continue
                    for work in [x for x in db["works"] if x.startswith(other_model+":")]:
                        # Same principle for cross-site sources: a translated
                        # search card cannot veto exact edition proof on-page.
                        body,source_status=load_html(session,target)
                        status["site_source_"+source_status]+=1
                        if body is None:continue
                        heading,context=source_headings(body)
                        if not page_matches(work,heading,context):continue
                        match={"model":other_model,"work":work,"source":target,
                               "observed_name":heading[:220],
                               "proof":"unique_named_work_page_model_and_edition"}
                        if match not in cross_site:cross_site.append(match)
                        if other_model==model:
                            album=work.split(":",1)[1]
                            row=next((x for x in results if x["id"]==album),None)
                            if row is not None:
                                if target not in row["urls"]:row["urls"].append(target)
                                row["observations"].append({
                                    "album_id":album,"model":model,
                                    "name":heading[:220],"source":target,
                                    "proof":"unique_named_work_page_model_and_edition"})
                        break
            if cross_budget<=0:break
        if cross_budget<=0:break
    return {"schema_version":1,"model":model,"targets":[
                {"id":r["id"],"title":r["title"],"urls":r["urls"]}
                for r in results if r["urls"]],
            "search_results":results,"new_site_hosts":sorted(hosts),
            "cross_model_verified_site_pages":cross_site,
            "cross_site_domains_total":len(domains),
            "cross_site_domains_scanned":rotated,
            "cross_site_model_alias_queries":16-cross_budget,
            "engine_status":dict(status),"research_only_not_yet_saved":True,
            "physical_originals_stored":0,"gallery_visible_added":0}

def merge_image_reverse_sites(db, report, model, results, session, limit=8, stats_out=None):
    """Resolve source-page identities across the *registered work catalog*.

    The reverse seed may be an unclassified or differently named preview
    album. Old code discarded the entire hit unless seed.album_id exactly
    matched a registered work ID; that discarded real image-source leads.
    Check same-model edition hints and independently verify the actual public
    page's heading/context. Ambiguous or generic-person pages never enter the
    trusted source scope.
    """
    accepted=[]
    stats=Counter()
    if report.get("research_only") is not True or not isinstance(report.get("results"),list):
        if stats_out is not None:stats_out.update(stats)
        return accepted
    catalog=[work for work in db["works"] if work.startswith(model+":")]
    seen=set()
    attempts=0
    for seed in report["results"]:
        if seed.get("model")!=model:continue
        seed_id=seed.get("album_id")
        for link in seed.get("candidate_pages",[])[:90]:
            if attempts>=limit:break
            stats['candidate_pages_seen']+=1
            url=link.get("url") if isinstance(link,dict) else None
            if not isinstance(url,str) or url in seen or not https_page(url):
                stats['invalid_or_duplicate_links']+=1
                continue
            # Search-title evidence is a cheap prefilter, NOT source identity
            # proof. A seed from an unrelated ID can still expose the exact
            # registered edition under an alternate published name.
            hint=str(link.get("label",""))+" "+url
            possible=[work for work in catalog if exact_work_in_text(work,hint)]
            # A *structured* same-photo host-page result can have no work
            # name in its search-card label or numeric URL. It is still
            # worth opening ONE bounded page and independently verifying
            # its actual model and edition heading. Generic Bing/Yandex
            # HTML links do NOT receive this privilege.
            structured=(link.get('source_engine') in (
                'yandex_sites','bing_visual_pages_including')
                and isinstance(link.get('matched_image_url'),str)
                and link['matched_image_url'].startswith('https://'))
            if not possible and structured:
                possible=catalog
                stats['structured_visual_host_page_without_edition_hint']+=1
            if not possible:
                stats['no_exact_edition_hint']+=1
                continue
            stats['exact_edition_hint_candidates']+=1
            seen.add(url)
            attempts+=1
            html,state=load_html(session,url)
            if html is None:
                stats['source_unreadable_'+str(state)[:50]]+=1
                continue
            stats['source_pages_opened']+=1
            heading,context=source_headings(html)
            confirmed=[work for work in possible if page_matches(work,heading,context)]
            if len(confirmed)!=1:
                stats['wrong_or_ambiguous_source_edition']+=1
                continue
            work=confirmed[0]
            album=work.split(":",1)[1]
            row=next((r for r in results if r["id"]==album),None)
            if row is None:
                row={"id":album,"title":db["works"][work][0]["name"],
                     "urls":[],"observations":[],"query_count":0}
                results.append(row)
            if url not in row["urls"]:row["urls"].append(url)
            row["observations"].append({
                "album_id":album,"model":model,"name":heading[:220],
                "source":url,"reverse_seed_album_id":seed_id,
                "proof":"unique_named_work_page_model_and_edition"})
            accepted.append({"model":model,"album_id":album,"source":url,
                             "reverse_seed_album_id":seed_id,
                             "origin":"reverse_photo_source_page_identified"})
            stats['accepted_verified_same_work_pages']+=1
            if seed_id!=album:stats['cross_album_seed_recovered']+=1
        if attempts>=limit:break
    if stats_out is not None:stats_out.update(stats)
    return accepted


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=["mimmi","yui"],required=True)
    p.add_argument("--ledger",type=Path,default=LEDGER)
    p.add_argument("--reverse",type=Path)
    p.add_argument("--reverse-limit",type=int,default=8)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--per-work",type=int,default=3)
    p.add_argument("--max-pages",type=int,default=12)
    p.add_argument("--work-budget",type=int,default=16)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if not 0<=a.offset or not 1<=a.per_work<=6 or not 1<=a.max_pages<=96 or not 1<=a.reverse_limit<=128 or not 1<=a.work_budget<=80:
        raise ValueError("bounded_research_budget_required")
    db=json.loads(a.ledger.read_text(encoding="utf-8"))
    new_works=hydrate_all_registered_works(db,a.model)
    report=crawl_names(db,a.model,a.offset,a.per_work,a.max_pages,
                       work_budget=a.work_budget)
    report['additional_registered_works_searched_by_catalog']=new_works
    if a.reverse and a.reverse.is_file():
        reverse_stats={}
        matches=merge_image_reverse_sites(db,json.loads(a.reverse.read_text(encoding="utf-8")),
                                         a.model,report["search_results"],requests.Session(),
                                         limit=a.reverse_limit,stats_out=reverse_stats)
        report["image_reverse_resolution_stats"]=reverse_stats
        report["image_reverse_sites_verified"]=matches
        report["targets"]=[{"id":x["id"],"title":x["title"],"urls":x["urls"]}
                           for x in report["search_results"] if x["urls"]]
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SAME_WORK_MULTILINGUAL_SOURCE_SEARCH",json.dumps({
        "model":a.model,"new_site_hosts":len(report["new_site_hosts"]),
        "target_source_pages":sum(len(x["urls"]) for x in report["targets"]),
        "physical_originals_stored":0},ensure_ascii=False))

if __name__=="__main__":main()
