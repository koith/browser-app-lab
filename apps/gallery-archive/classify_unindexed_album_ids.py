#!/usr/bin/env python3
"""Classify orphan owner storage folder labels against public work registries.

Never log private object paths, unknown private folder names, photo files,
hashes or account cookies. No media bytes downloaded, no storage changes.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

def classification(model, listing, owner, public, registry, aliases):
    if owner.get("model")!=model or not isinstance(listing,list):
        raise ValueError("MODEL_OR_LIST_INVALID")
    owner_ids={a["id"] for a in owner["albums"]}
    public_ids={a["id"] for a in public["albums"]}
    registered_ids={a["id"] for a in registry["albums"]}
    alias_dict=aliases.get("aliases",{})
    registered_names=[]
    by_folder=defaultdict(list)
    seen_paths={p["key"] for a in owner["albums"] for p in a["images"]}
    for row in listing:
        key=row.get("Path") if isinstance(row,dict) else None
        if not isinstance(key,str) or key in seen_paths or not key.startswith("originals/"):
            continue
        parts=key.split("/")
        if len(parts)!=3 or not key.casefold().endswith((".jpg",".jpeg",".png",".webp",".avif",".heic",".tif",".tiff")):
            continue
        if parts[1] in owner_ids: continue
        by_folder[parts[1]].append(row.get("Size",0))
    categories=Counter()
    for folder, files in by_folder.items():
        if folder in registered_ids:
            categories["registered_public_work"]+=len(files)
            registered_names.append({"public_id":folder,"file_candidates":len(files)})
        elif folder in public_ids:
            categories["existing_static_only_album"]+=len(files)
        elif folder in alias_dict and alias_dict[folder] in owner_ids:
            categories["alias_to_existing_owner_work"]+=len(files)
        elif folder in alias_dict and alias_dict[folder] in public_ids:
            categories["alias_to_existing_static_album"]+=len(files)
        else: categories["not_in_current_public_work_catalogs"]+=len(files)
    return {"model":model,"unindexed_unknown_owner_album_files":sum(map(len,by_folder.values())),
            "distinct_unknown_owner_folders":len(by_folder),
            "folder_size_distribution_sorted":sorted(map(len,by_folder.values()),reverse=True)[:30],
            "publicly_registered_work_matches":registered_names[:25],
            "category_counts":dict(sorted(categories.items())),"no_secret_paths_emitted":True}


def main():
    p=argparse.ArgumentParser()
    for name in ("listing","owner","public","registry","aliases"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--model",required=True,choices=("mimmi","yui"))
    a=p.parse_args()
    kwargs={name:json.loads(getattr(a,name).read_text(encoding="utf-8"))
            for name in ("listing","owner","public","registry","aliases")}
    print("OWNER_UNINDEXED_UNKNOWN_WORK_ID_CLASSIFICATION",
          json.dumps(classification(a.model,**kwargs),ensure_ascii=False,sort_keys=True))

if __name__=="__main__": main()
