"""Mirror independently SHA-verified public-account TeraBox ZIP to encrypted GH.

GitHub Actions can read the owner-approved TeraBox source ZIP, whereas the
free public viewer sometimes receives provider 403 on the same ZIP. Move only
AES-GCM ciphertext into an existing temporary GitHub Release with the existing
OIDC owner-gateway key. This does not make the backup permanent, access private
SNS resources or claim complete historical coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
import os
from pathlib import Path
import re
import tempfile

from demand_archive import CloudArchive
import github_temp_bundle as gh
from verified_bundle_reader import BUNDLE_RE, VerifiedBundle, BundleInvalid, names_from_cloud

RUN_ID = re.compile(r"[0-9]{6,30}\Z")
MAX_MATCHES = 4
MAX_RECENT = 12


@dataclass(frozen=True)
class Source:
    name: str
    contents: bytes
    bundle: VerifiedBundle


def load_source(root, run_id, *, minimum_posts=1):
    """Never promote unverified upload ACKs or unrelated archive files."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid reviewed source run")
    if not isinstance(minimum_posts, int) or minimum_posts < 1:
        raise ValueError("Invalid reviewed minimum coverage")
    names = [name for name in names_from_cloud(root)
             if BUNDLE_RE.fullmatch(name).group(2) == run_id]
    if not 1 <= len(names) <= MAX_MATCHES:
        raise RuntimeError("No bounded exact-run TeraBox ZIP available")
    verified = []
    for name in names:
        raw = root.command(["cat", root.remote+"/"+name, "--retries", "1"],
                           timeout=160, allow_missing=True)
        if raw is None:
            continue
        archive = VerifiedBundle(name, raw)
        if archive.post_count < minimum_posts:
            continue
        verified.append(Source(name,raw,archive))
    if not verified:
        raise RuntimeError("No source ZIP satisfied whole-file and object SHA checks")
    # One exact source per mirrored action; don't accidentally expose another
    # selected account or replace a previously more complete original.
    return max(verified, key=lambda x: (x.bundle.post_count,x.bundle.object_count))


def best_recent_github_count(account, key):
    """Conservative regression guard across the bounded release Atom window."""
    if not isinstance(key, bytes) or len(key)!=32:
        raise ValueError("Invalid private mirror key")
    best = 0
    for tag in itertools.islice(gh.atom_tags(),MAX_RECENT):
        encrypted = gh._download_tag(tag, missing_ok=True)
        if encrypted is None:
            continue
        try:
            other=gh._make_bundle(tag,gh.decrypt(encrypted,key))
        except (BundleInvalid,ValueError,TypeError):
            continue
        if other.account == account:
            best=max(best,other.post_count)
    return best


def mirror(*, source_run=None, minimum_posts=1, root=None):
    run_id=source_run or os.getenv("MIRROR_SOURCE_RUN_ID","")
    os.umask(0o077)
    root=root or CloudArchive()
    source=load_source(root,run_id,minimum_posts=minimum_posts)
    archive=source.bundle
    # Owner-only GitHub OIDC bridge yields the same 32-byte key that the
    # Render gateway uses. Never emit this value or any original bytes.
    key=gh._oidc_key()
    tag="intersection-github-archive-"+run_id+"-a1"
    remote=gh._download_tag(tag,missing_ok=True)
    if remote is not None:
        existing=gh._make_bundle(tag,gh.decrypt(remote,key))
        if existing.digest!=archive.digest or existing.account!=archive.account:
            raise RuntimeError("Existing immutable release differs from reviewed source")
        print("INTERSECTION_MIRROR_ALREADY_SHA_VERIFIED",
              "posts="+str(existing.post_count),flush=True)
        return {"state":"ALREADY_SHA_VERIFIED","posts":existing.post_count}
    existing_posts=best_recent_github_count(archive.account,key)
    if existing_posts >= archive.post_count:
        print("INTERSECTION_MIRROR_NO_COVERAGE_GAIN",
              "existing_verified_posts="+str(existing_posts),flush=True)
        return {"state":"ALREADY_MORE_COMPLETE","posts":existing_posts}
    # Deterministic release tag matches the ORIGINAL successful TeraBox run.
    # A new Actions run/retry must not create an unlimited series of releases.
    os.environ["GITHUB_RUN_ATTEMPT"]="1"
    with tempfile.TemporaryDirectory(prefix="intersection-private-mirror-") as folder:
        package=Path(folder)/"verified-immutable.zip"
        package.write_bytes(source.contents)
        identity=archive.account.split("-",1)[1]
        result=gh.upload_release(package,run_id=run_id,account_hash=identity)
    if (result.get("state")!="GITHUB_TEMP_SHA_VERIFIED"
            or result.get("sha256")!=archive.digest
            or result.get("key")!=tag):
        raise RuntimeError("Encrypted GitHub mirror lacks independent source SHA")
    print("INTERSECTION_TERABOX_GITHUB_MIRROR_END_TO_END_VERIFIED",
          "posts="+str(archive.post_count),
          "original_objects="+str(archive.object_count),
          "temporary_encrypted_storage=true",flush=True)
    return {"state":"GITHUB_TEMP_SHA_VERIFIED","posts":archive.post_count}


if __name__=="__main__":
    mirror(minimum_posts=int(os.environ.get("MIRROR_MINIMUM_POSTS","1")))
