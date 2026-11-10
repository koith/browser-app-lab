"""Temporary encrypted GitHub Release storage for bounded public-account ZIPs.

The public repository stores ONLY AES-256-GCM ciphertext. GitHub's Actions
artifact download API requires Actions read credentials, which this Render
gateway deliberately does not hold. Public Release assets allow readback of
encrypted bytes without sharing a GitHub token with Render.

Never mark a release successful without remote ciphertext SHA readback AND
authenticated decryption and per-entry manifest verification.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree
from urllib.request import Request, urlopen
import zipfile

from verified_bundle_reader import VerifiedBundle, BundleInvalid, MAX_VIEW_ZIP

REPO = "koith/browser-app-lab"
GATEWAY = "https://intersection-originals-free.onrender.com"
API = "https://api.github.com/repos/" + REPO
TAG = re.compile(r"^intersection-github-archive-([0-9]{6,30})-a([1-9][0-9]{0,3})$")
ENTRY = re.compile(r"^metadata/target-accounts/(bluesky|mastodon)-([a-f0-9]{40})\.json$")
MAGIC = b"INTGB1"
AAD = b"intersection-github-temporary-account-zip-v1"
ASSET = "account.enc"
MAX_CIPHER = MAX_VIEW_ZIP + 64
CACHE_SECONDS = 90
_cache = {}
_guard = threading.Lock()


def enabled():
    return os.getenv("DEMAND_ACCOUNT_TEMP_STORAGE", "") == "github_release"


def gateway_key():
    token = os.getenv("DEMAND_VIEWER_TOKEN", "")
    if len(token) < 24:
        raise RuntimeError("Private gateway encryption key unavailable")
    return hmac.new(token.encode(), AAD, hashlib.sha256).digest()


def _json(url, token=None):
    if not url.startswith(API + "/"):
        raise ValueError("Unsafe GitHub API address")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "intersection-encrypted-github-archive"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("GitHub release index unavailable")
        return json.loads(response.read(2_000_000))


def encrypt(data, key):
    if not isinstance(data, bytes) or not 100 < len(data) <= MAX_VIEW_ZIP:
        raise ValueError("Backup exceeds bounded temporary storage")
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Invalid temporary encryption key")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, AAD)


def decrypt(data, key):
    if not isinstance(data, bytes) or not 34 < len(data) <= MAX_CIPHER:
        raise BundleInvalid("Invalid encrypted temporary backup size")
    if not data.startswith(MAGIC) or len(key) != 32:
        raise BundleInvalid("Invalid encrypted temporary backup header")
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        return AESGCM(key).decrypt(data[6:18], data[18:], AAD)
    except (InvalidTag, ValueError):
        raise BundleInvalid("Temporary backup decryption/verification failed") from None


def _make_bundle(tag, plain):
    match = TAG.fullmatch(tag)
    if match is None:
        raise BundleInvalid("Unrecognized temporary backup identifier")
    with zipfile.ZipFile(io.BytesIO(plain), "r") as file:
        identities = [ENTRY.fullmatch(name) for name in file.namelist()]
        accounts = [m.group(2) for m in identities if m is not None]
    if len(accounts) != 1:
        raise BundleInvalid("Temporary backup has no unique account")
    digest = hashlib.sha256(plain).hexdigest()
    name = "account-bundle-" + accounts[0][:16] + "-" + match.group(1) + "-" + digest[:16] + ".zip"
    bundle = VerifiedBundle(name, plain)
    bundle.temporary = True
    bundle.archive_tag = tag
    return bundle


def _asset(release):
    if not isinstance(release, dict) or not TAG.fullmatch(str(release.get("tag_name", ""))):
        raise BundleInvalid("Not an Intersection temporary backup")
    if release.get("draft") or not release.get("prerelease"):
        raise BundleInvalid("Untrusted temporary release state")
    matches = [a for a in release.get("assets", []) if isinstance(a, dict)
               and a.get("name") == ASSET and type(a.get("size")) is int
               and 34 < a["size"] <= MAX_CIPHER]
    if len(matches) != 1:
        raise BundleInvalid("Missing encrypted backup release asset")
    url = matches[0].get("browser_download_url", "")
    expected = "https://github.com/" + REPO + "/releases/download/" + release["tag_name"] + "/" + ASSET
    if url != expected:
        raise BundleInvalid("Unexpected GitHub archive download URL")
    return matches[0]


def _download(asset):
    url = asset["browser_download_url"]
    # GitHub redirects its own release assets to its content delivery hosts.
    with urlopen(Request(url, headers={"User-Agent": "intersection-account-viewer",
                                       "Accept": "application/octet-stream"}), timeout=55) as response:
        raw = response.read(MAX_CIPHER + 1)
    if len(raw) > MAX_CIPHER or len(raw) != asset["size"]:
        raise BundleInvalid("Incomplete GitHub temporary archive download")
    digest = asset.get("digest", "")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        if not hmac.compare_digest(digest[7:], hashlib.sha256(raw).hexdigest()):
            raise BundleInvalid("GitHub release asset checksum mismatch")
    return raw


def readback_uploaded_release(tag, token, *, attempts=7):
    """Independently read the *published* immutable release asset.

    A freshly created GitHub Release may show an uploaded asset in REST while
    its public CDN download still returns 404 for several seconds. Never
    mistake a successful upload ACK for complete remote verification.
    """
    if not TAG.fullmatch(tag) or not isinstance(token,str) or not token:
        raise ValueError("Invalid private release readback request")
    if not isinstance(attempts,int) or not 1<=attempts<=8:
        raise ValueError("Invalid bounded readback attempts")
    endpoint=API+"/releases/tags/"+quote(tag,safe="")
    for attempt in range(attempts):
        try:
            release=_json(endpoint,token)
            asset=_asset(release)
            return _download(asset)
        except HTTPError as error:
            if error.code!=404:
                raise RuntimeError("GitHub temporary remote readback denied") from None
        except BundleInvalid as error:
            # Only a missing yet-to-appear asset qualifies for a bounded
            # retry. Wrong owner, checksum or unexpected URL FAIL closed.
            if str(error)!="Missing encrypted backup release asset":
                raise
        if attempt+1<attempts:
            time.sleep(min(1+attempt*2,9))
    raise RuntimeError("GitHub release asset readback unavailable after bounded retries")


def release_bundle(release, *, key=None):
    asset = _asset(release)
    artifact_id = asset.get("id")
    if not isinstance(artifact_id, int):
        raise BundleInvalid("Unidentified temporary backup asset")
    with _guard:
        found = _cache.get(artifact_id)
        if found is not None and time.monotonic() - found[0] < CACHE_SECONDS:
            return found[1]
    source = _download(asset)
    bundle = _make_bundle(release["tag_name"], decrypt(source, key or gateway_key()))
    with _guard:
        if len(_cache) >= 1:
            _cache.clear()
        _cache[artifact_id] = (time.monotonic(), bundle)
    return bundle


def releases(max_pages=2, *, token=None):
    for page in range(1, min(max_pages, 8) + 1):
        data = _json(API + "/releases?per_page=100&page=" + str(page), token=token)
        if not isinstance(data, list):
            raise RuntimeError("Invalid GitHub temporary backup list")
        for item in data:
            if isinstance(item, dict) and TAG.fullmatch(str(item.get("tag_name", ""))):
                yield item
        if len(data) < 100:
            return


def workflow_verified_bundles(max_scan=24):
    """Actions-only inventory of authenticated, immutable account releases.

    Read the GitHub release index with the job-scoped contents token, then
    decrypt archives with the Render-derived OIDC key. Never trust only a
    green workflow or the public release title as source proof. Returned
    bundles are newest first, and each object SHA is verified on download.
    """
    token=os.getenv("GITHUB_TOKEN","")
    if not token or os.getenv("GITHUB_REPOSITORY")!=REPO:
        raise RuntimeError("authorized GitHub account inventory unavailable")
    key=_oidc_key()
    checked=0
    for release in releases(max_pages=8,token=token):
        if checked>=max_scan:
            return
        checked+=1
        # An inaccessible or invalid encrypted release cannot silently
        # become accepted source bytes; it is skipped but never overwritten.
        try:
            yield release_bundle(release,key=key)
        except (BundleInvalid,RuntimeError,ValueError,zipfile.BadZipFile):
            continue


def matching_bundles(account, max_versions=500):
    """Load the newest verified ZIP plus ALL signed immutable ancestor tags.

    The public Atom feed holds only the most recent releases. The encrypted
    ancestor chain keeps older originals directly readable long after they
    age out of that feed; no historical release is edited or deleted.
    """
    if not re.fullmatch(r"(?:bluesky|mastodon)-[a-f0-9]{40}",str(account)):
        return []
    matches={}
    for tag in atom_tags():
        try:
            bundle=tagged_bundle(tag)
        except (BundleInvalid,RuntimeError,ValueError,zipfile.BadZipFile):
            continue
        if bundle.account!=account:
            continue
        matches[tag]=bundle
        if len(matches)>=max_versions:
            break
        for old_tag in bundle.ancestor_tags:
            if old_tag in matches:
                continue
            if len(matches)>=max_versions:
                raise RuntimeError("verified history exceeds bounded reader")
            old=tagged_bundle(old_tag)
            if old is None or old.account!=account:
                raise RuntimeError("signed immutable account history unavailable")
            matches[old_tag]=old
        break
    return list(matches.values())


def atom_tags():
    """Use the public GitHub release Atom feed, not rate-limited anonymous REST.

    GitHub's release Atom feed currently contains a limited recent window.
    Never infer completeness from its contents. The exact run route below can
    additionally recover any older run by its immutable tag without listing.
    """
    url="https://github.com/"+REPO+"/releases.atom"
    request=Request(url,headers={"Accept":"application/atom+xml",
                                  "User-Agent":"intersection-private-archive-reader"})
    try:
        with urlopen(request,timeout=25) as response:
            raw=response.read(1_000_001)
    except (HTTPError,URLError,TimeoutError,OSError) as error:
        raise RuntimeError("GitHub release feed unavailable") from None
    if len(raw)>1_000_000:
        raise RuntimeError("GitHub release feed exceeds safe limit")
    try:
        root=ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        raise RuntimeError("Invalid GitHub release feed") from None
    ns="{http://www.w3.org/2005/Atom}"
    if root.tag!=ns+"feed":
        raise RuntimeError("Unexpected GitHub release feed")
    seen=set()
    for entry in root.findall(ns+"entry"):
        for link in entry.findall(ns+"link"):
            href=link.attrib.get("href","")
            prefix="https://github.com/"+REPO+"/releases/tag/"
            if (href.startswith(prefix) and link.attrib.get("rel","alternate")=="alternate"):
                tag=href[len(prefix):]
                if TAG.fullmatch(tag) and tag not in seen:
                    seen.add(tag)
                    yield tag
                break


def _download_tag(tag, *, missing_ok=False):
    if not TAG.fullmatch(tag):
        raise ValueError("Invalid GitHub temporary archive tag")
    url="https://github.com/"+REPO+"/releases/download/"+tag+"/"+ASSET
    try:
        with urlopen(Request(url,headers={
                "Accept":"application/octet-stream",
                "User-Agent":"intersection-private-archive-reader"}),timeout=65) as response:
            raw=response.read(MAX_CIPHER+1)
    except HTTPError as error:
        if missing_ok and error.code==404:
            return None
        raise RuntimeError("GitHub temporary archive download unavailable") from None
    except (URLError,TimeoutError,OSError):
        raise RuntimeError("GitHub temporary archive download unavailable") from None
    if not 34<len(raw)<=MAX_CIPHER:
        raise BundleInvalid("Invalid remote encrypted archive size")
    return raw


def tagged_bundle(tag, *, missing_ok=False):
    with _guard:
        found=_cache.get(tag)
        if found is not None and time.monotonic()-found[0]<CACHE_SECONDS:
            return found[1]
    raw=_download_tag(tag,missing_ok=missing_ok)
    if raw is None:
        return None
    # AES-GCM and VerifiedBundle's whole-ZIP+manifest SHA checks establish
    # original integrity even without the rate-limited GitHub REST metadata.
    bundle=_make_bundle(tag,decrypt(raw,gateway_key()))
    with _guard:
        if len(_cache)>=1:_cache.clear()
        _cache[tag]=(time.monotonic(),bundle)
    return bundle


def latest_bundles(max_accounts=12):
    seen=set()
    for tag in atom_tags():
        try:
            bundle=tagged_bundle(tag)
        except (BundleInvalid,RuntimeError,ValueError,zipfile.BadZipFile):
            continue
        if bundle.account in seen:
            continue
        seen.add(bundle.account)
        yield bundle
        if len(seen)>=max_accounts:
            return


def account_bundle(account):
    for bundle in latest_bundles():
        if bundle.account==account:
            return bundle
    return None


def run_bundle(run_id,account=None):
    if type(run_id) is not int or run_id<=0:
        raise ValueError("Invalid workflow id")
    # Exact immutable URL avoids the anonymous REST rate limit, even after
    # this run ages out of the 10 most recent release feed entries.
    for attempt in range(1,5):
        tag="intersection-github-archive-"+str(run_id)+"-a"+str(attempt)
        bundle=tagged_bundle(tag,missing_ok=True)
        if bundle is None:
            continue
        if account is None or bundle.selected_account==account:
            return bundle
    return None


def _oidc_key():
    from urllib.parse import urlencode
    endpoint = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    url = endpoint + ("&" if "?" in endpoint else "?") + urlencode({
        "audience": "intersection-originals-free/credential-v1"})
    request = Request(url, headers={
        "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urlopen(request, timeout=15) as response:
        assertion = json.load(response)["value"]
    request = Request(GATEWAY + "/api/bridge/archive-key", headers={
        "Authorization": "Bearer " + assertion, "Accept": "application/json"})
    with urlopen(request, timeout=45) as response:
        encoded = json.load(response)["key"]
    key = base64.b64decode(encoded, validate=True)
    if len(key) != 32:
        raise RuntimeError("GitHub temporary backup key exchange failed")
    return key


def upload_release(zip_path, *, run_id, account_hash):
    # Called ONLY inside the authorized GitHub Actions account bundle workflow.
    if not re.fullmatch(r"[0-9]{6,30}", str(run_id)) or not re.fullmatch(r"[a-f0-9]{40}", account_hash):
        raise ValueError("Invalid GitHub backup identity")
    attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    if not re.fullmatch(r"[1-9][0-9]{0,3}", attempt):
        raise ValueError("Invalid GitHub backup attempt")
    if os.getenv("GITHUB_REPOSITORY") != REPO or not os.getenv("GITHUB_TOKEN"):
        raise RuntimeError("GitHub Actions job-scoped write permission unavailable")
    source = Path(zip_path).read_bytes()
    key = _oidc_key()
    wrapped = encrypt(source, key)
    tag = "intersection-github-archive-" + str(run_id) + "-a" + attempt
    with tempfile.TemporaryDirectory(prefix="int-github-temp-") as folder:
        target = Path(folder) / ASSET
        target.write_bytes(wrapped)
        env = {**os.environ, "GH_TOKEN": os.environ["GITHUB_TOKEN"]}
        command = ["gh", "release", "create", tag, str(target) + "#" + ASSET,
                   "--repo", REPO, "--target", "main", "--prerelease",
                   "--title", "Encrypted temporary account backup " + str(run_id),
                   "--notes", "Encrypted temporary backup only; no public plaintext. Not permanent storage."]
        result = subprocess.run(command, capture_output=True, timeout=90, env=env)
        if result.returncode != 0:
            raise RuntimeError("GitHub temporary release upload failed")
    # Independently re-download the encrypted bytes from the PUBLIC URL.
    remote = readback_uploaded_release(tag, os.environ["GITHUB_TOKEN"])
    if not hmac.compare_digest(hashlib.sha256(remote).digest(), hashlib.sha256(wrapped).digest()):
        raise RuntimeError("GitHub remote ciphertext SHA256 readback failed")
    check = _make_bundle(tag, decrypt(remote, key))
    if check.selected_platform not in ("bluesky", "mastodon"):
        raise RuntimeError("Invalid independently verified GitHub ZIP")
    return {"state": "GITHUB_TEMP_SHA_VERIFIED", "bytes": len(remote),
            "sha256": hashlib.sha256(source).hexdigest(), "key": tag}
