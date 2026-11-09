"""Authenticated read-only SNS-like viewer of verified private account archives.

Endpoints never fetch provider posts. They expose only previously stored private
TeraBox records to the owner of the private gateway's signed HttpOnly session.
No repo logs/analytics, broad CORS, unverified media or account identifier leaks.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from demand_archive import CloudArchive, sha256
import github_temp_bundle
from target_account_archive import REGISTRY_RE, archive_key, account_cloud
from target_account_enrichment import PROFILE_FILE_RE, THREAD_FILE_RE
from verified_bundle_reader import (
    BundleAccountCloud, available_bundles, latest_account_bundle, BundleInvalid,
)

HEX40=re.compile(r"^[a-f0-9]{40}$")
GRAPH_PAGE=re.compile(r"^(followers|following)-([0-9]{8})\.json$")
VIEW_DIR=Path(__file__).resolve().parent
CACHE_HEADERS={"Cache-Control":"private, no-store",
               "X-Content-Type-Options":"nosniff",
               "Referrer-Policy":"no-referrer",
               "X-Robots-Tag":"noindex, nofollow"}


def open_root():
    return CloudArchive()


class _BoundedZipRoot:
    """Keep unreliable private-cloud reads from stalling the GitHub fallback.

    This wrapper is only for immutable ZIP discovery. Legacy per-record paths
    continue using the original CloudArchive and its own timeout policy.
    """
    def __init__(self,root):
        self.root=root
        self.remote=root.remote
        self.authorization_denied=False

    def command(self,args,*,data=None,timeout=150,allow_missing=False):
        operation=args[0] if args and args[0] in ("lsf","cat") else "other"
        # When a provider denies one immutable ZIP, do not issue another
        # eight known-denied requests in the same collection pass.
        if self.authorization_denied and operation=="cat":
            raise RuntimeError("Private ZIP read unavailable (authorization)")
        # The exact 17.6 MB original ZIP was independently SHA verified on
        # GitHub Actions. An 18-second per-operation listing/read budget dropped
        # this same ZIP on the slower Render free instance. Keep a finite
        # per-operation bound and let GitHub remain a separate safe fallback.
        budget=min(timeout,55 if operation=="cat" else 30)
        started=time.monotonic()
        outcome="error"
        try:
            response=self.root.command(args,data=data,timeout=budget,
                                       allow_missing=allow_missing)
            outcome="missing" if response is None else "ok"
            return response
        except RuntimeError as error:
            if isinstance(error.__cause__,subprocess.TimeoutExpired):
                outcome="process_timeout"
            else:
                for category in ("authorization","missing","rate_limited",
                                 "network_timeout","capacity","remote_server",
                                 "backend_rejected"):
                    if "("+category+")" in str(error):
                        outcome=category
                        if category=="authorization":
                            self.authorization_denied=True
                        break
            raise
        finally:
            # Fixed categories and durations ONLY; never log original account
            # IDs, post text, private path, ZIP bytes, cookie, or provider body.
            print("INTERSECTION_ZIP_SOURCE_READ",
                  "operation="+operation,
                  "outcome="+outcome,
                  "elapsed_ms="+str(round((time.monotonic()-started)*1000)),
                  flush=True)


_ZIP_SESSION_CACHE=None
_ZIP_SESSION_LOCK=threading.Lock()
ZIP_VERIFIED_SESSION_SECONDS=90
ZIP_UNAVAILABLE_BACKOFF_SECONDS=25


def _verified_account_bundles(root):
    """Reuse only independently SHA-verified immutable ZIPs across reads.

    A free Render request typically builds a fresh CloudArchive. Repeating a
    TeraBox 403 probe for every feed, follower, image and comment request
    previously delayed actual SIX-post playback for minutes. Synthetic roots
    bypass this process-local cache; the GitHub verified reader stays usable.
    """
    global _ZIP_SESSION_CACHE
    if not github_temp_bundle.enabled():
        return available_bundles(root)
    cacheable=type(root) is CloudArchive
    now=time.monotonic()
    if cacheable:
        with _ZIP_SESSION_LOCK:
            cached=_ZIP_SESSION_CACHE
            if cached is not None and cached[0]==root.remote:
                ttl=(ZIP_UNAVAILABLE_BACKOFF_SECONDS if cached[3]
                     else ZIP_VERIFIED_SESSION_SECONDS)
                if now-cached[1]<ttl:
                    if cached[3]:
                        raise RuntimeError("Private ZIP provider temporarily unavailable")
                    return cached[2]
    try:
        # Materialize while the per-pass authorization circuit breaker is
        # alive, not after its wrapper has been discarded.
        result=tuple(available_bundles(_BoundedZipRoot(root)))
    except (RuntimeError,ValueError,TypeError,BundleInvalid):
        if cacheable:
            with _ZIP_SESSION_LOCK:
                _ZIP_SESSION_CACHE=(root.remote,time.monotonic(),(),True)
        raise
    if cacheable and len(result)<=4:
        with _ZIP_SESSION_LOCK:
            _ZIP_SESSION_CACHE=(root.remote,time.monotonic(),result,not bool(result))
    return result



def public_profile_fields(doc):
    if not isinstance(doc,dict):
        return {}
    return {key:doc.get(key) for key in (
        "platform","identity","handle","display_name","description",
        "followers_count","following_count","posts_count","fields",
        "created_at","captured_at","complete_media","profile_url")}


def sanitize_safe_link(value):
    if not isinstance(value,str) or len(value)>2048:
        return ""
    url=urlsplit(value)
    if (url.scheme!="https" or not url.hostname or url.username
            or url.password or url.fragment):
        return ""
    return value


def open_account(account):
    match=REGISTRY_RE.fullmatch(account+".json")
    if not match:
        raise HTTPException(400,"Invalid archive account key")
    github=None
    if github_temp_bundle.enabled():
        try:
            github=github_temp_bundle.account_bundle(account)
        except (RuntimeError,ValueError,TypeError,BundleInvalid):
            # A provider outage must not suppress a separately verified ZIP.
            github=None
    root=open_root()
    try:
        # Prefer the fully SHA-verified TeraBox source when it contains more
        # public posts than a previously verified temporary GitHub snapshot.
        # A denied/slow TeraBox lookup must NOT break the GitHub reader.
        bundle=next((item for item in _verified_account_bundles(root)
                     if account in item.accounts),None)
        if bundle is not None and (github is None
                                   or bundle.post_count>github.post_count):
            return root,bundle.accounts[account],BundleAccountCloud(bundle)
        if github is not None:
            return None,github.accounts[account],BundleAccountCloud(github)
        raw=root.read("metadata/target-accounts/"+account+".json",
                      cap=4000,optional=True)
        if raw is None:
            raise HTTPException(404,"Public account archive not registered")
        meta=json.loads(raw)
        if (not isinstance(meta,dict) or meta.get("platform")!=match.group(1)
                or archive_key(meta)!=match.group(2)):
            raise HTTPException(404,"Archive identity mismatch")
        return root,meta,account_cloud(root,meta)
    except (RuntimeError,TypeError,ValueError,KeyError):
        if github is not None:
            return None,github.accounts[account],BundleAccountCloud(github)
        raise HTTPException(502,"Private account archive read unavailable") from None


def latest_snapshot(archive,folder,pattern,cap=300_000):
    names=archive.names(folder)
    valid=sorted(n for n in names if pattern.fullmatch(n))
    if not valid:
        return None
    for name in valid[-3:][::-1]:
        raw=archive.read(folder+"/"+name,cap=cap,optional=True)
        if raw is None:
            continue
        try:
            item=json.loads(raw)
            if isinstance(item,dict):
                return item
        except (ValueError,TypeError):
            continue
    return None


def feed_data(archive,account,offset,limit):
    # Every returned post is backed by the existing read-verified entry journal.
    rows=archive.load_catalog(include_entries=True)
    matching=[]
    for post in rows:
        if not isinstance(post,dict) or not HEX40.fullmatch(str(post.get("id",""))):
            continue
        pid=post["id"]
        media=[]
        for index,item in enumerate(post.get("media",[])):
            if not isinstance(item,dict) or item.get("remote_verified") is not True:
                continue
            media.append({
                "kind":item.get("kind","image"),
                "mime":item.get("mime"),"bytes":item.get("bytes"),
                "url":"/api/account-archives/"+account+"/media/"+pid+"/"+str(index),
                "verified_sha256":True})
        matching.append({
            "id":pid,"posted_at":post.get("posted_at"),"text":post.get("text",""),
            "source_url":sanitize_safe_link(post.get("source_url")),
            "profile_url":sanitize_safe_link(post.get("profile_url")),
            "kind":post.get("kind","post"),
            "reply_to":post.get("reply_to",""),
            "media":media,"media_expected":post.get("media_expected",0),
            "media_saved":post.get("media_saved",0),
            "archive_complete":post.get("archive_complete") is True})
    return {"total":len(matching),"offset":offset,"limit":limit,
            "posts":matching[offset:offset+limit],"more":offset+limit<len(matching)}


def graph_data(archive,kind,offset,limit):
    page_names=sorted((int(m.group(2)),n) for n in archive.names("graph/pages")
                      if (m:=GRAPH_PAGE.fullmatch(n)) and m.group(1)==kind)
    merged=[]
    known=set()
    # Retain account records in public edge order; each page has a source
    # snapshot timestamp and remains immutable for history/reconciliation.
    for _seq,name in page_names:
        raw=archive.read("graph/pages/"+name,cap=100_000,optional=True)
        if raw is None:
            continue
        try:
            value=json.loads(raw)
            items=value.get("items",[])
            if not isinstance(items,list):
                continue
            for user in items:
                if not isinstance(user,dict):
                    continue
                key=str(user.get("id",""))
                if not key or key in known: continue
                known.add(key)
                merged.append({"id":key,"handle":str(user.get("handle",""))[:200],
                               "display_name":str(user.get("display_name",""))[:300],
                               "profile_url":sanitize_safe_link(user.get("profile_url"))})
        except (ValueError,TypeError):
            continue
    return {"kind":kind,"captured_unique":len(merged),
            "source_pages":len(page_names),"offset":offset,"limit":limit,
            "accounts":merged[offset:offset+limit],
            "more":offset+limit<len(merged),
            "full_network_coverage_guaranteed":False}


def get_verified_media(archive,item,request):
    key=item.get("key");digest=item.get("sha256")
    length=item.get("bytes");mime=item.get("mime")
    if not (isinstance(key,str) and isinstance(digest,str)
            and re.fullmatch(r"[a-f0-9]{64}",digest)
            and isinstance(length,int) and 0<length<=80_000_000
            and item.get("remote_verified",True) is True):
        raise HTTPException(404,"Original media not verified")
    try:
        raw=archive.read_verified(key,digest,cap=length+1)
    except (RuntimeError,ValueError):
        raw=None
    if raw is None or len(raw)!=length:
        raise HTTPException(502,"Archived media SHA readback unavailable")
    # Safari requires byte ranges for video; validate the request strictly.
    range_value=request.headers.get("range","")
    if range_value:
        m=re.fullmatch(r"bytes=(\d*)-(\d*)",range_value)
        if not m or (not m.group(1) and not m.group(2)):
            raise HTTPException(416,"Invalid media range")
        if m.group(1):
            start=int(m.group(1))
            end=min(int(m.group(2)),len(raw)-1) if m.group(2) else len(raw)-1
        else:
            suffix=int(m.group(2))
            start=max(0,len(raw)-suffix)
            end=len(raw)-1
        if start>=len(raw) or end<start:
            raise HTTPException(416,"Unsatisfiable media range")
        return Response(raw[start:end+1],status_code=206,media_type=mime,
                        headers={**CACHE_HEADERS,"Accept-Ranges":"bytes",
                                 "Content-Range":f"bytes {start}-{end}/{len(raw)}"})
    return Response(raw,media_type=mime,
                    headers={**CACHE_HEADERS,"Accept-Ranges":"bytes"})


def account_picker_details(entry,archive=None):
    """Return only source-verified nickname/handle for the private chooser.

    Profile snapshot names live inside the already SHA-verified account ZIP.
    This neither calls a live SNS API nor infers links between identities.
    """
    if not isinstance(entry,dict):
        return {"display_name":"","handle":"","profile_snapshot_verified":False}
    profile=None
    if archive is not None:
        try:
            snapshot=latest_snapshot(archive,"profile/snapshots",PROFILE_FILE_RE)
            if (isinstance(snapshot,dict)
                    and snapshot.get("identity")==entry.get("identity")
                    and snapshot.get("platform")==entry.get("platform")):
                profile=snapshot
        except (RuntimeError,ValueError,KeyError,TypeError):
            pass
    def short(value,limit):
        return " ".join(str(value).split())[:limit] if isinstance(value,str) else ""
    trusted=profile if profile is not None else entry
    name=short(trusted.get("display_name"),100)
    handle=short(trusted.get("handle"),200).lstrip("@")
    if not handle:
        url=sanitize_safe_link(entry.get("profile_url"))
        part=urlsplit(url)
        path=part.path.rstrip("/").split("/")
        if part.hostname=="bsky.app" and len(path)>=3 and path[-2]=="profile":
            candidate=path[-1]
            if not candidate.startswith("did:") and len(candidate)<=200:
                handle=candidate
        elif part.hostname and path[-1].startswith("@"):
            handle=path[-1].lstrip("@")+"@"+part.hostname
    return {"display_name":name,"handle":handle,
            "profile_snapshot_verified":profile is not None}


def bundled_account_picker_row(bundle,account,*,temporary):
    """Build label metadata from the exact verified ZIP already in memory."""
    entry=bundle.accounts[account]
    identity=account_picker_details(entry,BundleAccountCloud(bundle))
    return {"key":account,"platform":entry["platform"],
            "profile_url":sanitize_safe_link(entry.get("profile_url")),
            "backup_kind":"github_temp_sha_verified" if temporary
                          else "terabox_zip_sha_verified",
            "posts_verified_in_bundle":bundle.post_count,
            "objects_verified_in_bundle":bundle.object_count,
            "source_state":bundle.source_state,
            "temporary":bool(temporary),**identity}


def create_router(auth):
    # CloudArchive uses blocking rclone subprocesses. FastAPI dispatches these
    # sync GET handlers to its worker pool, keeping health, receipts and queue
    # admission responsive while a remote original is read and SHA-checked.
    router=APIRouter()

    @router.get("/account-archive",include_in_schema=False)
    def viewer(request:Request):
        auth(request)
        return FileResponse(VIEW_DIR/"account_archive_view.html",
                            media_type="text/html; charset=utf-8",
                            headers={**CACHE_HEADERS,
                                     "Content-Security-Policy":
                                     "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"})

    @router.get("/account-archive/{asset_name}",include_in_schema=False)
    def asset(request:Request,asset_name:str):
        auth(request)
        if asset_name not in ("account_archive_view.js","account_archive_view.css"):
            raise HTTPException(404,"Unknown viewer asset")
        mime="application/javascript" if asset_name.endswith(".js") else "text/css"
        return FileResponse(VIEW_DIR/asset_name,media_type=mime,headers=CACHE_HEADERS)

    @router.get("/api/account-archives")
    def accounts(request:Request):
        auth(request)
        if github_temp_bundle.enabled():
            data=[]
            github_failed=False
            terabox_failed=False
            try:
                data=[bundled_account_picker_row(bundle,bundle.account,
                                                temporary=True)
                      for bundle in github_temp_bundle.latest_bundles()]
            except (RuntimeError,ValueError,TypeError,BundleInvalid):
                github_failed=True
            try:
                root=open_root()
                index={item["key"]:item for item in data}
                for bundle in _verified_account_bundles(root):
                    for account,entry in bundle.accounts.items():
                        present=index.get(account)
                        # Exact account identity and independently checked
                        # whole ZIP SHA already gate both archive backends.
                        if (present is not None and bundle.post_count<=
                                present["posts_verified_in_bundle"]):
                            continue
                        row=bundled_account_picker_row(bundle,account,
                                                      temporary=False)
                        if present is None:
                            data.append(row)
                        else:
                            present.update(row)
                        index[account]=present if present is not None else row
            except (RuntimeError,ValueError,TypeError,KeyError,BundleInvalid):
                terabox_failed=True
            if not data and github_failed and terabox_failed:
                raise HTTPException(502,"Both verified account indexes unavailable")
            return JSONResponse({"accounts":data},headers=CACHE_HEADERS)
        root=open_root()
        try:
            # Legacy nested per-record paths can return copyto/lsf missing
            # even when a complete ZIP is remotely SHA-verified. Do not let
            # a broken old registry hide the independently verified backups.
            try:
                names=root.names("metadata/target-accounts")
            except RuntimeError:
                names=[]
            data=[]
            for name in names:
                if not REGISTRY_RE.fullmatch(name):
                    continue
                try:
                    raw=root.read("metadata/target-accounts/"+name,cap=4000,optional=True)
                    if raw is None:continue
                    entry=json.loads(raw)
                    if (entry.get("platform")+"-"+archive_key(entry)+".json")!=name:
                        continue
                    data.append({"key":name[:-5],"platform":entry["platform"],
                                 "profile_url":sanitize_safe_link(entry.get("profile_url")),
                                 **account_picker_details(entry,account_cloud(root,entry))})
                except (RuntimeError,ValueError,KeyError,TypeError):
                    continue
            seen={item["key"] for item in data}
            # ZIP receipts are independently re-read and verified against the
            # embedded 64-digit hashes, not inferred from GitHub green checks.
            for bundle in available_bundles(root):
                for account,entry in bundle.accounts.items():
                    if account in seen:
                        for row in data:
                            if row["key"]==account:
                                row["backup_kind"]="terabox_zip_sha_verified"
                                row["posts_verified_in_bundle"]=bundle.post_count
                                row["objects_verified_in_bundle"]=bundle.object_count
                                row.update(account_picker_details(
                                    bundle.accounts[account],BundleAccountCloud(bundle)))
                        continue
                    seen.add(account)
                    data.append(bundled_account_picker_row(
                        bundle,account,temporary=False))
            return JSONResponse({"accounts":data},headers=CACHE_HEADERS)
        except (RuntimeError,TypeError,ValueError,KeyError):
            raise HTTPException(502,"Private account index unavailable") from None

    @router.get("/api/account-archives/{account}/backup-status")
    def backup_status(request:Request,account:str):
        auth(request)
        _,_,archive=open_account(account)
        if isinstance(archive,BundleAccountCloud):
            bundle=archive.bundle
            return JSONResponse({
                "storage":"github_encrypted_temporary" if getattr(bundle,"temporary",False) else "private_terabox",
                "state":"REMOTE_ZIP_SHA_VERIFIED",
                "source_state":bundle.source_state,
                "original_objects":bundle.object_count,
                "public_posts":bundle.post_count,
                "recorded_at":bundle.recorded_at,
                "full_historical_coverage_guaranteed":False,
            },headers=CACHE_HEADERS)
        return JSONResponse({
            "storage":"private_terabox",
            "state":"LEGACY_PER_RECORD",
            "full_historical_coverage_guaranteed":False,
        },headers=CACHE_HEADERS)

    @router.get("/api/account-archives/{account}/profile")
    def profile(request:Request,account:str):
        auth(request)
        _,entry,archive=open_account(account)
        try:
            doc=latest_snapshot(archive,"profile/snapshots",PROFILE_FILE_RE)
            if not doc:
                return JSONResponse({"available":False,"profile_url":
                                     sanitize_safe_link(entry.get("profile_url"))},
                                    headers=CACHE_HEADERS)
            view=public_profile_fields(doc)
            view["available"]=True
            view["profile_url"]=sanitize_safe_link(entry.get("profile_url"))
            view["assets"]={}
            for name in ("avatar","banner"):
                asset=doc.get("assets",{}).get(name,{})
                if asset.get("status")=="sha256_verified":
                    view["assets"][name]="/api/account-archives/"+account+"/profile-asset/"+name
                else:
                    view["assets"][name]=None
            return JSONResponse(view,headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Archived public profile unavailable") from None

    @router.get("/api/account-archives/{account}/feed")
    def feed(request:Request,account:str,
                   offset:int=Query(0,ge=0,le=200000),
                   limit:int=Query(20,ge=1,le=50)):
        auth(request)
        _,_,archive=open_account(account)
        try:
            return JSONResponse(feed_data(archive,account,offset,limit),
                                headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Account history read unavailable") from None

    @router.get("/api/account-archives/{account}/graph/{kind}")
    def graph(request:Request,account:str,kind:str,
                    offset:int=Query(0,ge=0,le=200000),
                    limit:int=Query(50,ge=1,le=100)):
        auth(request)
        if kind not in ("followers","following"):
            raise HTTPException(400,"Invalid public graph")
        _,_,archive=open_account(account)
        try:
            return JSONResponse(graph_data(archive,kind,offset,limit),
                                headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Public graph archive unavailable") from None

    @router.get("/api/account-archives/{account}/threads/{pid}")
    def thread(request:Request,account:str,pid:str):
        auth(request)
        if not HEX40.fullmatch(pid):
            raise HTTPException(400,"Invalid post")
        _,_,archive=open_account(account)
        try:
            data=latest_snapshot(archive,"threads/"+pid,THREAD_FILE_RE,cap=500_000)
            if not data:
                return JSONResponse({"captured":False,"replies":[]},headers=CACHE_HEADERS)
            out=[]
            for r in data.get("replies",[])[:120]:
                if not isinstance(r,dict):continue
                out.append({"id":r.get("id"),"author":r.get("author"),
                            "display_name":r.get("display_name"),
                            "text":r.get("text"),"posted_at":r.get("posted_at"),
                            "source_url":sanitize_safe_link(r.get("uri")),
                            "media_source_links":[sanitize_safe_link(v)
                                    for v in r.get("media_urls",[])[:16]
                                    if sanitize_safe_link(v)]})
            return JSONResponse({"captured":True,"replies":out,
                                 "truncated":bool(data.get("truncated")),
                                 "captured_at":data.get("captured_at"),
                                 "comment_media_backed_up":False},headers=CACHE_HEADERS)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Public reply archive unavailable") from None

    @router.get("/api/account-archives/{account}/media/{pid}/{index}")
    def post_media(request:Request,account:str,pid:str,index:int):
        auth(request)
        if not HEX40.fullmatch(pid) or index<0 or index>=16:
            raise HTTPException(400,"Invalid original media")
        _,_,archive=open_account(account)
        try:
            posts=archive.load_catalog()
            post=next((p for p in posts if p.get("id")==pid),None)
            if not post or index>=len(post.get("media",[])):
                raise HTTPException(404,"Media not archived")
            media=post["media"][index]
            if not media.get("key","").startswith("posts/"+pid+"/media/"):
                raise HTTPException(404,"Invalid original source")
            return get_verified_media(archive,media,request)
        except (RuntimeError,ValueError,TypeError):
            raise HTTPException(502,"Original media read unavailable") from None

    @router.get("/api/account-archives/{account}/profile-asset/{kind}")
    def profile_asset(request:Request,account:str,kind:str):
        auth(request)
        if kind not in ("avatar","banner"):
            raise HTTPException(400,"Invalid profile media")
        _,_,archive=open_account(account)
        doc=latest_snapshot(archive,"profile/snapshots",PROFILE_FILE_RE)
        if not doc:
            raise HTTPException(404,"Profile snapshot unavailable")
        asset=doc.get("assets",{}).get(kind,{})
        if (asset.get("status")!="sha256_verified"
                or not str(asset.get("key","")).startswith("profile/assets/")):
            raise HTTPException(404,"Profile image not archived")
        return get_verified_media(archive,
                                  {**asset,"remote_verified":True},request)

    return router
