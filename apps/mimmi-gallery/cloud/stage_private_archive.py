#!/usr/bin/env python3
"""Build a private Mimmi catalogue from truly downloaded individual source bytes.

Incremental: preserve previously verified remote album rows when a source is
temporarily offline. Never claim remote completeness until upload+readback passes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

SAFE_ID=re.compile(r"^[a-z0-9][a-z0-9-]{1,100}$")
SAFE_NAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,180}$")
HEX=re.compile(r"^[a-f0-9]{64}$")
EXT={".jpg",".jpeg",".png",".webp",".avif"}

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def valid_previous_image(album_id,p):
    key=p.get("key","")
    return (isinstance(key,str) and key.startswith(f"originals/{album_id}/")
            and len(key.split("/"))==3 and SAFE_NAME.fullmatch(key.split("/")[-1])
            and type(p.get("number")) is int and p["number"]>0
            and type(p.get("bytes")) is int and 4500<=p["bytes"]<=30_000_000
            and isinstance(p.get("sha256"),str) and HEX.fullmatch(p["sha256"]))

def build(source, private, out, old=None):
    source=Path(source);private=Path(private);out=Path(out)
    data=json.loads(source.read_text(encoding="utf-8"))
    downloaded=json.loads((private/"private-archive-index.json").read_text(encoding="utf-8"))
    if data.get("model")!="mimmi" or downloaded.get("model")!="mimmi":
        raise ValueError("Mixed model archive rejected")
    indexes={a["id"]:a for a in data["albums"]}
    by_hash={(a["id"],p["sha256"]):p for a in data["albums"] for p in a["images"]}
    albums={}
    if old and Path(old).is_file() and Path(old).stat().st_size:
        historical=json.loads(Path(old).read_text(encoding="utf-8"))
        if historical.get("model")!="mimmi" or historical.get("schema_version")!=1:
            raise ValueError("Refusing to overwrite an unrelated existing private archive")
        for a in historical.get("albums",[]):
            aid=a.get("id")
            if not isinstance(aid,str) or not SAFE_ID.fullmatch(aid):
                raise ValueError("Unsafe existing album ID")
            good=a.get("images",[])
            if not all(valid_previous_image(aid,p) for p in good):
                raise ValueError("Unsafe previous archived image path")
            nums=[p["number"] for p in good]
            if len(nums)!=len(set(nums)):
                raise ValueError("Existing archive has conflicting image numbers")
            albums[aid]=dict(a,images=list(good))
    new_files=[]
    for item in downloaded.get("files",[]):
        aid=item.get("album_id")
        h=item.get("sha256")
        if not isinstance(aid,str) or not SAFE_ID.fullmatch(aid):
            raise ValueError("Invalid album ID in private archive index")
        if not isinstance(h,str) or not HEX.fullmatch(h):
            raise ValueError("Unverified digest")
        evidence=by_hash.get((aid,h))
        if not evidence or aid not in indexes or item.get("bytes")!=evidence.get("bytes"):
            raise ValueError("Photo not present in trusted source verification manifest")
        rel=item.get("path","")
        parts=Path(rel).parts
        if len(parts)!=3 or parts[0]!="albums" or parts[1]!=aid or not SAFE_NAME.fullmatch(parts[2]):
            raise ValueError("Unsafe local file path")
        path=private.joinpath(*parts)
        if not path.is_file() or path.stat().st_size!=evidence["bytes"] or sha256(path)!=h:
            raise ValueError("Local original file integrity mismatch")
        album=albums.setdefault(aid,{
            "id":aid,"title":indexes[aid]["title"],"publisher":indexes[aid].get("publisher"),
            "source":indexes[aid].get("source"),"quality":"public_web",
            "ai_enhanced":bool(indexes[aid].get("ai_enhanced")),"images":[]})
        if any(p.get("sha256")==h for p in album["images"]):continue
        occupied={p["number"] for p in album["images"]}
        n=evidence.get("number")
        if type(n) is not int or n<1 or n in occupied:
            n=max(occupied,default=0)+1
        remote_key=f"originals/{aid}/{parts[2]}"
        destination=out/remote_key
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        record={"number":n,"key":remote_key,"sha256":h,"bytes":evidence["bytes"],
                "width":evidence["width"],"height":evidence["height"],
                "source_number":evidence.get("number"),"source":evidence.get("url")}
        album["images"].append(record)
        new_files.append(record)
    if not albums:
        raise ValueError("No private photos acquired; refusing to publish empty catalogue")
    for a in albums.values():
        a["images"].sort(key=lambda p:p["number"])
        a["stored"]=len(a["images"])
        a["expected"]=indexes.get(a["id"],{}).get("expected")
    report={"schema_version":1,"model":"mimmi","storage_provider":"terabox",
            "access":"private_authenticated_bearer_only",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "albums":sorted(albums.values(),key=lambda a:a["title"].casefold()),
            "summary":{"albums":len(albums),"private_photo_records":sum(len(a["images"]) for a in albums.values()),
                       "new_file_verification_pending":len(new_files)}}
    metadata=out/"metadata"
    metadata.mkdir(parents=True,exist_ok=True)
    (metadata/"catalog.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (metadata/"new-files.json").write_text(json.dumps(new_files,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_PRIVATE_STAGED",json.dumps(report["summary"]),flush=True)
    return report

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--private",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--previous")
    args=ap.parse_args()
    build(args.source,args.private,args.out,args.previous)
