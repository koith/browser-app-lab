"""AES-GCM sealed, SHA-checked account-index cold-start recovery.

Only encrypted SQLite bytes are published as immutable GitHub Release assets.
The secret comes from the already-configured Render viewer token, never from
the repository, release, or private provider cookie. This is a small fallback
checkpoint, not a replacement for hourly verified live OIDC delivery.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO="koith/browser-app-lab"
API="https://api.github.com/repos/"+REPO
TAG_PREFIX="intersection-index-boot-"
TAG=re.compile(r"^intersection-index-boot-([0-9]{8})$")
ASSET="index.enc"
MAGIC=b"INTIDX1"
AAD=b"intersection-account-index-cold-start-v1"
MAX_RAW=8*1024*1024
MAX_CIPHER=MAX_RAW+512
RUN=re.compile(r"^[0-9]{6,30}$")
SHA=re.compile(r"^[a-f0-9]{64}$")


def _key(bridge_key:bytes)->bytes:
    if not isinstance(bridge_key,bytes) or len(bridge_key)!=32:
        raise ValueError("invalid private viewer encryption key")
    return hmac.new(bridge_key,AAD,hashlib.sha256).digest()


def _check_sqlite(raw:bytes):
    if not 64<=len(raw)<=MAX_RAW or not raw.startswith(b"SQLite format 3\x00"):
        raise ValueError("invalid private index size/header")
    with tempfile.TemporaryDirectory(prefix="int-index-check-") as directory:
        p=Path(directory)/"verified.sqlite3"
        p.write_bytes(raw)
        with sqlite3.connect("file:"+str(p)+"?mode=ro",uri=True,timeout=5) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("invalid private index SQLite")
            accounts=conn.execute("SELECT count(*) FROM accounts").fetchone()[0]
            observed=conn.execute("SELECT count(*) FROM observed").fetchone()[0]
        if not (isinstance(accounts,int) and accounts>0
                and isinstance(observed,int) and observed>0):
            raise ValueError("empty private index")
        return accounts,observed


def encrypt_snapshot(raw:bytes, bridge_key:bytes, run_id:str, sha256:str)->bytes:
    if not RUN.fullmatch(str(run_id)) or not SHA.fullmatch(str(sha256)):
        raise ValueError("invalid private source revision")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),sha256):
        raise ValueError("private snapshot digest mismatch")
    _check_sqlite(raw)
    header=json.dumps({"run":str(run_id),"sha":sha256},sort_keys=True,
                      separators=(",",":")).encode()
    if len(header)>256:
        raise ValueError("oversized private source manifest")
    plain=len(header).to_bytes(2,"big")+header+raw
    nonce=os.urandom(12)
    ciphertext=MAGIC+nonce+AESGCM(_key(bridge_key)).encrypt(nonce,plain,AAD)
    if len(ciphertext)>MAX_CIPHER:
        raise ValueError("oversized private encrypted snapshot")
    return ciphertext


def decrypt_snapshot(ciphertext:bytes, bridge_key:bytes):
    if not (isinstance(ciphertext,bytes) and len(MAGIC)+12+16+66<=len(ciphertext)<=MAX_CIPHER
            and ciphertext.startswith(MAGIC)):
        raise ValueError("invalid encrypted private index size/version")
    try:
        plain=AESGCM(_key(bridge_key)).decrypt(
            ciphertext[len(MAGIC):len(MAGIC)+12],
            ciphertext[len(MAGIC)+12:],AAD)
    except Exception:
        raise ValueError("private index authentication failed") from None
    header_size=int.from_bytes(plain[:2],"big")
    if not 0<header_size<=256 or 2+header_size>=len(plain):
        raise ValueError("invalid authenticated private index manifest")
    try:
        meta=json.loads(plain[2:2+header_size])
    except (ValueError,UnicodeError,TypeError):
        raise ValueError("invalid authenticated private index manifest") from None
    if type(meta) is not dict or set(meta)!={"run","sha"}:
        raise ValueError("invalid private index manifest fields")
    run_id,sha=meta["run"],meta["sha"]
    raw=plain[2+header_size:]
    if not isinstance(run_id,str) or not RUN.fullmatch(run_id):
        raise ValueError("invalid private index revision")
    if not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise ValueError("invalid private index digest")
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),sha):
        raise ValueError("private index content corrupted")
    accounts,observed=_check_sqlite(raw)
    return {"payload":raw,"run_id":run_id,"sha":sha,
            "accounts":accounts,"source_rows":observed}


def tag_for_date(now=None):
    date=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return TAG_PREFIX+date.strftime("%Y%m%d")


def _json(url, token=None):
    if not url.startswith(API+"/"):
        raise ValueError("untrusted private mirror metadata URL")
    headers={"Accept":"application/vnd.github+json",
             "User-Agent":"intersection-index-sealed-bootstrap"}
    if token:
        headers["Authorization"]="Bearer "+token
    with urlopen(Request(url,headers=headers),timeout=20) as response:
        if response.status!=200:
            raise RuntimeError("private mirror GitHub metadata unavailable")
        body=response.read(200000)
    return json.loads(body)


def release_tag(tag,token=None):
    if not TAG.fullmatch(tag):
        raise ValueError("invalid private mirror tag")
    try:
        return _json(API+"/releases/tags/"+tag,token)
    except HTTPError as e:
        if e.code==404:
            return None
        raise RuntimeError("private mirror release lookup unavailable") from None


def _asset(release,tag):
    if (type(release) is not dict or release.get("tag_name")!=tag
            or release.get("draft") or release.get("prerelease") is not True):
        raise ValueError("untrusted encrypted mirror release")
    assets=[a for a in release.get("assets",[]) if type(a) is dict
            and a.get("name")==ASSET]
    if len(assets)!=1:
        raise ValueError("missing or duplicate index mirror asset")
    asset=assets[0]
    expected="https://github.com/"+REPO+"/releases/download/"+tag+"/"+ASSET
    if asset.get("browser_download_url")!=expected:
        raise ValueError("invalid private mirror download URL")
    if (not isinstance(asset.get("size"),int)
            or not 1<=asset["size"]<=MAX_CIPHER):
        raise ValueError("invalid encrypted index release size")
    return asset


def download_cipher(release,tag):
    asset=_asset(release,tag)
    with urlopen(Request(asset["browser_download_url"],headers={
            "User-Agent":"intersection-index-sealed-bootstrap"}),timeout=30) as response:
        ciphertext=response.read(MAX_CIPHER+1)
    if len(ciphertext)!=asset["size"]:
        raise ValueError("incomplete encrypted private index asset")
    expected_digest=asset.get("digest","")
    if expected_digest and expected_digest.startswith("sha256:"):
        if not hmac.compare_digest(expected_digest[7:],
                                  hashlib.sha256(ciphertext).hexdigest()):
            raise ValueError("encrypted index release SHA mismatch")
    return ciphertext


def find_latest_cipher(bridge_key:bytes, now=None, *, lookback_days=7):
    date=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for offset in range(lookback_days):
        tag=tag_for_date(date-timedelta(days=offset))
        release=release_tag(tag)
        if release is None:
            continue
        result=decrypt_snapshot(download_cipher(release,tag),bridge_key)
        result["age_days"]=offset
        return result
    raise RuntimeError("no bounded encrypted private index checkpoint")


def publish_daily(ciphertext:bytes, bridge_key:bytes, *, today=None, token=None):
    """One immutable encrypted release per UTC day; never replace old assets.

    The hourly OIDC transfer still carries fresher indexes. This daily
    checkpoint only fills the cold-start window after free Render sleeps.
    """
    data=decrypt_snapshot(ciphertext,bridge_key)
    tag=tag_for_date(today)
    auth=token or os.environ.get("GITHUB_TOKEN","")
    if not auth:
        raise RuntimeError("private index publish token not configured")
    release=release_tag(tag,auth)
    created=False
    if release is None:
        with tempfile.TemporaryDirectory(prefix="int-sealed-index-") as folder:
            path=Path(folder)/ASSET
            path.write_bytes(ciphertext)
            result=subprocess.run(
                ["gh","release","create",tag,str(path)+"#"+ASSET,
                 "--repo",REPO,"--target","main","--prerelease",
                 "--title","Encrypted INTERSECTION private index boot checkpoint",
                 "--notes","AES-256-GCM ciphertext only; no plaintext profile data"],
                env={**os.environ,"GH_TOKEN":auth},
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                timeout=70,check=False)
            if result.returncode!=0:
                raise RuntimeError("private encrypted index release upload failed")
        created=True
    for attempt in range(7):
        try:
            release=release_tag(tag,auth)
            remote=download_cipher(release,tag)
            existing=decrypt_snapshot(remote,bridge_key)
            if created:
                if (not hmac.compare_digest(remote,ciphertext)
                        or existing["sha"]!=data["sha"]
                        or existing["run_id"]!=data["run_id"]):
                    raise ValueError("private mirror readback differs")
            return {"new_upload":created,"accounts":existing["accounts"],
                    "source_rows":existing["source_rows"],
                    "remote_sha256":True}
        except (HTTPError,URLError,ValueError,RuntimeError,TypeError):
            if attempt==6:
                raise RuntimeError("encrypted index readback not verified") from None
            time.sleep(min(3+attempt,8))
    raise RuntimeError("encrypted index readback unavailable")


def restore_local(db_path:str, bridge_key:bytes):
    import account_index
    if not db_path:
        raise ValueError("private account DB path unavailable")
    target=Path(db_path).expanduser()
    if target.exists():
        try:
            with account_index.connect(str(target)) as conn:
                if conn.execute("SELECT count(*) FROM accounts").fetchone()[0]>0:
                    return {"state":"already_populated"}
        except sqlite3.Error:
            raise RuntimeError("local private index invalid") from None
    source=find_latest_cipher(bridge_key)
    with tempfile.TemporaryDirectory(prefix="int-sealed-restore-") as directory:
        p=Path(directory)/"checked.sqlite3"
        p.write_bytes(source["payload"])
        with sqlite3.connect("file:"+str(p)+"?mode=ro",uri=True,timeout=10) as src:
            target.parent.mkdir(parents=True,exist_ok=True)
            with account_index.connect(str(target)) as dst:
                if dst.execute("SELECT count(*) FROM accounts").fetchone()[0]>0:
                    return {"state":"already_populated"}
                src.backup(dst)
                dst.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                           ("last_imported_index_run",source["run_id"]))
                dst.execute("INSERT OR REPLACE INTO index_meta(key,value) VALUES(?,?)",
                           ("last_imported_index_sha",source["sha"]))
                dst.commit()
    return {"state":"restored","accounts":source["accounts"],
            "source_rows":source["source_rows"],"age_days":source["age_days"]}
