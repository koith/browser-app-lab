#!/usr/bin/env python3
"""Single existing-owner object read diagnostic; no data leaves the runner.

Only two numbered photos from the user's actual iPhone error albums.
Print only allowlisted failure classifications, no paths, cookies, full
provider responses, signed URLs, or photo bytes.
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
from restore_known_owner_cache import verified_owner_catalog, REMOTE, COOKIE, cookie_header

TARGET = {
    "mimmi": ("v2ph-actor-a8n8n85a",44),
    "yui": ("teddy-bear97",84),
}

def classified(stderr):
    s=stderr.decode("utf-8","replace")[:65536]
    status=re.search(r"(?:HTTP (?:error|status)|status(?: code)?)[\s:]*([45]\d\d)\b",s,re.I)
    error_code=re.search(r'(?:error_code|errno)[\s":=]+(\d{4,6})',s,re.I)
    code=error_code.group(1) if error_code else "none"
    http=status.group(1) if status else "none"
    if "31326" in s or "anti hotlinking" in s.lower() or http in ("401","403"):
        category="EXPLICIT_ACCESS_DENIAL"
    elif "400141" in s:
        category="DOCUMENTED_SAME_OWNER_COPYTO_ELIGIBLE"
    elif http=="404":
        category="OBJECT_MISSING"
    elif http=="429" or (http != "none" and http.startswith("5")):
        category="TRANSIENT_HTTP"
    elif re.search(r"(?:timeout|timed out|connection reset|unexpected EOF|context deadline)",s,re.I):
        category="TRANSIENT_TRANSPORT"
    else:
        category="UNKNOWN_READ_FAILURE"
    return {"category":category,"http_status":http,"provider_error_code":code}

def main(model):
    album_id,number=TARGET[model]
    secret=os.environ.get(COOKIE[model],"")
    if len(secret)<8:
        raise SystemExit("ACCOUNT_CREDENTIAL_NOT_AVAILABLE")
    env=os.environ.copy()
    env["RCLONE_CONFIG_ARCHIVE_TYPE"]="terabox"
    env["RCLONE_CONFIG_ARCHIVE_COOKIE"]=cookie_header(secret)
    env.pop("RCLONE_CONFIG_ARCHIVE_DOMAIN",None)
    raw,catalog=verified_owner_catalog(model,env,attempts=3)
    album=next((a for a in catalog["albums"] if a.get("id")==album_id),None)
    if not album:
        raise SystemExit("EXISTING_OWNER_ALBUM_UNAVAILABLE")
    items=[p for p in album["images"] if p.get("number")==number]
    if len(items)!=1:
        raise SystemExit("EXISTING_OWNER_PHOTO_NUMBER_INVALID")
    p=items[0]
    path=p.get("key")
    if not isinstance(path,str) or not path.startswith(f"originals/{album_id}/") or ".." in path.split("/"):
        raise SystemExit("EXISTING_OWNER_SOURCE_PATH_INVALID")
    remote=REMOTE[model]
    with tempfile.TemporaryDirectory(prefix="single-owned-") as d:
        target=Path(d)/"verified"
        with target.open("wb") as out:
            result=subprocess.run(["rclone","cat",remote+"/"+path,"--timeout=35s","--retries=1"],
                      stdout=out,stderr=subprocess.PIPE,env=env,timeout=65,check=False)
        if result.returncode:
            diag=classified(result.stderr)
            print("OWNED_SCREENSHOT_SINGLE_OBJECT_DIAG",json.dumps({
               "model":model,"album":album_id,"number":number,
               "cat_result":"failed",**diag},sort_keys=True),flush=True)
            # Do not use any alternate method after 403, 31326, unknown
            # denial, or absent object. Copyto is documented only for 400141.
            if diag["category"]!="DOCUMENTED_SAME_OWNER_COPYTO_ELIGIBLE":
                raise SystemExit(2)
            target.unlink(missing_ok=True)
            result=subprocess.run(["rclone","copyto",remote+"/"+path,str(target),
                        "--timeout=35s","--retries=1"],
                        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                        env=env,timeout=65,check=False)
            if result.returncode:
                print("OWNED_SCREENSHOT_SINGLE_OBJECT_COPYTO",
                      json.dumps({"model":model,"number":number,**classified(result.stderr)}),flush=True)
                raise SystemExit(3)
        b=target.read_bytes()
        if len(b)!=p["bytes"] or hashlib.sha256(b).hexdigest()!=p["sha256"]:
            raise SystemExit("EXISTING_OWNER_EXACT_SHA_REJECTED")
        with Image.open(io.BytesIO(b)) as image:
            image.load()
            if (image.width,image.height)!=(p["width"],p["height"]):
                raise SystemExit("EXISTING_OWNER_PIXEL_DIMENSIONS_REJECTED")
        print("OWNED_SCREENSHOT_SINGLE_OBJECT_SHA_PASS",
              json.dumps({"model":model,"number":number,"bytes":len(b),
                          "source_owner_authorized":True,
                          "public_original_publication":False}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=tuple(TARGET),required=True)
    a=p.parse_args()
    main(a.model)
