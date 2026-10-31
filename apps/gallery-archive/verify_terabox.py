#!/usr/bin/env python3
"""Read back EVERY photo and preview from private TeraBox before publishing catalog."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import selectors
import time
import tempfile
import re
from safe_rclone import diagnostic
from merge_incremental import checked_row


class RemoteCommandFailure(ValueError):
    def __init__(self,rc,count,size,detail):
        denied=bool(re.search(r'\b(?:401|403|429|451)\b|failed to login|access denied',detail,re.I))
        self.retryable_transport=(count<size and not denied and bool(re.search(
            r'i/o timeout|connection reset|unexpected EOF|TLS handshake timeout',detail,re.I)))
        self.returncode,self.received_bytes,self.expected_bytes=rc,count,size
        self.cause='transport_interruption' if self.retryable_transport else 'remote_command_failed'
        super().__init__(f'{self.cause}: exit={rc}, received={count}, expected={size}; '+diagnostic(detail)[:500])


def read_remote(row,remote,deadline_seconds=75,command=None):
    key,size,sha=row
    errors=tempfile.TemporaryFile()
    process=subprocess.Popen(command or ["rclone","cat",remote.rstrip("/")+"/"+key,
                              "--timeout=65s","--retries=1"],
                             stdout=subprocess.PIPE,stderr=errors)
    count=0;digest=hashlib.sha256();prefix=bytearray();deadline=time.monotonic()+deadline_seconds
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):
                    raise TimeoutError('Remote byte stream deadline exceeded')
                data=process.stdout.read1(256*1024)
                if not data:break
                count+=len(data)
                if len(prefix)<512:prefix.extend(data[:512-len(prefix)])
                if count>size:raise ValueError('Remote exceeds expected size')
                digest.update(data)
        rc=process.wait(timeout=max(.01,deadline-time.monotonic()))
        if rc:
            errors.seek(0)
            raise RemoteCommandFailure(rc,count,size,errors.read(32000).decode('utf-8','replace'))
        if count!=size or digest.hexdigest()!=sha:
            if count<=512:
                try:response=json.loads(prefix)
                except (ValueError,TypeError):response={}
                code=response.get('errno') if isinstance(response,dict) else None
                if type(code) is int:
                    # No raw provider message, request ID, URL or cookie leaves
                    # this process, and this exception is never retried.
                    raise ValueError('Owner provider response instead of image: errno='+str(code)+
                        ', verification_required='+str(code==400141)+', received='+str(count))
            raise ValueError(f'Remote integrity mismatch: received={count}, expected={size}; command exited successfully')
    finally:
        if process.poll() is None:
            process.kill();process.wait()
        process.stdout.close()
        errors.close()
    return key


def read_remote_with_recovery(row,remote,deadline_seconds=75,command=None):
    deadline=time.monotonic()+deadline_seconds
    try:return read_remote(row,remote,deadline_seconds,command)
    except RemoteCommandFailure as error:
        if not error.retryable_transport or deadline-time.monotonic()<=2:raise
        time.sleep(1)
        # The original total per-file deadline stays fixed. Never retry a
        # successful-command SHA mismatch, access denial or write operation.
        return read_remote(row,remote,deadline-time.monotonic(),command)

def verify(stage: Path, remote: str, workers: int, only_staged: bool = False):
    manifest=json.loads((stage/"metadata/catalog.json").read_text(encoding="utf-8"))
    specs=[];object_work={};photo_specs=[]
    for album in manifest["albums"]:
        for photo in album["images"]:
            checked_row(manifest['model'],album['id'],photo)
            specs.append((photo["key"],photo["bytes"],photo["sha256"]))
            if photo.get('preview'):
                specs.append((photo["preview"],photo["preview_bytes"],photo["preview_sha256"]))
            photo_specs.append([photo[k] for k in ('key','preview') if photo.get(k)])
            for field in ('key','preview'):
                if not photo.get(field):continue
                key=photo[field]
                if key in object_work and object_work[key]!=album['id']:
                    raise ValueError('Remote object belongs to conflicting works')
                object_work[key]=album['id']
    if only_staged:
        specs = [row for row in specs if (stage / row[0]).is_file()]
    selected_keys={r[0] for r in specs}
    photos=sum(bool(selected_keys.intersection(keys)) for keys in photo_specs)
    if not specs and not only_staged:
        raise ValueError("No photo bytes to verify")
    def readback(row):
        return read_remote_with_recovery(row,remote)
    work_specs={}
    for row in specs:work_specs.setdefault(object_work[row[0]],[]).append(row)
    work_passed={aid:0 for aid in work_specs};work_failed={aid:0 for aid in work_specs}
    passed=0
    errors=[]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future={executor.submit(readback,item):item[0] for item in specs}
        for f in as_completed(future):
            aid=object_work[future[f]]
            try: f.result();passed+=1;work_passed[aid]+=1
            except Exception as e:
                work_failed[aid]+=1
                errors.append({"name":future[f],"error":str(e)[:140]})
            if passed and passed%250==0:print("REMOTE_SHA256_READBACK_PROGRESS",passed,"/",len(specs),flush=True)
    report={"model":manifest["model"],"media_checked":len(specs),
            "full_SHA256_verified":passed,"failed":len(errors),
            "photos":photos,"errors":errors[:20],"work_verification":{}}
    for aid,rows in work_specs.items():
        result={'media_checked':len(rows),'full_SHA256_verified':work_passed[aid],
                'failed':work_failed[aid]}
        if not result['failed'] and result['media_checked']==result['full_SHA256_verified']:
            result['verified_specs_sha256']=hashlib.sha256(
                json.dumps(sorted(rows),separators=(',',':')).encode()).hexdigest()
        report['work_verification'][aid]=result
    if not errors and passed==len(specs):
        report['verified_specs_sha256']=hashlib.sha256(
            json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest()
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
