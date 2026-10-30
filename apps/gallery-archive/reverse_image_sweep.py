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
from urllib.parse import urlsplit

import requests
from reverse_seed_priority import seeds
from reverse_sites_parser import sites_from_html
from reverse_image_discovery import untrack, leads_from_html, identity_supported

RESEARCH_UA="PersonalPublicPhotoSourceResearch/1.0"
SEARCH_URL="https://yandex.com/images/search"
BING_URL="https://www.bing.com/images/search"

def query_page(client,source,params):
    try:
        r=client.get(source,params=params,timeout=(9,26),allow_redirects=False,
                     headers={"User-Agent":RESEARCH_UA,"Accept":"text/html"})
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
    client=client or requests.Session()
    url=seed["public_image_url"]
    status,html=query_page(client,SEARCH_URL,{"rpt":"imageview","cbir_page":"sites","url":url})
    links=sites_from_html(html,untrack) if html else []
    if not links and html:
        links=leads_from_html(html)
    stages={"yandex_sites":status if status!="ok" else "leads_"+str(len(links))}
    if not links and status not in ("captcha_not_bypassed","http_429"):
        alt_status,alt_html=query_page(client,SEARCH_URL,{"rpt":"imageview","url":url})
        extra=sites_from_html(alt_html,untrack) if alt_html else []
        if not extra and alt_html:extra=leads_from_html(alt_html)
        links=extra
        stages["yandex_general"]=alt_status if alt_status!="ok" else "leads_"+str(len(extra))
    # Bing remains a genuinely independent fallback.
    if not links:
        b_status,b_html=query_page(client,BING_URL,{
            "view":"detailv2","iss":"sbi","FORM":"SBIHMP","sbisrc":"UrlPaste",
            "q":"imgurl:"+url})
        b_links=leads_from_html(b_html) if b_html else []
        links=b_links
        stages["bing"]=b_status if b_status!="ok" else "leads_"+str(len(b_links))
    approved=[]
    rejected=0
    for link in links:
        if identity_supported(seed,link):
            approved.append(link)
        else: rejected+=1
    return {**seed,"search_status":stages,"candidate_pages":approved[:90],
            "off_model_rejected":rejected,"originals_stored":0,"visible_gallery_added":0}

def sweep(root,limit,offset,workers=2,client_factory=None):
    inventory=seeds(root)
    if not inventory:raise ValueError("No stored seed photographs")
    if limit<1 or limit>48 or offset<0 or workers<1 or workers>3:
        raise ValueError("Bounded public image search budget")
    selected=[inventory[(offset+i)%len(inventory)]
              for i in range(min(limit,len(inventory)))]
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
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    from reverse_seed_priority import ROOT
    result=sweep(ROOT,args.seeds,args.offset,args.workers)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("IMAGE_FIRST_PRIORITY_SWEEP",json.dumps({
        key:result[key] for key in ("seed_queries","unique_albums_queried",
            "source_pages_accepted","off_model_rejected","physical_photos_new")
    },ensure_ascii=False),flush=True)

if __name__=="__main__":main()
