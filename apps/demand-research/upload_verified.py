"""Publish permissioned post bundles to private TeraBox with byte-for-byte readback.

Input stage:
  posts/<hex-id>/post.json          (one original post + media references)
  posts/<hex-id>/media/<filename>  (authorized original bytes)
Do not place stage in a public repository. Upload media first; publish catalog LAST.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path

VALID_ID=re.compile(r"^[a-f0-9]{16,64}$")
VALID_NAME=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,150}$")
VALID_MIME={"image/jpeg","image/png","image/webp","image/avif","video/mp4","video/webm","video/quicktime"}
MAX_MEDIA=1500000000

def digest(path):
    sha=hashlib.sha256()
    n=0
    with open(path,"rb") as f:
        while b:=f.read(1024*1024):
            sha.update(b);n+=len(b)
    return n,sha.hexdigest()

def remote_digest(remote,key,max_size):
    target=remote.rstrip("/")+"/"+key
    p=subprocess.Popen(["rclone","cat",target,"--timeout=65s","--retries=2"],
                        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    sha=hashlib.sha256();n=0
    try:
        while b:=p.stdout.read(256*1024):
            n+=len(b)
            if n>max_size:
                p.kill();p.wait()
                raise ValueError("Remote file exceeds declared size: "+key)
            sha.update(b)
        if p.wait(timeout=120):
            raise RuntimeError("Remote read failed: "+key)
    finally:
        if p.poll() is None:
            p.kill();p.wait()
    return n,sha.hexdigest()

def run(*args):
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)

def publish(stage,remote):
    stage=Path(stage).resolve()
    if not stage.is_dir() or not (stage/"posts").is_dir():
        raise ValueError("Missing local post-bundle folder")
    if not os.getenv("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("TeraBox secret is missing; upload was not attempted")
    if not remote.startswith("archive:") or "/" in remote.split(":",1)[0]:
        raise ValueError("Invalid TeraBox remote")
    posts=[]
    for folder in sorted((stage/"posts").iterdir()):
        if not folder.is_dir():continue
        pid=folder.name
        if not VALID_ID.fullmatch(pid):raise ValueError("Unsafe post directory name")
        manifest=folder/"post.json"
        if not manifest.is_file():raise ValueError("Missing post manifest: "+pid)
        post=json.loads(manifest.read_text(encoding="utf-8"))
        if post.get("id")!=pid or not isinstance(post.get("text"),str) or not isinstance(post.get("media"),list):
            raise ValueError("Invalid post schema: "+pid)
        for m in post["media"]:
            key=m.get("key","")
            prefix="posts/"+pid+"/media/"
            if (not isinstance(key,str) or not key.startswith(prefix)
                or not VALID_NAME.fullmatch(key[len(prefix):])
                or m.get("mime") not in VALID_MIME):
                raise ValueError("Invalid media path/type: "+pid)
            path=stage/key
            if not path.is_file():raise ValueError("Missing media file: "+key)
            size,sha=digest(path)
            if not 0<size<=MAX_MEDIA or size!=m.get("bytes") or sha!=m.get("sha256"):
                raise ValueError("Local integrity failure: "+key)
            m["remote_verified"]=False
        posts.append(post)
    if not posts:
        raise ValueError("No post bundles found; nothing uploaded")
    # Stage is copied to a private remote. Never push raw staged posts to GitHub.
    run("rclone","copy",str(stage/"posts"),remote+"/posts",
        "--transfers","3","--checkers","4","--retries","3")
    verified=[]
    for post in posts:
        for m in post["media"]:
            size,sha=remote_digest(remote,m["key"],m["bytes"]+1)
            if size!=m["bytes"] or sha!=m["sha256"]:
                raise ValueError("Remote integrity mismatch: "+m["key"])
            m["remote_verified"]=True
            verified.append({"key":m["key"],"bytes":size,"sha256":sha})
        # Create a post-local canonical JSON, even if catalog exists.
        blob=(json.dumps(post,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
        key="posts/"+post["id"]+"/post.json"
        run("rclone","rcat",remote+"/"+key,"--size",str(len(blob))) if False else None
        subprocess.run(["rclone","rcat",remote+"/"+key],input=blob,check=True,
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        size,sha=remote_digest(remote,key,len(blob)+1)
        if size!=len(blob) or sha!=hashlib.sha256(blob).hexdigest():
            raise ValueError("Remote post JSON mismatch: "+key)
        verified.append({"key":key,"bytes":size,"sha256":sha})
    # Reuse any existing older posts when writing an incremental catalog.
    # This script requires a full export of records; it deliberately does NOT
    # overwrite a catalog on the remote without an explicit replace switch.
    content=(json.dumps({"schema_version":1,"posts":posts},ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    if os.getenv("DEMAND_ALLOW_CATALOG_REPLACE")!="true":
        # Refuse to destroy older catalog by accident. A new deployment can
        # upload to an empty DemandResearch prefix, or opt into replacement.
        test=subprocess.run(["rclone","lsf",remote+"/metadata/catalog.json"],
                            capture_output=True,text=True)
        if test.returncode==0 and test.stdout.strip():
            raise RuntimeError("Existing catalog detected; explicit replacement approval required")
    key="metadata/catalog.json"
    subprocess.run(["rclone","rcat",remote+"/"+key],input=content,check=True,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    size,sha=remote_digest(remote,key,len(content)+1)
    if size!=len(content) or sha!=hashlib.sha256(content).hexdigest():
        raise ValueError("Cloud catalog readback did not match")
    return {"posts":len(posts),"verified_files":len(verified),"catalog_sha256":sha,"remote":remote}

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--stage",required=True)
    a.add_argument("--remote",default="archive:DemandResearch")
    p=a.parse_args()
    print(json.dumps(publish(p.stage,p.remote),ensure_ascii=False))
