#!/usr/bin/env python3
"""Diagnose changed public image bytes before choosing a recovery strategy.

Only confirmed existing source-index URLs are read. Never guess private URLs,
bypass blocked endpoints, count probes as saved photos or publish photo bytes.
"""
import argparse
import collections
import hashlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mimmi-gallery"))
from collect_private_batch import allowed_url
from missing_candidates import saved_positions, safe_id

MAX_BYTES = 24_000_000


def missing_rows(base: Path):
    source = json.loads((base/"source-viewer-albums.json").read_text(encoding="utf-8"))
    public = json.loads((base/"stored-albums.json").read_text(encoding="utf-8"))
    owner = json.loads((base/"owner-index.json").read_text(encoding="utf-8"))
    covered = {(a, n) for a,n,*_ in saved_positions(public)}
    for album in owner.get("albums", []):
        for image in album.get("images", []):
            covered.add((album["id"], image["number"]))
    rows=[]
    for album in source["albums"]:
        aid=safe_id(album["id"])
        for image in album.get("images", []):
            n=image.get("number")
            if type(n) is int and (aid,n) not in covered and allowed_url(image.get("url",""))[0]:
                rows.append({"id":aid,"number":n,"source":album.get("source"),"photo":image})
    return rows


def inspect(row):
    photo=row["photo"]
    url=photo["url"]
    domain=urlsplit(url).hostname
    record={"id":row["id"],"number":row["number"],"host":domain,
            "expected_bytes":photo.get("bytes"),"expected_dimensions":[photo.get("width"),photo.get("height")]}
    if not allowed_url(url)[0]:
        record["outcome"]="disallowed_source"
        return record
    session=requests.Session()
    session.headers.update({"User-Agent":"Mozilla/5.0 (compatible; PersonalImageArchive/1.0)",
                           "Accept":"image/avif,image/webp,image/png,image/jpeg,image/*"})
    if str(row.get("source") or "").startswith("https://"):
        session.headers["Referer"]=row["source"]
    try:
        with session.get(url,timeout=(8,20),stream=True,allow_redirects=False) as resp:
            record["status"]=resp.status_code
            record["content_type"]=resp.headers.get("content-type","").split(";")[0].lower()[:70]
            if resp.status_code!=200:
                record["outcome"]="http_error"
                return record
            raw=bytearray()
            for b in resp.iter_content(65536):
                raw.extend(b)
                if len(raw)>MAX_BYTES:
                    record["outcome"]="too_large"
                    return record
        record["observed_bytes"]=len(raw)
        record["observed_sha256"]=hashlib.sha256(raw).hexdigest()
        if record["observed_sha256"]==photo.get("sha256") and len(raw)==photo.get("bytes"):
            record["outcome"]="matches_old_source"
            return record
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                record["format"]=im.format
                record["dimensions"]=[im.width,im.height]
                record["outcome"]="changed_image"
        except (OSError,ValueError):
            record["outcome"]="non_image_response"
        return record
    except requests.RequestException as exc:
        record["outcome"]="network_error"
        record["error_type"]=type(exc).__name__
        return record


def run(limit=50,workers=3):
    base=ROOT/"mimmi-gallery"
    missing=missing_rows(base)
    chosen=missing[:limit]
    checked=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(inspect,r) for r in chosen]):
            checked.append(future.result())
    checked.sort(key=lambda r:(r["id"],r["number"]))
    hashes=collections.Counter(r["observed_sha256"] for r in checked if "observed_sha256" in r)
    outcomes=collections.Counter(r["outcome"] for r in checked)
    hosts=collections.Counter(r["host"] for r in checked)
    image_reencodes=sum(
        r["outcome"]=="changed_image" and
        r.get("dimensions")==r["expected_dimensions"] for r in checked
    )
    report={"source_missing_total":len(missing),"checked":len(checked),"outcomes":dict(outcomes),
        "hosts":dict(hosts),"identical_dimensions_changed_byte_responses":image_reencodes,
        "repeated_response_hashes":[{"sha_prefix":k[:10],"occurrences":v}
                                    for k,v in hashes.most_common(5) if v>1],
        "unique_observed_image_hashes":len(hashes),
        "examples":[{"id":r["id"],"number":r["number"],"host":r["host"],
                     "outcome":r["outcome"],"status":r.get("status"),
                     "format":r.get("format"),"expected_dimensions":r["expected_dimensions"],
                     "dimensions":r.get("dimensions"),
                     "expected_bytes":r["expected_bytes"],
                     "observed_bytes":r.get("observed_bytes"),
                     "sha_prefix":r.get("observed_sha256","")[:10]} for r in checked]
    }
    print("MIMMI_SOURCE_BYTE_REPROBE",json.dumps(report,ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=50)
    parser.add_argument("--workers",type=int,default=3)
    args=parser.parse_args()
    if not (1<=args.limit<=100 and 1<=args.workers<=4):
        parser.error("bounded public source diagnostics")
    run(args.limit,args.workers)
