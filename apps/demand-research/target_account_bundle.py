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
from urllib.request import Request as UrlRequest, urlopen

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


def make_zip(store,destination,*,state,selected,ancestor_tags=()):
    objects=sorted(store.objects.items())
    manifest={"schema_version":1,"format":"immutable-public-account-bundle-v1",
              "selected_platform":selected["platform"],
              "selected_account":selected["account"],
              "recorded_at":datetime.now(timezone.utc).isoformat(),
              "capture_state":state,
              "ancestor_tags":list(ancestor_tags),
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
                   uploader=upload_verified_bundle,prior_bundles=None):
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
        candidates=(workflow_verified_bundles(max_scan=40)
                    if prior_bundles is None else prior_bundles)
        prior=tuple(bundle for bundle in candidates
                    if bundle.account==selected_key)
        api=transport
    root=LayeredBundleCloud(store,prior=prior)
    result=None
    interrupted=None
    interrupted_reason=None
    captured=io.StringIO()
    with redirect_stdout(captured):
        try:
            result=run_one(platform,account,root=root,
                           api=api or Transport(),max_pages=pages,
                           archive_factory=lambda _root, profile:
                               LayeredBundleCloud(store,
                                   "account-archives/"+profile["platform"]+"/"+
                                   archive_key(profile)+"/",prior=prior))
        except (RuntimeError,ValueError,TypeError,KeyError) as error:
            interrupted=type(error).__name__
            # Only static, reviewed reason categories are ever printed.
            # Raw provider messages and account identifiers remain private.
            message=str(error)
            interrupted_reason=(
                "STAGING_LIMIT" if message==
                    "public source exceeds bounded ZIP staging capacity"
                else "IMMUTABLE_CONFLICT" if message==
                    "historical archive path collision"
                else "PUBLIC_SOURCE_UNAVAILABLE" if
                    isinstance(error,RuntimeError) and
                    message.startswith("public source ")
                else "OTHER")

    # The old code discarded the real cause, then called ANY exception
    # "Required public profile snapshot not captured". The archive worker's
    # own aggregate contains only counts and stage flags, never identifiers.
    summary={}
    for line in captured.getvalue().splitlines():
        if not line.startswith("TARGET_ACCOUNT_ARCHIVE_AGGREGATE "):
            continue
        try:
            candidate=json.loads(line.split(" ",1)[1])
            if isinstance(candidate,dict):
                summary=candidate
        except (ValueError,TypeError):
            pass
    source_evidence=any(
        ("/profile/snapshots/" in key or
         "/metadata/source-records/" in key or
         ("/posts/" in key and key.endswith("/post.json")))
        for key in store.objects
    )
    profile_snapshot_staged=any("/profile/snapshots/" in key
                                for key in store.objects)
    profile_proven=(profile_snapshot_staged and isinstance(result,dict) and
                    result.get("profile",{}).get("profile_verified") is True)
    if interrupted is not None:
        # If collection failed after some originals were staged, preserve the
        # SHA-verified bytes as explicitly PARTIAL instead of throwing them
        # away. Never upload a registration-only or empty green archive.
        if not source_evidence:
            print("TARGET_ACCOUNT_SOURCE_UNAVAILABLE "+
                  json.dumps({"error_class":interrupted,
                              "profile_verified":summary.get("profile_verified",False),
                              "staged_source_objects":0},sort_keys=True),flush=True)
            raise RuntimeError("No independently captured account originals available")
        result={"status":"SOURCE_PARTIAL",
                "profile":{"profile_verified":(
                    profile_snapshot_staged and summary.get("profile_verified") is True),
                           "profile_assets_unavailable":int(
                               summary.get("profile_assets_unavailable",0))},
                "media_pending_total":int(summary.get("media_pending_total",0)),
                "graph":{},"threads":{"threads_pending":True}}
    elif not isinstance(result,dict):
        raise RuntimeError("No verified public account capture result")
    elif not profile_proven:
        result["status"]="SOURCE_PARTIAL"
        if isinstance(result.get("profile"),dict):
            result["profile"]["profile_verified"]=False

    if not source_evidence:
        raise RuntimeError("No independently captured profile or post originals staged")
    if os.getenv("DEMAND_REQUIRE_PROFILE_SNAPSHOT","0")=="1" and (
            result.get("profile",{}).get("profile_verified") is not True):
        # The ZIP may contain real posts even if the profile API is down.
        # This result is always PARTIAL and must never close completeness QA.
        result["status"]="SOURCE_PARTIAL"
    if interrupted is not None or result.get("status")=="SOURCE_PARTIAL":
        print("TARGET_ACCOUNT_CAPTURE_PARTIAL "+
              json.dumps({"error_class":interrupted,
                          "reason":interrupted_reason,
                          "profile_verified":result["profile"].get("profile_verified",False),
                          "posts_staged":sum(key.endswith("/post.json")
                                              for key in store.objects),
                          "source_records_staged":sum("/metadata/source-records/" in key
                                                      for key in store.objects)},
                         sort_keys=True),flush=True)
    refs=[k for k in store.objects if k.endswith("/post.json")]
    account_name=next((k.split("/")[2] for k in store.objects
                       if k.startswith("account-archives/"+platform+"/")),None)
    if not account_name:
        raise RuntimeError("public account identity unresolved")
    run_id=run_id or os.getenv("GITHUB_RUN_ID","")
    with tempfile.TemporaryDirectory(prefix="int-bundle-stage-") as directory:
        package=Path(directory)/"public-account-immutable.zip"
        ancestors=set()
        for bundle in prior:
            ancestors.update(bundle.ancestor_tags)
            if getattr(bundle,"archive_tag",None):
                ancestors.add(bundle.archive_tag)
        if len(ancestors)>10000:
            raise RuntimeError("immutable account history exceeds reference bound")
        manifest=make_zip(store,package,state=result["status"] if result else "SOURCE_PARTIAL",
                          selected=selected,ancestor_tags=sorted(ancestors))
        remote=uploader(package,run_id=run_id,account_hash=account_name)
    totals={"platform":platform,"storage":"github_encrypted_temporary" if github_temp else "terabox",
            "objects_remote_verified":len(manifest["objects"]),
            "public_posts_in_bundle":len(refs),
            "remote_sha256_verified":True,
            "remote_zip_bytes":remote["bytes"],
            "source_state":manifest["capture_state"],
            "source_interruption":interrupted_reason,
            "source_partial":(interrupted is not None or
                result is None or result.get("status")!="COMPLETE_CURRENT_PUBLIC_CURSOR"),
            "unresolved_media_records":(result or {}).get("media_pending_total",0),
            "profile_snapshot_verified":(result or {}).get("profile",{}).get(
                "profile_verified") is True,
            "profile_assets_unavailable":(result or {}).get("profile",{}).get(
                "profile_assets_unavailable",0),
            "graph_more_pages":any(v.get("more_public_pages") is not False
                for v in (result or {}).get("graph",{}).values()),
            "threads_pending":(result or {}).get("threads",{}).get(
                "threads_pending",True)}
    marker="TARGET_ACCOUNT_GITHUB_TEMP_SHA_VERIFIED" if github_temp else "TARGET_ACCOUNT_BUNDLE_REMOTE_VERIFIED"
    print(marker+" "+json.dumps(totals,sort_keys=True),flush=True)
    if interrupted and not github_temp:
        raise RuntimeError("remote backup verified but source crawl is partial")
    return totals


def execute_scheduled():
    """Refresh one registered public account without sacrificing old records.

    If the oldest registered source is now unavailable, try another verified
    account rather than starving the entire schedule. Historical ZIPs are
    NEVER deleted or changed when a provider returns HTTP 400/404.
    """
    from github_temp_bundle import workflow_verified_bundles
    from target_account_archive import SourceUnavailable
    inventory=tuple(workflow_verified_bundles(max_scan=40))
    latest={}
    for bundle in inventory:
        if bundle.account not in latest:
            latest[bundle.account]=bundle
    if not latest:
        selected=read_bootstrap_request()
        if selected is None:
            raise RuntimeError("no verified registered public account")
        return execute_bundle(selected=selected,prior_bundles=inventory)
    # New successful deltas move their account to the end of this queue,
    # while an unavailable account never prevents the next public account.
    unavailable=0
    for bundle in sorted(latest.values(),
                         key=lambda b:(str(b.recorded_at or ""),b.account)):
        metadata=bundle.accounts[bundle.account]
        selected={"platform":metadata["platform"],
                  "account":metadata["profile_url"],
                  "max_pages":2}
        try:
            result=execute_bundle(selected=selected,prior_bundles=inventory)
        except (SourceUnavailable,ValueError):
            unavailable+=1
            continue
        print("TARGET_ACCOUNT_ARCHIVE_SCHEDULE",
              json.dumps({"registered":len(latest),"source_unavailable":unavailable,
                          "state":"REMOTE_READBACK_COMPLETED"},
                         sort_keys=True),flush=True)
        return result
    # Never produce a green run or synthetic backup if every public account
    # is no longer queryable. The previous encrypted sources remain intact.
    print("TARGET_ACCOUNT_ARCHIVE_SCHEDULE",
          json.dumps({"registered":len(latest),"source_unavailable":unavailable,
                      "state":"NO_CURRENT_PUBLIC_SOURCE"},
                     sort_keys=True),flush=True)
    raise SourceUnavailable("all registered public accounts unavailable; historical ZIPs retained")

MAX_AUTOMATED_CONTINUATION_PASSES=8


def dispatch_verified_followup(result, *, send=urlopen):
    """Start another immutable account delta ONLY for a proved staging limit.

    A job that uploaded and re-read an encrypted ZIP containing new posts can
    continue from that exact preserved ancestry. Failed/empty/unverified jobs,
    transient provider denials and AppView-only partiality MUST NOT auto-loop.
    Never print selected account identifiers, raw source content, or tokens.
    """
    if (not isinstance(result,dict) or
        result.get("remote_sha256_verified") is not True or
        result.get("source_partial") is not True or
        result.get("source_interruption")!="STAGING_LIMIT" or
        type(result.get("public_posts_in_bundle")) is not int or
        result["public_posts_in_bundle"]<1):
        return "NOT_ELIGIBLE"
    if (os.getenv("GITHUB_REPOSITORY")!="koith/browser-app-lab" or
        os.getenv("GITHUB_REF")!="refs/heads/main" or
        os.getenv("GITHUB_EVENT_NAME")!="workflow_dispatch"):
        return "NOT_TRUSTED_CONTEXT"
    raw=os.getenv("TARGET_RESUME_PASS","0") or "0"
    if not re.fullmatch(r"[0-9]{1,2}",raw):
        raise RuntimeError("Invalid bounded account continuation count")
    depth=int(raw)
    if depth>MAX_AUTOMATED_CONTINUATION_PASSES:
        raise RuntimeError("Untrusted continuation count")
    if depth==MAX_AUTOMATED_CONTINUATION_PASSES:
        print("TARGET_ACCOUNT_RESUME_LIMIT_REACHED",depth,flush=True)
        return "LIMIT_REACHED"
    platform=os.getenv("TARGET_PLATFORM","")
    account=os.getenv("TARGET_ACCOUNT","")
    profile_input(platform,account)
    token=os.getenv("GITHUB_TOKEN","")
    if len(token)<20:
        raise RuntimeError("Trusted account continuation token unavailable")
    payload=canonical_json({"ref":"main","return_run_details":True,
        "inputs":{"platform":platform,"account":account,
                  "max_pages":"all","resume_pass":str(depth+1)}})
    req=UrlRequest(
        "https://api.github.com/repos/koith/browser-app-lab/actions/workflows/"
        "intersection-target-account-bundle.yml/dispatches",
        data=payload,method="POST",headers={
          "Authorization":"Bearer "+token,
          "Accept":"application/vnd.github+json",
          "Content-Type":"application/json",
          "X-GitHub-Api-Version":"2026-03-10",
          "User-Agent":"intersection-verified-account-continuation"})
    with send(req,timeout=30) as response:
        if response.status!=200:
            raise RuntimeError("Verified account continuation was not dispatched")
        body=json.loads(response.read(10000))
    new_run=body.get("workflow_run_id") if isinstance(body,dict) else None
    if type(new_run) is not int or new_run<=0:
        raise RuntimeError("Account continuation lacks trackable execution")
    print("TARGET_ACCOUNT_VERIFIED_CONTINUATION_DISPATCHED "+
          json.dumps({"pass":depth+1,"workflow_run_id":new_run},
                     sort_keys=True),flush=True)
    return "DISPATCHED"


if __name__=="__main__":
    if "--scheduled" in os.sys.argv[1:]:
        if os.sys.argv[1:]!=["--scheduled"]:
            raise ValueError("invalid scheduled account options")
        execute_scheduled()
    else:
        outcome=execute_bundle()
        dispatch_verified_followup(outcome)
