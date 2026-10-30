#!/usr/bin/env python3
"""Safely publish a SHA-verified metadata-only owner gallery index.

The GH_TOKEN runs on trusted main Actions and can update two exact public
catalogue paths. Image bytes, cloud object keys and credentials never leave
TeraBox. This script does not use arbitrary URLs or user-supplied GH paths.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

REPO = "koith/browser-app-lab"
ALLOWED = {"yui": "apps/yui-gallery/owner-index.json",
           "mimmi": "apps/mimmi-gallery/owner-index.json"}

def gh(*args: str, input_file: str | None = None):
    options = ["gh", "api", *args]
    if input_file:
        options.extend(("--input", input_file))
    return subprocess.run(options, capture_output=True, text=True, check=False)


def publish(model: str, source: Path, retries: int = 7) -> bool:
    if model not in ALLOWED or not 1 <= retries <= 10 or not os.environ.get("GH_TOKEN"):
        raise ValueError("Trusted model and Actions token required")
    data = source.read_bytes()
    loaded = json.loads(data)
    if (loaded.get("schema_version") != 1 or loaded.get("model") != model
            or loaded.get("storage") != "sha-verified-owner-metadata-only"
            or not isinstance(loaded.get("albums"), list)):
        raise ValueError("Refuse unsigned/unverified source-list content")
    path = ALLOWED[model]
    target = "repos/" + REPO + "/contents/" + path
    for attempt in range(retries):
        get = gh(target, "-H", "Accept: application/vnd.github+json")
        oldsha = None
        if get.returncode == 0:
            info = json.loads(get.stdout)
            oldsha = info.get("sha")
            olddata = base64.b64decode((info.get("content") or "").replace("\n", ""))
            if olddata == data:
                print("STATIC_OWNER_INDEX_UNCHANGED", model,flush=True)
                return False
        elif "404" not in get.stderr and "Not Found" not in get.stderr:
            raise RuntimeError("Failed to check current GitHub content status")
        payload={"message":f"gallery({model}): refresh exact SHA-verified owner album metadata only",
                 "branch":"main","content":base64.b64encode(data).decode("ascii")}
        if oldsha:
            payload["sha"]=oldsha
        with tempfile.NamedTemporaryFile("w",delete=False,suffix=".json",encoding="utf-8") as output:
            json.dump(payload, output)
            tmp=output.name
        try:
            update=gh("--method","PUT",target,input_file=tmp)
        finally:
            os.unlink(tmp)
        if update.returncode == 0:
            print("STATIC_OWNER_INDEX_PUBLISHED",model,
                  "physical_originals",loaded.get("physical_originals_indexed"),
                  "albums",len(loaded["albums"]),flush=True)
            return True
        if "409" not in update.stderr and "422" not in update.stderr and "conflict" not in update.stderr.lower():
            raise RuntimeError("GitHub owner-index update failed (credentials/content withheld)")
        time.sleep(min(2 * (attempt + 1), 10))
    raise RuntimeError("Owner index could not be committed after retries")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=sorted(ALLOWED),required=True)
    p.add_argument("--input",type=Path,required=True)
    a=p.parse_args()
    changed=publish(a.model,a.input)
    if changed and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as output:
            output.write("changed=true\n")
