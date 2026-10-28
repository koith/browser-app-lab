#!/usr/bin/env python3
"""High-recall Mimmi photo-book research across independent public catalogues.

This is SOURCE DISCOVERY, not an image acquisition count. It scrapes public
readable work inventories, tracks contradictions, duplicates and provenance.
No paid API, paywall, authentication, site bypass or compressed archives.
"""
from __future__ import annotations
import argparse
import json
import re
import time
import unicodedata
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
SOURCES=[
    ("xiantuji","https://www.xiantuji.com/mimmi/"),
    ("cosmiao","https://www.cosmiao.info/mimmi/"),
    ("miaohuaying","https://www.miaohuaying.com/mimmi/"),
    ("simimiao","https://www.simimiao.com/mimmi/"),
    ("miaojishe","https://www.miaojishe.com/mimmi/"),
]
HEAD={"User-Agent":"Mozilla/5.0 (compatible; PublicMimmiWorkCatalogue/1.0)",
      "Accept":"text/html,application/xhtml+xml"}
WORK_RE=re.compile(r"(?:Mimmi\s+)?NO\.\s*0*(\d{1,3})\s*[\-–.:：]?\s*(.+)",re.I)
COUNT_RE=re.compile(r"[\[【〖\(（]\s*(\d{1,4})\s*P",re.I)

def canonical(text):
    text=unicodedata.normalize("NFKC",text).lower()
    text=re.sub(r"\[[^\]]*\]"," ",text)
    text=re.sub(r"(?i)\b(djawa photo|cream soda|creamsoda|mimmi|밈미|vol\.?|photo|set)\b"," ",text)
    text=re.sub(r"[^\w]+"," ",text).strip()
    return text[:150]

def extract_entries(raw):
    soup=BeautifulSoup(raw,"html.parser")
    for tag in soup(["script","style","nav","footer","header"]):tag.decompose()
    text=soup.get_text("\n",strip=True)
    found={}
    for line in text.splitlines():
        line=re.sub(r"\s+"," ",line.strip())
        m=WORK_RE.search(line)
        if not m:continue
        num=int(m.group(1))
        if not 1<=num<=250:continue
        title=m.group(2).strip(" -:·")
        if not title or len(title)>230:continue
        count_match=COUNT_RE.search(title)
        count=int(count_match.group(1)) if count_match else None
        title=re.sub(r"[\[【〖]\s*\d{1,4}\s*P[^\]】〗]*[\]】〗]","",title,flags=re.I).strip()
        title=re.sub(r"\s+"," ",title)
        if title.lower().startswith("djawa") and len(title)<6:continue
        candidate={"number":num,"title":title,"advertised_photos":count}
        previous=found.get(num)
        if previous is None or (len(title)>len(previous["title"]) and len(title)<180):
            found[num]=candidate
    return list(found.values())

def scan(timeout=22):
    records={}
    statuses=[]
    for name,url in SOURCES:
        host=urlsplit(url).hostname
        try:
            resp=requests.get(url,headers=HEAD,timeout=(10,timeout))
            resp.raise_for_status()
            if urlsplit(resp.url).hostname!=host:
                raise ValueError("Cross-domain redirect refused")
            items=extract_entries(resp.text)
            statuses.append({"source":name,"url":url,"records":len(items),"status":"ok"})
            for entry in items:
                row=records.setdefault(entry["number"],{"number":entry["number"],
                    "title":entry["title"],"advertised_photos":entry["advertised_photos"],
                    "sources":[],"alternate_titles":[],"count_disagreement":False,
                    "samples":[],"images":[],"status":"research_only_not_archived"})
                row["sources"].append({"site":name,"url":url,"claimed_count":entry["advertised_photos"]})
                if entry["title"] not in row["alternate_titles"]:
                    row["alternate_titles"].append(entry["title"])
                if not row["advertised_photos"] and entry["advertised_photos"]:
                    row["advertised_photos"]=entry["advertised_photos"]
                elif row["advertised_photos"] and entry["advertised_photos"] and row["advertised_photos"]!=entry["advertised_photos"]:
                    row["count_disagreement"]=True
            print("MIMMI_RESEARCH_SOURCE",name,len(items),flush=True)
        except Exception as error:
            statuses.append({"source":name,"url":url,"status":"unavailable","error":type(error).__name__+": "+str(error)[:170],"records":0})
            print("MIMMI_RESEARCH_SOURCE_FAILURE",name,type(error).__name__,flush=True)
        time.sleep(.4)
    entries=sorted(records.values(),key=lambda x:x["number"],reverse=True)
    return {"model":"mimmi","generated_at":datetime.now(timezone.utc).isoformat(),
            "warning":"Research source listing != individually acquired and verified images. Catalogues can include duplicates, inconsistent counts, mixed-model collaboration.",
            "sources":statuses,
            "summary":{"sources_checked":len(statuses),
                       "sources_with_items":sum(s["records"]>0 for s in statuses),
                       "numbered_rows":len(entries),
                       "photo_files_archived":0,
                       "rows_with_disagreements":sum(x["count_disagreement"] for x in entries)},
            "works":entries}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=ROOT/"research-catalogue.json")
    args=ap.parse_args()
    result=scan()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_RESEARCH_INVENTORY",json.dumps(result["summary"],ensure_ascii=False))
