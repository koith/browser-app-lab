#!/usr/bin/env python3
"""Rank low-count *stored* Mimmi/Yui albums for image-first discovery.

Only already-public, first-party cover/image URLs are search inputs.
Private TeraBox keys, credentials, and original data never leave the archive.
"""
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
GITHUB="https://koith.github.io/browser-app-lab/apps"
COVERS="https://mimmi-private-gallery-free.onrender.com/api/cover"
SHA=re.compile(r"^[0-9a-f]{64}$")
AI=re.compile(r"ai[ -_]*enhanced|ai[ -_]*보정",re.I)

def seeds(root=ROOT):
    all_albums=[]
    for model in ("mimmi","yui"):
        base=root/(model+"-gallery")
        owner=json.loads((base/"owner-index.json").read_text(encoding="utf-8"))
        public=json.loads((base/"stored-albums.json").read_text(encoding="utf-8"))
        if owner.get("model")!=model or public.get("model",model)!=model:
            raise ValueError("Wrong stored model inventory")
        public_by_id={a["id"]:a for a in public["albums"]}
        for album in owner["albums"]:
            aid=album["id"]
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}",aid):continue
            title=album.get("title") or aid
            if AI.search(title):continue
            owned=[x for x in album.get("images",[])
                   if type(x.get("number")) is int and x["number"]>0
                   and SHA.fullmatch(str(x.get("sha256","")))
                   and type(x.get("bytes")) is int and x["bytes"]>1024]
            if not owned:continue
            public_photos=[x for x in public_by_id.get(aid,{}).get("images",[])
                           if isinstance(x.get("url"),str)
                           and x["url"].startswith("stored-albums/")
                           and ".." not in x["url"].split("/")
                           and SHA.fullmatch(str(x.get("sha256","")))]
            samples=[]
            if public_photos:
                choices=list(dict.fromkeys([0,len(public_photos)//2,len(public_photos)-1]))
                for index in choices:
                    p=public_photos[index]
                    samples.append((p["sha256"],
                         GITHUB+"/"+model+"-gallery/"+quote(p["url"],safe="/"),
                         "static-public"))
            else:
                choices=list(dict.fromkeys([0,len(owned)//2,len(owned)-1]))
                for index in choices:
                    p=owned[index]
                    version=str(p.get("preview_sha256") or p["sha256"])[:24]
                    samples.append((p["sha256"],
                        COVERS+"/"+model+"/"+quote(aid,safe="")+"/"+str(p["number"])+
                        "?v="+version,"public-gateway-cover"))
            expected=album.get("expected")
            missing=max(0,expected-len(owned)) if type(expected) is int else None
            all_albums.append([{"model":model,"album_id":aid,"album_title":title,
                 "owner_saved_count":len(owned),"expected_gap":missing,
                 "photo_sha256":sha,"public_image_url":url,"seed_kind":kind}
                 for sha,url,kind in samples])
    all_albums.sort(key=lambda album:(
        0 if album[0]["expected_gap"] is not None else 1,
        -(album[0]["expected_gap"] or 0),album[0]["owner_saved_count"],
        album[0]["model"],album[0]["album_id"]))
    return [photo for i in range(3) for album in all_albums
            for photo in album[i:i+1]]
