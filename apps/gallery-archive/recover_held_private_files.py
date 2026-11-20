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

def locate_known_drive_copy(remote):
    """Find the single known SHA only within the same owner's existing archive.

    This never accesses the original source site or uploads via a public repo.
    If the old Drive import was never transferred, retain the Drive copy.
    """
    aid="djawa-nikke-elegg"
    sha="6ea4ca4c1f49447f0a5d2f1e1982bf792de42eaae9ca2a13acaf1c65d9a96137"
    size=206433
    if remote!="archive:MimmiArchive":raise ValueError("Wrong owner remote")
    prefix=remote+"/originals/"+aid
    try:
        listed=subprocess.run(["rclone","lsjson",prefix,"--files-only","--max-depth","1","--timeout","45s","--retries","1"],
            capture_output=True,check=True,timeout=65)
        items=json.loads(listed.stdout)
        candidates=[x["Name"] for x in items if x.get("Size")==size and
                    re.fullmatch(r"[a-zA-Z0-9._-]+\.(jpg|jpeg|png|webp)",x.get("Name",""),re.I)]
        if len(candidates)>20:raise ValueError("Too many ambiguous exact-size owner files")
        for name in candidates:
            value=subprocess.run(["rclone","cat",prefix+"/"+name,"--timeout","45s","--retries","1"],
                capture_output=True,check=False,timeout=65)
            raw=value.stdout
            if value.returncode==0 and len(raw)==size and hashlib.sha256(raw).hexdigest()==sha:
                return {"sha256":sha,"bytes":size,"width":1005,"height":1005},raw
    except (subprocess.SubprocessError,ValueError):
        print("DRIVE_COPY_EXISTING_OWNER_LOOKUP_UNAVAILABLE",flush=True)
    return None

def prepare(owner,stage,rows=None,reader=None,remote=None):
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
    albums=[{"id":ALBUM,"title":album["title"],"images":prepared}]
    if remote:
        extra_sha="6ea4ca4c1f49447f0a5d2f1e1982bf792de42eaae9ca2a13acaf1c65d9a96137"
        if extra_sha in seen:
            print("DRIVE_COPY_ALREADY_IN_OWNER_INDEX",flush=True)
        else:
            found=locate_known_drive_copy(remote)
            if found is None:
                print("DRIVE_COPY_PRIVATE_TRANSFER_STILL_REQUIRED",flush=True)
            else:
                p,raw=found
                actual,preview,_=inspect(raw)
                if any(actual[k]!=p[k] for k in ("sha256","bytes","width","height")):
                    raise ValueError("Exact Drive copy metadata mismatch")
                aid="djawa-nikke-elegg"
                work=next(a for a in owner["albums"] if a["id"]==aid)
                num=max((p["number"] for p in work["images"]),default=0)+1
                ext=actual.pop("extension")
                name=f"{num:05d}-{actual['sha256'][:16]}"
                key=f"originals/{aid}/{name}.{ext}"; thumb=f"previews/{aid}/{name}.webp"
                row={**actual,"number":num,"key":key,"preview":thumb,
                     "preview_sha256":hashlib.sha256(preview).hexdigest(),"preview_bytes":len(preview),
                     "numbering_provenance":"archive_append_order_not_publisher_number"}
                checked_row("mimmi",aid,row)
                atomic_bytes(stage/key,raw);atomic_bytes(stage/thumb,preview)
                albums.append({"id":aid,"title":work["title"],"images":[row]})
                print("DRIVE_COPY_EXACT_OWNER_BYTES_RECOVERED",1,flush=True)
    out={"schema_version":1,"model":"mimmi",
         "storage":"owner-private-terabox-sha-verified-bytes",
         "albums":albums}
    meta=stage/"metadata";meta.mkdir(parents=True,exist_ok=True)
    (meta/"catalog.json").write_text(json.dumps(out,ensure_ascii=False)+"\n")
    print("HELD_PRIVATE_STAGE",len(rows),"already_owner_sha",skipped,
          "new_staged",len(prepared),flush=True)
    return len(prepared)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--owner",type=Path,required=True)
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--remote")
    a=p.parse_args()
    prepare(json.loads(a.owner.read_text()),a.stage,remote=a.remote)
