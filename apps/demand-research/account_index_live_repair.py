"""Deliver a previously SHA-verified immutable account index to the free viewer.

This backup channel does NOT create, modify or delete TeraBox originals.
GitHub OIDC authenticates the exact approved main-branch workflow; the raw
SQLite index is transferred only over HTTPS and never written to repository
artifacts or action logs.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from account_index_job import latest_manifest, latest_manifest_from_public_actions, load_snapshot

GATEWAY="https://intersection-originals-free.onrender.com"
AUDIENCE="intersection-originals-free/credential-v1"
MAX_INDEX_BYTES=8*1024*1024

def validated_index():
    print("ACCOUNT_INDEX_LIVE_PHASE manifest_lookup",flush=True)
    manifest=latest_manifest() or latest_manifest_from_public_actions()
    if not manifest:
        raise RuntimeError("private index manifest unavailable")
    print("ACCOUNT_INDEX_LIVE_PHASE manifest_verified",flush=True)
    match=re.fullmatch(r"snapshot-([0-9]{6,30})\.sqlite3",manifest["file"])
    if not match:
        raise ValueError("unsafe immutable index revision")
    with tempfile.TemporaryDirectory(prefix="private-index-transfer-") as temp:
        path=Path(temp)/"index.sqlite3"
        load_snapshot(path,manifest)
        print("ACCOUNT_INDEX_LIVE_PHASE snapshot_sha_verified",flush=True)
        size=path.stat().st_size
        if not 0<size<=MAX_INDEX_BYTES:
            raise ValueError("private index exceeds safe viewer bound")
        payload=path.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=manifest["sha256"]:
            raise RuntimeError("private index readback mismatch")
        with sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("invalid index database")
            accounts=db.execute("SELECT count(*) FROM accounts").fetchone()[0]
            rows=db.execute("SELECT count(*) FROM observed").fetchone()[0]
            if not (0<accounts and 0<rows):
                raise ValueError("invalid empty index")
        print("ACCOUNT_INDEX_LIVE_PHASE sqlite_integrity_verified",flush=True)
        return {"run_id":match.group(1),"sha":manifest["sha256"],
                "payload":payload,"accounts":accounts,"source_rows":rows}

def signed_assertion():
    endpoint=os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    sep="&" if "?" in endpoint else "?"
    url=endpoint+sep+urlencode({"audience":AUDIENCE})
    request=Request(url,headers={
        "Authorization":"bearer "+os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urlopen(request,timeout=20) as response:
        return json.load(response)["value"]

def push():
    candidate=validated_index()
    print("ACCOUNT_INDEX_LIVE_PHASE viewer_warmup",flush=True)
    # Wake a sleeping free Render instance BEFORE issuing the short-lived JWT.
    for retry in range(3):
        try:
            with urlopen(GATEWAY+"/health",timeout=45) as response:
                if response.status==200:
                    break
        except (TimeoutError,OSError,URLError,HTTPError):
            if retry==2:
                raise RuntimeError("free viewer unavailable")
            time.sleep(5)
    print("ACCOUNT_INDEX_LIVE_PHASE viewer_ready",flush=True)
    token=signed_assertion()
    print("ACCOUNT_INDEX_LIVE_PHASE oidc_issued",flush=True)
    req=Request(GATEWAY+"/api/bridge/index-snapshot",
        data=candidate["payload"],method="POST",headers={
            "Content-Type":"application/octet-stream",
            "Authorization":"Bearer "+token,
            "X-Index-SHA256":candidate["sha"],
            "X-Index-Source-Run":candidate["run_id"]})
    print("ACCOUNT_INDEX_LIVE_PHASE signed_https_post",flush=True)
    with urlopen(req,timeout=70) as response:
        outcome=json.load(response)
    if (outcome.get("accepted") is not True
        or outcome.get("accounts")!=candidate["accounts"]
        or outcome.get("source_rows")!=candidate["source_rows"]):
        raise RuntimeError("private viewer index handshake invalid")
    print("ACCOUNT_INDEX_LIVE_IMPORT_VERIFIED",json.dumps({
        "accounts":candidate["accounts"],"source_rows":candidate["source_rows"],
        "transport":"verified_https_oidc","snapshot_sha256":True
    },sort_keys=True),flush=True)

    # The live Render database is ephemeral. An immutable daily AES-GCM asset
    # provides a no-fee, no-private-plaintext, authenticated cold-start copy.
    # Obtain its derived key ONLY from the trusted OIDC viewer bridge.
    import account_index_bootstrap
    key_request=Request(GATEWAY+"/api/bridge/archive-key",headers={
        "Authorization":"Bearer "+token})
    with urlopen(key_request,timeout=30) as response:
        key_payload=json.load(response)
    try:
        bridge_key=base64.b64decode(key_payload["key"],validate=True)
    except (KeyError,TypeError,ValueError):
        raise RuntimeError("private encrypted index key unavailable") from None
    ciphertext=account_index_bootstrap.encrypt_snapshot(
        candidate["payload"],bridge_key,candidate["run_id"],candidate["sha"])
    result=account_index_bootstrap.publish_daily(ciphertext,bridge_key)
    print("ACCOUNT_INDEX_ENCRYPTED_BOOT_RELEASE_VERIFIED",json.dumps({
        "new_upload":result["new_upload"],
        "accounts":result["accounts"],"source_rows":result["source_rows"],
        "encrypted_remote_readback":result["remote_sha256"]
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:
        push()
    except Exception as error:
        # Fixed exception classes only: no HTTP bodies, tokens or TeraBox paths.
        safe=("RuntimeError","ValueError","TimeoutError","URLError","HTTPError",
              "KeyError","OSError","OperationalError","DatabaseError")
        category=type(error).__name__
        print("ACCOUNT_INDEX_LIVE_IMPORT_FAILURE_CLASS",
              category if category in safe else "Other",flush=True)
        raise SystemExit("ACCOUNT_INDEX_LIVE_IMPORT_UNVERIFIED") from None
