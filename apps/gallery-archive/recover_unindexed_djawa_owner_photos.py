#!/usr/bin/env python3
"""Recover physically present, unindexed owner photos for two verified DJAWA works.

This stages ONLY existing owner-account bytes; the existing G07 publisher
independently checks each SHA, decoded image, known work and near-duplicate
photo before writing immutable files to the static gallery. No remote writes,
new source crawls or private storage paths ever leave the Actions runner.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from PIL import Image, ImageOps
from qa_existing_owner_exact_file import read_existing

MODEL = "mimmi"
REMOTE = "archive:MimmiArchive"
ALLOWED_WORKS = (
    "djawa-retrospection",
    "djawa-christmas-special-2021-mimmi",
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,150}$")
EXT = {".jpg":"JPEG", ".jpeg":"JPEG", ".png":"PNG", ".webp":"WEBP"}


def eligible(listing, catalog, known_sha, maximum):
    if not 1 <= maximum <= 18 or not isinstance(listing, list):
        raise ValueError("INVALID_BOUNDED_EXISTING_OWNER_INPUT")
    if (catalog.get("schema_version") != 1 or catalog.get("model") != MODEL
            or catalog.get("storage") != "owner-private-terabox-sha-verified-bytes"
            or not isinstance(catalog.get("albums"), list)):
        raise ValueError("UNVERIFIED_EXISTING_OWNER_CATALOG")
    known_keys = {p["key"] for a in catalog["albums"] for p in a["images"]}
    registered = {a["id"] for a in catalog["albums"]}
    candidates = []
    for row in listing:
        if not isinstance(row,dict):
            continue
        key, size = row.get("Path"), row.get("Size")
        if not isinstance(key,str) or key in known_keys or type(size) is not int:
            continue
        segments = key.split("/")
        if (len(segments)!=3 or segments[0]!="originals"
                or segments[1] not in ALLOWED_WORKS or segments[1] not in registered
                or not SAFE_NAME.fullmatch(segments[2])
                or Path(segments[2]).suffix.lower() not in EXT
                or not 1000 <= size <= 10_000_000):
            continue
        candidates.append((key,size,segments[1]))
    candidates.sort(key=lambda x:(ALLOWED_WORKS.index(x[2]), x[0]))
    return candidates[:maximum],len(candidates)


def stage(root, stage_dir, listing, catalog, limit=18, reader=read_existing):
    root,stage_dir = Path(root),Path(stage_dir)
    owner_index = json.loads((root/"apps/mimmi-gallery/owner-index.json").read_text(encoding="utf-8"))
    saved = json.loads((root/"apps/mimmi-gallery/stored-albums.json").read_text(encoding="utf-8"))
    registered = json.loads((root/"apps/mimmi-gallery/public-work-pages.json").read_text(encoding="utf-8"))
    approved = {a["id"]:a for a in registered["albums"]}
    if not all(a in approved for a in ALLOWED_WORKS):
        raise ValueError("SOURCE_WORK_NOT_REGISTERED")
    if owner_index.get("model")!=MODEL or saved.get("model",MODEL)!=MODEL:
        raise ValueError("OWNER_STATIC_MODEL_MISMATCH")
    known_sha = {p["sha256"] for d in (owner_index,saved,catalog)
                 for a in d["albums"] for p in a["images"]}
    requested,available = eligible(listing,catalog,known_sha,limit)
    selected={a:[] for a in ALLOWED_WORKS}
    counts={"eligible_unindexed_owner_files":available,"attempted":0,
            "valid_new_sha_staged":0,"sha_already_indexed":0,
            "read_unavailable":0,"invalid_decoded_or_size":0}
    for key,bytes_expected,aid in requested:
        counts["attempted"]+=1
        local=stage_dir/key
        if not local.resolve().is_relative_to(stage_dir.resolve()):
            raise ValueError("UNSAFE_ORIGINAL_STAGE_PATH")
        local.parent.mkdir(parents=True,exist_ok=True)
        ok, reason = reader(REMOTE,key,local,__import__("os").environ.copy())
        if not ok:
            counts["read_unavailable"]+=1
            local.unlink(missing_ok=True)
            continue
        try:
            if local.stat().st_size!=bytes_expected:
                raise ValueError("CHANGED_REMOTE_SIZE")
            with local.open("rb") as f:
                sha=hashlib.file_digest(f,"sha256").hexdigest()
            if sha in known_sha:
                counts["sha_already_indexed"]+=1
                local.unlink(missing_ok=True)
                continue
            with Image.open(local) as photo:
                if photo.format!=EXT[local.suffix.lower()]:
                    raise ValueError("WRONG_IMAGE_EXTENSION")
                photo.verify()
            with Image.open(local) as photo:
                photo.load()
                width,height=photo.size
                if min(width,height)<300 or width*height>50_000_000:
                    raise ValueError("INVALID_IMAGE_DIMENSIONS")
            selected[aid].append({
                "number":0, "key":key, "sha256":sha,
                "bytes":bytes_expected,"width":width,"height":height
            })
            known_sha.add(sha)
            counts["valid_new_sha_staged"]+=1
        except (ValueError,OSError,Image.DecompressionBombError):
            local.unlink(missing_ok=True)
            counts["invalid_decoded_or_size"]+=1
    albums=[{"id":aid,"title":approved[aid]["title"],
             "images":selected[aid]} for aid in ALLOWED_WORKS if selected[aid]]
    meta=stage_dir/"metadata"
    meta.mkdir(parents=True,exist_ok=True)
    doc={"schema_version":1,"model":MODEL,"storage":"existing-owner-verified-byte-staging",
         "verified_new_work_sources":[],"albums":albums}
    (meta/"catalog.json").write_text(json.dumps(doc,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    # Only aggregate information can enter logs. No remote keys, account data,
    # photograph SHA values or signed URLs are printed by this script.
    print("EXISTING_DJAWA_OWNER_ORPHAN_STAGED",json.dumps(counts,sort_keys=True),flush=True)
    return counts


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--stage",required=True,type=Path)
    p.add_argument("--listing",required=True,type=Path)
    p.add_argument("--catalog",required=True,type=Path)
    p.add_argument("--limit",type=int,default=18)
    a=p.parse_args()
    stage(a.root,a.stage,json.loads(a.listing.read_text()),
          json.loads(a.catalog.read_text()),a.limit)


if __name__=="__main__": main()
