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
from demand_archive import CloudArchive, QueueStorageDenied
from verified_bundle_reader import names_from_cloud, load_verified_bundle
import backup_queue
import github_temp_bundle

WORKFLOW = "intersection-target-account-bundle.yml"
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_last_request = None
_lock = asyncio.Lock()
_public_run_cache = {}


def dispatch_enabled():
    token=os.getenv("DEMAND_ARCHIVE_DISPATCH_TOKEN","")
    repo=os.getenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    return len(token)>=24 and _REPO.fullmatch(repo) is not None


def can_start():
    # The alternative OIDC-pulled durable queue does not need a permanent
    # GitHub personal access token on Render.
    return dispatch_enabled() or backup_queue.enabled()


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
    if dispatch_enabled():
        run=_github_api("GET","actions/runs/"+str(run_id))
    else:
        # GitHub run metadata for a public repository is public; no private
        # workflow token leaves GitHub Actions or gets embedded in the page.
        cached=_public_run_cache.get(run_id)
        if cached is not None and time.monotonic()-cached[0]<50:
            run=cached[1]
        else:
            repo=os.getenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
            if _REPO.fullmatch(repo) is None:
                raise RuntimeError("Untrusted repository")
            request=UrlRequest("https://api.github.com/repos/"+repo+
                      "/actions/runs/"+str(run_id),
                      headers={"Accept":"application/vnd.github+json",
                               "User-Agent":"intersection-public-workflow-status"})
            try:
                with urlopen(request,timeout=12) as response:
                    if response.status!=200:
                        raise RuntimeError("GitHub status unavailable")
                    run=json.loads(response.read(100000))
            except (HTTPError,URLError,ValueError,TimeoutError,OSError):
                raise RuntimeError("GitHub status unavailable") from None
            _public_run_cache.clear()
            _public_run_cache[run_id]=(time.monotonic(),run)
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


def _receipt_signing_key(request):
    # Public app mode intentionally has no login cookie. Using the old
    # cookie-only signer made POST /start write a durable cloud request and
    # then fail with HTTP 502 while generating the receipt. It also left the
    # job progress route unusable. A bearer receipt instead authenticates
    # exactly the job the requester just queued, without exposing TOKEN.
    if os.getenv("DEMAND_PUBLIC_ARCHIVE_MODE","0")=="1":
        from gateway import TOKEN
        if len(TOKEN)<24:
            raise RuntimeError("archive receipt signer unavailable")
        return TOKEN.encode(),"archive-job-public-v2:"
    session=request.cookies.get("demand_view","")
    if len(session)<50:
        raise RuntimeError("private archive session missing")
    return session.encode(),"archive-job-v1:"


def make_receipt(request,run_id,platform,account):
    key,context=_receipt_signing_key(request)
    payload=json.dumps({"run_id":run_id,"platform":platform,"account":account,
                        "at":int(time.time())},sort_keys=True,
                       separators=(",",":")).encode()
    token=_encode(payload)
    tag=hmac.new(key,(context+token).encode(),hashlib.sha256).hexdigest()
    return token+"."+tag


def read_receipt(request,receipt,run_id):
    if (not isinstance(receipt,str) or len(receipt)>900 or
            not re.fullmatch(r"[A-Za-z0-9_-]{20,800}\.[a-f0-9]{64}",receipt)):
        raise HTTPException(403,"Invalid archive job receipt")
    try:
        key,context=_receipt_signing_key(request)
    except RuntimeError:
        raise HTTPException(403,"Invalid archive job receipt") from None
    token,signature=receipt.split(".",1)
    expected=hmac.new(key,(context+token).encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):
        raise HTTPException(403,"Invalid archive job receipt")
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
        raise HTTPException(403,"Invalid archive job receipt") from None


def read_exact_verified_archive(run_id,platform,account):
    if github_temp_bundle.enabled():
        # A green workflow alone never means backup success. Read actual
        # encrypted GitHub release bytes, authenticate AES-GCM and check the
        # embedded per-object SHA256 manifest before displaying any media.
        bundle=github_temp_bundle.run_bundle(run_id,account)
        if bundle is None or bundle.selected_platform!=platform:
            return None
        complete=bundle.source_state=="COMPLETE_CURRENT_PUBLIC_CURSOR"
        return {"state":"REMOTE_VERIFIED" if complete else "PARTIAL_BACKUP",
                "remote_verified":True,
                "storage":"github_encrypted_temporary",
                "posts":bundle.post_count,"objects":bundle.object_count,
                "account_key":bundle.account,
                "source_state":bundle.source_state,
                "temporary":True}
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
        return JSONResponse({"enabled":bool(can_start()),
                             "platforms":["bluesky","mastodon"],
                             "storage":"github_encrypted_temporary" if github_temp_bundle.enabled() else "private_terabox",
                             "viewer_path":"/account-archive",
                             "jobs_pollable":bool(can_start()),
                             "historical_completeness_guaranteed":False},
                            headers={"Cache-Control":"private, no-store"})

    @router.post("/api/target-archive/start")
    async def start(request:Request):
        global _last_request
        auth(request)
        same_origin_operator(request)
        if not can_start():
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
            normalized=profile_input(platform,account)
            if platform=="bluesky" and not account.startswith("https://"):
                account=normalized
        except (ValueError,KeyError,TypeError):
            raise HTTPException(400,"Invalid public account selection") from None
        async with _lock:
            if _last_request is not None and time.monotonic()-_last_request<45:
                raise HTTPException(429,"Archive request throttled")
            try:
                if backup_queue.enabled():
                    run_id=await asyncio.to_thread(
                        backup_queue.create_request,platform,account)
                else:
                    run_id=await asyncio.to_thread(dispatch,platform,account)
                receipt=make_receipt(request,run_id,platform,account)
            except QueueStorageDenied:
                _last_request=time.monotonic()
                return JSONResponse({"accepted":False, "code":"storage_read_denied",
                    "detail":"TeraBox가 백업 요청의 원격 읽기를 거부했습니다. 접수와 무결성을 확인하지 못했습니다. 저장소 인증·다운로드 권한 확인이 필요합니다."},
                    status_code=503, headers={"Cache-Control":"private, no-store", "Retry-After":"45"})
            except RuntimeError:
                raise HTTPException(502,"Private archive job could not be scheduled") from None
            _last_request=time.monotonic()
        return JSONResponse({"accepted":True,"state":"QUEUED_NOT_VERIFIED",
                             "run_id":run_id,"receipt":receipt,
                             "storage":"github_encrypted_temporary" if github_temp_bundle.enabled() else "private_terabox",
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
        if not can_start():
            raise HTTPException(503,"Private archive job status unavailable")
        workflow_id=run_id
        if backup_queue.enabled():
            try:
                queued=await asyncio.to_thread(backup_queue.state,run_id)
            except (RuntimeError,ValueError):
                raise HTTPException(503,"Private queue status unavailable") from None
            if queued is None:
                raise HTTPException(404,"Unknown private backup request")
            accepted=queued.get("accepted")
            if accepted is None:
                return JSONResponse({"run_id":run_id,"state":"QUEUED",
                         "remote_verified":False,"account_key":None},
                         headers={"Cache-Control":"private, no-store"})
            workflow_id=accepted["workflow_run_id"]
        try:
            run=await asyncio.to_thread(get_workflow_run,workflow_id)
        except RuntimeError:
            raise HTTPException(502,"Private archive status fetch failed") from None
        run_status=run.get("status")
        state="QUEUED"
        if run_status=="in_progress":state="RUNNING"
        if run_status=="completed":
            if run.get("conclusion")=="success":
                try:
                    verified=await asyncio.to_thread(read_exact_verified_archive,
                       workflow_id,item["platform"],item["account"])
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
