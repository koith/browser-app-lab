"""Private TeraBox post viewer gateway. Never expose cloud credentials in Pages."""
from __future__ import annotations
import asyncio, hashlib, hmac, json, os, re, secrets, sqlite3, tempfile, time
from pathlib import Path
from typing import AsyncIterator
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from datetime import datetime, timezone, timedelta
from social_sources import TERMS, ROUTES, request_one_page
import account_index
import account_index_sources
import account_groups
from demand_archive import CloudArchive, QueueStorageDenied

from target_archive_api import create_router as create_target_archive_router, dispatch_enabled

app=FastAPI(title="Demand Research Private Cloud",docs_url=None,redoc_url=None)

@app.get("/health",include_in_schema=False)
async def liveness():
    # Availability checks must not expose private archive names, keys or data.
    # A healthy process can still be awaiting its three server-side secrets.
    return JSONResponse({"alive":True},headers={"Cache-Control":"no-store"})

# GitHub Actions transfers its EXISTING TeraBox credential to this private
# process over TLS. A short-lived signed OIDC JWT proves the exact repository,
# workflow and main ref; the public web app cannot call this route successfully.
BRIDGE_AUDIENCE="intersection-originals-free/credential-v1"
BRIDGE_WORKFLOW="koith/browser-app-lab/.github/workflows/intersection-gateway-credential-sync.yml@refs/heads/main"
ARCHIVE_WORKFLOW="koith/browser-app-lab/.github/workflows/intersection-target-account-bundle.yml@refs/heads/main"
MIRROR_WORKFLOW="koith/browser-app-lab/.github/workflows/intersection-terabox-gh-mirror.yml@refs/heads/main"
INDEX_IMPORT_WORKFLOW="koith/browser-app-lab/.github/workflows/intersection-index-live-repair.yml@refs/heads/main"
BRIDGE_ISSUER="https://token.actions.githubusercontent.com"
BRIDGE_JWKS=BRIDGE_ISSUER+"/.well-known/jwks"

def verify_bridge_token(token, workflow=BRIDGE_WORKFLOW):
    if not isinstance(token,str) or len(token)>12000 or len(token)<100:
        raise ValueError("Invalid bridge assertion")
    # Lazy import keeps normal offline tests and public-only routes lightweight.
    import jwt
    client=jwt.PyJWKClient(BRIDGE_JWKS,cache_jwk_set=True,lifespan=3600,timeout=8)
    key=client.get_signing_key_from_jwt(token)
    claims=jwt.decode(token,key.key,algorithms=["RS256"],
                      audience=BRIDGE_AUDIENCE,issuer=BRIDGE_ISSUER,
                      options={"require":["exp","iat","iss","aud","sub"]},
                      leeway=15)
    must={
        "repository":"koith/browser-app-lab",
        "repository_id":"1284121913",
        "ref":"refs/heads/main",
        "workflow_ref":workflow,
    }
    if any(str(claims.get(k,""))!=v for k,v in must.items()):
        raise ValueError("Untrusted bridge workflow")
    allowed_events=("schedule","workflow_dispatch","push")
    if workflow in (MIRROR_WORKFLOW,INDEX_IMPORT_WORKFLOW):
        allowed_events+=("workflow_run",)
    if claims.get("event_name") not in allowed_events:
        raise ValueError("Unexpected bridge event")
    return claims

@app.post("/api/bridge/credential",include_in_schema=False)
async def receive_authenticated_credential(request:Request):
    # Never accept arbitrary public credentials, and never reflect or log NDUS.
    raw=await request.body()
    if len(raw)>18000:
        raise HTTPException(413,"Bridge request too large")
    try:
        payload=json.loads(raw)
        if not isinstance(payload,dict) or set(payload)!={"assertion","credential"}:
            raise ValueError("Invalid bridge payload")
        credential=payload["credential"]
        if not isinstance(credential,str) or not 16<=len(credential)<=4096:
            raise ValueError("Invalid private cloud credential")
        if any(ord(c)<32 for c in credential):
            raise ValueError("Invalid credential characters")
        verify_bridge_token(payload["assertion"])
    except (ValueError,KeyError,TypeError,AttributeError):
        raise HTTPException(403,"Bridge authentication failed") from None
    except Exception:
        # JWK network failures and signature validation never become a bypass.
        raise HTTPException(503,"Bridge verification unavailable") from None
    global COOKIE
    COOKIE=credential
    os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]=credential
    # On a free Render instance the secret arrives AFTER process startup.
    # Start the optional account-index loop now; otherwise startup skipped
    # it permanently and the Accounts page remains empty after 503 recovery.
    if INDEX_DB and _index_task is None and configured():
        await start_account_index()
    return JSONResponse({"accepted":True,"storage_configured":configured()},
                        headers={"Cache-Control":"no-store"})

def _bridge_authenticated(request):
    header=request.headers.get("authorization","")
    if not header.startswith("Bearer ") or len(header)>12500:
        raise HTTPException(403,"Bridge identity required")
    try:
        return verify_bridge_token(header[7:])
    except (ValueError,TypeError,KeyError):
        raise HTTPException(403,"Bridge identity rejected") from None
    except Exception:
        raise HTTPException(503,"Bridge identity verification unavailable") from None


@app.post("/api/bridge/index-snapshot",include_in_schema=False)
async def accept_signed_index_snapshot(request:Request):
    """Import an already SHA-verified, immutable public-account index.

    The GitHub main-branch repair worker has access to the TeraBox snapshot
    when the free Render reader receives provider 403. Only its short-lived
    signed OIDC assertion can import. Never print or return account records.
    """
    header=request.headers.get("authorization","")
    if not header.startswith("Bearer ") or len(header)>12500:
        raise HTTPException(403,"Signed index import required")
    try:
        verify_bridge_token(header[7:],workflow=INDEX_IMPORT_WORKFLOW)
    except (ValueError,KeyError,TypeError):
        raise HTTPException(403,"Index import identity rejected") from None
    except Exception:
        raise HTTPException(503,"Index import identity unavailable") from None
    if not INDEX_DB:
        raise HTTPException(503,"Private index storage not configured")
    digest=request.headers.get("x-index-sha256","")
    run_id=request.headers.get("x-index-source-run","")
    if not SHA_RE.fullmatch(digest) or not re.fullmatch(r"[0-9]{6,30}",run_id):
        raise HTTPException(400,"Invalid signed index metadata")
    cap=8*1024*1024
    try:
        declared=int(request.headers.get("content-length","0"))
    except ValueError:
        raise HTTPException(413,"Index too large") from None
    if declared<=0 or declared>cap:
        raise HTTPException(413,"Index too large")
    raw=bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw)>cap:
            raise HTTPException(413,"Index too large")
    if len(raw)!=declared or not secrets.compare_digest(hashlib.sha256(raw).hexdigest(),digest):
        raise HTTPException(422,"Index SHA256 mismatch")
    with tempfile.TemporaryDirectory(prefix="intersection-signed-index-") as folder:
        candidate=Path(folder)/"verified.sqlite3"
        candidate.write_bytes(raw)
        try:
            source=sqlite3.connect("file:"+str(candidate)+"?mode=ro",uri=True)
            try:
                if source.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise ValueError("invalid SQLite")
                count=source.execute("SELECT count(*) FROM accounts").fetchone()[0]
                rows=source.execute("SELECT count(*) FROM observed").fetchone()[0]
                if not (isinstance(count,int) and count>0 and isinstance(rows,int) and rows>0):
                    raise ValueError("empty index")
                async with _index_lock:
                    dest=account_index.connect(INDEX_DB)
                    try:
                        previous=dict(dest.execute(
                            "SELECT key,value FROM index_meta WHERE key IN "
                            "('last_imported_index_run','last_imported_index_sha')").fetchall())
                        current=int(previous.get("last_imported_index_run","0"))
                        if int(run_id)<current or (
                            int(run_id)==current and previous.get("last_imported_index_sha")!=digest):
                            raise HTTPException(409,"Older or conflicting index revision")
                        if int(run_id)>current:
                            source.backup(dest)
                            dest.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                                         ("last_imported_index_run",run_id))
                            dest.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                                         ("last_imported_index_sha",digest))
                            dest.commit()
                    finally:
                        dest.close()
                    global _index_synced_at,_index_last_error
                    _index_synced_at=time.monotonic()
                    _index_last_error=""
                    _index_snapshot_info.update(sha256=digest,catalog="not_verified",verified=True)
            finally:
                source.close()
        except (sqlite3.Error,ValueError,TypeError):
            raise HTTPException(422,"Invalid verified index database") from None
    print("ACCOUNT_INDEX_SIGNED_IMPORT_SHA_VERIFIED",
          json.dumps({"accounts":count,"source_rows":rows},sort_keys=True),flush=True)
    return JSONResponse({"accepted":True,"accounts":count,"source_rows":rows},
                        headers={"Cache-Control":"no-store"})


@app.get("/api/bridge/archive-key", include_in_schema=False)
async def issue_temporary_archive_key(request:Request):
    """Share a derived encryption key ONLY with the trusted selected-account runner.

    The GitHub token remains inside Actions; the stable private viewer secret
    never leaves Render. Issued key must never appear in workflow logs.
    """
    import base64
    import github_temp_bundle
    header=request.headers.get("authorization","")
    if not header.startswith("Bearer ") or len(header)>12500:
        raise HTTPException(403,"Authorized GitHub account runner required")
    try:
        try:
            verify_bridge_token(header[7:], workflow=ARCHIVE_WORKFLOW)
        except ValueError:
            try:
                verify_bridge_token(header[7:], workflow=MIRROR_WORKFLOW)
            except ValueError:
                # Only this reviewed main-branch index-delivery job can
                # obtain the derived encryption key for sealed boot recovery.
                # No provider-cookie, backup-write, or broader permission.
                verify_bridge_token(header[7:], workflow=INDEX_IMPORT_WORKFLOW)
    except (ValueError,TypeError,KeyError):
        raise HTTPException(403,"GitHub account runner rejected") from None
    except Exception:
        raise HTTPException(503,"GitHub identity verification unavailable") from None
    try:
        key=github_temp_bundle.gateway_key()
    except RuntimeError:
        raise HTTPException(503,"Archive encryption unavailable") from None
    return JSONResponse({"key":base64.b64encode(key).decode("ascii")},
                        headers={"Cache-Control":"private, no-store"})


@app.get("/api/bridge/pending",include_in_schema=False)
async def github_pending_requests(request:Request):
    _bridge_authenticated(request)
    if not configured():
        raise HTTPException(503,"Private archive not connected")
    try:
        from backup_queue import pending
        rows=await asyncio.to_thread(pending,limit=4)
    except (RuntimeError,ValueError):
        raise HTTPException(503,"Private queue listing unavailable") from None
    return JSONResponse({"requests":rows},
                        headers={"Cache-Control":"private, no-store"})


@app.get("/api/bridge/accepted",include_in_schema=False)
async def github_accepted_runs(request:Request):
    _bridge_authenticated(request)
    if not configured():
        raise HTTPException(503,"Private archive not connected")
    try:
        from backup_queue import accepted_runs
        runs=await asyncio.to_thread(accepted_runs,limit=64)
    except (RuntimeError,ValueError,QueueStorageDenied):
        raise HTTPException(503,"Private accepted-run listing unavailable") from None
    return JSONResponse({"runs":runs},
                        headers={"Cache-Control":"private, no-store"})


@app.post("/api/bridge/ack",include_in_schema=False)
async def github_acknowledge_job(request:Request):
    _bridge_authenticated(request)
    if not configured():
        raise HTTPException(503,"Private archive not connected")
    raw=await request.body()
    if len(raw)>1000:
        raise HTTPException(413,"Invalid bridge acknowledgment")
    try:
        payload=json.loads(raw)
        if type(payload) is not dict or set(payload)!={"job_id","workflow_run_id"}:
            raise ValueError("Invalid acknowledgment")
        from backup_queue import accept
        row=await asyncio.to_thread(accept,payload["job_id"],
                                     payload["workflow_run_id"])
    except (ValueError,TypeError,KeyError):
        raise HTTPException(400,"Invalid bridge acknowledgment") from None
    except (RuntimeError,QueueStorageDenied):
        raise HTTPException(503,"Unable to verify immutable queue acknowledgment") from None
    return JSONResponse({"accepted":True,"job_id":row["job_id"]},
                        headers={"Cache-Control":"private, no-store"})


@app.get("/ready",include_in_schema=False)
async def backup_readiness():
    # Public frontend probes only after the user clicks backup. Liveness alone
    # must never direct them to an unconfigured private service.
    from backup_queue import enabled as queue_enabled
    ready=configured() and (dispatch_enabled() or queue_enabled())
    return JSONResponse({"ready":ready},
                        status_code=200 if ready else 503,
                        headers={"Cache-Control":"no-store"})

app.add_middleware(CORSMiddleware,allow_origins=["https://koith.github.io","http://localhost:8765"],allow_methods=["GET","OPTIONS"],allow_headers=["Authorization","Content-Type"])
REMOTE=os.getenv("DEMAND_TERABOX_REMOTE","archive:DemandResearch").rstrip("/")
TOKEN=os.getenv("DEMAND_VIEWER_TOKEN","")
COOKIE=os.getenv("RCLONE_CONFIG_ARCHIVE_COOKIE","")
ID_RE=re.compile(r"^[a-f0-9]{16,64}$")
SHA_RE=re.compile(r"^[a-f0-9]{64}$")
MIMES={"image/jpeg","image/png","image/webp","image/avif","video/mp4","video/webm","video/quicktime", "audio/mpeg", "audio/mp4", "audio/ogg",
       "audio/wav", "audio/webm", "audio/flac"}
MAX_SIZE=1500000000
_cache={"at":0.0,"posts":None}
_lock=asyncio.Lock()
# Bound a slow TeraBox journal reconstruction to ONE background worker on
# the 512MiB free gateway. Requests never launch duplicate rclone scans.
_catalog_task=None
_catalog_retry_after=0.0
CATALOG_INITIAL_WAIT_SECONDS=18
CATALOG_RETRY_COOLDOWN_SECONDS=30


def configured():
    return len(TOKEN)>=24 and bool(COOKIE) and REMOTE.startswith("archive:")

# The private bookmark is https://gateway.example/#access=<random 32+ char secret>.
# URL fragments are never transmitted in HTTP request lines, referrers or proxy logs.
# A one-time POST exchanges that capability for a signed HttpOnly cookie, so
# repeated visits require no password, and rotating TOKEN revokes both.
SESSION_SECONDS=30*24*60*60
SESSION_COOKIE="demand_view"
VIEW_FILE=Path(__file__).resolve().parent/"index.html"
INDEX_DB=os.getenv("DEMAND_ACCOUNT_INDEX_DB","").strip()
INDEX_SECONDS=15*60
_index_lock=asyncio.Lock()
_index_synced_at=0.0
_index_last_error=""
_index_task=None
_index_snapshot_info={"sha256":"","catalog":"not_checked","verified":False}

def verified_signed_import_receipt(db_path):
    """Recover signed SHA provenance from the same local SQLite after restart.

    Render may restart its 512MiB process but keep its working SQLite file.
    An in-memory boolean must not erase an independently verified import
    receipt. Never claim verification for unmarked or malformed indexes.
    """
    if not db_path:
        return False
    try:
        path=Path(db_path).expanduser().resolve()
        if not path.is_file():
            return False
        db=sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True,timeout=5)
        try:
            if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                return False
            metadata=dict(db.execute(
                "SELECT key,value FROM index_meta WHERE key IN "
                "('last_imported_index_run','last_imported_index_sha')"))
            run=metadata.get("last_imported_index_run","")
            digest=metadata.get("last_imported_index_sha","")
            if (not re.fullmatch(r"[0-9]{6,30}",run)
                    or not re.fullmatch(r"[0-9a-f]{64}",digest)):
                return False
            return (db.execute("SELECT count(*) FROM accounts").fetchone()[0]>0
                    and db.execute("SELECT count(*) FROM observed").fetchone()[0]>0)
        finally:
            db.close()
    except (OSError,ValueError,TypeError,sqlite3.Error):
        return False


_index_lazy_task=None
_index_lazy_attempt_at=0.0
INDEX_LAZY_RETRY_SECONDS=180

def remote_index_poll_enabled():
    """The signed OIDC bridge updates this index; free Render must not run
    concurrent remote index fetches on every wake-up or account status poll.
    Explicit owner-triggered /api/accounts/sync is unaffected.
    """
    return os.getenv("DEMAND_ACCOUNT_INDEX_REMOTE_POLL","1")=="1"

def _read_verified_account_index_snapshot(previous_sha=""):
    """Restore immutable SHA-checked account index without scanning every post.

    The hourly GitHub worker performs source scanning, account grouping and
    cloud checkpointing. Render free only reads its verified SQLite snapshot:
    this avoids rescanning all remote journals inside a 512MiB web process.
    A failed read never replaces the existing local SQLite database.
    """
    import account_index_job
    manifest=account_index_job.latest_manifest()
    if not manifest:
        raise RuntimeError("verified account index snapshot unavailable")
    if manifest["sha256"]==previous_sha:
        return {"sha256":previous_sha,"unchanged":True}
    with tempfile.TemporaryDirectory(prefix="intersection-index-view-") as d:
        verified=Path(d)/"verified.sqlite3"
        account_index_job.load_snapshot(verified,manifest)
        source=sqlite3.connect(str(verified),timeout=20)
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("account index snapshot integrity check failed")
            stats=account_index.status(str(verified))
            destination=sqlite3.connect(INDEX_DB,timeout=25)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
    return {"sha256":manifest["sha256"],"unchanged":False,
            "catalog":str(manifest.get("catalog","not_checked"))[:60],
            "accounts":stats["accounts"],"source_rows":stats["source_rows"]}


async def refresh_account_index(force=False):
    global _index_synced_at,_index_last_error
    if not INDEX_DB:
        raise HTTPException(503,"Private account-index storage not configured")
    async with _index_lock:
        if not force and _index_synced_at and time.monotonic()-_index_synced_at<INDEX_SECONDS:
            return
        try:
            result=await asyncio.to_thread(
                _read_verified_account_index_snapshot,_index_snapshot_info["sha256"])
            if not result["unchanged"]:
                _index_snapshot_info.update(sha256=result["sha256"],
                    catalog=result["catalog"],verified=True)
                print("ACCOUNT_INDEX_VERIFIED_SNAPSHOT_LOADED",
                    json.dumps({"accounts":result["accounts"],
                                "source_rows":result["source_rows"],
                                "catalog":result["catalog"]}),flush=True)
            _index_synced_at=time.monotonic()
            _index_last_error=""
        except Exception as error:
            _index_last_error=type(error).__name__
            raise

@app.on_event("startup")
async def start_account_index():
    global _index_task
    if not INDEX_DB or not configured():
        return
    async def periodic():
        # A free Render instance can lose its ephemeral SQLite when it sleeps.
        # Restore only previously AES-GCM sealed, immutable GitHub ciphertext,
        # using the existing viewer-token-derived key; never expose identities.
        try:
            import github_temp_bundle
            import account_index_bootstrap
            # Account status returns refreshing=True during cold boot,
            # so the existing UI reloads automatically instead of freezing
            # an initial empty account count at zero.
            async with _index_lock:
                result=await asyncio.to_thread(
                    account_index_bootstrap.restore_local,INDEX_DB,
                    github_temp_bundle.gateway_key())
                if result["state"]=="restored":
                    _index_snapshot_info.update(sha256=result["sha256"],
                        catalog="encrypted_cold_boot",verified=True)
                    print("ACCOUNT_INDEX_ENCRYPTED_BOOT_SHA_VERIFIED",
                          json.dumps({"accounts":result["accounts"],
                                      "source_rows":result["source_rows"],
                                      "cache_age_days":result["age_days"]}),
                          flush=True)
        except Exception as error:
            # Never log private download addresses, encrypted bytes, tokens.
            print("ACCOUNT_INDEX_ENCRYPTED_BOOT_UNAVAILABLE",
                  type(error).__name__,flush=True)
        while True:
            if remote_index_poll_enabled():
                try:
                    await refresh_account_index()
                except Exception as error:
                    print("ACCOUNT_INDEX_SNAPSHOT_REFRESH_FAILED",
                          type(error).__name__,flush=True)
            # Collection, journal reconciliation and group scanning already
            # run in the hourly GitHub job that publishes the immutable DB.
            # Never do heavy full-catalog scans in the 512MiB web gateway.
            await asyncio.sleep(INDEX_SECONDS)
    _index_task=asyncio.create_task(periodic())

@app.on_event("shutdown")
async def stop_account_index():
    if _index_task is not None:
        _index_task.cancel()
        try:
            await _index_task
        except asyncio.CancelledError:
            pass


def session_value(issued_at:int)->str:
    stamp=str(issued_at)
    digest=hmac.new(TOKEN.encode(),("demand-session:v1:"+stamp).encode(),hashlib.sha256).hexdigest()
    return stamp+"."+digest

def check_auth(request:Request):
    if not configured():
        raise HTTPException(status_code=503,detail="TeraBox gateway not connected")
    # This dedicated site contains only already PUBLIC social-network content.
    # Its user explicitly chose URL-only viewing and backup initiation.
    # The bridge/credential routes still require signed GitHub OIDC.
    # Expensive index refresh and paid discovery commands stay protected.
    if os.getenv("DEMAND_PUBLIC_ARCHIVE_MODE","0")=="1":
        path=request.url.path
        if (request.method=="GET" and (
                path in {"/api/session","/api/posts","/api/archive-overview",
                         "/api/target-archive/status","/auto-archive",
                         "/account-archive","/api/accounts/status",
                         "/api/accounts","/api/account-groups"}
                or path.startswith("/api/account-archives")
                or path.startswith("/api/target-archive/jobs/")
                or path.startswith("/account-archive/")
                or path.startswith("/auto-archive/"))
            or request.method=="POST" and path=="/api/target-archive/start"):
            return
    value=request.cookies.get(SESSION_COOKIE,"")
    parts=value.split(".",1)
    if len(parts)!=2 or not parts[0].isdigit() or len(parts[0])>11:
        raise HTTPException(status_code=401,detail="Private link required")
    issued=int(parts[0])
    now=int(time.time())
    if issued>now+60 or now-issued>SESSION_SECONDS or not secrets.compare_digest(value,session_value(issued)):
        raise HTTPException(status_code=401,detail="Private link expired")

@app.get("/",include_in_schema=False)
async def viewer():
    # The public HTML shell contains NO secret or private data.
    # Actual posts/media remain behind signed cloud session checks.
    return FileResponse(VIEW_FILE,media_type="text/html; charset=utf-8",
        headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer",
                 "X-Robots-Tag":"noindex, nofollow","X-Content-Type-Options":"nosniff"})

# Separate read-only viewer of the five-minute keyword capture journal.
# Never serve archived originals on GitHub Pages or without a signed session.
AUTO_DIR=VIEW_FILE.parent
AUTO_FILES={"auto_archive_view.js":"application/javascript",
            "auto_archive_view.css":"text/css"}
AUTO_CSP=("default-src 'none'; script-src 'self'; style-src 'self'; "
          "img-src 'self' data:; media-src 'self'; connect-src 'self'; "
          "base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
AUTO_HEADERS={"Cache-Control":"private, no-store","Referrer-Policy":"no-referrer",
              "X-Robots-Tag":"noindex, nofollow",
              "X-Content-Type-Options":"nosniff"}
@app.get("/auto-archive",include_in_schema=False)
async def auto_archive_page(request:Request):
    check_auth(request)
    return FileResponse(AUTO_DIR/"auto_archive_view.html",
                        media_type="text/html; charset=utf-8",
                        headers={**AUTO_HEADERS,"Content-Security-Policy":AUTO_CSP})

@app.get("/auto-archive/{asset_name}",include_in_schema=False)
async def auto_archive_asset(request:Request,asset_name:str):
    check_auth(request)
    mime=AUTO_FILES.get(asset_name)
    if not mime:
        raise HTTPException(404,"Unsupported archive asset")
    return FileResponse(AUTO_DIR/asset_name,media_type=mime,
                        headers=AUTO_HEADERS)

@app.post("/api/activate",include_in_schema=False)
async def activate(request:Request):
    if not configured():
        raise HTTPException(status_code=503,detail="Cloud not connected")
    body=await request.body()
    if len(body)>512:
        raise HTTPException(status_code=413,detail="Invalid link")
    try:
        key=json.loads(body).get("token","")
    except (json.JSONDecodeError,AttributeError,TypeError):
        raise HTTPException(status_code=400,detail="Invalid link")
    if not isinstance(key,str) or not secrets.compare_digest(key,TOKEN):
        raise HTTPException(status_code=403,detail="Invalid private link")
    result=JSONResponse({"connected":True},headers={"Cache-Control":"no-store"})
    result.set_cookie(SESSION_COOKIE,session_value(int(time.time())),
        max_age=SESSION_SECONDS,httponly=True,secure=True,samesite="strict",path="/")
    return result

@app.get("/api/session")
async def session(request:Request):
    check_auth(request)
    return JSONResponse({"connected":True},headers={"Cache-Control":"no-store"})

@app.post("/api/end-session",include_in_schema=False)
async def end_session():
    response=JSONResponse({"connected":False},headers={"Cache-Control":"no-store"})
    response.delete_cookie(SESSION_COOKIE,path="/",secure=True,httponly=True,samesite="strict")
    return response

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

async def _refresh_verified_catalog():
    """Single bounded in-process task; cloud data never leaves private RAM."""
    global _catalog_retry_after
    try:
        posts=await asyncio.to_thread(CloudArchive(REMOTE).load_catalog)
        if not isinstance(posts,list):
            raise ValueError("Verified remote catalog is not a list")
        # Replace the cache only after complete independent journal readback.
        # Any failure retains previously verified immutable originals.
        _cache.update(at=time.time(),posts=posts)
        _catalog_retry_after=0.0
        return True
    except Exception:
        # Raw provider exceptions, post IDs and source URLs must not enter
        # publicly readable logs or browser responses.
        _catalog_retry_after=time.monotonic()+CATALOG_RETRY_COOLDOWN_SECONDS
        return False


async def get_catalog():
    """Serve last SHA-verified immutable snapshot while one remote refresh runs.

    First access waits a finite amount; subsequent requests attach to the
    same task instead of spawning multiple huge catalog scans. Historical
    posts are append-only: serving an older independently verified snapshot
    is preferable to losing all real posts while a provider times out.
    """
    global _catalog_task
    if _cache["posts"] is not None and time.time()-_cache["at"]<90:
        return _cache["posts"]
    async with _lock:
        if ((_catalog_task is None or _catalog_task.done()) and
                time.monotonic()>=_catalog_retry_after):
            _catalog_task=asyncio.create_task(_refresh_verified_catalog())
        current=_catalog_task
    if _cache["posts"] is not None:
        return _cache["posts"]
    if current is None:
        raise HTTPException(503,"Verified archive temporarily unavailable")
    try:
        verified=await asyncio.wait_for(asyncio.shield(current),
                                        timeout=CATALOG_INITIAL_WAIT_SECONDS)
    except asyncio.TimeoutError:
        # Do not cancel the ONE still-running cloud read. Later retry calls
        # can reuse its progress; never return unverified candidate posts.
        raise HTTPException(503,"Verified archive still loading") from None
    if not verified or _cache["posts"] is None:
        raise HTTPException(502,"Cloud catalog validation failure")
    return _cache["posts"]

def media_signature(post_id,index,expires):
    return hmac.new(TOKEN.encode(),(post_id+":"+str(index)+":"+str(expires)).encode(),hashlib.sha256).hexdigest()

async def _background_account_index_refresh():
    try:
        await refresh_account_index()
    except Exception as error:
        print("ACCOUNT_INDEX_LAZY_REFRESH_FAILED",type(error).__name__,flush=True)


def schedule_lazy_account_index_refresh():
    """Coalesce status-triggered refreshes on memory-limited free instances.

    Rapid GET /api/accounts/status requests previously queued many copies
    before the first task acquired the lock. A failing remote catalog read
    then started another expensive attempt immediately after each failure.
    Never schedule a second copy while periodic/previous refresh is alive.
    """
    global _index_lazy_task,_index_lazy_attempt_at
    if not remote_index_poll_enabled():
        return False
    now=time.monotonic()
    if (_index_task is not None and not _index_task.done()
            or _index_lazy_task is not None and not _index_lazy_task.done()
            or _index_lock.locked()
            or (_index_synced_at and now-_index_synced_at<INDEX_SECONDS)
            or (_index_lazy_attempt_at and now-_index_lazy_attempt_at<INDEX_LAZY_RETRY_SECONDS)):
        return False
    _index_lazy_attempt_at=now
    _index_lazy_task=asyncio.create_task(_background_account_index_refresh())
    return True

@app.get("/api/account-groups")
async def account_groups_list(request:Request,
                              offset:int=Query(0,ge=0,le=10000000),
                              limit:int=Query(30,ge=1,le=100)):
    check_auth(request)
    if not INDEX_DB:
        raise HTTPException(503,"Private account-index storage not configured")
    return JSONResponse(await asyncio.to_thread(
        account_groups.groups_page, INDEX_DB, offset=offset, limit=limit),
        headers={"Cache-Control":"private, no-store"})

@app.get("/api/accounts/status")
async def accounts_status(request:Request):
    check_auth(request)
    if not INDEX_DB:
        raise HTTPException(503,"Private account-index storage not configured")
    # Indexing must not block the UI; the background refresh is also periodic.
    schedule_lazy_account_index_refresh()
    data=await asyncio.to_thread(account_index.status,INDEX_DB)
    if os.getenv("DEMAND_AUTO_PUBLIC_INDEX","1")=="1":
        data["public_scan_windows"]=await asyncio.to_thread(account_index_sources.coverage,INDEX_DB)
    # A Render OOM restart may reset process state without deleting SQLite.
    # Recover only a previously signed import receipt with valid digest,
    # monotonically scoped run ID, checked SQLite and nonempty rows.
    if (not _index_snapshot_info["verified"] and data["accounts"]>0
            and data["source_rows"]>0):
        recovered=await asyncio.to_thread(verified_signed_import_receipt,INDEX_DB)
        if recovered:
            _index_snapshot_info.update(verified=True,catalog="not_verified")
            print("ACCOUNT_INDEX_SIGNED_IMPORT_RECEIPT_RECOVERED",
                  json.dumps({"accounts":data["accounts"],
                              "source_rows":data["source_rows"]}),flush=True)
    data.update({"refreshing":_index_lock.locked(),
                 "refresh_error":_index_last_error,"persistent_db_configured":True,
                 "remote_snapshot_verified":_index_snapshot_info["verified"],
                 "remote_catalog_state":_index_snapshot_info["catalog"]})
    return JSONResponse(data,headers={"Cache-Control":"private, no-store"})

@app.get("/api/accounts")
async def accounts_list(request:Request,offset:int=Query(0,ge=0,le=10000000),
                        limit:int=Query(80,ge=1,le=100),
                        q:str=Query("",max_length=80),platform:str=Query("",max_length=20)):
    check_auth(request)
    if not INDEX_DB:
        raise HTTPException(503,"Private account-index storage not configured")
    try:
        data=await asyncio.to_thread(account_index.page,INDEX_DB,offset,limit,q,platform)
    except ValueError as error:
        raise HTTPException(400,str(error)) from None
    return JSONResponse(data,headers={"Cache-Control":"private, no-store"})

@app.post("/api/accounts/sync")
async def accounts_sync(request:Request):
    check_auth(request)
    if _index_synced_at and time.monotonic()-_index_synced_at<300:
        raise HTTPException(429,"Account-index sync recently completed")
    await refresh_account_index(force=True)
    return JSONResponse(await asyncio.to_thread(account_index.status,INDEX_DB),
                        headers={"Cache-Control":"private, no-store"})

@app.get("/api/health")
async def health():
    return {"service":"demand-research-terabox","cloud":"terabox","configured":configured(),"data_cached":_cache["posts"] is not None}

# An authenticated, operator-enabled, one-page provider bridge.
# Default OFF. No API key, cookies, personal results or media bytes are exposed
# through public Pages, the repo, job artifacts or the cloud catalog.
_search_cache={}
_search_lock=asyncio.Lock()
_search_usage={"date":"","requests":0}
_SEARCH_TTL_SECONDS=600

@app.get("/api/discovery/status")
async def discovery_status(request:Request):
    check_auth(request)
    enabled=os.getenv("DEMAND_SOCIAL_SEARCH_ENABLED","")=="1"
    key=os.getenv("DEMAND_SOCIALCRAWL_API_KEY","")
    budget=int(os.getenv("DEMAND_SOCIAL_MAX_DAILY_CALLS","0") or "0")
    return JSONResponse({"enabled":enabled and bool(key) and budget>0,
                         "providers":list(ROUTES),"terms":list(TERMS),
                         "max_daily_calls":max(0,budget)},
                        headers={"Cache-Control":"private, no-store"})

@app.get("/api/discovery")
async def discovery(request:Request,
                    platform:str=Query(...,min_length=1,max_length=20),
                    term:str=Query(...,min_length=1,max_length=20),
                    start:str=Query(...,min_length=10,max_length=10),
                    end:str=Query(...,min_length=10,max_length=10),
                    cursor:str=Query("",max_length=900)):
    check_auth(request)
    if platform not in ROUTES or term not in TERMS:
        raise HTTPException(400,"unsupported source or term")
    if os.getenv("DEMAND_SOCIAL_SEARCH_ENABLED","")!="1":
        raise HTTPException(503,"External social search disabled")
    key=os.getenv("DEMAND_SOCIALCRAWL_API_KEY","")
    limit=int(os.getenv("DEMAND_SOCIAL_MAX_DAILY_CALLS","0") or "0")
    if len(key)<12 or limit<=0:
        raise HTTPException(503,"External social provider not configured")
    try:
        begin=datetime.strptime(start,"%Y-%m-%d").replace(tzinfo=timezone.utc)
        finish=datetime.strptime(end,"%Y-%m-%d").replace(tzinfo=timezone.utc)+timedelta(days=1)
    except ValueError:
        raise HTTPException(400,"invalid dates") from None
    now=datetime.now(timezone.utc)
    if finish<=begin or finish-begin>timedelta(days=32) or begin>now or finish>now+timedelta(days=2):
        raise HTTPException(400,"invalid date window")
    cache_key=(platform,term,start,end,cursor)
    async with _search_lock:
        cached=_search_cache.get(cache_key)
        if cached and time.monotonic()-cached["at"]<_SEARCH_TTL_SECONDS:
            return JSONResponse({**cached["response"],"cache":"gateway"},
                                headers={"Cache-Control":"private, no-store"})
        today=now.date().isoformat()
        if _search_usage["date"]!=today:
            _search_usage.update(date=today,requests=0)
        if _search_usage["requests"]>=min(limit,80):
            raise HTTPException(429,"Daily operator-configured call guard reached")
        _search_usage["requests"]+=1
        try:
            result=await asyncio.to_thread(request_one_page,key,platform,term,begin,finish,cursor)
        except ValueError as error:
            # Fail closed; never forward paid-provider responses or credentials.
            raise HTTPException(502,str(error)[:100]) from None
        if INDEX_DB and result.get("items"):
            try:
                await asyncio.to_thread(account_index.ingest_discovery,INDEX_DB,result["items"])
            except Exception as error:
                print("ACCOUNT_INDEX_DISCOVERY_FAILED",type(error).__name__,flush=True)
        _search_cache[cache_key]={"at":time.monotonic(),"response":result}
        # Do not retain all searches indefinitely in long-lived workers.
        if len(_search_cache)>100:
            for key_to_del,_ in sorted(_search_cache.items(),key=lambda pair:pair[1]["at"])[:40]:
                del _search_cache[key_to_del]
        return JSONResponse(result,headers={"Cache-Control":"private, no-store"})

# Read-only diagnostic counts. This exposes no account identity, content,
# cookie, signed media URL or cloud key; operators can distinguish an empty
# archive from an unavailable TeraBox read instead of seeing a blank screen.
_archive_probe={"at":0.0,"value":None}
_archive_probe_lock=asyncio.Lock()

def _archive_inventory():
    # A free 512MiB Render instance must NEVER enumerate the entire TeraBox
    # root merely to paint a status label. Even a shallow rclone lsf can load
    # many remote items and trigger OOM while multiple browser tabs reload.
    # Actual verified posts and account ZIPs remain browsable via their own
    # authenticated API. This diagnostic listing is opt-in only.
    # Object existence is never represented as remote SHA verification.
    remote_list=os.getenv("DEMAND_ARCHIVE_OVERVIEW_REMOTE_LIST","0")=="1"
    result={"automated_posts":None,"post_journal_candidates":None,
            "account_zip_candidates":None,"account_zip_read_verified":None,
            "account_registry_count":None,
            "automated_posts_state":"not_read_verified",
            "post_journal_state":"not_checked",
            "account_bundles_state":"not_checked",
            "account_registry_state":"not_checked"}
    cached=_cache.get("posts")
    if cached is not None:
        result["automated_posts"]=len(cached)
        result["automated_posts_state"]="cached_verified"
    if not remote_list:
        result["post_journal_state"]="listing_deferred_memory_guard"
        result["account_bundles_state"]="listing_deferred_memory_guard"
        result["account_registry_state"]="listing_deferred_memory_guard"
        return result
    root=CloudArchive(REMOTE)
    try:
        raw=root.command(["lsf",root.remote,"--files-only",
                          "--retries","1"],timeout=28)
        names=raw.decode("utf-8","replace").splitlines()
        result["account_zip_candidates"]=sum(
            1 for name in names if re.fullmatch(
                r"account-bundle-[a-f0-9]{16}-[0-9]{6,30}-[a-f0-9]{16}\.zip",name))
        result["account_bundles_state"]=(
            "candidates_unverified" if result["account_zip_candidates"]
            else "zero_candidates_unverified")
    except (RuntimeError,ValueError,TypeError):
        result["account_bundles_state"]="listing_failed"
    try:
        raw=root.command(["lsf",root.remote+"/metadata","--files-only",
                          "--retries","1"],timeout=28,allow_missing=True)
        if raw is None:
            result["post_journal_state"]="listing_unavailable"
        else:
            names=raw.decode("utf-8","replace").splitlines()
            result["post_journal_candidates"]=sum(
                1 for name in names if re.fullmatch(
                    r"flat-entry-[a-f0-9]{40}\.json",name))
            result["post_journal_state"]="candidates_unverified"
    except (RuntimeError,ValueError,TypeError):
        result["post_journal_state"]="listing_failed"
    return result

async def _get_archive_inventory():
    if not configured():
        raise HTTPException(503,"Archive storage connection is being restored")
    if (_archive_probe["value"] is not None and
            time.monotonic()-_archive_probe["at"]<180):
        return _archive_probe["value"]
    async with _archive_probe_lock:
        if (_archive_probe["value"] is not None and
                time.monotonic()-_archive_probe["at"]<180):
            return _archive_probe["value"]
        try:
            value=await asyncio.wait_for(asyncio.to_thread(_archive_inventory),timeout=85)
        except (TimeoutError,RuntimeError,ValueError):
            raise HTTPException(503,"Archive readback timed out") from None
        _archive_probe.update(at=time.monotonic(),value=value)
        return value

@app.get("/api/archive-overview")
async def archive_overview(request:Request):
    check_auth(request)
    return JSONResponse(await _get_archive_inventory(),
                        headers={"Cache-Control":"private, no-store"})

@app.get("/api/bridge/diagnostics",include_in_schema=False)
async def bridge_archive_diagnostics(request:Request):
    _bridge_authenticated(request)
    return JSONResponse(await _get_archive_inventory(),
                        headers={"Cache-Control":"private, no-store"})

def _verify_latest_account_zip():
    # This is deliberately separate from the fast listing endpoint:
    # only independent TeraBox ZIP bytes and all manifest SHA hashes can
    # establish a validated backup. Never return account identities.
    from verified_bundle_reader import names_from_cloud, load_verified_bundle
    root=CloudArchive(REMOTE)
    try:
        filenames=names_from_cloud(root)
        if not filenames:
            return {"state":"NO_ZIP_CANDIDATES","posts":None,"objects":None}
        archive=load_verified_bundle(root,filenames[0])
        return {"state":"SHA_VERIFIED","posts":archive.post_count,
                "objects":archive.object_count}
    except (RuntimeError,ValueError,TypeError,KeyError):
        return {"state":"READBACK_UNVERIFIED","posts":None,"objects":None}

@app.get("/api/bridge/verify-one",include_in_schema=False)
async def verify_one_account_archive(request:Request):
    _bridge_authenticated(request)
    if not configured():
        raise HTTPException(503,"Private archive storage unavailable")
    try:
        data=await asyncio.wait_for(
            asyncio.to_thread(_verify_latest_account_zip),timeout=85)
    except TimeoutError:
        data={"state":"READBACK_TIMED_OUT","posts":None,"objects":None}
    return JSONResponse(data,headers={"Cache-Control":"private, no-store"})

@app.get("/api/posts")
async def list_posts(request:Request,offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=60),q:str=Query("",max_length=100),
                     platform:str=Query("",max_length=32),media_status:str=Query("",max_length=16)):
    check_auth(request)
    if platform not in ("","bluesky","mastodon","misskey","lemmy"):
        raise HTTPException(400,"Invalid platform filter")
    if media_status not in ("","complete","partial"):
        raise HTTPException(400,"Invalid attachment status filter")
    posts=await get_catalog()
    if q: posts=[p for p in posts if q.casefold() in p["text"].casefold()]
    if platform: posts=[p for p in posts if p.get("platform")==platform]
    if media_status:
        def complete(p):
            return bool(p.get("archive_complete",len(p.get("media",[]))>=p.get("media_expected",len(p.get("media",[])))))
        posts=[p for p in posts if complete(p)==(media_status=="complete")]
    posts=sorted(posts,key=lambda p:p.get("posted_at",""),reverse=True)
    exp=int(time.time())+3600
    output=[]
    for post in posts[offset:offset+limit]:
        media=[]
        for i,m in enumerate(post["media"]):
            media.append({"kind":m.get("kind","unknown"),"mime":m["mime"],"bytes":m["bytes"],"verified":True,
                          "url":"/api/media/"+post["id"]+"/"+str(i)+"?exp="+str(exp)+"&sig="+media_signature(post["id"],i,exp)})
        output.append({"id":post["id"],"platform":post.get("platform","unknown"),"posted_at":post.get("posted_at",""),
                       "text":post["text"],"media":media,"reply_count":post.get("reply_count",0),
                       "source_url":post.get("source_url",""),
                        "profile_url":post.get("profile_url",""),
                        "media_expected":post.get("media_expected",len(post["media"])),
                        "media_saved":len(post["media"]),
                        "capture_status":"remote_verified" if post.get("archive_complete",True) else "partial_media"})
    age=max(0,int(time.time()-_cache["at"])) if _cache["posts"] is not None else None
    return {"total":len(posts),"offset":offset,"limit":limit,"posts":output,
            "storage":"TeraBox",
            "verified_catalog_cache_age_seconds":age,
            "verified_catalog_refresh_pending":bool(_catalog_task is not None
                                                  and not _catalog_task.done())}

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
    # Metadata checks alone do not certify the original bytes actually
    # returned by this backend. Fail closed if a stale/corrupt TeraBox read
    # doesn't match the SHA256 originally committed to the private journal.
    if not 0<total<=80_000_000:
        raise HTTPException(413,"Original media exceeds safe readback size")
    original=await asyncio.to_thread(
        CloudArchive(REMOTE).read_verified,item["key"],item["sha256"],cap=total+1)
    if original is None or len(original)!=total:
        raise HTTPException(502,"Original media remote checksum unverified")
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
    return Response(original[start:end+1],status_code=status,media_type=item["mime"],headers=headers)

# Read-only SNS-style account archive must be registered BEFORE the
# single-segment script catchall. All routes check the private signed session.
from target_account_viewer import create_router as create_account_viewer_router
app.include_router(create_account_viewer_router(check_auth))

# A previously loaded device can render a PUBLIC shell while Render wakes.
# The worker does not cache private posts, account details or API responses.
@app.get("/intersection-sw.js",include_in_schema=False)
async def public_shell_worker():
    return FileResponse(VIEW_FILE.parent/"intersection-sw.js",
        media_type="application/javascript",
        headers={"Cache-Control":"no-store","Service-Worker-Allowed":"/",
                 "X-Content-Type-Options":"nosniff"})

# Allow only the browser's three known scripts and fixed SVG assets. Never
# expose the Python source tree, cloud files or private database via StaticFiles.
@app.get("/{asset_name}",include_in_schema=False)
async def viewer_script(asset_name:str):
    if asset_name not in {"account_auto_analysis.js","account_index_client.js","account_group_client.js","account_watch.js","archive_tab.js","free_discovery.js","live_feed_recovery.js","bsky_search_fallback.js","post_activity_ranking.js","public_video_trends.js","target_archive_client.js"}:
        raise HTTPException(404,"Not found")
    return FileResponse(VIEW_FILE.parent/asset_name,media_type="application/javascript",
        headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})

@app.get("/assets/{asset_name}",include_in_schema=False)
async def viewer_asset(asset_name:str):
    if not re.fullmatch(r"[a-z0-9_-]{1,50}\.svg",asset_name):
        raise HTTPException(404,"Not found")
    path=VIEW_FILE.parent/"assets"/asset_name
    if not path.is_file():
        raise HTTPException(404,"Not found")
    return FileResponse(path,media_type="image/svg+xml",
                        headers={"Cache-Control":"public,max-age=3600","X-Content-Type-Options":"nosniff"})

# Authenticated command routes are separate from public read-only APIs.
app.include_router(create_target_archive_router(check_auth))

# Render's free instance suspends and loses in-memory values. This must run
# before the first HTTP request after a cold start. GitHub Actions publishes
# only an authenticated-encrypted blob, sealed to this Render-only private key.
async def _restore_cloud_credential():
    global COOKIE
    if COOKIE or not os.getenv("DEMAND_ARCHIVE_SEAL_PRIVATE"):
        return
    from sealed_credentials import restore_from_github
    try:
        recovered=await asyncio.wait_for(asyncio.to_thread(
            restore_from_github,os.environ["DEMAND_ARCHIVE_SEAL_PRIVATE"]),timeout=16)
    except (RuntimeError,ValueError,TypeError,TimeoutError,OSError,KeyError) as error:
        print("SEALED_ARCHIVE_COLD_RESTORE_NOT_READY",type(error).__name__,flush=True)
        return
    COOKIE=recovered
    os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]=recovered
    print("SEALED_ARCHIVE_COLD_RESTORE_SUCCESS",flush=True)
    if INDEX_DB and _index_task is None:
        await start_account_index()

@app.on_event("startup")
async def cold_start_cloud_restore():
    await _restore_cloud_credential()


