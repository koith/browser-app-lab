#!/usr/bin/env python3
"""Read back EVERY photo and preview from private TeraBox before publishing catalog."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess

def verify(stage: Path, remote: str, workers: int, only_staged: bool = False):
    manifest=json.loads((stage/"metadata/catalog.json").read_text(encoding="utf-8"))
    specs=[]
    for album in manifest["albums"]:
        for photo in album["images"]:
            specs.append((photo["key"],photo["bytes"],photo["sha256"]))
            specs.append((photo["preview"],photo["preview_bytes"],photo["preview_sha256"]))
    if only_staged:
        specs = [row for row in specs if (stage / row[0]).is_file()]
    if not specs and not only_staged:
        raise ValueError("No photo bytes to verify")
    def readback(row):
        key,size,sha=row
        # Streaming subprocess avoids storing large albums in memory.
        process=subprocess.Popen(["rclone","cat",remote.rstrip("/")+"/"+key,
                                  "--timeout=65s","--retries=1"],
                                 stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        count=0;digest=hashlib.sha256()
        try:
            while True:
                data=process.stdout.read(256*1024)
                if not data:break
                count+=len(data)
                if count>size:raise ValueError("Remote exceeds expected size")
                digest.update(data)
            rc=process.wait(timeout=75)
            if rc or count!=size or digest.hexdigest()!=sha:
                raise ValueError("SHA or length readback mismatch")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
        return key
    passed=0
    errors=[]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future={executor.submit(readback,item):item[0] for item in specs}
        for f in as_completed(future):
            try: f.result();passed+=1
            except Exception as e:errors.append({"name":future[f],"error":str(e)[:140]})
            if passed and passed%250==0:print("REMOTE_SHA256_READBACK_PROGRESS",passed,"/",len(specs),flush=True)
    report={"model":manifest["model"],"media_checked":len(specs),
            "full_SHA256_verified":passed,"failed":len(errors),
            "photos":len(specs)//2,"errors":errors[:20]}
    (stage/"metadata/remote-verification.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("REMOTE_FULL_BYTE_SHA256_AUDIT",json.dumps(report,ensure_ascii=False),flush=True)
    if errors or passed!=len(specs):raise ValueError("TeraBox remote failed full byte verification")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--remote",required=True)
    p.add_argument("--workers",type=int,default=8)
    p.add_argument("--only-staged",action="store_true",
                   help="For incremental import, only re-read files newly present in local staging")
    a=p.parse_args()
    if not 1<=a.workers<=12:raise SystemExit("workers must be 1..12")
    verify(a.stage,a.remote,a.workers,a.only_staged)
