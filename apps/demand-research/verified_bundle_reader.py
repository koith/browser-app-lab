"""Authenticated, SHA-checked read-only adapter for immutable TeraBox ZIPs.

Only the existing private account gateway may call this module. Public GitHub
Pages never see remote archive paths, cookies, ZIP bytes or credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import re
import threading
import time
import zipfile

from demand_archive import CloudArchive, MAX_CATALOG, sha256
from target_account_archive import REGISTRY_RE, archive_key

BUNDLE_RE=re.compile(r"^account-bundle-([a-f0-9]{16})-([0-9]{6,30})-([a-f0-9]{16})\.zip$")
ACCOUNT_RE=re.compile(r"^(bluesky|mastodon)-([a-f0-9]{40})$")
MAX_VIEW_ZIP=90_000_000
MAX_OBJECTS=50_000
MAX_LIST_BYTES=3_000_000
CACHE_SECONDS=90
_cache={}
_lock=threading.Lock()


class BundleInvalid(RuntimeError):
    pass


class VerifiedBundle:
    def __init__(self,name,blob):
        match=BUNDLE_RE.fullmatch(name)
        if not match or not isinstance(blob,bytes) or not 100<len(blob)<=MAX_VIEW_ZIP:
            raise BundleInvalid("invalid private archive bundle")
        self.name=name
        self.account_prefix=match.group(1)
        # An immutable artifact filename embeds the previously remote-verified
        # whole-ZIP digest prefix. Verify it again after reading from TeraBox.
        self.digest=sha256(blob)
        if not self.digest.startswith(match.group(3)):
            raise BundleInvalid("remote ZIP checksum does not match immutable key")
        self.items={}
        self.accounts={}
        try:
            with zipfile.ZipFile(io.BytesIO(blob),"r") as zipped:
                info=zipped.infolist()
                if (len(info)>MAX_OBJECTS+1 or len(info)<2
                        or any(i.is_dir() or i.flag_bits&1
                               or i.compress_type!=zipfile.ZIP_STORED for i in info)):
                    raise BundleInvalid("invalid original ZIP entry metadata")
                names=[i.filename for i in info]
                if len(set(names))!=len(names) or "bundle-manifest.json" not in names:
                    raise BundleInvalid("duplicate or missing ZIP manifest")
                manifest=json.loads(zipped.read("bundle-manifest.json"))
                if (type(manifest) is not dict or manifest.get("schema_version")!=1
                        or manifest.get("format")!="immutable-public-account-bundle-v1"
                        or not isinstance(manifest.get("objects"),list)
                        or not 1<=len(manifest["objects"])<=MAX_OBJECTS):
                    raise BundleInvalid("invalid original source ZIP manifest")
                self.source_state=manifest.get("capture_state")
                self.recorded_at=manifest.get("recorded_at")
                self.selected_platform=manifest.get("selected_platform")
                self.selected_account=manifest.get("selected_account")
                history=manifest.get("ancestor_tags",[])
                if not isinstance(history,list) or len(history)>10000 or (
                    len(set(history))!=len(history)) or any(
                    not isinstance(tag,str) or not re.fullmatch(
                        r"intersection-github-archive-[0-9]{6,30}-a[1-9][0-9]{0,3}",tag)
                    for tag in history):
                    raise BundleInvalid("invalid immutable ancestor references")
                self.ancestor_tags=tuple(history)
                if (self.selected_platform not in ("bluesky","mastodon")
                        or not isinstance(self.selected_account,str)
                        or not 3<=len(self.selected_account)<=260):
                    raise BundleInvalid("invalid reviewed public account in ZIP")
                entries=manifest["objects"]
                stated={item.get("key") for item in entries if isinstance(item,dict)}
                if stated!=set(names)-{"bundle-manifest.json"}:
                    raise BundleInvalid("ZIP entry/manifest mismatch")
                total=0
                for item in entries:
                    key=item["key"]
                    if (not isinstance(key,str) or not 1<=len(key)<=240
                            or not re.fullmatch(r"[A-Za-z0-9_./-]+",key)
                            or key.startswith("/") or ".." in key or "//" in key
                            or not isinstance(item.get("bytes"),int)
                            or not 0<=item["bytes"]<=MAX_VIEW_ZIP
                            or not re.fullmatch(r"[a-f0-9]{64}",str(item.get("sha256","")))):
                        raise BundleInvalid("unsafe immutable ZIP object")
                    value=zipped.read(key)
                    if len(value)!=item["bytes"] or sha256(value)!=item["sha256"]:
                        raise BundleInvalid("immutable ZIP entry SHA mismatch")
                    total+=len(value)
                    if total>MAX_VIEW_ZIP:
                        raise BundleInvalid("ZIP extracted size exceeds memory bound")
                    self.items[key]=value
        except (ValueError,KeyError,TypeError,zipfile.BadZipFile,RuntimeError) as error:
            raise BundleInvalid("private ZIP cannot be independently verified") from error
        # Registry entries bind this ZIP to one exact public SNS identity.
        for key,value in self.items.items():
            if not key.startswith("metadata/target-accounts/"):
                continue
            filename=key.rsplit("/",1)[-1]
            if not REGISTRY_RE.fullmatch(filename):
                continue
            try:
                item=json.loads(value)
                account=item["platform"]+"-"+archive_key(item)
                if (account+".json"==filename
                        and account.startswith(item["platform"]+"-")
                        and account.rsplit("-",1)[-1].startswith(self.account_prefix)):
                    self.accounts[account]=item
            except (ValueError,TypeError,KeyError):
                continue
        if len(self.accounts)!=1:
            raise BundleInvalid("ZIP has no unique verified source identity")
        self.account=next(iter(self.accounts))
        account=self.account
        platform=account.split("-",1)[0]
        identity=account.split("-",1)[1]
        self.prefix="account-archives/"+platform+"/"+identity+"/"
        if (not any(k.startswith(self.prefix) for k in self.items)
                or any(k.startswith("account-archives/") and not k.startswith(self.prefix)
                       for k in self.items)):
            raise BundleInvalid("mixed or missing account source records")
        self.object_count=len(self.items)
        self.post_count=sum(
            k.startswith(self.prefix+"posts/") and k.endswith("/post.json")
            for k in self.items)


class BundleAccountCloud(CloudArchive):
    def __init__(self,bundle):
        self.bundle=bundle
        self.prefix=bundle.prefix
        super().__init__(remote="archive:DemandResearch/account-archives/"+
                         bundle.account.replace("-", "/",1))

    def read(self,key,*,cap=MAX_CATALOG,optional=False,domain=None):
        if (not isinstance(key,str) or key.startswith("/") or ".." in key
                or not re.fullmatch(r"[A-Za-z0-9_./-]+",key)):
            raise ValueError("unsafe archive key")
        data=self.bundle.items.get(self.prefix+key)
        if data is None:
            if optional:return None
            raise RuntimeError("immutable ZIP source record not found")
        if len(data)>cap:
            raise ValueError("source record exceeds read bound")
        return data

    def names(self,prefix):
        if not isinstance(prefix,str) or ".." in prefix or prefix.startswith("/"):
            raise ValueError("unsafe archive prefix")
        head=self.prefix+prefix.rstrip("/")+"/"
        found={key[len(head):] for key in self.bundle.items if key.startswith(head)
               and "/" not in key[len(head):]}
        return sorted(found)

    def read_verified(self,key,expected_digest,*,cap=100_000):
        if not re.fullmatch(r"[a-f0-9]{64}",str(expected_digest)):
            raise ValueError("invalid expected SHA")
        raw=self.read(key,cap=cap,optional=True)
        return raw if raw is not None and sha256(raw)==expected_digest else None


class MergedBundleAccountCloud(BundleAccountCloud):
    """Read-only union across separately SHA-verified immutable ZIP snapshots.

    Never alter a previously saved ZIP. Older originals and all new
    revisions remain individually addressable even when subsequent provider
    history no longer includes them.
    """

    def __init__(self,bundles):
        if not bundles or len(bundles)>50:
            raise BundleInvalid("invalid verified account history length")
        if len({bundle.account for bundle in bundles})!=1:
            raise BundleInvalid("mixed public account history refused")
        # Oldest first so the original observation wins on key collisions.
        self.bundles=tuple(sorted(bundles,
            key=lambda bundle:str(bundle.recorded_at or "")))
        super().__init__(self.bundles[-1])

    def read(self,key,*,cap=MAX_CATALOG,optional=False,domain=None):
        if not isinstance(key,str) or key.startswith("/") or ".." in key or not re.fullmatch(r"[A-Za-z0-9_./-]+",key):
            raise ValueError("unsafe archive key")
        for bundle in self.bundles:
            value=bundle.items.get(self.prefix+key)
            if value is not None:
                if len(value)>cap:
                    raise ValueError("verified original exceeds reader bound")
                return value
        if optional:
            return None
        raise RuntimeError("verified history object unavailable")

    def names(self,prefix):
        if not isinstance(prefix,str) or prefix.startswith("/") or ".." in prefix:
            raise ValueError("unsafe archive prefix")
        head=self.prefix+prefix.rstrip("/")+"/"
        return sorted({key[len(head):] for bundle in self.bundles
                       for key in bundle.items if key.startswith(head)
                       and "/" not in key[len(head):]})

    def read_verified(self,key,expected_digest,*,cap=100_000):
        if not re.fullmatch(r"[a-f0-9]{64}",str(expected_digest)):
            raise ValueError("invalid expected SHA")
        if not isinstance(key,str) or key.startswith("/") or ".." in key:
            raise ValueError("unsafe archive key")
        for bundle in self.bundles:
            value=bundle.items.get(self.prefix+key)
            if value is not None and len(value)<=cap and sha256(value)==expected_digest:
                return value
        return None


def names_from_cloud(root):
    raw=root.command(["lsf",root.remote,"--files-only","--retries","2"],
                     timeout=90,allow_missing=True)
    if raw is None:
        return []
    if not isinstance(raw,bytes) or len(raw)>MAX_LIST_BYTES:
        raise BundleInvalid("private ZIP listing too large")
    return sorted((name for name in raw.decode("utf-8","replace").splitlines()
                   if BUNDLE_RE.fullmatch(name)),
                  key=lambda value:int(BUNDLE_RE.fullmatch(value).group(2)),
                  reverse=True)[:20000]


def load_verified_bundle(root,name):
    if not BUNDLE_RE.fullmatch(name):
        raise BundleInvalid("invalid private bundle filename")
    now=time.monotonic()
    with _lock:
        cached=_cache.get(name)
        if cached and now-cached[0]<CACHE_SECONDS:
            return cached[1]
    raw=root.command(["cat",root.remote+"/"+name,"--retries","2"],
                     timeout=180,allow_missing=True)
    if raw is None:
        raise BundleInvalid("private original ZIP missing")
    bundle=VerifiedBundle(name,raw)
    with _lock:
        if len(_cache)>2:_cache.clear()
        _cache[name]=(time.monotonic(),bundle)
    return bundle


def available_bundles(root):
    # Read one latest verified ZIP for each account, instead of downloading
    # every old 17MB snapshot whenever the browser opens the saved-account list.
    verified_prefixes=set()
    for name in names_from_cloud(root):
        account_prefix=BUNDLE_RE.fullmatch(name).group(1)
        if account_prefix in verified_prefixes:
            continue
        try:
            bundle=load_verified_bundle(root,name)
            verified_prefixes.add(account_prefix)
            yield bundle
        except (BundleInvalid,RuntimeError,ValueError):
            continue


def latest_account_bundle(root,account):
    match=ACCOUNT_RE.fullmatch(account)
    if match is None:
        return None
    for bundle in available_bundles(root):
        if account in bundle.accounts:
            return bundle
    return None
