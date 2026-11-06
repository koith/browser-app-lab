#!/usr/bin/env python3
"""Fail-closed, budget-aware private existing-owner mirror policy.

No subscriptions, buckets, credentials or media are created here. Neither a
project-local cap nor provider free-tier estimates prove an unrelated account
has no billable activity: private usage/charges need independent monitoring.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

FREE_STORAGE_BYTES=10_000_000_000
# 20% margin for previews, catalog metadata and future already-owned photos.
PROJECT_STORAGE_SOFT_CAP=8_000_000_000
PROJECT_MAX_OBJECTS=25_000
PROJECT_MAX_ESTIMATED_CLASS_A=100_000
PROJECT_MAX_ESTIMATED_CLASS_B=500_000
MODELS=("mimmi","yui")

class PolicyRefusal(RuntimeError):
    pass

def check_existing_owner_budget(root: Path):
    rows=[]
    keys=set()
    for model in MODELS:
        try:
            data=json.loads((root/(model+"-gallery")/"owner-index.json").read_text())
        except (ValueError,OSError) as error:
            raise PolicyRefusal("Existing owner SHA inventory not readable") from None
        if data.get("model")!=model or not isinstance(data.get("albums"),list):
            raise PolicyRefusal("Wrong private owner inventory")
        for album in data["albums"]:
            aid=album.get("id")
            if not isinstance(aid,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,99}",aid):
                raise PolicyRefusal("Invalid existing owner album identifier")
            for photo in album.get("images",[]):
                n,size,sha=photo.get("number"),photo.get("bytes"),photo.get("sha256")
                if (type(n) is not int or n<1 or type(size) is not int
                        or not 1<=size<=140_000_000 or not isinstance(sha,str)
                        or not re.fullmatch("[a-f0-9]{64}",sha)
                        or (model,aid,n) in keys):
                    raise PolicyRefusal("Invalid or duplicate existing owner SHA record")
                keys.add((model,aid,n))
                rows.append(size)
    count=len(rows)
    size=sum(rows)
    # Budget for two verification reads per object + one existence/readback
    # and conservative retries. Does NOT count other Cloudflare usage.
    class_a=count+len(MODELS)+100
    class_b=count*5+len(MODELS)*3+100
    if not count or (size>PROJECT_STORAGE_SOFT_CAP
            or count>PROJECT_MAX_OBJECTS
            or class_a>PROJECT_MAX_ESTIMATED_CLASS_A
            or class_b>PROJECT_MAX_ESTIMATED_CLASS_B):
        raise PolicyRefusal("Proposed backup exceeds conservative free project budget")
    return {"models":2,"objects":count,"original_bytes":size,
            "free_storage_bytes":FREE_STORAGE_BYTES,
            "project_soft_cap_bytes":PROJECT_STORAGE_SOFT_CAP,
            "estimated_class_a":class_a,"estimated_class_b":class_b,
            "zero_paid_operations_promised":False}

def validated_private_config(environ=None):
    e=os.environ if environ is None else environ
    bucket=e.get("OWNER_REPLICA_BUCKET","")
    remote=e.get("OWNER_DURABLE_REMOTE","")
    provider=e.get("OWNER_REPLICA_PROVIDER","")
    endpoint=e.get("RCLONE_CONFIG_OWNERREPLICA_ENDPOINT","")
    region=e.get("RCLONE_CONFIG_OWNERREPLICA_REGION","")
    key=e.get("RCLONE_CONFIG_OWNERREPLICA_ACCESS_KEY_ID","")
    secret=e.get("RCLONE_CONFIG_OWNERREPLICA_SECRET_ACCESS_KEY","")
    rclone_provider=e.get("RCLONE_CONFIG_OWNERREPLICA_PROVIDER","")
    if (not re.fullmatch("[a-z0-9][a-z0-9-]{2,62}",bucket)
        or remote!="ownerreplica:"+bucket
        or e.get("RCLONE_CONFIG_OWNERREPLICA_TYPE")!="s3"
        or min(len(key),len(secret))<12):
        raise PolicyRefusal("Private mirror not explicitly configured")
    if provider=="cloudflare-r2":
        account=e.get("OWNER_REPLICA_CF_ACCOUNT_ID","")
        token=e.get("OWNER_REPLICA_CF_AUDIT_TOKEN","")
        if (rclone_provider!="Cloudflare"
            or not re.fullmatch("[a-f0-9]{32}",account)
            or endpoint!="https://"+account+".r2.cloudflarestorage.com"
            or region!="auto" or len(token)<20):
            raise PolicyRefusal("Cloudflare R2 audit credentials/endpoint unavailable")
    elif provider=="backblaze-b2":
        if (rclone_provider!="Other"
            or not re.fullmatch(r"https://s3\.[a-z0-9-]+\.backblazeb2\.com",endpoint)
            or not re.fullmatch(r"[a-z0-9-]{4,32}",region)
            or region not in endpoint):
            raise PolicyRefusal("B2 private bucket provider mismatch")
    else:
        raise PolicyRefusal("Explicit supported private provider selection required")
    return {"bucket":bucket,"remote":remote,"provider":provider,
            "endpoint":endpoint,"region":region,"key":key,"secret":secret}

def _cloudflare_json(path,account,token,opener=urlopen):
    url="https://api.cloudflare.com/client/v4/accounts/"+account+"/r2/buckets/"+path
    req=Request(url,headers={"Authorization":"Bearer "+token,
                             "Accept":"application/json"},method="GET")
    try:
        with opener(req,timeout=15) as response:
            if response.status!=200:
                raise PolicyRefusal("R2 privacy verification HTTP failure")
            data=json.loads(response.read(128_000))
    except (OSError,ValueError,KeyError):
        raise PolicyRefusal("R2 privacy verification unavailable") from None
    if not isinstance(data,dict) or data.get("success") is not True:
        raise PolicyRefusal("R2 privacy API failed")
    return data.get("result")

def require_cloudflare_private_standard(config,environ=None,opener=urlopen):
    e=os.environ if environ is None else environ
    account=e.get("OWNER_REPLICA_CF_ACCOUNT_ID","")
    token=e.get("OWNER_REPLICA_CF_AUDIT_TOKEN","")
    bucket=config["bucket"]
    info=_cloudflare_json(bucket,account,token,opener=opener)
    if (not isinstance(info,dict) or info.get("name")!=bucket
            or info.get("storage_class")!="Standard"):
        raise PolicyRefusal("Only known private R2 Standard bucket is eligible")
    managed=_cloudflare_json(bucket+"/domains/managed",account,token,opener=opener)
    custom=_cloudflare_json(bucket+"/domains/custom",account,token,opener=opener)
    if (not isinstance(managed,dict) or managed.get("enabled") is not False
        or not isinstance(custom,dict) or not isinstance(custom.get("domains"),list)
        or any(not isinstance(x,dict) or x.get("enabled") is not False
                for x in custom["domains"])):
        raise PolicyRefusal("Public or unverifiable R2 access path is forbidden")
    return config["remote"]
