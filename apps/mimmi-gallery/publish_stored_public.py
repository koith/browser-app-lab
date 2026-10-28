#!/usr/bin/env python3
"""Yui-style: publish ONLY real, SHA-verified public preview image bytes.

No TeraBox, no external URL pretending to be an archived image, no paywall.
GitHub Pages is PUBLIC: only use images whose public rehosting is authorized.
"""
import argparse, hashlib, json, os, re, time
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image
from download_public_images_private import fetch_verified, permitted

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/"source-viewer-albums.json"
INDEX=ROOT/"stored-albums.json"
OUT=ROOT/"stored-albums"
MAX_FILE=30_000_000
# Keep the full multi-app GitHub Pages site below the provider's size limit.
MAX_PUBLIC_IMAGE_BYTES=780*1024*1024

# Independently confirmed: exact same CreamSoda editions in the existing
# ten-image V2PH teasers and the publicly visible Xiutu photo galleries.
# Save to the existing edition folder, not six misleading duplicate cards.
XIUTU_EDITION_LINKS={
    "xiutu-public-1190160":"v2ph-actor-a5e78m5a",  # Neko Mimmi (62 public photos)
    "xiutu-public-1190158":"v2ph-actor-a8847m5a",  # Mashu Mimmi (59)
    "xiutu-public-1190156":"v2ph-actor-a884435a",  # Chic Nerd & Maness Nurse (63)
    "xiutu-public-1190145":"v2ph-actor-ae57484a",  # Belt choker (46)
}

def xiutu_verified_public_editions(root=ROOT):
    """Convert real SHA-backed public image URLs into existing physical albums.

    This is a list of image *candidates* for archival, not stored-image proof.
    The actual byte download, SHA matching and file write remain mandatory.
    """
    path=root/"xiutu-public-previews.json"
    if not path.is_file():return []
    source=json.loads(path.read_text(encoding="utf-8"))
    if source.get("model")!="mimmi":raise ValueError("Wrong model in independent photo source")
    albums=[]
    for a in source.get("albums",[]):
        original=a.get("id","")
        if not re.fullmatch(r"xiutu-public-[0-9]{4,12}",original):continue
        if not a.get("source","").startswith("https://www.xiutu.me/photo/"):continue
        photos=[]
        for p in a.get("samples",[]):
            url=p.get("url","")
            digest=p.get("sha256","")
            size=p.get("bytes")
            if (not permitted(url) or not re.fullmatch(r"[0-9a-f]{64}",digest)
                or type(size) is not int or not 5000<=size<=MAX_FILE
                or type(p.get("width")) is not int or type(p.get("height")) is not int
                or min(p["width"],p["height"])<300):
                continue
            photos.append({"url":url,"sha256":digest,"bytes":size,
                           "width":p["width"],"height":p["height"],"alternate_source_urls":[]})
        if not photos:continue
        albums.append({"id":XIUTU_EDITION_LINKS.get(original,original),
            "title":a.get("title","Mimmi CreamSoda public photo collection"),
            "publisher":"CreamSoda","source":a["source"],
            "original_work_id":original,"images":photos})
    priority={"xiutu-public-1190160":0,"xiutu-public-1190158":1,
              "xiutu-public-1190156":2,"xiutu-public-1190145":3,
              "xiutu-public-1190154":4,"xiutu-public-1190152":5}
    albums.sort(key=lambda a:priority.get(a["original_work_id"],100))
    return albums

def fetch_from_verified_alternates(photo, downloader=fetch_verified):
    """Try only independently SHA-identical public URLs, never guessed files."""
    digest=photo["sha256"]
    count=photo["bytes"]
    attempts=[]
    for url in [photo["url"],*photo.get("alternate_source_urls",[])[:12]]:
        if url in attempts or not permitted(url):continue
        attempts.append(url)
        try:
            return downloader(url,digest,count),url
        except (ValueError,OSError,Exception) as exc:
            # A public mirror may go offline/change bytes; the exact SHA and
            # byte count are still compulsory on EVERY alternative.
            print("MIMMI_MULTISOURCE_FAILED",type(exc).__name__,url[:140],flush=True)
    raise ValueError(f"No SHA-identical public source currently downloadable ({len(attempts)} attempts)")

def publish(limit=250, budget_mb=90, allow_rehost=False):
    if not allow_rehost:
        raise PermissionError("Public GitHub Pages publication requires explicit permission to rehost these files")
    src=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if src.get("model")!="mimmi":raise ValueError("Wrong model")
    old=json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"albums":[]}
    byid={a["id"]:a for a in old.get("albums",[])}
    seen={p["sha256"] for a in byid.values() for p in a.get("images",[]) if p.get("sha256")}
    existing_bytes=sum(p.get("bytes",0) for a in byid.values() for p in a.get("images",[]))
    if existing_bytes>MAX_PUBLIC_IMAGE_BYTES:
        raise ValueError("Current public archive already exceeds maximum Pages file budget")
    new=0;bytes_new=0;failed=0
    # First complete the six independently SHA-verified CreamSoda editions,
    # merging four matching V2PH teaser folders into the SAME work.
    # Then continue all other deep, publicly accessible source albums.
    candidates=[*xiutu_verified_public_editions(ROOT),
                *sorted(src["albums"],key=lambda a:(-len(a.get("images",[])),str(a.get("title","")).casefold()))]
    for album in candidates:
        aid=album["id"]
        if not re.fullmatch(r"[a-z0-9-]{2,110}",aid):continue
        row=byid.get(aid,{"id":aid,"title":album["title"],"publisher":album.get("publisher",""),"source":album.get("source",""),"images":[],"status":"public_previews_only_not_complete"})
        for photo in album.get("images",[]):
            if new>=limit or bytes_new>=budget_mb*1024*1024:break
            sha=photo.get("sha256","")
            url=photo.get("url","")
            if not re.fullmatch(r"[0-9a-f]{64}",sha) or not permitted(url):continue
            if sha in seen:continue
            size=photo.get("bytes",0)
            if not isinstance(size,int) or size<5000 or size>MAX_FILE or bytes_new+size>budget_mb*1024*1024 or existing_bytes+bytes_new+size>MAX_PUBLIC_IMAGE_BYTES:continue
            try:
                raw,working_url=fetch_from_verified_alternates(photo)
                suffix=Path(urlsplit(working_url).path).suffix.lower()
                path=OUT/aid/(sha+"."+suffix.lstrip("."))
                path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError("Stored file hash conflict")
                if not path.exists():
                    tmp=path.with_suffix(path.suffix+".tmp")
                    tmp.write_bytes(raw);os.replace(tmp,path)
                if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError("Write hash mismatch")
                with Image.open(path) as im:
                    im.verify()
                row["images"].append({"url":str(path.relative_to(ROOT)).replace(os.sep,"/"),
                    "source_url":working_url,"sha256":sha,"bytes":size,"width":photo["width"],
                    "height":photo["height"],"number":len(row["images"])+1})
                seen.add(sha);new+=1;bytes_new+=size
                time.sleep(.3)
            except Exception as exc:
                failed+=1
                print("STORE_FAILED",aid,sha[:12],type(exc).__name__,str(exc)[:100],flush=True)
        if row["images"]:byid[aid]=row
        if new>=limit or bytes_new>=budget_mb*1024*1024:break
    # Re-audit ALL claimed stored files. Missing bytes are never published.
    physical=0
    for a in byid.values():
        for p in a.get("images",[]):
            f=ROOT/p["url"]
            if not f.is_file() or f.stat().st_size!=p["bytes"] or hashlib.sha256(f.read_bytes()).hexdigest()!=p["sha256"]:
                raise ValueError("Missing/corrupt physically archived file: "+str(f))
            physical+=1
    INDEX.write_text(json.dumps({"schema_version":1,"model":"mimmi","updated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "storage":"physically committed public previews under GitHub Pages; not licensed publisher masters",
        "albums":list(byid.values()),"physical_verified_image_count":physical},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MIMMI_PHYSICAL_FILES",physical,"NEW",new,"FAILED",failed,"BYTES",bytes_new,flush=True)
    if physical==0:raise RuntimeError("No physical images archived. Refuse success.")
    return physical

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--limit",type=int,default=250)
    p.add_argument("--budget-mb",type=int,default=90)
    p.add_argument("--authorized-public-rehost",action="store_true")
    a=p.parse_args()
    publish(a.limit,a.budget_mb,a.authorized_public_rehost)
