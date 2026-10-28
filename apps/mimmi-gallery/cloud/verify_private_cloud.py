#!/usr/bin/env python3
"""Verify exact stored private bytes by remote readback, then verify catalog."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

HEX=re.compile(r"^[a-f0-9]{64}$")

def remote_read(remote,key,timeout=90):
    if not remote.startswith("archive:") or not key.startswith(("originals/","metadata/")):
        raise ValueError("Unknown remote or unsafe path")
    result=subprocess.run(["rclone","cat",f"{remote.rstrip('/')}/{key}","--timeout=50s","--retries=2"],
                          check=True,capture_output=True,timeout=timeout)
    return result.stdout

def check(stage,remote,mode):
    stage=Path(stage)
    if mode=="media":
        rows=json.loads((stage/"metadata/new-files.json").read_text(encoding="utf-8"))
        for p in rows:
            key=p["key"]
            expected=p["sha256"]
            if not HEX.fullmatch(expected) or not key.startswith("originals/"):
                raise ValueError("Untrusted photo metadata")
            raw=remote_read(remote,key)
            if len(raw)!=p["bytes"] or hashlib.sha256(raw).hexdigest()!=expected:
                raise ValueError("Remote photo failed exact SHA-256 verification: "+key)
        print("MIMMI_PRIVATE_REMOTE_PHOTOS_VERIFIED",len(rows),flush=True)
        return len(rows)
    if mode=="catalog":
        expected=(stage/"metadata/catalog.json").read_bytes()
        remote=remote_read(remote,"metadata/catalog.json")
        if expected!=remote:
            raise ValueError("Private cloud metadata differs from staged manifest")
        data=json.loads(remote)
        if data.get("model")!="mimmi":
            raise ValueError("Mixed-model archive")
        print("MIMMI_PRIVATE_CATALOG_READBACK_PASS",data.get("summary"),flush=True)
        return len(data.get("albums",[]))
    raise ValueError("Unknown verification mode")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage",required=True)
    ap.add_argument("--remote",default="archive:MimmiArchive")
    ap.add_argument("--mode",choices=["media","catalog"],required=True)
    args=ap.parse_args()
    check(args.stage,args.remote,args.mode)
