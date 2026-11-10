"""Single-file, private, readback-verified TeraBox rescue for selected public SNS.

Stages verified public originals in ephemeral GitHub Actions memory; uploads one
immutable ZIP to TeraBox and streams remote bytes back through SHA256 before
claiming backup success. No user device, paid services, public artifacts or
private platform APIs are used.
"""
from __future__ import annotations
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from demand_archive import CloudArchive, canonical_json, sha256, MAX_CATALOG
from target_account_archive import run_one, archive_key, read_bootstrap_request, Transport, profile_input

MAX_BUNDLE=550_000_000
RUN_ID_RE=re.compile(r"^[0-9]{6,30}$")


class BundleStore:
    def __init__(self,limit=MAX_BUNDLE):
        self.objects={}
        self.total=0
        self.limit=limit

    def write(self,key,payload):
        if (not isinstance(key,str) or not 1<=len(key)<=240 or
                key.startswith("/") or ".." in key or "\\" in key or
                not isinstance(payload,bytes)):
            raise ValueError("invalid private ZIP source")
        old=self.objects.get(key)
        if old is not None:
            if old!=payload:
                raise RuntimeError("immutable ZIP source collision")
            return False
        if self.total+len(payload)>self.limit:
            raise RuntimeError("public source exceeds bounded ZIP staging capacity")
        self.objects[key]=payload
        self.total+=len(payload)
        return True


class BundleCloud(CloudArchive):
    """Locally staged CloudArchive-compatible API; never claims remote status."""

    def __init__(self,store,prefix=""):
        self.store=store
        self.prefix=prefix
        super().__init__(remote="archive:DemandResearch")

    def key(self,key):
        if not isinstance(key,str) or key.startswith("/") or ".." in key:
            raise ValueError("unsafe staged key")
        return self.prefix+key

    def preflight(self):
        return None

    def write_immutable(self,key,data):
        return self.store.write(self.key(key),data)

    def read(self,key,*,cap=MAX_CATALOG,optional=False,domain=None):
        raw=self.store.objects.get(self.key(key))
        if raw is None:
            if optional:return None
            raise RuntimeError("unavailable staged archive object")
        if len(raw)>cap:
            raise ValueError("staged archive object too large")
        return raw

    def read_verified(self,key,expected_digest,*,cap=100_000):
        raw=self.read(key,cap=cap,optional=True)
        if raw is not None and sha256(raw)==expected_digest:
            return raw
        return None

    def names(self,prefix):
        head=self.key(prefix.rstrip("/")+"/")
        result={path[len(head):] for path in self.store.objects
                if path.startswith(head) and "/" not in path[len(head):]}
        return sorted(name for name in result if name)


class LayeredBundleCloud(BundleCloud):
    """Read old SHA-verified ZIPs, write ONLY newly observed immutable keys.

    Historical media and posts remain in their original release files. A
    new release is a small independently verified delta, never a replacement
    or a mutable re-upload of prior records. The reader unions this chain.
    """

    def __init__(self,store,prefix="",prior=()):
        self.prior=tuple(prior)
        super().__init__(store,prefix)

    def read(self,key,*,cap=MAX_CATALOG,optional=False,domain=None):
        staged=super().read(key,cap=cap,optional=True,domain=domain)
        if staged is not None:
            return staged
        full=self.key(key)
        # Earliest captured byte sequence always wins an original-key
        # collision. Changed source is written using a NEW revision key.
        for bundle in reversed(self.prior):
            data=bundle.items.get(full)
            if data is not None:
                if len(data)>cap:
                    raise ValueError("verified prior object exceeds read bound")
                return data
        if optional:
            return None
        raise RuntimeError("verified previous archive object unavailable")

    def names(self,prefix):
        current=set(super().names(prefix))
        root=self.key(prefix.rstrip("/")+"/")
        for bundle in self.prior:
            current.update(path[len(root):] for path in bundle.items
                           if path.startswith(root) and
                           "/" not in path[len(root):])
        return sorted(current)

    def read_verified(self,key,expected_digest,*,cap=100_000):
        if not re.fullmatch(r"[a-f0-9]{64}",str(expected_digest)):
            raise ValueError("invalid expected digest")
        full=self.key(key)
        # Older and newer verified ZIPs may share a path; never allow one
        # mismatched version to hide a matching immutable predecessor.
        staged=self.store.objects.get(full)
        candidates=([staged] if staged is not None else [])+[
            bundle.items[full] for bundle in reversed(self.prior)
            if full in bundle.items]
        for raw in candidates:
            if len(raw)<=cap and sha256(raw)==expected_digest:
                return raw
        return None

    def write_immutable(self,key,data):
        if not isinstance(data,bytes):
            raise ValueError("invalid immutable source data")
        previous=self.read(key,cap=max(len(data)+1,MAX_CATALOG),
                           optional=True)
        if previous is not None:
            if previous!=data:
                raise RuntimeError("historical archive path collision")
            # Every standalone delta must declare its exact one account,
            # even if the registration already exists in an older ZIP.
            if not (not self.prefix and key.startswith("metadata/target-accounts/")):
                return False
        return super().write_immutable(key,data)


def bundle_factory(root,profile):
    prefix="account-archives/"+profile["platform"]+"/"+archive_key(profile)+"/"
    return BundleCloud(root.store,prefix)


def make_zip(store,destination,*,state,selected):
    objects=sorted(store.objects.items())
    manifest={"schema_version":1,"format":"immutable-public-account-bundle-v1",
              "selected_platform":selected["platform"],
              "selected_account":selected["account"],
              "recorded_at":datetime.now(timezone.utc).isoformat(),
              "capture_state":state,
              "objects":[{"key":key,"bytes":len(body),"sha256":sha256(body)}
                         for key,body in objects]}
    with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_STORED,
                         allowZip64=True) as archive:
        for key,body in objects:
            archive.writestr(key,body)
        archive.writestr("bundle-manifest.json",canonical_json(manifest))
    if destination.stat().st_size>MAX_BUNDLE+5_000_000:
        raise RuntimeError("private bundle exceeds upload size limit")
    # Local packaging validates the individual immutable entries before any
    # remote copy. Remote verification below validates the whole uploaded ZIP.
    with zipfile.ZipFile(destination,"r") as archive:
        for item in manifest["objects"]:
            if sha256(archive.read(item["key"]))!=item["sha256"]:
                raise RuntimeError("local package checksum mismatch")
    return manifest


def digest_file(path):
    digest=hashlib.sha256()
    with open(path,"rb") as handle:
        while chunk:=handle.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_stream(target,expected):
    # Stream the exact remote bytes directly into a hash, never print private
    # data and never accept only an upload ACK as a backup.
    command=["timeout","--signal=TERM","450s","rclone","cat",target,
             "--retries","1","--timeout","15s"]
    try:
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        digest=hashlib.sha256()
        while True:
            chunk=proc.stdout.read(1024*1024)
            if not chunk:break
            digest.update(chunk)
        code=proc.wait(timeout=20)
        return code==0 and digest.hexdigest()==expected
    except (OSError,subprocess.TimeoutExpired):
        try:proc.kill()
        except Exception:pass
        return False
    finally:
        try:proc.stdout.close()
        except Exception:pass


def upload_verified_bundle(zip_path,*,run_id,account_hash):
    if not RUN_ID_RE.fullmatch(str(run_id)):
        raise ValueError("invalid remote run identifier")
    digest=digest_file(zip_path)
    key="account-bundle-"+account_hash[:16]+"-"+str(run_id)+"-"+digest[:16]+".zip"
    target="archive:DemandResearch/"+key
    with tempfile.TemporaryDirectory(prefix="int-bundle-upload-") as folder:
        source=Path(folder)/key
        source.write_bytes(zip_path.read_bytes())
        commands=[
            ["rclone","copyto",str(source),target,"--ignore-existing",
             "--retries","1","--timeout","15s"],
            ["rclone","copy",folder,"archive:DemandResearch","--ignore-existing",
             "--retries","1","--timeout","15s"],
        ]
        for cmd in commands:
            try:
                subprocess.run(cmd,stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,timeout=180,check=False)
            except (OSError,subprocess.TimeoutExpired):
                pass
            if verify_stream(target,digest):
                return {"state":"TERABOX_ZIP_REMOTE_SHA_VERIFIED",
                        "bytes":zip_path.stat().st_size,
                        "sha256":digest,"key":key}
    raise RuntimeError("TeraBox ZIP upload lacked independent remote SHA256 readback")


def execute_bundle(*,selected=None,api=None,run_id=None,cloud_check=True,
                   uploader=upload_verified_bundle):
    if selected is None:
        env_platform=os.getenv("TARGET_PLATFORM","").strip()
        env_account=os.getenv("TARGET_ACCOUNT","").strip()
        if env_platform or env_account:
            if not env_platform or not env_account:
                raise ValueError("selected public account missing")
            profile_input(env_platform,env_account)
            raw_pages=os.getenv("TARGET_MAX_PAGES","2")
            github_temp=os.getenv("DEMAND_ACCOUNT_TEMP_STORAGE","")=="github_release"
            if raw_pages=="all" and github_temp:
                max_pages=200
            else:
                try:
                    max_pages=int(raw_pages)
                except (TypeError,ValueError):
                    raise ValueError("invalid public account page budget") from None
            if not 1<=max_pages<=(200 if github_temp else 4):
                raise ValueError("invalid public account page budget")
            selected={"platform":env_platform,"account":env_account,
                      "max_pages":max_pages}
        else:
            selected=read_bootstrap_request()
    if selected is None:
        raise ValueError("no reviewed public account configured")
    platform=selected["platform"]
    account=selected["account"]
    pages=selected["max_pages"]
    github_temp=os.getenv("DEMAND_ACCOUNT_TEMP_STORAGE","")=="github_release"
    if github_temp:
        from github_temp_bundle import upload_release
        uploader=upload_release
        cloud_check=False
        os.environ["DEMAND_TARGET_FULL_HISTORY"]="1"
    if cloud_check:
        CloudArchive().preflight()
    store=BundleStore(limit=80_000_000 if github_temp else MAX_BUNDLE)
    prior=()
    if github_temp:
        from github_temp_bundle import workflow_verified_bundles
        from target_account_archive import resolve
        transport=api or Transport()
        selected_profile=resolve(platform,account,transport)
        selected_key=platform+"-"+archive_key(selected_profile)
        # Job-scoped private inventory; failure to enumerate is not silently
        # treated as a clean first archive. Never overwrite an older release.
        prior=tuple(bundle for bundle in workflow_verified_bundles(max_scan=40)
                    if bundle.account==selected_key)
        api=transport
    root=LayeredBundleCloud(store,prior=prior)
    result=None
    interrupted=None
    with redirect_stdout(io.StringIO()):
        try:
            result=run_one(platform,account,root=root,
                           api=api or Transport(),max_pages=pages,
                           archive_factory=lambda _root, profile:
                               LayeredBundleCloud(store,
                                   "account-archives/"+profile["platform"]+"/"+
                                   archive_key(profile)+"/",prior=prior))
        except (RuntimeError,ValueError,TypeError,KeyError) as error:
            interrupted=type(error).__name__
    if not store.objects:
        raise RuntimeError("no verifiable public content staged")
    refs=[k for k in store.objects if k.endswith("/post.json")]
    if not refs and not prior:
        raise RuntimeError("no public post original staged in first bundle")
    account_name=next((k.split("/")[2] for k in store.objects
                       if k.startswith("account-archives/"+platform+"/")),None)
    if not account_name:
        raise RuntimeError("public account identity unresolved")
    run_id=run_id or os.getenv("GITHUB_RUN_ID","")
    with tempfile.TemporaryDirectory(prefix="int-bundle-stage-") as directory:
        package=Path(directory)/"public-account-immutable.zip"
        manifest=make_zip(store,package,state=result["status"] if result else "SOURCE_PARTIAL",
                          selected=selected)
        remote=uploader(package,run_id=run_id,account_hash=account_name)
    totals={"platform":platform,"storage":"github_encrypted_temporary" if github_temp else "terabox",
            "objects_remote_verified":len(manifest["objects"]),
            "public_posts_in_bundle":len(refs),
            "remote_sha256_verified":True,
            "remote_zip_bytes":remote["bytes"],
            "source_state":manifest["capture_state"],
            "source_partial":interrupted is not None}
    marker="TARGET_ACCOUNT_GITHUB_TEMP_SHA_VERIFIED" if github_temp else "TARGET_ACCOUNT_BUNDLE_REMOTE_VERIFIED"
    print(marker+" "+json.dumps(totals,sort_keys=True),flush=True)
    if interrupted and not github_temp:
        raise RuntimeError("remote backup verified but source crawl is partial")
    return totals


if __name__=="__main__":
    execute_bundle()
