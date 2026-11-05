"""Non-destructive live TeraBox upload-method probe (synthetic bytes only).

Prints only operation name, source-independent error category and verified SHA result.
No tokens, cookies, real account data, paths or raw backend stderr reach Actions.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

RUN=re.sub(r"[^0-9]","",os.getenv("GITHUB_RUN_ID",""))[:25]
if len(RUN)<6:
    raise SystemExit("GitHub Actions run identifier required")
ROOT="archive:DemandResearch"
PAYLOAD=(b"INTERSECTION synthetic nonprivate TeraBox upload integrity probe\n"*4)
BIG_PAYLOAD=PAYLOAD*2000
CASES=[
    ("copyto_short","copyto","upload-probe-"+RUN+"-s.bin",PAYLOAD,None),
    ("rcat_short","rcat","upload-probe-"+RUN+"-r.bin",PAYLOAD,None),
    ("copy_short","copy","upload-probe-"+RUN+"-c.bin",PAYLOAD,None),
    ("copyto_long","copyto","upload-probe-"+RUN+"-l-"+("x"*134)+".bin",PAYLOAD,None),
    ("copyto_1mb","copyto","upload-probe-"+RUN+"-b.bin",BIG_PAYLOAD,None),
    ("copyto_alternate","copyto","upload-probe-"+RUN+"-a.bin",PAYLOAD,"https://nephobox.com"),
    ("copyto_nested","copyto","metadata/probe/"+RUN+"-n.bin",PAYLOAD,None),
]

def classify(output:bytes)->str:
    msg=output.decode("utf8","replace").lower()
    if any(w in msg for w in ("not found","does not exist","no such file","directory not found")):return "missing"
    if any(w in msg for w in ("429","rate limit","too many requests")):return "rate_limited"
    if any(w in msg for w in ("403","unauthorized","permission","cookie")):return "authorization"
    if any(w in msg for w in ("timeout","timed out","deadline")):return "timeout"
    if any(w in msg for w in ("quota","capacity","space")):return "capacity"
    if any(w in msg for w in ("500","502","503","504")):return "server"
    return "backend_rejected"

def call(args, *, payload=None, limit=55):
    try:
        p=subprocess.run(["rclone",*args],input=payload,capture_output=True,
                         timeout=limit,check=False)
    except subprocess.TimeoutExpired:
        return False,b"","timeout"
    if p.returncode:
        return False,b"",classify(p.stderr)
    return True,p.stdout,"ok"

results={}
with tempfile.TemporaryDirectory(prefix="int-probe-") as d:
    for name,mode,rel,body,domain in CASES:
        target=ROOT+"/"+rel
        src=Path(d)/"synthetic.bin"
        src.write_bytes(body)
        args=[]
        if mode=="copyto":args=["copyto",str(src),target]
        elif mode=="rcat":args=["rcat",target]
        elif mode=="copy":
            folder=Path(d)/("case-"+name)
            folder.mkdir(exist_ok=True)
            (folder/rel.rsplit("/",1)[-1]).write_bytes(body)
            args=["copy",str(folder),ROOT]
        extra=(["--terabox-domain",domain] if domain else [])
        start=time.monotonic()
        ok,_,category=call([*args,*extra,"--retries","1","--timeout","15s"],
                           payload=body if mode=="rcat" else None)
        verified=False
        if ok:
            ok_read,actual,_=call(["cat",target,*extra,"--retries","1","--timeout","15s"],limit=35)
            verified=ok_read and hashlib.sha256(actual).digest()==hashlib.sha256(body).digest()
            if not verified:category="readback_missing_or_sha_mismatch"
        results[name]={"write":ok,"sha256_verified":verified,
                       "failure_class":None if verified else category,
                       "seconds":round(time.monotonic()-start,1)}
        print("TERABOX_SYNTHETIC_METHOD "+json.dumps({name:results[name]},sort_keys=True),flush=True)
print("TERABOX_SYNTHETIC_SUMMARY "+json.dumps(results,sort_keys=True),flush=True)
if not any(v["sha256_verified"] for v in results.values()):
    raise SystemExit("no synthetic upload method produced remote SHA readback")
