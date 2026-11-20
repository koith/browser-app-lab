#!/usr/bin/env python3
"""Reconcile already held archive files into the existing private owner store.

No network search, no new public photo commits, no paid source fetches.
The input is an exact previously stored revision. Only verified original
bytes and generated previews go to the existing authenticated private account.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from direct_photo_pipeline import inspect, atomic_bytes
from merge_incremental import checked_row

ROOT=Path(__file__).resolve().parents[2]
PREVIOUS="1da6ff3d78b6f316374d63d9a664d1013dd3096a"
HELD="5c8e09257044ab33d5b588f84ee5dbef09636622"
ALBUM="djawa-asuna-the-maid"
BASE="apps/mimmi-gallery/"
MANIFEST=BASE+"stored-albums.json"

def read_revision(ref,path):
    return subprocess.run(["git","show",ref+":"+path],cwd=ROOT,
                          capture_output=True,check=True,timeout=30).stdout

def held_rows():
    prior=json.loads(read_revision(PREVIOUS,MANIFEST))
    held=json.loads(read_revision(HELD,MANIFEST))
    old={p["sha256"] for a in prior["albums"] for p in a["images"]}
    album=next(a for a in held["albums"] if a["id"]==ALBUM)
    rows=[p for p in album["images"] if p["sha256"] not in old]
    if len(rows)!=49 or len({p["sha256"] for p in rows})!=49:
        raise ValueError("Unexpected held-file delta")
    return rows

def prepare(owner,stage,rows=None,reader=None):
    if owner.get("model")!="mimmi" or owner.get("schema_version")!=1:
        raise ValueError("Not the current Mimmi owner catalogue")
    album=next(a for a in owner["albums"] if a["id"]==ALBUM)
    seen={p["sha256"] for a in owner["albums"] for p in a["images"]}
    number=max((p["number"] for p in album["images"]),default=0)+1
    rows=held_rows() if rows is None else rows
    reader=reader or (lambda p:read_revision(HELD,BASE+p["url"]))
    prepared=[]; skipped=0
    for p in rows:
        if not re.fullmatch(r"stored-albums/"+ALBUM+r"/[a-f0-9]{20}\.(jpg|jpeg|png|webp)",p["url"]):
            raise ValueError("Unexpected existing held-file path")
        if p["sha256"] in seen:
            skipped+=1;continue
        raw=reader(p)
        actual,preview,fmt=inspect(raw)
        if any(actual[k]!=p[k] for k in ("sha256","bytes","width","height")):
            raise ValueError("Held original bytes do not match recorded identity")
        ext=actual.pop("extension")
        # Content addresses prevent collisions with existing remote files.
        name=f"{number:05d}-{actual['sha256'][:16]}"
        key=f"originals/{ALBUM}/{name}.{ext}"
        thumb=f"previews/{ALBUM}/{name}.webp"
        row={**actual,"number":number,"key":key,"preview":thumb,
             "preview_sha256":hashlib.sha256(preview).hexdigest(),
             "preview_bytes":len(preview),
             "numbering_provenance":"archive_append_order_not_publisher_number"}
        checked_row("mimmi",ALBUM,row)
        atomic_bytes(stage/key,raw);atomic_bytes(stage/thumb,preview)
        prepared.append(row);seen.add(row["sha256"]);number+=1
    out={"schema_version":1,"model":"mimmi",
         "storage":"owner-private-terabox-sha-verified-bytes",
         "albums":[{"id":ALBUM,"title":album["title"],"images":prepared}]}
    meta=stage/"metadata";meta.mkdir(parents=True,exist_ok=True)
    (meta/"catalog.json").write_text(json.dumps(out,ensure_ascii=False)+"\n")
    print("HELD_PRIVATE_STAGE",len(rows),"already_owner_sha",skipped,
          "new_staged",len(prepared),flush=True)
    return len(prepared)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--owner",type=Path,required=True)
    p.add_argument("--stage",type=Path,required=True)
    a=p.parse_args()
    prepare(json.loads(a.owner.read_text()),a.stage)
