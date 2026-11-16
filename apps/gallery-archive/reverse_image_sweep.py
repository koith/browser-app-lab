#!/usr/bin/env python3
"""Image-first source search of weakly covered physically archived photobooks.

A search lead is *never* automatically counted as a downloaded photo.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urljoin

import requests
from reverse_seed_priority import seeds
from reverse_sites_parser import sites_from_html
from reverse_image_discovery import untrack, leads_from_html, identity_supported

RESEARCH_UA="PersonalPublicPhotoSourceResearch/1.0"
SEARCH_URL="https://yandex.com/images/search"
BING_URL="https://www.bing.com/images/search"

def query_page(client,source,params):
    try:
        current=source
        for hop in range(4):
            r=client.get(current,params=params if hop==0 else None,timeout=(9,26),allow_redirects=False,
                         headers={"User-Agent":RESEARCH_UA,"Accept":"text/html"})
            if r.status_code not in (301,302,303,307,308):break
            target=urljoin(current,r.headers.get('Location',''));parsed=urlsplit(target)
            if (parsed.scheme!='https' or parsed.hostname!=urlsplit(source).hostname or
                parsed.username or parsed.password or parsed.port not in (None,443) or
                any(word in parsed.path.casefold() for word in ('captcha','challenge','login','signin','verify'))):
                return 'redirect_access_boundary_not_followed',[]
            current=target
        else:return 'redirect_limit',[]
        if r.status_code!=200:
            return "http_"+str(r.status_code),[]
        if "html" not in r.headers.get("Content-Type","").lower():
            return "not_html",[]
        if len(r.content)>4500000:return "oversized",[]
        if "are you not a robot" in r.text[:20000].lower() or "smartcaptcha" in r.text[:10000].lower():
            return "captcha_not_bypassed",[]
        return "ok",r.text
    except requests.RequestException as e:
        return "network_"+type(e).__name__,[]

def search_one(seed,client=None):
    """Keep searching when the first engine returns *unrelated* pages.

    The previous fallback used `not links`, so a Yandex page containing
    unrelated models stopped the Bing search even if zero usable matches
    were found. Count distinct model-supported URLs, not raw HTML anchors.
    """
    client=client or requests.Session()
    url=seed["public_image_url"]
    approved=[]
    seen=set()
    rejected=0
    per_engine={}
    def accept(items,name):
        nonlocal rejected
        accepted_here=0
        for link in items:
            if not isinstance(link,dict):
                continue
            target=link.get("url")
            if not isinstance(target,str) or not target.startswith("https://"):
                continue
            if identity_supported(seed,link):
                if target not in seen:
                    approved.append(link)
                    seen.add(target)
                    accepted_here+=1
            else:
                rejected+=1
        per_engine[name]=accepted_here

    status,html=query_page(client,SEARCH_URL,{"rpt":"imageview","cbir_page":"sites","url":url})
    links=sites_from_html(html,untrack) if html else []
    if not links and html:
        links=leads_from_html(html)
    stages={"yandex_sites":status if status!="ok" else "leads_"+str(len(links))}
    accept(links,"yandex_sites")

    # A nonempty collection of unrelated links is NOT a visual match.
    if not approved and status not in ("captcha_not_bypassed","http_429"):
        alt_status,alt_html=query_page(client,SEARCH_URL,{"rpt":"imageview","url":url})
        extra=sites_from_html(alt_html,untrack) if alt_html else []
        if not extra and alt_html:
            extra=leads_from_html(alt_html)
        stages["yandex_general"]=alt_status if alt_status!="ok" else "leads_"+str(len(extra))
        accept(extra,"yandex_general")

    # Query Bing when Yandex has no match or only one/two distinct leads.
    # This stays bounded (one Bing request) and does not retry access blocks.
    if len(approved)<3:
        b_status,b_html=query_page(client,BING_URL,{
            "view":"detailv2","iss":"sbi","FORM":"SBIHMP","sbisrc":"UrlPaste",
            "q":"imgurl:"+url})
        b_links=leads_from_html(b_html) if b_html else []
        stages["bing"]=b_status if b_status!="ok" else "leads_"+str(len(b_links))
        accept(b_links,"bing")
    return {**seed,"search_status":stages,"candidate_pages":approved[:90],
            "matched_urls_by_engine":per_engine,
            "off_model_rejected":rejected,
            "originals_stored":0,"visible_gallery_added":0}

def diversified_seed_window(inventory, limit, offset):
    """Deterministic, complete round-robin photo queue with contiguous windows.

    Workflows call this with offset=run_number*limit. Previously the album
    cursor and an epoch derived from album count could revisit an album's
    even-numbered photos indefinitely while never searching odd-numbered
    ones. Flatten every distinct (model, album, SHA) once, interleaving
    albums for early diversity, and slice by global photo position instead.
    """
    if not inventory or not 1 <= limit <= 48 or offset < 0:
        raise ValueError('INVALID_DIVERSE_SEED_WINDOW')
    by_album = {}
    seen = set()
    for photo in inventory:
        key = (photo['model'], photo['album_id'])
        identity = (key, photo['photo_sha256'])
        if identity in seen:
            continue
        seen.add(identity)
        by_album.setdefault(key, []).append(photo)
    albums = list(by_album)
    max_cuts = max(len(group) for group in by_album.values())
    ordered = []
    for photo_index in range(max_cuts):
        for key in albums:
            group = by_album[key]
            if photo_index < len(group):
                ordered.append(group[photo_index])
    count = min(limit, len(ordered))
    return [ordered[(offset + i) % len(ordered)] for i in range(count)]


def sweep(root,limit,offset,workers=2,client_factory=None,model=None,all_cuts=False):
    inventory=seeds(root,all_cuts=all_cuts)
    if model is not None:
        inventory=[entry for entry in inventory if entry['model']==model]
    if not inventory:raise ValueError("No stored seed photographs")
    if limit<1 or limit>48 or offset<0 or workers<1 or workers>3:
        raise ValueError("Bounded public image search budget")
    selected=diversified_seed_window(inventory,limit,offset)
    def run(photo):
        client=client_factory() if client_factory else requests.Session()
        return search_one(photo,client)
    results=[None]*len(selected)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(run,photo):i for i,photo in enumerate(selected)}
        for done in as_completed(jobs):
            i=jobs[done]
            try:results[i]=done.result()
            except Exception as exc:
                results[i]={**selected[i],"search_status":{"worker_error":type(exc).__name__},
                            "candidate_pages":[],"off_model_rejected":0,
                            "originals_stored":0,"visible_gallery_added":0}
    result={
        "schema_version":1,"method":"visual_same-photo-first",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "total_seed_frames":len(inventory),"seed_queries":len(results),
        "unique_albums_queried":len({(r["model"],r["album_id"]) for r in results}),
        "source_pages_accepted":len({p["url"] for r in results for p in r["candidate_pages"]}),
        "off_model_rejected":sum(r["off_model_rejected"] for r in results),
        "physical_photos_new":0,"gallery_photos_new":0,
        "research_only":True,"results":results,
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",type=int,default=36)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--model",choices=["mimmi","yui"])
    p.add_argument("--all-cuts",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    from reverse_seed_priority import ROOT
    result=sweep(ROOT,args.seeds,args.offset,args.workers,model=args.model,all_cuts=args.all_cuts)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("IMAGE_FIRST_PRIORITY_SWEEP",json.dumps({
        key:result[key] for key in ("seed_queries","unique_albums_queried",
            "source_pages_accepted","off_model_rejected","physical_photos_new")
    },ensure_ascii=False),flush=True)

if __name__=="__main__":main()
