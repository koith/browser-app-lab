#!/usr/bin/env python3
"""Discover additional Mimmi photobooks by traversing her public V2PH actor pages.

Pages are strictly actor-scoped, verified by model identity. Photo URLs are
only from normal published previews; second-page/login failures are recorded,
not circumvented. No ZIPs or paid tools.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,urlunsplit
import requests
from bs4 import BeautifulSoup
from collect_v2ph_public import S,T,safe_source,photos_on_page,get_bytes_verified
ROOT=Path(__file__).resolve().parent
ACTOR_URL="https://www.v2ph.com/actor/Mimmi"
ALBUM_PATH=re.compile(r"^/album/[a-z0-9]+\.html$",re.I)
MIMMI=re.compile(r"mimmi|밈미|밈미",re.I)

def scan_actor(max_pages=8,max_album_candidates=80):
    found={}
    pages=[]
    for n in range(1,max_pages+1):
        u=ACTOR_URL if n==1 else ACTOR_URL+"?page="+str(n)
        try:
            resp=S.get(u,timeout=T)
            resp.raise_for_status()
            if not safe_source(resp.url):break
            soup=BeautifulSoup(resp.content,"html.parser")
            head=soup.find("h1")
            if not head or not MIMMI.search(head.get_text(" ",strip=True)):
                raise ValueError("Actor heading not Mimmi; stop to prevent wrong models")
            urls={}
            for anchor in soup.select("a[href]"):
                raw=urljoin(resp.url,anchor.get("href",""))
                parsed=urlsplit(raw)
                if not safe_source(raw) or not ALBUM_PATH.fullmatch(parsed.path):continue
                canonical=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,"",""))
                # Accept only album cards; avoid recommended unrelated cards.
                parent=anchor.find_parent(["article","li","div"])
                name=anchor.get_text(" ",strip=True)
                if not name and anchor.select_one("img"):
                    name=anchor.select_one("img").get("alt","")
                if not name and parent:
                    heading=parent.find(["h2","h3","h4","h5"])
                    if heading:name=heading.get_text(" ",strip=True)
                if len(name)>210:name=name[:210]
                if canonical not in urls or len(name)>len(urls[canonical]):urls[canonical]=name
            new=0
            for url,title in urls.items():
                if url not in found:
                    if not title:title=urlsplit(url).path.rsplit("/",1)[-1][:-5]
                    found[url]={"id":"v2ph-actor-"+urlsplit(url).path.rsplit("/",1)[-1][:-5],
                                "title":title,"source":url,"publisher":"DJAWA or other verified credited studio"}
                    new+=1
            pages.append({"url":u,"candidate_links":len(urls),"new_works":new})
            print("MIMMI_V2PH_ACTOR_PAGE",n,"links",len(urls),"new",new,"all",len(found),flush=True)
            if not urls or new==0 or len(found)>=max_album_candidates:break
            time.sleep(.4)
        except Exception as exc:
            pages.append({"url":u,"error":type(exc).__name__+": "+str(exc)[:160]})
            print("MIMMI_ACTOR_DISCOVERY_ERROR",type(exc).__name__,str(exc)[:150],flush=True)
            break
    return list(found.values())[:max_album_candidates],pages

def verify_album(album,max_samples=10):
    url=album["source"]
    outputs=[]
    pages=[]
    for page in range(1,4):
        loc=url if page==1 else url+"?page="+str(page)
        try:
            r=S.get(loc,timeout=T)
            r.raise_for_status()
            if not safe_source(r.url):break
            soup=BeautifulSoup(r.content,"html.parser")
            header=soup.find("h1")
            if not header:break
            title=header.get_text(" ",strip=True)
            # Do not collect from wrong model or arbitrary redirected pages.
            if not MIMMI.search(soup.get_text(" ",strip=True)[:2000]):break
            album["title"]=title[:210]
            urls=photos_on_page(soup,r.url)
            new=[x for x in urls if x not in {i["url"] for i in outputs}]
            pages.append({"page":page,"candidate_images":len(new)})
            for img in new:
                if len(outputs)>=max_samples:break
                evidence=get_bytes_verified(img)
                if evidence and evidence["sha256"] not in {p["sha256"] for p in outputs}:
                    evidence["number"]=len(outputs)+1
                    outputs.append(evidence)
            if len(outputs)>=max_samples or not new:break
            time.sleep(.2)
        except Exception as e:
            print("MIMMI_ACTOR_ALBUM_ERROR",album["id"],type(e).__name__,flush=True)
            break
    album.update(samples=outputs,images=[],pages=pages,status="public_previews_verified" if outputs else "source_only")
    return album

def run(max_pages=8,max_albums=70,max_samples=10):
    catalog,pages=scan_actor(max_pages,max_albums)
    known=set()
    try:
        target=json.loads((ROOT/"v2ph-targets.json").read_text())
        known={urlsplit(a["source"]).path for a in target["albums"] if safe_source(a["source"])}
    except Exception:pass
    new=[a for a in catalog if urlsplit(a["source"]).path not in known]
    results=[]
    for i,book in enumerate(new,1):
        result=verify_album(book,max_samples)
        results.append(result)
        print("MIMMI_ACTOR_ALBUM",i,len(new),result["id"],len(result["samples"]),flush=True)
    # Preserve earlier verified photographs when a source responds with 429,
    # a paywall, or a temporary network error. Never replace 10 old images by 0.
    previous_file=ROOT/"v2ph-actor-previews.json"
    if previous_file.exists():
        historical=json.loads(previous_file.read_text(encoding="utf-8"))
        by_id={a["id"]:a for a in results}
        for old in historical.get("albums",[]):
            if old["id"] not in by_id:
                by_id[old["id"]]=old
                results.append(old)
                continue
            fresh=by_id[old["id"]]
            have={p.get("sha256") for p in fresh.get("samples",[])}
            for item in old.get("samples",[]):
                if item.get("sha256") not in have:
                    fresh["samples"].append(item)
                    have.add(item.get("sha256"))
            for i,photo in enumerate(fresh["samples"],1):
                photo["number"]=i
            if fresh["samples"]:
                fresh["status"]="public_previews_verified"
    result={"version":"v0.1.0-mimmi.3","model":"mimmi","generated_at":datetime.now(timezone.utc).isoformat(),
            "source":ACTOR_URL,"actor_pages":pages,
            "summary":{"actor_albums_discovered":len(catalog),"previously_configured_albums":len(catalog)-len(new),
                       "new_album_candidates":len(results),
                       "verified_public_image_urls":sum(len(a["samples"]) for a in results),
                       "private_cloud_photos_archived":0},
            "albums":results}
    (ROOT/"v2ph-actor-previews.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("MIMMI_ACTOR_DISCOVERY_SUMMARY",json.dumps(result["summary"],ensure_ascii=False),flush=True)
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--pages",type=int,default=6)
    parser.add_argument("--albums",type=int,default=60)
    parser.add_argument("--images",type=int,default=10)
    args=parser.parse_args()
    if not 1<=args.pages<=12 or not 1<=args.albums<=90 or not 1<=args.images<=25:parser.error("bounded crawl only")
    run(args.pages,args.albums,args.images)
