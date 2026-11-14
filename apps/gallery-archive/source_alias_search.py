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

def https_page(url):
    if not safe_url(url):return False
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
    headlines=[x.get_text(" ",strip=True) for x in soup.select("h1,h2,meta[property='og:title']")[:8]]
    heads=" ".join([title]+headlines)
    context=soup.get_text(" ",strip=True)[:3000]
    return heads,context

def crawl_names(db,model,offset=0,per_work=3,max_pages=12,session=None,delay=.5):
    session=session or requests.Session()
    results=[]
    visited_urls=set()
    hosts=set()
    status=Counter()
    work_ids=[x for x in db["works"] if x.startswith(model+":")]
    per_album_pages=max(1,max_pages//max(1,len(work_ids)))
    for work in work_ids:
        checked_this_work=0
        album=work.split(":",1)[1]
        terms=queries(db,model,album)
        if not terms:continue
        # Persistent external workflow-run number rotates the spelling candidates.
        selected=[terms[(offset+i)%len(terms)] for i in range(min(per_work,len(terms)))]
        approved=[]
        observed=[]
        for term in selected:
            for engine,(endpoint,parameter) in ENGINES.items():
                html,state=load_html(session,endpoint+"?"+urlencode({parameter:term}))
                status["search_"+state]+=1
                if html is None:continue
                for result in hits_from_html(html,engine):
                    url=result["url"]
                    if url in visited_urls or not https_page(url):continue
                    # URL candidates cannot pass merely on a search title; open source.
                    if not exact_work_in_text(work,result.get("title","")+" "+result.get("snippet","")):continue
                    visited_urls.add(url)
                    if checked_this_work>=per_album_pages:break
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
    for site in sorted(hosts)[:2]:
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
                        if not exact_work_in_text(work,hit.get("title","")+" "+hit.get("snippet","")):continue
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
            "cross_site_model_alias_queries":16-cross_budget,
            "engine_status":dict(status),"research_only_not_yet_saved":True,
            "physical_originals_stored":0,"gallery_visible_added":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=["mimmi","yui"],required=True)
    p.add_argument("--ledger",type=Path,default=LEDGER)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--per-work",type=int,default=3)
    p.add_argument("--max-pages",type=int,default=12)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if not 0<=a.offset or not 1<=a.per_work<=6 or not 1<=a.max_pages<=32:
        raise ValueError("bounded_research_budget_required")
    report=crawl_names(json.loads(a.ledger.read_text(encoding="utf-8")),
                       a.model,a.offset,a.per_work,a.max_pages)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SAME_WORK_MULTILINGUAL_SOURCE_SEARCH",json.dumps({
        "model":a.model,"new_site_hosts":len(report["new_site_hosts"]),
        "target_source_pages":sum(len(x["urls"]) for x in report["targets"]),
        "physical_originals_stored":0},ensure_ascii=False))

if __name__=="__main__":main()
