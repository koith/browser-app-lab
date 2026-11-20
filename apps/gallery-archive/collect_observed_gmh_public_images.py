#!/usr/bin/env python3
"""Import only exact public image URLs observed in user-requested G-MH pages.

Do not crawl G-MH origin: its robots.txt disallows automated page reads. The
reviewed static evidence records exactly observed image URLs; this importer
downloads only those CDN paths if that separate CDN permits the request.
Never generate missing filenames, bypass anti-bot/login, count thumbnails as
publisher masters, or consider staged hashes a published gallery result.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from collector_v2 import PublicHTTP, DownloadFailure, inspect_photo, public_https
from photo_visual_dedupe import WorkVisualIndex
from perceptual_duplicate_audit import scan_image, candidate_relation

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/"apps/gallery-archive/verification/observed-gmh-public-media.json"
MODEL_WORDS={"mimmi":("mimmi","밈미"),"yui":("yui","유이")}
IMAGE_RE=re.compile(r"^/([a-z0-9-]{8,120})/g-mhcom_([0-9]{3,4})\.webp$", re.I)
WORK_RE=re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")

def normalize(value):
    return re.sub(r"[^a-z0-9가-힣]", "", str(value).casefold())

def verified_item(entry, model, registry):
    if not isinstance(entry,dict) or entry.get("model")!=model:
        return False,"model"
    aid=entry.get("work_id")
    if not isinstance(aid,str) or not WORK_RE.fullmatch(aid) or aid not in registry:
        return False,"work_not_registered"
    heading=entry.get("observed_heading","")
    edition=entry.get("edition_identity","")
    if not isinstance(heading,str) or not isinstance(edition,str) or len(edition)<5:
        return False,"missing_title_evidence"
    if normalize(edition) not in normalize(heading):
        return False,"wrong_edition"
    if not any(normalize(m) in normalize(heading) for m in MODEL_WORDS[model]):
        return False,"wrong_model"
    source=entry.get("source_page")
    if not public_https(source):
        return False,"invalid_source"
    parsed=urlsplit(source)
    match=re.fullmatch(r"/gallery/([a-z0-9-]{8,120})/?",parsed.path,re.I)
    if parsed.hostname!="g-mh.com" or not match or parsed.query or parsed.fragment:
        return False,"unreviewed_source_path"
    images=entry.get("media_urls")
    if not isinstance(images,list) or not 1<=len(images)<=100:
        return False,"invalid_media_count"
    slug=match.group(1)
    seen=set()
    for image in images:
        if not isinstance(image,str) or not public_https(image):
            return False,"non_public_media"
        parsed=urlsplit(image)
        filematch=IMAGE_RE.fullmatch(parsed.path)
        if (parsed.hostname!="img.g-mh.com" or parsed.query
                or parsed.fragment or not filematch
                or filematch.group(1)!=slug or image in seen):
            return False,"cdn_media_not_observed_for_exact_work"
        seen.add(image)
    return True,"exact_observed_album_and_cdn"

def collect(model, stage, root=ROOT, evidence=EVIDENCE, http=None,
            max_photos=80, max_per_work=12, bytes_budget=45_000_000,
            deadline_seconds=800):
    if model not in MODEL_WORDS or not 1<=max_photos<=150 or not 1<=max_per_work<=50:
        raise ValueError("bounded mode only")
    if not 10000<=bytes_budget<=100_000_000 or not 5<=deadline_seconds<=2400:
        raise ValueError("bounded budget/deadline")
    stage=Path(stage);root=Path(root)
    base=root/"apps"/(model+"-gallery")
    evidence_doc=json.loads(Path(evidence).read_text(encoding="utf-8"))
    if evidence_doc.get("schema_version")!=1 or evidence_doc.get("cdn_domain")!="img.g-mh.com":
        raise ValueError("invalid evidence provenance")
    registry={x["id"]:x for x in json.loads(
        (base/"public-work-pages.json").read_text(encoding="utf-8"))["albums"]}
    owner=json.loads((base/"owner-index.json").read_text(encoding="utf-8"))
    saved=json.loads((base/"stored-albums.json").read_text(encoding="utf-8"))
    by_saved={x["id"]:x for x in saved["albums"]}
    known_sha={p["sha256"] for a in owner["albums"]+saved["albums"] for p in a["images"]
               if isinstance(p.get("sha256"),str)}
    saved_urls={p["source_url"] for a in saved["albums"] for p in a["images"]
                if isinstance(p.get("source_url"),str)}
    already=Counter();untrusted=[];works=[]
    for entry in evidence_doc.get("works",[]):
        if entry.get("model")!=model:continue
        valid,reason=verified_item(entry,model,registry)
        if not valid:
            untrusted.append({"id":entry.get("work_id"),"error":reason})
            continue
        works.append(entry)
    if untrusted:raise ValueError("REJECTED_REVIEWED_MEDIA_IDENTITY "+json.dumps(untrusted))
    # Explicit path + edition evidence is the only source authority.
    work_ids=list(dict.fromkeys(x["work_id"] for x in works))
    result={"model":model,"reviewed_work_ids":work_ids,"observed_media_urls":sum(
        len(e["media_urls"]) for e in works),"real_downloaded_files_staged":0,
        "actual_pages_publication_pending":True,"errors":{},"work_counts":{},
        "reused_source_urls":0,"same_frame_filtered":0,"existing_sha_filtered":0,
        "no_guessed_media_urls":True,"source_origin_crawled":False}
    if not works:raise ValueError("no verified exact work sources")
    client=http or PublicHTTP()
    album_photos=defaultdict(list)
    stage_scans=defaultdict(list)
    visuals={id:WorkVisualIndex(base,by_saved.get(id,{"id":id,"images":[]})) for id in work_ids}
    total_bytes=0
    cutoff=time.monotonic()+deadline_seconds
    session_sha=set()
    error_counts=Counter()
    for entry in works:
        aid=entry["work_id"]
        if len(album_photos[aid])>=max_per_work:continue
        for url in entry["media_urls"]:
            if (len(session_sha)>=max_photos or time.monotonic()>=cutoff
                    or len(album_photos[aid])>=max_per_work
                    or total_bytes>=bytes_budget):
                break
            if url in saved_urls:
                result["reused_source_urls"]+=1
                continue
            try:
                raw=client.fetch(url,kind="image",max_bytes=min(25_000_000,bytes_budget))
                meta=inspect_photo(raw)
            except DownloadFailure as exc:
                error_counts[exc.code]+=1
                continue
            if total_bytes+len(raw)>bytes_budget:
                error_counts["campaign_size_budget"]+=1
                continue
            digest=meta["sha256"]
            if digest in known_sha or digest in session_sha:
                result["existing_sha_filtered"]+=1
                continue
            match=visuals[aid].classify(raw)
            if match and not match["needs_replacement_transaction"]:
                result["same_frame_filtered"]+=1
                continue
            try:
                scanned=scan_image(raw)
                candidates=stage_scans[aid]
                duplicate=any((lambda rel,dist,diff:
                    rel=="perceptually_similar_review" and dist is not None and
                    dist<=3 and diff is not None and diff<=2.0
                    )(*candidate_relation(scanned,previous)) for previous in candidates)
                if duplicate:
                    result["same_frame_filtered"]+=1
                    continue
            except (ValueError,OSError):
                scanned=None
            rel="originals/"+aid+"/"+digest[:20]+"."+meta["ext"]
            dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and dest.read_bytes()!=raw:
                raise ValueError("immutable_stage_sha_mismatch")
            if not dest.exists():
                tmp=dest.with_suffix(".partial")
                tmp.write_bytes(raw)
                os.replace(tmp,dest)
            source_no=int(IMAGE_RE.fullmatch(urlsplit(url).path).group(2))
            album_photos[aid].append({"key":rel,"sha256":digest,
                "bytes":len(raw),"width":meta["width"],"height":meta["height"],
                "number":len(album_photos[aid])+1,
                "source_photo_number":source_no,
                "source_url":url,"watermark_status":"unknown",
                "numbering_provenance":"published_source_order"})
            session_sha.add(digest);total_bytes+=len(raw)
            if scanned is not None:stage_scans[aid].append(scanned)
        if len(session_sha)>=max_photos or time.monotonic()>=cutoff:break
    albums=[{"id":id,"title":registry[id]["title"],"images":album_photos[id]}
            for id in work_ids if album_photos[id]]
    report_counts={id:len(album_photos[id]) for id in work_ids}
    result["work_counts"]=report_counts
    result["real_downloaded_files_staged"]=len(session_sha)
    result["bytes_staged"]=total_bytes
    result["errors"]=dict(error_counts)
    metadata=stage/"metadata";metadata.mkdir(parents=True,exist_ok=True)
    (metadata/"catalog.json").write_text(json.dumps(
        {"model":model,"albums":albums},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (metadata/"observed-media-report.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OBSERVED_CDN_PHYSICAL_FILES_STAGED",json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True,choices=list(MODEL_WORDS))
    parser.add_argument("--stage",type=Path,required=True)
    parser.add_argument("--evidence",type=Path,default=EVIDENCE)
    parser.add_argument("--max-photos",type=int,default=80)
    parser.add_argument("--max-per-work",type=int,default=12)
    parser.add_argument("--budget",type=int,default=45_000_000)
    args=parser.parse_args()
    collect(args.model,args.stage,evidence=args.evidence,max_photos=args.max_photos,
            max_per_work=args.max_per_work,bytes_budget=args.budget)
