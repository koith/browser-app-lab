"""Private TeraBox post viewer gateway. Never expose cloud credentials in Pages."""
from __future__ import annotations
import asyncio, hashlib, hmac, json, os, re, secrets, time
from typing import AsyncIterator
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app=FastAPI(title="Demand Research Private Cloud",docs_url=None,redoc_url=None)
app.add_middleware(CORSMiddleware,allow_origins=["https://koith.github.io","http://localhost:8765"],allow_methods=["GET","OPTIONS"],allow_headers=["Authorization","Content-Type"])
REMOTE=os.getenv("DEMAND_TERABOX_REMOTE","archive:DemandResearch").rstrip("/")
TOKEN=os.getenv("DEMAND_VIEWER_TOKEN","")
COOKIE=os.getenv("RCLONE_CONFIG_ARCHIVE_COOKIE","")
ID_RE=re.compile(r"^[a-f0-9]{16,64}$")
SHA_RE=re.compile(r"^[a-f0-9]{64}$")
MIMES={"image/jpeg","image/png","image/webp","image/avif","video/mp4","video/webm","video/quicktime"}
MAX_SIZE=1500000000
_cache={"at":0.0,"posts":None}
_lock=asyncio.Lock()

def configured():
    return len(TOKEN)>=24 and bool(COOKIE) and REMOTE.startswith("archive:")

def check_auth(value):
    if not configured():
        raise HTTPException(status_code=503,detail="TeraBox gateway not connected")
    if not value or not secrets.compare_digest(value,"Bearer "+TOKEN):
        raise HTTPException(status_code=401,detail="Viewer authentication required")

def validate_catalog(obj):
    if type(obj) is not dict or obj.get("schema_version")!=1 or type(obj.get("posts")) is not list:
        raise ValueError("Invalid cloud catalog")
    ids=set()
    for post in obj["posts"]:
        if type(post) is not dict or not ID_RE.fullmatch(str(post.get("id",""))) or post["id"] in ids:
            raise ValueError("Invalid or duplicate post ID")
        ids.add(post["id"])
        if not isinstance(post.get("text"),str) or len(post["text"])>30000:
            raise ValueError("Invalid post text")
        if type(post.get("media")) is not list or len(post["media"])>100:
            raise ValueError("Invalid media list")
        for m in post["media"]:
            if type(m) is not dict:
                raise ValueError("Invalid media")
            path=m.get("key")
            if not isinstance(path,str) or not path.startswith("posts/"+post["id"]+"/media/") or ".." in path or "\\" in path or "%" in path or len(path)>300:
                raise ValueError("Unsafe media path")
            if m.get("mime") not in MIMES or type(m.get("bytes")) is not int or not 0<m["bytes"]<=MAX_SIZE:
                raise ValueError("Invalid media type or size")
            if not SHA_RE.fullmatch(str(m.get("sha256",""))) or m.get("remote_verified") is not True:
                raise ValueError("Unverified media in catalog")
    return obj["posts"]

async def remote_bytes(path,cap=15000000):
    proc=await asyncio.create_subprocess_exec("rclone","cat",REMOTE+"/"+path,"--timeout=40s","--retries=2",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    data=bytearray()
    try:
        while True:
            b=await asyncio.wait_for(proc.stdout.read(65536),timeout=60)
            if not b: break
            data.extend(b)
            if len(data)>cap: raise HTTPException(413,"Catalog too large")
        if await asyncio.wait_for(proc.wait(),timeout=15):
            raise HTTPException(502,"Remote catalog read failed")
        return bytes(data)
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()

async def get_catalog():
    if _cache["posts"] is not None and time.time()-_cache["at"]<90:
        return _cache["posts"]
    async with _lock:
        if _cache["posts"] is not None and time.time()-_cache["at"]<90:
            return _cache["posts"]
        try:
            posts=validate_catalog(json.loads(await remote_bytes("metadata/catalog.json")))
        except (ValueError,json.JSONDecodeError) as e:
            raise HTTPException(502,"Cloud catalog validation failure") from e
        _cache.update(at=time.time(),posts=posts)
        return posts

def media_signature(post_id,index,expires):
    return hmac.new(TOKEN.encode(),(post_id+":"+str(index)+":"+str(expires)).encode(),hashlib.sha256).hexdigest()

@app.get("/api/health")
async def health():
    return {"service":"demand-research-terabox","cloud":"terabox","configured":configured(),"data_cached":_cache["posts"] is not None}

@app.get("/api/posts")
async def list_posts(authorization:str|None=Header(None),offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=60),q:str=Query("",max_length=100)):
    check_auth(authorization)
    posts=await get_catalog()
    if q: posts=[p for p in posts if q.casefold() in p["text"].casefold()]
    posts=sorted(posts,key=lambda p:p.get("posted_at",""),reverse=True)
    exp=int(time.time())+1200
    output=[]
    for post in posts[offset:offset+limit]:
        media=[]
        for i,m in enumerate(post["media"]):
            media.append({"kind":m.get("kind","unknown"),"mime":m["mime"],"bytes":m["bytes"],"verified":True,
                          "url":"/api/media/"+post["id"]+"/"+str(i)+"?exp="+str(exp)+"&sig="+media_signature(post["id"],i,exp)})
        output.append({"id":post["id"],"platform":post.get("platform","unknown"),"posted_at":post.get("posted_at",""),
                       "text":post["text"],"media":media,"reply_count":post.get("reply_count",0),
                       "source_url":post.get("source_url",""),"capture_status":"remote_verified"})
    return {"total":len(posts),"offset":offset,"limit":limit,"posts":output,"storage":"TeraBox"}

async def remote_stream(path,start,length)->AsyncIterator[bytes]:
    proc=await asyncio.create_subprocess_exec("rclone","cat",REMOTE+"/"+path,"--offset",str(start),"--count",str(length),
              "--timeout=60s","--retries=2",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    sent=0
    try:
        while sent<length:
            data=await asyncio.wait_for(proc.stdout.read(min(262144,length-sent)),timeout=90)
            if not data: break
            sent+=len(data)
            yield data
        if await asyncio.wait_for(proc.wait(),timeout=20) or sent!=length:
            print("REMOTE_MEDIA_TRUNCATED",path,sent,length,flush=True)
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()

@app.get("/api/media/{post_id}/{index}")
async def media(post_id:str,index:int,request:Request,exp:int,sig:str):
    if not configured():raise HTTPException(503,"Cloud gateway not configured")
    if not ID_RE.fullmatch(post_id) or index<0:raise HTTPException(400,"Invalid reference")
    now=int(time.time())
    if not now<exp<=now+3600 or not secrets.compare_digest(sig,media_signature(post_id,index,exp)):
        raise HTTPException(403,"Expired/invalid media link")
    posts=await get_catalog()
    post=next((p for p in posts if p["id"]==post_id),None)
    if post is None or index>=len(post["media"]):raise HTTPException(404,"Not found")
    item=post["media"][index]
    total=item["bytes"]
    start,end,status=0,total-1,200
    raw=request.headers.get("range","")
    if raw:
        match=re.fullmatch(r"bytes=(\d*)-(\d*)",raw)
        if not match or (not match.group(1) and not match.group(2)):
            raise HTTPException(416,"Invalid range",headers={"Content-Range":"bytes */"+str(total)})
        if match.group(1):
            start=int(match.group(1));end=min(int(match.group(2)),total-1) if match.group(2) else total-1
        else:
            start=max(0,total-int(match.group(2)))
        if start>=total or end<start:
            raise HTTPException(416,"Unsatisfiable range",headers={"Content-Range":"bytes */"+str(total)})
        status=206
    headers={"Accept-Ranges":"bytes","Content-Length":str(end-start+1),
             "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"}
    if status==206: headers["Content-Range"]="bytes "+str(start)+"-"+str(end)+"/"+str(total)
    return StreamingResponse(remote_stream(item["key"],start,end-start+1),status_code=status,media_type=item["mime"],headers=headers)
