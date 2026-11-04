#!/usr/bin/env python3
"""Existing-owner-only readback into exact-SHA private Render RAM, no uploads to storage.

Runs only as an authorized GitHub Actions main-branch session workflow.
Only existing private catalog records may be copied; original bytes are never
written to GitHub, Pages, logs or third-party persistent stores.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mimmi-gallery" / "cloud" / "gateway"))
from cookie_format import cookie_header

ORIGIN="https://mimmi-private-gallery-free.onrender.com"
AUDIENCE="gallery-archive-terabox-sync"
REMOTE={"mimmi":"archive:MimmiArchive","yui":"archive:YuiArchive"}
COOKIE={"mimmi":"MIMMI_COOKIE","yui":"YUI_COOKIE"}
# Snapshot of the exact owner works visible in the user's incident screenshots.
# The counts are intentionally strict: never accept an incomplete model index.
TARGET={
    "mimmi":( ("djawa-janus-scary-lantern-night",8),
              ("mimmi-indie-sana-sopmod2-2019",7) ),
    "yui":( ("djawa-privaty-public-samples",30),
            ("yui-chinokun-illustar-2026-public",4) ),
}
MAX_FILE=12*1024*1024
MAX_SHARD_BYTES=58*1024*1024
MAX_COVERS=35


class OwnerReadUnavailable(Exception):
    pass


def identity():
    origin = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    sep = "&" if "?" in origin else "?"
    url = origin + sep + "audience=" + AUDIENCE
    req = Request(url, headers={"Authorization":"Bearer " +
                   os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urlopen(req, timeout=22) as response:
        return json.load(response)["value"]


def send(path, body, token, extra=None):
    headers={
        "Authorization":"Bearer "+token,
        "Content-Type":"application/octet-stream",
        **(extra or {}),
    }
    req=Request(ORIGIN+path,method="POST",data=body,headers=headers)
    with urlopen(req,timeout=70) as response:
        if response.status != 200:
            raise RuntimeError("Signed owner mirror did not acknowledge")
        return json.load(response)


def send_verified_photo_with_catalog_recovery(model, body, token, headers, catalog_bytes):
    """Recover once if Render restarted after receiving the owner catalog.

    HTTP 409 is not automatically retried: only a signed endpoint's exact
    'Owner catalog is not verified' response permits re-sending the SAME
    already verified catalog. Never retry or downgrade other denials.
    """
    endpoint="/internal/gallery-rescue-media/"+model
    try:
        return send(endpoint, body, token, headers)
    except HTTPError as error:
        if error.code != 409:
            raise
        try:
            detail=json.loads(error.read(2048)).get("detail")
        except (ValueError,AttributeError,UnicodeError):
            raise error
        if detail!="Owner catalog is not verified":
            raise error
        result=send("/internal/gallery-rescue-catalog/"+model,catalog_bytes,token)
        if result.get("verified") is not True:
            raise OwnerReadUnavailable("Owner catalog was not restored after restart")
        return send(endpoint,body,token,headers)


def verified_file(remote, key, env, maximum):
    if (not isinstance(key,str) or key.startswith("/")
            or ".." in key.split("/") or "\\\\" in key or
            not re.fullmatch("[a-zA-Z0-9/_ .-]+",key)):
        raise OwnerReadUnavailable("Invalid existing owner file")
    with tempfile.TemporaryDirectory(prefix="owner-rescue-") as work:
        destination=Path(work)/"owner-file"
        with destination.open("wb") as file:
            try:
                process=subprocess.run(
                    ["rclone","cat",remote+"/"+key,
                     "--timeout=45s","--retries=1"],
                    stdout=file,stderr=subprocess.DEVNULL,
                    timeout=65,check=False,env=env)
            except subprocess.TimeoutExpired as error:
                raise OwnerReadUnavailable("Existing read timed out") from error
        if process.returncode or not destination.is_file():
            raise OwnerReadUnavailable("Authenticated original unavailable")
        if not 1 <= destination.stat().st_size <= maximum:
            raise OwnerReadUnavailable("Existing original size invalid")
        return destination.read_bytes()


def photo_ok(photo,data,variant):
    if variant=="original":
        sha,size=photo.get("sha256"),photo.get("bytes")
    else:
        sha,size=photo.get("preview_sha256"),photo.get("preview_bytes")
    if (not isinstance(sha,str) or not re.fullmatch("[a-f0-9]{64}",sha)
        or type(size) is not int or len(data)!=size or
        hashlib.sha256(data).hexdigest()!=sha):
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>40_000_000:
                return False
            if variant=="original" and (
                (type(photo.get("width")) is int and image.width!=photo["width"]) or
                (type(photo.get("height")) is int and image.height!=photo["height"])
            ):
                return False
            image.verify()
    except (ValueError,OSError):
        return False
    return True


def verified_same_owner_existing_read(model, key, env, photo, variant, attempts=1):
    """Bound transient incomplete content; never retry explicit provider denial.

    All attempts use exactly the original authorized model account and key.
    Bytes are returned ONLY after the recorded SHA, length and pixels pass.
    """
    if not 1 <= attempts <= 3:
        raise ValueError("Invalid owner read budget")
    for number in range(attempts):
        data=verified_file(REMOTE[model],key,env,MAX_FILE)
        if len(data)<=512:
            try:
                provider=json.loads(data)
            except (ValueError,UnicodeError):
                provider={}
            if isinstance(provider,dict) and provider.get("error_code")==31326:
                raise OwnerReadUnavailable("Owner provider explicitly denied this read")
        if photo_ok(photo,data,variant):
            return data
        if number+1<attempts:
            print("OWNER_EXISTING_SHA_INCOMPLETE_RETRY",model,variant,number+1,flush=True)
            time.sleep(1.0)
    raise OwnerReadUnavailable("Owner media SHA/pixel integrity not verified")



def verified_owner_catalog(model, env, attempts=3):
    """Accept a catalog from only its model's existing account.

    A stale/wrong-model body may be retried with the same credentials.
    Explicit provider access-denial documents must never be retried.
    """
    if not 1 <= attempts <= 3:
        raise ValueError("Invalid owner catalog read budget")
    for number in range(attempts):
        raw=verified_file(REMOTE[model],"metadata/catalog.json",env,6_000_000)
        try:
            data=json.loads(raw)
        except (ValueError,UnicodeError):
            data=None
        if isinstance(data,dict):
            if ((type(data.get("error_code")) is int and data["error_code"]!=0)
                or (type(data.get("errno")) is int and data["errno"]!=0)):
                raise OwnerReadUnavailable("Owner catalog provider explicitly rejected access")
            if (data.get("schema_version")==1 and data.get("model")==model
                and isinstance(data.get("albums"),list) and data["albums"]):
                return raw,data
        if number+1 < attempts:
            print("OWNER_CATALOG_WRONG_OR_INCOMPLETE_RETRY",model,number+1,flush=True)
            time.sleep(1.0)
    raise OwnerReadUnavailable("Wrong or incomplete owner catalog metadata")


def select_rows(model,catalog):
    covers_path=ROOT / (model+"-gallery") / "album-covers.json"
    # The pinned cover manifest is only an advisory selector; never a
    # source for unverified bytes, which still come from the owner catalog.
    covers=json.loads(covers_path.read_text()).get("covers",{})
    albums=catalog["albums"]
    covers_rows=[]
    for album in albums:
        rows=album.get("images",[])
        candidate=covers.get(album["id"],{})
        item=next((p for p in rows if p.get("sha256")==candidate.get("sha256")),None)
        if item is None and rows:
            item=rows[0]
        if item is not None:
            variant="preview" if (isinstance(item.get("preview"),str) and
                item.get("preview_bytes",MAX_FILE+1)<=MAX_FILE) else "original"
            covers_rows.append((album,item,variant))
    # Covers are ranked by existing manifest order only, not by scraping.
    chosen=covers_rows[:MAX_COVERS]
    full_rows=[]
    for album_id, expected in TARGET[model]:
        wanted=next((a for a in albums if a["id"]==album_id),None)
        if wanted is None or len(wanted.get("images",[]))!=expected:
            raise OwnerReadUnavailable("Incident work missing/incomplete: "+model)
        numbers=[p.get("number") for p in wanted["images"]]
        if len(set(numbers))!=expected or not all(type(n) is int and n>=1 for n in numbers):
            raise OwnerReadUnavailable("Incident photo numbering is not unique")
        full_rows.extend((wanted,p,"original") for p in sorted(
            wanted["images"],key=lambda x:x["number"]))
    return chosen,full_rows


def ensure_only_private_original(model,album,photo,variant):
    key=photo.get("key" if variant=="original" else "preview")
    sha=photo.get("sha256" if variant=="original" else "preview_sha256")
    size=photo.get("bytes" if variant=="original" else "preview_bytes")
    expected=("originals" if variant=="original" else "previews")+"/"+album["id"]+"/"
    return (isinstance(key,str) and key.startswith(expected) and
       isinstance(sha,str) and re.fullmatch("[a-f0-9]{64}",sha) and
       type(size) is int and 0<size<=MAX_FILE and
       type(photo.get("number")) is int and 1<=photo["number"]<=99999)


def run(model,token):
    secret=os.environ.get(COOKIE[model],"")
    if not 8<=len(secret)<=16000:
        raise OwnerReadUnavailable("Existing owner credential is not configured")
    env=os.environ.copy()
    env["RCLONE_CONFIG_ARCHIVE_TYPE"]="terabox"
    env["RCLONE_CONFIG_ARCHIVE_COOKIE"]=cookie_header(secret)
    # Do not copy Render-specific regional experiments into the authorized
    # owner's GitHub Runner, whose direct archive read already passed.
    env.pop("RCLONE_CONFIG_ARCHIVE_DOMAIN",None)
    raw,data=verified_owner_catalog(model,env,attempts=3)
    receipt=send("/internal/gallery-rescue-catalog/"+model,raw,token)
    if receipt.get("verified") is not True:
        raise OwnerReadUnavailable("Signed catalog not acknowledged")
    chosen,full=select_rows(model,data)
    # First restore all currently user-reported 30+8 and original 4+7 photos.
    # Optional covers must never delay the user's photo-detail albums.
    priority=full+chosen
    # Keep first occurrence: an optional cover must not delay urgent photos.
    unique={}
    for album,photo,variant in priority:
        if ensure_only_private_original(model,album,photo,variant):
            key=(album["id"],photo["number"],variant)
            if key not in unique:
                unique[key]=(album,photo,variant)
    fullset={(a["id"],p["number"],variant) for a,p,variant in full}
    count=0;urgent=0;used=0;skipped=0
    per_work={album_id:0 for album_id,_ in TARGET[model]}
    rejected_incident=[]
    token_timestamp=time.monotonic()
    for album,photo,variant in unique.values():
        if time.monotonic()-token_timestamp>120:
            token=identity();token_timestamp=time.monotonic()
        key=photo["key" if variant=="original" else "preview"]
        expected=int(photo["bytes" if variant=="original" else "preview_bytes"])
        if used+expected>MAX_SHARD_BYTES and (
            album["id"],photo["number"],variant) not in fullset:
            skipped+=1
            continue
        urgent_photo=(album["id"],photo["number"],variant) in fullset
        try:
            content=verified_same_owner_existing_read(
                model,key,env,photo,variant,attempts=3 if urgent_photo else 1)
        except OwnerReadUnavailable:
            if variant=="preview" and not urgent_photo:
                # Stale preview SHA does not authorize silently using it.
                # A separately recorded original may still be verified.
                print("OWNER_RESCUE_PREVIEW_SHA_MISMATCH_TRY_VERIFIED_ORIGINAL",model,flush=True)
                if not ensure_only_private_original(model,album,photo,"original"):
                    skipped+=1
                    continue
                try:
                    content=verified_same_owner_existing_read(
                        model,photo["key"],env,photo,"original",attempts=2)
                except OwnerReadUnavailable:
                    skipped+=1
                    continue
                variant="original"
            elif urgent_photo:
                # Do not mislabel a failed SHA as recovered, but continue
                # other incident photos to maximize actual visible recovery.
                rejected_incident.append((album["id"],photo["number"]))
                print("OWNER_INCIDENT_EXACT_SHA_PHOTO_UNAVAILABLE",model,
                      album["id"],photo["number"],flush=True)
                continue
            else:
                skipped+=1
                continue
        receipt=send_verified_photo_with_catalog_recovery(
            model,content,token,{
                "X-Owner-Album":album["id"],
                "X-Owner-Number":str(photo["number"]),
                "X-Owner-Variant":variant
            },raw)
        if receipt.get("cached") is not True:
            raise OwnerReadUnavailable("Render rejected the verified original")
        count+=1;used+=len(content)
        if (album["id"],photo["number"],variant) in fullset:
            sha=photo["sha256"]
            prefix="/api/yui" if model=="yui" else "/api"
            address=ORIGIN+prefix+"/media/"+album["id"]+"/"+str(photo["number"])+"/original?v="+sha
            with urlopen(address,timeout=65) as proof:
                live=proof.read(MAX_FILE+1)
                if (proof.status!=200 or len(live)!=len(content)
                    or hashlib.sha256(live).hexdigest()!=sha
                    or not proof.headers.get("Content-Type","").startswith("image/")):
                    raise OwnerReadUnavailable("Actual live Render original SHA readback failed")
            urgent+=1
            per_work[album["id"]]+=1
    print("OWNER_RESCUE_EXISTING_READBACK",json.dumps({
        "model":model,"albums":len(data["albums"]),
        "verified_transfer":count,"urgent_verified":urgent,
        "urgent_expected":len(fullset),"incident_breakdown":per_work,
        "incident_sha_rejected":len(rejected_incident),"skipped":skipped,
        "upstream_gallery_originals_modified":False,
        "new_image_collection":False
    }),flush=True)
    if urgent!=len(fullset) or rejected_incident:
        raise OwnerReadUnavailable("Not all user-reported photos were SHA-verified")
    if count<=urgent:
        raise OwnerReadUnavailable("No album covers recovered outside targeted work")


def main():
    failed=[]
    for model in ("yui","mimmi"):
        try:
            run(model,identity())
        except (OwnerReadUnavailable, HTTPError, URLError,
                TimeoutError, ValueError, OSError) as error:
            # Retain the other owner's verified successes even if this
            # account has a transient or explicit provider error.
            print("OWNER_RESCUE_MODEL_NOT_VERIFIED",model,type(error).__name__,flush=True)
            failed.append(model)
    if failed:
        raise OwnerReadUnavailable("Owner restore incomplete for "+",".join(failed))
    print("BOTH_GALLERIES_EXISTING_OWNER_EMERGENCY_CACHE_REHYDRATED",flush=True)


if __name__=="__main__":
    main()
