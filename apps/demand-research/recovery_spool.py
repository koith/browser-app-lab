"""Encrypted, short-lived emergency spool for source-verified public posts.

TeraBox's unofficial upload backend sometimes fails after it has accepted a
public first observation or original attachment. A GitHub Actions job must not
lose its only in-memory copy when it exits. Only AES-256-GCM ciphertext is
eligible for upload as a restricted Actions artifact, never plaintext bytes,
URLs, author profiles, post text, or media.

This is a temporary recovery buffer, NOT a replacement for verified TeraBox
archive storage. The repair workflow imports and SHA-verifies each object
before counting it as recovered. Requires a high-entropy Actions secret; the
existing private archive cookie is a compatible fallback while it remains
valid. A dedicated DEMAND_ARCHIVE_RECOVERY_KEY survives cookie rotation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import tempfile
import zlib

from demand_archive import ID, MAX_MEDIA_BYTES, canonical_json, sha256, validate_post

MAGIC=b"INTSP1"
AAD=b"intersection-private-recovery-v1"
MAX_BUFFER_BYTES=96*1024*1024
MAX_BLOBS=16
FILE_PATTERN=re.compile(r"[a-f0-9]{64}\.enc\Z")


def _encryption_secret():
    secret=(os.getenv("DEMAND_ARCHIVE_RECOVERY_KEY")
            or os.getenv("RCLONE_CONFIG_ARCHIVE_COOKIE") or "")
    if len(secret)<24:
        raise RuntimeError("private recovery encryption key unavailable")
    return secret.encode("utf-8")


def _crypto():
    # Imported only when explicitly enabling private recovery. A captured
    # original is never written to disk if authenticated encryption is absent.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM


def _key(secret,salt):
    # Per-object salt and costly KDF; no token or derivation values are logged.
    return hashlib.pbkdf2_hmac("sha256",secret,salt,360_000,dklen=32)


def _filename(pid,secret):
    if not isinstance(pid,str) or ID.fullmatch(pid) is None:
        raise ValueError("unsafe first-observation id")
    return hmac.new(secret,pid.encode("ascii"),hashlib.sha256).hexdigest()+".enc"


def _decode_file(raw,secret):
    if not isinstance(raw,bytes) or not 34<len(raw)<=MAX_BUFFER_BYTES+2048:
        raise ValueError("invalid encrypted buffer size")
    if not raw.startswith(MAGIC):
        raise ValueError("invalid encrypted buffer header")
    salt=raw[6:22]
    nonce=raw[22:34]
    from cryptography.exceptions import InvalidTag
    try:
        decrypted=_crypto()(_key(secret,salt)).decrypt(nonce,raw[34:],AAD)
    except InvalidTag:
        # Incorrect key or tampering is a recoverable, privacy-safe failure.
        # Never expose ciphertext or personal originals in exception text.
        raise ValueError("encrypted recovery authentication failed") from None
    # Bound decompression to avoid a hostile artifact consuming unlimited RAM.
    decomp=zlib.decompressobj()
    try:
        plain=decomp.decompress(decrypted,MAX_BUFFER_BYTES+1)
    except zlib.error:
        raise ValueError("invalid compressed private recovery record") from None
    if len(plain)>MAX_BUFFER_BYTES or not decomp.eof or decomp.unused_data:
        raise ValueError("invalid recovered buffer payload")
    result=json.loads(plain)
    if not isinstance(result,dict) or result.get("schema")!=1:
        raise ValueError("invalid buffer record")
    first=result.get("first")
    if not isinstance(first,dict) or not isinstance(first.get("id"),str):
        raise ValueError("invalid original observation")
    if not ID.fullmatch(first["id"]):
        raise ValueError("invalid original id")
    if not isinstance(result.get("media"),list) or len(result["media"])>MAX_BLOBS:
        raise ValueError("invalid original attachment list")
    if result.get("post") is not None:
        post=validate_post(result["post"])
        compared=("id","platform","source_url","posted_at","text")
        if (len(post["media"])!=len(result["media"])
                or any(post.get(field)!=first.get(field) for field in compared)
                or post.get("media_expected")!=len(first.get("media_links",[]))):
            raise ValueError("post and original media identity mismatch")
    return result


class RecoverySpool:
    def __init__(self, directory=None, secret=None):
        self.directory=Path(directory or os.environ["DEMAND_RECOVERY_SPOOL_DIR"])
        self.secret=secret if isinstance(secret,bytes) else _encryption_secret()
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.directory.chmod(0o700)

    @classmethod
    def from_environment(cls):
        root=os.getenv("DEMAND_RECOVERY_SPOOL_DIR")
        return cls(root) if root else None

    def _path(self,pid):
        return self.directory/_filename(pid,self.secret)

    def save(self,pid,first,post=None,blobs=(),*,verified_remote_first=False):
        if first.get("id")!=pid or ID.fullmatch(str(pid)) is None:
            raise ValueError("wrong source observation id")
        original=first
        old_post=None
        old_media=[]
        target=self._path(pid)
        if target.exists():
            prior=_decode_file(target.read_bytes(),self.secret)
            original=(first if verified_remote_first else prior["first"])
            # The immutable cloud first sighting is authoritative if it has
            # independently verified to be an earlier observation than the
            # local pre-write safety copy from this process.
            old_post=prior["post"]
            old_media=prior["media"]
        if post is not None:
            validate_post(post)
            if post["id"]!=pid or len(blobs)!=len(post["media"]):
                raise ValueError("incomplete source attachment payload")
            serial=[]
            for info,blob in zip(post["media"],blobs):
                if (not isinstance(blob,bytes) or len(blob)!=info["bytes"]
                        or sha256(blob)!=info["sha256"]
                        or len(blob)>MAX_MEDIA_BYTES):
                    raise ValueError("original attachment checksum mismatch")
                serial.append(base64.b64encode(blob).decode("ascii"))
        else:
            post=old_post
            serial=old_media
        record={"schema":1,"first":original,"post":post,"media":serial}
        zipped=zlib.compress(canonical_json(record),level=6)
        if len(zipped)>MAX_BUFFER_BYTES:
            raise ValueError("encrypted capture exceeds bounded recovery size")
        salt=os.urandom(16)
        nonce=os.urandom(12)
        sealed=MAGIC+salt+nonce+_crypto()(_key(self.secret,salt)).encrypt(nonce,zipped,AAD)
        with tempfile.NamedTemporaryFile(dir=self.directory,prefix="sealed-",suffix=".tmp",
                                         delete=False) as fp:
            os.chmod(fp.name,0o600)
            fp.write(sealed)
            fp.flush()
            os.fsync(fp.fileno())
            tmp=Path(fp.name)
        tmp.replace(target)
        target.chmod(0o600)
        return target

    def discard(self,pid):
        target=self._path(pid)
        if target.exists():
            target.unlink()

    def read(self,path):
        path=Path(path)
        if not FILE_PATTERN.fullmatch(path.name):
            raise ValueError("unsafe encrypted artifact name")
        return _decode_file(path.read_bytes(),self.secret)

    def restore(self,path,cloud):
        record=self.read(path)
        first=record["first"]
        pid=first["id"]
        if path.name!=_filename(pid,self.secret):
            raise ValueError("encrypted artifact filename identity mismatch")
        original=canonical_json(first)
        current=cloud.save_first_observation(pid,original,prefer_flat=True)
        if current!=original:
            # An earlier saved observation may have a different captured time
            # but still describe exactly this public source. Resume media only
            # when all independent identity/content fields match; otherwise
            # preserve the earlier original and refuse a silent substitution.
            previous=json.loads(current)
            compared=("id","platform","source_url","posted_at","text","media_links")
            if any(previous.get(field)!=first.get(field) for field in compared):
                return "prior_original_preserved"
        post=record.get("post")
        if post is None:
            return "first_observation_verified"
        blobs=[base64.b64decode(x,validate=True) for x in record["media"]]
        if len(blobs)!=len(post["media"]):
            raise ValueError("original media attachment count mismatch")
        for info,blob in zip(post["media"],blobs):
            if len(blob)!=info["bytes"] or sha256(blob)!=info["sha256"]:
                raise ValueError("recovered original attachment checksum mismatch")
        if post.get("archive_complete"):
            cloud.save_post(post,blobs)
            return "post_and_media_verified"
        if blobs:
            cloud.stage_partial_media(post,blobs)
        return "original_media_incomplete"


def recover_directory(directory,cloud,secret=None):
    spool=RecoverySpool(directory=directory,secret=secret)
    counts={"buffer_files":0,"first_observation_verified":0,
            "post_and_media_verified":0,"original_media_incomplete":0,
            "prior_original_preserved":0,"failures":0}
    for path in sorted(spool.directory.glob("*.enc")):
        counts["buffer_files"]+=1
        try:
            status=spool.restore(path,cloud)
            counts[status]+=1
        except (RuntimeError,ValueError,KeyError,TypeError,OverflowError):
            counts["failures"]+=1
    return counts
