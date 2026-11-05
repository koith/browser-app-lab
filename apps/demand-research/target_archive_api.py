"""Authenticated selected-public-account archive dispatch; never runs via public Pages.

An operator-configured fine-grained GitHub token with only actions:write
is necessary; no authorization, provider credentials or target media bytes
are ever sent to the browser. Submission means QUEUED, not SHA VERIFIED.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import urlsplit

from target_account_archive import profile_input
from demand_archive import CloudArchive
from verified_bundle_reader import names_from_cloud, load_verified_bundle

WORKFLOW = "intersection-target-account-bundle.yml"
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_last_request = None
_lock = asyncio.Lock()


def dispatch_enabled():
    token=os.getenv("DEMAND_ARCHIVE_DISPATCH_TOKEN","")
    repo=os.getenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    return len(token)>=24 and _REPO.fullmatch(repo) is not None


def _github_api(method,path,payload=None):
    if not dispatch_enabled():
        raise RuntimeError("private archive dispatch disabled")
    repo=os.getenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    url="https://api.github.com/repos/"+repo+"/"+path.lstrip("/")
    req=UrlRequest(url,method=method,
        data=(json.dumps(payload,separators=(",",":")).encode()
              if payload is not None else None),
        headers={"Authorization":"Bearer "+os.environ["DEMAND_ARCHIVE_DISPATCH_TOKEN"],
                 "Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2026-03-10",
                 "Content-Type":"application/json",
                 "User-Agent":"intersection-private-archive-dispatch"})
    try:
        with urlopen(req,timeout=20) as response:
            status=response.status
            body=response.read(20000)
        if status!=200:
            raise RuntimeError("GitHub run details unavailable")
        return json.loads(body)
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,
            json.JSONDecodeError) as error:
        raise RuntimeError("GitHub action request failed") from error


def dispatch(platform,account):
    # Since February 2026, requesting run details returns the exact run id;
    # 204 without a run id is NOT sufficient to track success.
    response=_github_api("POST","actions/workflows/"+WORKFLOW+"/dispatches",{
        "ref":"main","return_run_details":True,
        "inputs":{"platform":platform,"account":account,"max_pages":"2"}
    })
    run=response.get("workflow_run_id")
    if type(run) is not int or run<=0:
        raise RuntimeError("GitHub did not return a trackable workflow run")
    return run


def get_workflow_run(run_id):
    run=_github_api("GET","actions/runs/"+str(run_id))
    if (run.get("id")!=run_id or
        run.get("path")!=".github/workflows/"+WORKFLOW or
        run.get("event")!="workflow_dispatch" or
        run.get("head_branch")!="main"):
        raise RuntimeError("workflow run does not match requested archive")
    return run


def _encode(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(data):
    return base64.urlsafe_b64decode(data+"="*((-len(data))%4))


def make_receipt(request,run_id,platform,account):
    # The HttpOnly signed session is the receipt's HMAC key. Server restarts
    # do not lose outstanding job receipts; a different session cannot use one.
    session=request.cookies.get("demand_view","")
    if len(session)<50:
        raise RuntimeError("private archive session missing")
    payload=json.dumps({"run_id":run_id,"platform":platform,"account":account,
                        "at":int(time.time())},sort_keys=True,
                       separators=(",",":")).encode()
    token=_encode(payload)
    tag=hmac.new(session.encode(),("archive-job-v1:"+token).encode(),
                 hashlib.sha256).hexdigest()
    return token+"."+tag


def read_receipt(request,receipt,run_id):
    session=request.cookies.get("demand_view","")
    if (not isinstance(receipt,str) or len(receipt)>900 or
            not re.fullmatch(r"[A-Za-z0-9_-]{20,800}\.[a-f0-9]{64}",receipt)
            or len(session)<50):
        raise HTTPException(403,"Invalid private archive job receipt")
    token,signature=receipt.split(".",1)
    expected=hmac.new(session.encode(),("archive-job-v1:"+token).encode(),
                      hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):
        raise HTTPException(403,"Invalid private archive job receipt")
    try:
        item=json.loads(_decode(token))
        if (type(item) is not dict or type(item.get("run_id")) is not int
                or item["run_id"]!=run_id
                or type(item.get("at")) is not int
                or not 0<=time.time()-item["at"]<=30*86400
                or type(item.get("platform")) is not str
                or type(item.get("account")) is not str):
            raise ValueError("invalid receipt")
        profile_input(item["platform"],item["account"])
        return item
    except (ValueError,UnicodeError,KeyError,TypeError):
        raise HTTPException(403,"Invalid private archive job receipt") from None


def read_exact_verified_archive(run_id,platform,account):
    # A green GitHub check is NOT storage verification. Read the exact ZIP
    # for this Actions run from TeraBox and validate every object's SHA.
    remote=os.getenv("DEMAND_TERABOX_REMOTE","archive:DemandResearch")
    root=CloudArchive(remote)
    marker="-"+str(run_id)+"-"
    for filename in names_from_cloud(root):
        if marker not in filename:
            continue
        bundle=load_verified_bundle(root,filename)
        if (bundle.selected_platform!=platform or
                bundle.selected_account!=account):
            continue
        if bundle.source_state!="COMPLETE_CURRENT_PUBLIC_CURSOR":
            return {"state":"PARTIAL_BACKUP","remote_verified":True,
                    "posts":bundle.post_count,"objects":bundle.object_count,
                    "account_key":bundle.account}
        return {"state":"REMOTE_VERIFIED","remote_verified":True,
                "posts":bundle.post_count,"objects":bundle.object_count,
                "account_key":bundle.account}
    return None


def same_origin_operator(request):
    # The signed private site is behind a TLS-terminating reverse proxy.
    # Compare the browser Origin against the server's Host, not an internal
    # http:// proxy hop (which can make request.base_url differ from HTTPS).
    origin=request.headers.get("origin","")
    try:
        parsed=urlsplit(origin)
    except ValueError:
        raise HTTPException(403,"Private origin/intent required") from None
    host=request.headers.get("host","").lower()
    trusted=(parsed.scheme=="https" or
             (parsed.scheme=="http" and host.startswith(("localhost:","127.0.0.1:"))))
    if (not trusted or parsed.netloc.lower()!=host or
            origin!=parsed.scheme+"://"+parsed.netloc or
            parsed.username or parsed.password or
            request.headers.get("x-archive-intent","")!="selected-public-account-v1"):
        raise HTTPException(403,"Private origin/intent required")


def create_router(auth):
    router=APIRouter()

    @router.get("/api/target-archive/status")
    async def status(request:Request):
        auth(request)
        return JSONResponse({"enabled":bool(dispatch_enabled()),
                             "platforms":["bluesky","mastodon"],
                             "storage":"private_terabox",
                             "viewer_path":"/account-archive",
                             "jobs_pollable":bool(dispatch_enabled()),
                             "historical_completeness_guaranteed":False},
                            headers={"Cache-Control":"private, no-store"})

    @router.post("/api/target-archive/start")
    async def start(request:Request):
        global _last_request
        auth(request)
        same_origin_operator(request)
        if not dispatch_enabled():
            raise HTTPException(503,"Private archive dispatch not configured")
        raw=await request.body()
        if len(raw)>900:
            raise HTTPException(413,"Archive request too large")
        try:
            item=json.loads(raw)
            if not isinstance(item,dict):
                raise ValueError("invalid account request")
            platform=item["platform"]
            account=item["account"]
            if not isinstance(platform,str) or not isinstance(account,str):
                raise ValueError("invalid account request")
            profile_input(platform,account)
        except (ValueError,KeyError,TypeError):
            raise HTTPException(400,"Invalid public account selection") from None
        async with _lock:
            if _last_request is not None and time.monotonic()-_last_request<45:
                raise HTTPException(429,"Archive request throttled")
            try:
                run_id=await asyncio.to_thread(dispatch,platform,account)
                receipt=make_receipt(request,run_id,platform,account)
            except RuntimeError:
                raise HTTPException(502,"Private archive job could not be scheduled") from None
            _last_request=time.monotonic()
        return JSONResponse({"accepted":True,"state":"QUEUED_NOT_VERIFIED",
                             "run_id":run_id,"receipt":receipt,
                             "storage":"private_terabox",
                             "scope":"currently_public_only",
                             "completion_guaranteed":False},
                            status_code=202,
                            headers={"Cache-Control":"private, no-store"})


    @router.get("/api/target-archive/jobs/{run_id}")
    async def job_state(request:Request,run_id:int,
                        receipt:str=Query(...,min_length=80,max_length=900)):
        auth(request)
        if not 1<=run_id<=999999999999:
            raise HTTPException(400,"Invalid workflow run id")
        item=read_receipt(request,receipt,run_id)
        if not dispatch_enabled():
            raise HTTPException(503,"Private archive job status unavailable")
        try:
            run=await asyncio.to_thread(get_workflow_run,run_id)
        except RuntimeError:
            raise HTTPException(502,"Private archive status fetch failed") from None
        run_status=run.get("status")
        state="QUEUED"
        if run_status=="in_progress":state="RUNNING"
        if run_status=="completed":
            if run.get("conclusion")=="success":
                try:
                    verified=await asyncio.to_thread(read_exact_verified_archive,
                       run_id,item["platform"],item["account"])
                except (RuntimeError,ValueError,TypeError,KeyError):
                    verified=None
                if verified:
                    return JSONResponse({"run_id":run_id,**verified},
                                        headers={"Cache-Control":"private, no-store"})
                state="VERIFYING_STORAGE"
            else:
                state="FAILED"
        return JSONResponse({"run_id":run_id,"state":state,
                             "remote_verified":False,
                             "account_key":None,"posts":None,"objects":None},
                            headers={"Cache-Control":"private, no-store"})

    return router
