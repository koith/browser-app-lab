#!/usr/bin/env python3
"""Cumulative, evidence-linked search names; unverified observations never become trusted names."""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

LEDGER=Path(__file__).with_name("source-names.json")
STOP={"photo","photos","photobook","public","preview","djawa","the","artgravia","cosplay","vol","sample","samples","mimmi","yui"}

def key(s):
    return " ".join(re.findall(r"[\w]+",unicodedata.normalize("NFKC",s).casefold()))

def safe_url(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and bool(p.hostname and "." in p.hostname) and not p.username and not p.password and p.port in (None,443)
    except (ValueError,TypeError):
        return False

def observe(db,model,album,name,url,proof,confirmed=False):
    if model not in db["model_names"] or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}",album):
        raise ValueError("invalid_work")
    if not isinstance(name,str) or not 3<=len(name.strip())<=220 or not safe_url(url):
        raise ValueError("invalid_spelling_or_source")
    item={"name":name.strip(),"source":url,"proof":proof}
    if not confirmed:
        pending=db.setdefault("pending_observations",[])
        if not any((x["model"],x["album_id"],key(x["name"]),x["source"])==
                   (model,album,key(name),url) for x in pending):
            pending.append({"model":model,"album_id":album,**item})
        return "pending"
    rows=db["works"].setdefault(model+":"+album,[])
    for existing in rows:
        if key(existing["name"])==key(name):
            if url!=existing["source"]:
                sources=existing.setdefault("other_sources",[])
                if url not in sources:sources.append(url)
            return "existing"
    rows.append(item)
    return "added"

def ingest_discovery(db,report):
    """Only uniquely matched SAME normalized work titles are promoted automatically."""
    out={"added":0,"existing":0,"pending":0,"skipped_ambiguous":0}
    for lead in report.get("leads",[]):
        model=lead.get("model")
        if model not in db["model_names"]:continue
        ids={x.get("id") for x in lead.get("exact_stored_title_matches",[])
             if isinstance(x,dict) and x.get("id")}
        if len(ids)!=1:
            out["skipped_ambiguous"]+=1
            continue
        album=next(iter(ids))
        for site in lead.get("sources",[]):
            source=site.get("url")
            if safe_url(source):
                status=observe(db,model,album,lead["title"],source,
                               "unique_exact_normalized_stored_work",True)
                out[status]+=1
    return out

def ingest_search_report(db, report):
    """Accumulate different observed source headings only for source pages
    whose model and exact work/edition were checked before observation."""
    out={"added":0,"existing":0,"pending":0}
    model=report.get("model")
    if model not in db["model_names"]:return out
    for entry in report.get("search_results",[]):
        album=entry.get("id")
        if model+":"+str(album) not in db["works"]:continue
        for observation in entry.get("observations",[]):
            if (observation.get("album_id")!=album or
                    observation.get("model")!=model or
                    observation.get("proof")!="unique_named_work_page_model_and_edition"):
                continue
            status=observe(db,model,album,observation.get("name",""),
                           observation.get("source",""),
                           observation["proof"],True)
            out[status]+=1
    # An accepted new host is also searched for the OTHER tracked model.
    for observation in report.get("cross_model_verified_site_pages",[]):
        target_model=observation.get("model")
        work=observation.get("work","")
        if target_model not in db["model_names"] or not work.startswith(target_model+":"):
            continue
        if work not in db["works"]:
            continue
        if observation.get("proof")!="unique_named_work_page_model_and_edition":
            continue
        album=work.split(":",1)[1]
        status=observe(db,target_model,album,observation.get("observed_name",""),
                       observation.get("source",""),observation["proof"],True)
        out[status]+=1
    return out


def forms(value):
    text=unicodedata.normalize("NFKC",value).strip()
    compact=re.sub(r"[\[\]()·:–—_/-]+"," ",text)
    compact=" ".join(compact.split())
    strong=[w for w in compact.split() if len(w)>2 and w.casefold() not in STOP]
    variants=[text,compact]
    if len(strong)>=2:variants.append(" ".join(strong))
    if len(strong)>=3:variants.append(" ".join(strong[-3:]))
    return list(dict.fromkeys(x for x in variants if len(key(x))>=5))

def queries(db,model,album,cap=72):
    works=db.get("works",{}).get(model+":"+album,[])
    models=db.get("model_names",{}).get(model,[])
    if not works or not models:return []
    candidates=[]
    for item in works:
        for title in forms(item["name"]):
            for name in models:
                # Work anchored: a generic 'Yui' must not become a standalone identity search.
                candidates.append('"'+name["name"]+'" "'+title+'"')
            candidates.append('"'+title+'" '+("DJAWA" if model=="mimmi" else "심유이"))
    return list(dict.fromkeys(candidates))[:cap]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ledger",type=Path,default=LEDGER)
    parser.add_argument("--discover",type=Path)
    parser.add_argument("--search-report",type=Path)
    parser.add_argument("--work",help="model:album-id")
    parser.add_argument("--out",type=Path)
    a=parser.parse_args()
    db=json.loads(a.ledger.read_text(encoding="utf-8"))
    if db["schema_version"]!=1:raise ValueError("invalid_ledger_schema")
    if a.discover:
        summary=ingest_discovery(db,json.loads(a.discover.read_text(encoding="utf-8")))
        if a.out:a.out.write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("SOURCE_ALIAS_ACCUMULATION",json.dumps(summary))
    if a.search_report:
        summary=ingest_search_report(db,json.loads(a.search_report.read_text(encoding="utf-8")))
        if a.out:a.out.write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("SEARCH_SITE_NAME_ACCUMULATION",json.dumps(summary))
    if a.work:
        model,album=a.work.split(":",1)
        output={"work":a.work,"queries":queries(db,model,album)}
        if a.out:a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(output,ensure_ascii=False))
    if not a.work and not a.discover and not a.search_report:
        print("SOURCE_NAME_LEDGER_READY",len(db["works"]))

if __name__=="__main__":main()
