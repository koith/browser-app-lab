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

def seeds(root=ROOT,all_cuts=False):
    all_albums=[]
    for model in ("mimmi","yui"):
        base=root/(model+"-gallery")
        owner=json.loads((base/"owner-index.json").read_text(encoding="utf-8"))
        public=json.loads((base/"stored-albums.json").read_text(encoding="utf-8"))
        if owner.get("model")!=model or public.get("model",model)!=model:
            raise ValueError("Wrong stored model inventory")
        public_by_id={a["id"]:a for a in public["albums"]}
        owner_ids={album.get("id") for album in owner["albums"]}
        for album in owner["albums"]:
            aid=album["id"]
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}",aid):continue
            title=album.get("title") or aid
            if AI.search(title):continue
            owned=[x for x in album.get("images",[])
                   if type(x.get("number")) is int and x["number"]>0
                   and SHA.fullmatch(str(x.get("sha256","")))
                   and type(x.get("bytes")) is int and x["bytes"]>1024]
            if not owned and not all_cuts:continue
            occupied_slot_count=len(owned)
            unique_owned=[]
            hashes=set()
            for image in owned:
                if image["sha256"] in hashes:continue
                hashes.add(image["sha256"])
                unique_owned.append(image)
            owned=unique_owned
            public_photos=[x for x in public_by_id.get(aid,{}).get("images",[])
                           if isinstance(x.get("url"),str)
                           and x["url"].startswith("stored-albums/")
                           and ".." not in x["url"].split("/")
                           and SHA.fullmatch(str(x.get("sha256","")))]
            unique_public=[]
            seen_public=set()
            for image in public_photos:
                if image["sha256"] in seen_public:continue
                seen_public.add(image["sha256"])
                unique_public.append(image)
            public_photos=unique_public
            samples=[]
            if public_photos:
                choices=(list(range(len(public_photos))) if all_cuts else
                         list(dict.fromkeys([0,len(public_photos)//2,len(public_photos)-1])))
                for index in choices:
                    p=public_photos[index]
                    samples.append((p["sha256"],
                         GITHUB+"/"+model+"-gallery/"+quote(p["url"],safe="/"),
                         "static-public"))
            else:
                choices=(list(range(len(owned))) if all_cuts else
                         list(dict.fromkeys([0,len(owned)//2,len(owned)-1])))
                for index in choices:
                    p=owned[index]
                    version=str(p.get("preview_sha256") or p["sha256"])[:24]
                    samples.append((p["sha256"],
                        COVERS+"/"+model+"/"+quote(aid,safe="")+"/"+str(p["number"])+
                        "?v="+version,"public-gateway-cover"))
            if all_cuts and public_photos:
                # Static previews and owner catalog may contain different frames.
                # Search ALL union SHA, not merely first/middle/last public cuts.
                public_sha={p["sha256"] for p in public_photos}
                for p in owned:
                    if p["sha256"] in public_sha:continue
                    version=str(p.get("preview_sha256") or p["sha256"])[:24]
                    samples.append((p["sha256"],
                        COVERS+"/"+model+"/"+quote(aid,safe="")+"/"+str(p["number"])+
                        "?v="+version,"public-gateway-cover"))
            expected=album.get("expected")
            missing=max(0,expected-len(owned)) if type(expected) is int else None
            all_albums.append([{"model":model,"album_id":aid,"album_title":title,
                 "owner_saved_count":len(owned),"owner_slot_count":occupied_slot_count,"expected_gap":missing,
                 "union_saved_count":len(set(hashes)|set(seen_public)),
                 "photo_sha256":sha,"public_image_url":url,"seed_kind":kind}
                 for sha,url,kind in samples])
        if all_cuts:
            # Static-only public preview works (e.g. Yui Meow) have no owner
            # metadata and were previously invisible to all reverse searches.
            for aid,album in public_by_id.items():
                if aid in owner_ids or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}",aid):
                    continue
                title=album.get("title") or aid
                if AI.search(title):continue
                photos=[]
                distinct=set()
                for p in album.get("images",[]):
                    url=p.get("url","")
                    sha=p.get("sha256","")
                    if (not isinstance(url,str) or not url.startswith("stored-albums/")
                            or ".." in url.split("/") or not SHA.fullmatch(str(sha))
                            or sha in distinct):continue
                    distinct.add(sha)
                    photos.append((sha,GITHUB+"/"+model+"-gallery/"+quote(url,safe="/"),"static-public"))
                if photos:
                    all_albums.append([{"model":model,"album_id":aid,"album_title":title,
                        "owner_saved_count":0,"owner_slot_count":0,
                        "union_saved_count":len(photos),"expected_gap":None,
                        "photo_sha256":sha,"public_image_url":url,"seed_kind":kind}
                        for sha,url,kind in photos])
    all_albums.sort(key=(lambda album:(
        album[0]["union_saved_count"] > 20,
        album[0]["union_saved_count"],
        -(album[0]["expected_gap"] or 0),
        album[0]["model"],album[0]["album_id"])) if all_cuts else (lambda album:(
        0 if album[0]["expected_gap"] is not None else 1,
        -(album[0]["expected_gap"] or 0),
        album[0].get("union_saved_count",album[0]["owner_saved_count"]),
        album[0]["model"],album[0]["album_id"])))
    if all_cuts:
        # Complete per-photo queue, ordered by sparse album first.
        # The caller rotates a small bounded window, never all remote requests at once.
        return [photo for album in all_albums for photo in album]
    return [photo for i in range(3) for album in all_albums
            for photo in album[i:i+1]]
