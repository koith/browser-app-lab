#!/usr/bin/env python3
"""Append-only, SHA-verified existing-owner private Backblaze B2 mirror.

This CLI is an explicit opt-in migration runner, NOT a crawler, not a public
photo publisher, and not the canonical TeraBox source of truth. Refuse every
write unless a private B2 bucket and limited application key are verified.
No secrets, full paths, signed URLs, image bodies or provider stderr are logged.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import boto3
from botocore.config import Config
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"mimmi-gallery"/"cloud"/"gateway"))
from cookie_format import cookie_header
from restore_known_owner_cache import (
    COOKIE, REMOTE, MAX_FILE, OwnerReadUnavailable, verified_owner_catalog,
    verified_same_owner_existing_read, ensure_only_private_original, photo_ok,
)

def credentials():
    bucket=os.environ.get("OWNER_REPLICA_BUCKET","")
    remote=os.environ.get("OWNER_DURABLE_REMOTE","")
    endpoint=os.environ.get("RCLONE_CONFIG_OWNERREPLICA_ENDPOINT","")
    region=os.environ.get("RCLONE_CONFIG_OWNERREPLICA_REGION","")
    key=os.environ.get("RCLONE_CONFIG_OWNERREPLICA_ACCESS_KEY_ID","")
    secret=os.environ.get("RCLONE_CONFIG_OWNERREPLICA_SECRET_ACCESS_KEY","")
    if (not re.fullmatch(r"[a-z0-9][a-z0-9-]{5,49}",bucket)
            or remote!="ownerreplica:"+bucket
            or os.environ.get("RCLONE_CONFIG_OWNERREPLICA_TYPE")!="s3"
            or os.environ.get("RCLONE_CONFIG_OWNERREPLICA_PROVIDER")!="Other"
            or not re.fullmatch(r"https://s3\.[a-z0-9-]+\.backblazeb2\.com",endpoint)
            or not re.fullmatch(r"[a-z0-9-]{4,32}",region)
            or region not in endpoint
            or min(len(key),len(secret))<12):
        raise RuntimeError("Private mirror account/bucket configuration is incomplete")
    return bucket,remote,endpoint,region,key,secret

def require_private_bucket():
    bucket,remote,endpoint,region,key,secret=credentials()
    client=boto3.client("s3",region_name=region,endpoint_url=endpoint,
        aws_access_key_id=key,aws_secret_access_key=secret,
        config=Config(retries={"max_attempts":2}))
    acl=client.get_bucket_acl(Bucket=bucket)
    grants=acl.get("Grants",[])
    if not grants:
        raise RuntimeError("Bucket privacy ACL was not verifiable")
    for item in grants:
        grantee=item.get("Grantee",{})
        if grantee.get("Type")=="Group" or "AllUsers" in str(grantee.get("URI","")):
            raise RuntimeError("Refusing media upload to a nonprivate bucket")
    # A standalone account-key check must be done for EACH model/shard job:
    # read-write credentials are never sent to the public Pages browser.
    print("PRIVATE_B2_BUCKET_ACL_VERIFIED",flush=True)
    return remote

def run_cmd(argv,output):
    with output.open("wb") as out:
        try:
            p=subprocess.run(argv,stdout=out,stderr=subprocess.PIPE,
                timeout=90,check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Object-store read timed out") from None
    return p.returncode,(p.stderr or b"")[:2048]

def verify_remotely(remote,path,sha,size):
    with tempfile.TemporaryDirectory(prefix="private-readback-") as directory:
        target=Path(directory)/"verify"
        rc,stderr=run_cmd([
            "rclone","cat",remote+"/"+path,"--timeout=35s","--retries=1"],target)
        if rc:
            info=stderr.decode("utf-8","replace").lower()
            missing=any(t in info for t in (
                "not found","does not exist","nosuchkey","object not found"))
            if missing:return False
            raise RuntimeError("Object-store read failed; never treat ambiguous failure as absent")
        raw=target.read_bytes()
        if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=sha:
            raise RuntimeError("Existing destination file has unexpected SHA/size; refuse overwrite")
        return True

def save_immutable(remote,path,data,sha):
    if verify_remotely(remote,path,sha,len(data)):
        return False
    with tempfile.TemporaryDirectory(prefix="private-upload-") as directory:
        src=Path(directory)/"verified"
        src.write_bytes(data)
        result=subprocess.run(["rclone","copyto",str(src),remote+"/"+path,
             "--immutable","--timeout=45s","--retries=1"],
             stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=100,check=False)
        # A concurrently completed identical upload is allowed; no overwrite.
        if result.returncode and not verify_remotely(remote,path,sha,len(data)):
            raise RuntimeError("Private storage immutable upload rejected")
        if not verify_remotely(remote,path,sha,len(data)):
            raise RuntimeError("Private storage SHA readback failed")
    return True

def fingerprint(records):
    return Counter((album["id"],p.get("number"),p.get("sha256"),p.get("bytes"))
                   for album in records for p in album.get("images",[]))

def planned_rows(model,catalog):
    index=json.loads((ROOT/(model+"-gallery")/"owner-index.json").read_text())
    if index.get("model")!=model or not isinstance(index.get("albums"),list):
        raise RuntimeError("Expected public SHA index missing")
    if fingerprint(index["albums"])!=fingerprint(catalog["albums"]):
        raise RuntimeError("Private owner catalog differs from published SHA index")
    rows=[]
    for a in catalog["albums"]:
        for p in a["images"]:
            if not ensure_only_private_original(model,a,p,"original"):
                raise RuntimeError("Unexpected owner original metadata")
            rows.append((a,p))
    rows.sort(key=lambda ap:(ap[0]["id"],ap[1]["number"]))
    return rows

def main(args):
    remote=require_private_bucket()
    cookie=os.environ.get(COOKIE[args.model],"")
    if not 8<=len(cookie)<=16000:
        raise RuntimeError("Verified existing-owner account secret not configured")
    env=os.environ.copy()
    env["RCLONE_CONFIG_ARCHIVE_TYPE"]="terabox"
    env["RCLONE_CONFIG_ARCHIVE_COOKIE"]=cookie_header(cookie)
    env.pop("RCLONE_CONFIG_ARCHIVE_DOMAIN",None)
    manifest_raw,catalog=verified_owner_catalog(args.model,env,attempts=3)
    rows=planned_rows(args.model,catalog)
    dest=remote+"/"+args.model
    if args.finalize:
        for a,p in rows:
            if not verify_remotely(dest,p["key"],p["sha256"],p["bytes"]):
                raise RuntimeError("Full private mirror still missing a recorded owner original")
        if save_immutable(dest,"metadata/catalog.json",manifest_raw,
             hashlib.sha256(manifest_raw).hexdigest()):
            print("PRIVATE_OWNER_CATALOG_IMMUTABLY_MIRRORED",args.model,flush=True)
        print("PRIVATE_OWNER_MODEL_ALL_ORIGINAL_SHA_BYTES_READBACK_PASS",
              json.dumps({"model":args.model,"count":len(rows)}),flush=True)
        return

    segment=rows[args.offset:args.offset+args.count]
    if not segment:
        raise RuntimeError("Empty shard selected; no data processed")
    uploaded=0;existing=0;failed=0
    for album,photo in segment:
        try:
            if verify_remotely(dest,photo["key"],photo["sha256"],photo["bytes"]):
                existing+=1
                continue
            body=verified_same_owner_existing_read(
                args.model,photo["key"],env,photo,"original",attempts=3)
            if not photo_ok(photo,body,"original"):
                raise RuntimeError("Source bytes do not match owner SHA/pixels")
            if save_immutable(dest,photo["key"],body,photo["sha256"]):
                uploaded+=1
            else:existing+=1
        except (OwnerReadUnavailable,RuntimeError,subprocess.TimeoutExpired,OSError):
            # No original key/URL, cookie, image bytes or ambiguous provider
            # error body in logs. Other items may still be backed up safely.
            failed+=1
    print("PRIVATE_OWNER_IMMUTABLE_MIRROR_SHARD",json.dumps({
        "model":args.model,"offset":args.offset,"count":len(segment),
        "uploaded":uploaded,"already_SHA_verified":existing,
        "failed":failed,"originals_publicly_published":False,
        "terabox_originals_modified":False},sort_keys=True),flush=True)
    if failed:
        raise SystemExit(1)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=("mimmi","yui"),required=True)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--count",type=int,default=100)
    p.add_argument("--finalize",action="store_true")
    args=p.parse_args()
    if not 0<=args.offset<=10000 or not 1<=args.count<=200:
        raise SystemExit("Invalid bounded shard selection")
    main(args)
