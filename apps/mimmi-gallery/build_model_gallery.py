#!/usr/bin/env python3
"""Translate all VERIFIED, publicly viewable Mimmi photo URLs into the latest
Yui beta.18 album-viewer schema. This is NOT a paid-photobook downloader.

Merge identical independently identified works, but NEVER mix AI and non-AI
editions. Every image is SHA-256-backed evidence from a real HTTP fetch.
Images remain unchanged at their source, not redistributed by Pages.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
FILES=[
  ("official","official-previews.json"),
  ("v2ph_seed","v2ph-public-previews.json"),
  ("v2ph_actor","v2ph-actor-previews.json"),
]
ALLOWED={"djawaphoto.com","www.djawaphoto.com","cdn.v2ph.com"}
MODEL_VERSION="v0.1.0-mimmi.4"

def canonical_title(title):
    s=unicodedata.normalize("NFKC",str(title)).casefold()
    s=re.sub(r"[-–]\s*page\s*\d+\s*$","",s)
    s=re.sub(r"\b(?:public|web|sample|photo|photobook|djawa|mimmi)\b"," ",s)
    s=re.sub(r"밈미|밈미|미미|공개 웹판|공개분"," ",s)
    s=re.sub(r"\b(?:cosplay|collection|set)\b"," ",s)
    # Explicit AI edition must never be mixed with the photographic edition.
    ai=bool(re.search(r"ai\s*enhanced|ai\s*보정",s))
    s=re.sub(r"ai\s*enhanced|ai\s*보정"," ",s)
    s=re.sub(r"[^a-z0-9가-힣]+"," ",s).strip()
    return ("ai" if ai else "web",s)

def nice_title(title):
    s=re.sub(r"\s*[-–]\s*Page\s*\d+\s*$","",title,flags=re.I)
    s=re.sub(r"^\s*\[DJAWA\]\s*","",s,flags=re.I)
    s=re.sub(r"^(?:DJAWA\s+Photo\s*[-–:]\s*)+","",s,flags=re.I)
    s=re.sub(r"^\s*Mimmi\s*\((?:밈미|밈미|미미)\)\s*[-–:]*\s*","",s,flags=re.I)
    return s.strip() or title

def publisher(album,kind):
    t=(album.get("title","")+" "+album.get("publisher","")).casefold()
    if "creamsoda" in t or "cream soda" in t:return "CreamSoda"
    if "artgravia" in t:return "ArtGravia"
    return "DJAWA" if kind=="official" or "djawa" in t else "독립 화보"

def url_allowed(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and p.hostname in ALLOWED and not p.username and not p.password
    except (ValueError,TypeError):return False

def build(root=ROOT):
    groups={}
    seen_hashes=set()
    collisions=Counter()
    input_count=0
    for kind,filename in FILES:
        source=json.loads((root/filename).read_text(encoding="utf-8"))
        for record in source["albums"]:
            samples=record.get("samples",[])
            if not samples:continue
            title=nice_title(record["title"])
            key=canonical_title(title)
            if not key[1]:key=(key[0],record["id"])
            if key not in groups:
                groups[key]={
                    "id":record["id"],"title":title,"publisher":publisher(record,kind),
                    "source":record["source"],"source_pages":[],
                    "images":[],"sourceHosted":True,
                    "status":"verified_collected_individual_files_source_hosted_online_view",
                    "quality":"public_web","publisher_original_verified":False,
                    "model":"mimmi","expected":None,"photos":None,
                    "ai_enhanced":key[0]=="ai","original_sources":[],
                    "completeness":"partial_public_previews",
                }
            g=groups[key]
            g["source_pages"].append(record["source"])
            g["original_sources"].append({"source_type":kind,"id":record["id"],
                                          "source":record["source"],"verified_image_count":len(samples),
                                          "claimed_image_count":record.get("advertised_photos")})
            expected=record.get("advertised_photos")
            if isinstance(expected,int) and expected>0 and (g["expected"] is None or kind=="official"):
                g["expected"]=expected
                g["photos"]=expected
            for p in samples:
                input_count+=1
                digest=p.get("sha256","")
                if not re.fullmatch(r"[0-9a-f]{64}",digest) or not url_allowed(p.get("url")):
                    collisions["invalid"]+=1;continue
                if digest in seen_hashes:
                    collisions["sha256_duplicate"]+=1;continue
                if not isinstance(p.get("bytes"),int) or p["bytes"]<4500 or min(p.get("width",0),p.get("height",0))<250:
                    collisions["invalid_image_evidence"]+=1;continue
                seen_hashes.add(digest)
                g["images"].append({
                    "number":len(g["images"])+1,"url":p["url"],"source_url":p["url"],
                    "sha256":digest,"width":p["width"],"height":p["height"],
                    "bytes":p["bytes"],"quality":"official_public_sample" if kind=="official" else "third_party_public_web",
                    "publisher_original_verified":False,
                })
    albums=[]
    for group in groups.values():
        if not group["images"]:continue
        if group["expected"] is not None and group["expected"]<len(group["images"]):
            group["expected"]=None
            group["photos"]=None
        if group["expected"]==len(group["images"]):
            group["completeness"]="advertised_public_sequence_verified"
        # DO NOT certify complete publisher-original albums from page count alone.
        group["source_pages"]=list(dict.fromkeys(group["source_pages"]))
        albums.append(group)
    albums.sort(key=lambda r:r["title"].casefold())
    count=sum(len(a["images"]) for a in albums)
    if count!=len(seen_hashes):
        raise ValueError("Duplicate evidence registered in more than one album")
    return {
        "schema_version":1,"model":"mimmi","version":MODEL_VERSION,
        "source_link_only":True,"private_cloud_archived_image_files":0,
        "fully_acquired_paid_photobooks":0,
        "disclaimer":"Every image is verified public source evidence, not a purchased full photobook. Public sites may block remote image hotlinks.",
        "summary":{"displayed_albums":len(albums),"verified_unique_source_images":count,
                   "input_source_image_occurrences":input_count,
                   "duplicate_hashes_skipped":collisions["sha256_duplicate"],
                   "actual_full_publisher_photobooks":0,
                   "incomplete_known_count_albums":sum(a["expected"] is not None and len(a["images"])<a["expected"] for a in albums)},
        "albums":albums,
    }

def save(root=ROOT):
    data=build(root)
    (root/"source-viewer-albums.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Product-list metadata is separate from the photos. No duplicate empty cards.
    meta=[{k:a.get(k) for k in ("id","title","publisher","source","expected","photos","ai_enhanced")} for a in data["albums"]]
    base={"model":{"id":"mimmi","name":"밈미"},"version":MODEL_VERSION,
          "albums":meta,"summary":data["summary"],
          "notes":"Individual accessible public samples are NOT complete commercial editions."}
    (root/"albums.json").write_text(json.dumps(base,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_LATEST_GALLERY_DATA",json.dumps(data["summary"],ensure_ascii=False),flush=True)
    return data

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);args=p.parse_args()
    save(args.root)
