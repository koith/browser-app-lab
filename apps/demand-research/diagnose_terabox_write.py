"""Isolated TeraBox write/readback diagnostic using tiny SYNTHETIC fixtures only.

Never touches live DemandResearch posts/catalogs, does not print credentials,
remote object names, personal data, or raw backend stderr.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path


def cmd(args, *, data=None, tolerate=False):
    p=subprocess.run(["rclone", *args, "--retries", "2", "--low-level-retries", "1"],
                     input=data, capture_output=True, timeout=75)
    if p.returncode and not tolerate:
        err=p.stderr.decode("utf-8","replace").lower()
        category=("auth" if re.search("403|denied|unauthorized|cookie",err)
                  else "rate" if re.search("429|rate.limit|throttl",err)
                  else "missing" if re.search("not found|does.not.exist",err)
                  else "quota" if re.search("quota|space|capacity",err)
                  else "network" if re.search("timeout|connection",err)
                  else "backend")
        raise RuntimeError("rclone_"+args[0]+"_"+category)
    return p.stdout if p.returncode==0 else None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def probe():
    run_id=os.environ.get("GITHUB_RUN_ID","")
    if not re.fullmatch(r"[0-9]{6,30}",run_id):
        raise ValueError("Missing numeric run id")
    if not os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("No private cloud secret")
    base="archive:DemandResearchQA/write-method-probe-"+run_id
    cmd(["lsf","archive:","--max-depth","1"])
    payloads={
        "copyto-json":b'{"kind":"SYNTHETIC_PUBLIC_QA","value":1}\n',
        "rcat-json":b'{"kind":"SYNTHETIC_PUBLIC_QA","value":2}\n',
        "copyto-long-post":b'{"kind":"SYNTHETIC_PUBLIC_QA","value":3}\n',
        "copyto-unicode-capture":json.dumps({"kind":"SYNTHETIC_QA","message":"검증"*1000},ensure_ascii=False).encode("utf-8"),
        "rcat-unicode-capture":json.dumps({"kind":"SYNTHETIC_QA","message":"확인"*1100},ensure_ascii=False).encode("utf-8"),
        "prodroot-unicode-capture":json.dumps({"kind":"SYNTHETIC_QA","message":"검사"*900},ensure_ascii=False).encode("utf-8"),
        "realmeta-versioned-catalog":json.dumps({"schema_version":1,"posts":[],"kind":"SYNTHETIC_QA"},ensure_ascii=False).encode("utf-8"),
    }
    outcomes={}
    with tempfile.TemporaryDirectory(prefix="terabox-write-qa-") as local:
        for label,raw in payloads.items():
            target_base=("archive:DemandResearch/qa/write-method-probe-"+run_id
                         if label=="prodroot-unicode-capture" else base)
            name=("/posts/"+"a"*40+"/post.json" if label=="copyto-long-post" else
                  "/posts/"+"b"*40+"/capture.json" if label=="copyto-unicode-capture" else
                  "/posts/"+"c"*40+"/capture.json" if label=="rcat-unicode-capture" else
                  "/posts/"+"d"*40+"/capture.json" if label=="prodroot-unicode-capture" else
                  "/"+label+".json")
            target=target_base+name
            if label=="realmeta-versioned-catalog":
                # Directly test the formerly failing production DIRECTORY, but
                # never place a file matching the production catalog name.
                for parent in ("metadata","metadata/catalogs"):
                    cmd(["mkdir","archive:DemandResearch/"+parent])
                target="archive:DemandResearch/metadata/catalogs/qa-synthetic-"+run_id+".json"
            local_file=Path(local)/("local-"+label+".json")
            local_file.write_bytes(raw)
            try:
                if label.startswith("rcat"):
                    cmd(["rcat",target],data=raw)
                else:
                    cmd(["copyto",str(local_file),target])
                verified=False
                mismatch=False
                for _ in range(4):
                    try:
                        actual=cmd(["cat",target],tolerate=True)
                    except (OSError,subprocess.TimeoutExpired):
                        actual=None
                    if actual is not None:
                        if actual==raw:
                            verified=True
                            break
                        mismatch=True
                    time.sleep(1)
                outcomes[label]={"success":verified,"mismatch":mismatch}
            except (OSError,subprocess.TimeoutExpired,RuntimeError) as e:
                outcomes[label]={"success":False,"error":str(e)}
    # A second write to the SAME synthetic object tests TeraBox's duplicate-name
    # and eventual-consistency semantics, without touching production objects.
    collision_target=base+"/collision-test.json"
    first=b'{"synthetic":"initial"}\n'
    second=b'{"synthetic":"replacement"}\n'
    try:
        cmd(["rcat",collision_target],data=first)
        time.sleep(1)
        initial=cmd(["cat",collision_target],tolerate=True)
        if initial!=first:
            outcomes["same-key-overwrite"]={"first_readback":False}
        else:
            try:
                cmd(["rcat",collision_target],data=second)
                time.sleep(2)
                replacement=cmd(["cat",collision_target],tolerate=True)
                outcomes["same-key-overwrite"]={
                    "first_readback":True,
                    "updated_bytes_visible":replacement==second,
                    "old_bytes_returned":replacement==first}
            except RuntimeError as e:
                outcomes["same-key-overwrite"]={
                    "first_readback":True,"error":str(e)}
    except RuntimeError as e:
        outcomes["same-key-overwrite"]={"error":str(e)}
    print("SYNTHETIC_TERABOX_WRITE_TEST",json.dumps(outcomes,sort_keys=True),flush=True)
    if not all(r.get("success") for name,r in outcomes.items() if name!="same-key-overwrite"):
        raise RuntimeError("Synthetic cloud write integrity failed; live archive remains unverified")


if __name__=="__main__":
    probe()
