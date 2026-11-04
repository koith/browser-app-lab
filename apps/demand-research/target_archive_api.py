"""Authenticated selected-public-account archive dispatch; never runs via public Pages.

An operator-configured fine-grained GitHub token with only actions:write
is necessary; no authorization, provider credentials or target media bytes
are ever sent to the browser. Submission means QUEUED, not SHA VERIFIED.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
import asyncio
import json
import os
import re
import time
from urllib.parse import urlsplit

from target_account_archive import profile_input

WORKFLOW = "intersection-target-account-archive.yml"
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_last_request = None
_lock = asyncio.Lock()


def dispatch_enabled():
    token=os.getenv("DEMAND_ARCHIVE_DISPATCH_TOKEN","")
    repo=os.getenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    return len(token)>=24 and _REPO.fullmatch(repo) is not None


def dispatch(platform,account):
    if not dispatch_enabled():
        raise RuntimeError("private archive dispatch disabled")
    repo=os.getenv("DEMAND_ARCHIVE_DISPATCH_REPO","koith/browser-app-lab")
    token=os.environ["DEMAND_ARCHIVE_DISPATCH_TOKEN"]
    url="https://api.github.com/repos/"+repo+"/actions/workflows/"+WORKFLOW+"/dispatches"
    payload=json.dumps({"ref":"main","inputs":{
        "platform":platform,"account":account,"max_pages":"2"
    }},separators=(",",":")).encode()
    req=UrlRequest(url,data=payload,method="POST",
        headers={"Authorization":"Bearer "+token,
                 "Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28",
                 "Content-Type":"application/json",
                 "User-Agent":"intersection-private-archive-dispatch"})
    try:
        with urlopen(req,timeout=20) as response:
            if response.status!=204:
                raise RuntimeError("GitHub archive dispatch was not accepted")
    except (HTTPError,URLError,TimeoutError,OSError) as error:
        raise RuntimeError("GitHub archive dispatch not accepted") from error


def same_origin_operator(request):
    """Require an exact browser Origin host and explicit operator intent.

    Render and other TLS terminators forward HTTPS to the ASGI app over
    internal HTTP. Comparing the external Origin to request.base_url's
    *internal scheme* rejects legitimate HTTPS POSTs with a false 403.
    Match the exact browser-visible Host instead, and require HTTPS except
    for the explicitly local development test hosts. Never trust arbitrary
    forwarded headers or a loose suffix/domain match.
    """
    if request.headers.get("x-archive-intent","")!="selected-public-account-v1":
        raise HTTPException(403,"Private origin/intent required")
    origin=request.headers.get("origin","")
    try:
        parsed=urlsplit(origin)
        host=request.headers.get("host","").lower()
        same_host=(parsed.netloc.lower()==host and
                   parsed.hostname is not None and not parsed.username and
                   not parsed.password and
                   origin==parsed.scheme+"://"+parsed.netloc)
        secure=(parsed.scheme=="https" or
                (parsed.scheme=="http" and
                 parsed.hostname in ("localhost","127.0.0.1","testserver")))
    except ValueError:
        same_host=secure=False
    if not (same_host and secure):
        raise HTTPException(403,"Private origin/intent required")


def create_router(auth):
    router=APIRouter()

    @router.get("/api/target-archive/status")
    async def status(request:Request):
        auth(request)
        return JSONResponse({"enabled":bool(dispatch_enabled()),
                             "platforms":["bluesky","mastodon"],
                             "storage":"private_terabox",
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
                await asyncio.to_thread(dispatch,platform,account)
            except RuntimeError:
                raise HTTPException(502,"Private archive job could not be scheduled") from None
            _last_request=time.monotonic()
        return JSONResponse({"accepted":True,"state":"QUEUED_NOT_VERIFIED",
                             "storage":"private_terabox",
                             "scope":"currently_public_only",
                             "completion_guaranteed":False},
                            status_code=202,
                            headers={"Cache-Control":"private, no-store"})

    return router
