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
    return VerifiedBundle(name, plain)


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
        if len(_cache) >= 2:
            _cache.clear()
        _cache[artifact_id] = (time.monotonic(), bundle)
    return bundle


def releases(max_pages=2):
    for page in range(1, min(max_pages, 3) + 1):
        data = _json(API + "/releases?per_page=100&page=" + str(page))
        if not isinstance(data, list):
            raise RuntimeError("Invalid GitHub temporary backup list")
        for item in data:
            if isinstance(item, dict) and TAG.fullmatch(str(item.get("tag_name", ""))):
                yield item
        if len(data) < 100:
            return


def latest_bundles(max_accounts=12):
    seen = set()
    for release in releases():
        try:
            bundle = release_bundle(release)
        except (BundleInvalid, RuntimeError, OSError, ValueError, zipfile.BadZipFile):
            continue
        if bundle.account in seen:
            continue
        seen.add(bundle.account)
        yield bundle
        if len(seen) >= max_accounts:
            return


def account_bundle(account):
    for bundle in latest_bundles():
        if bundle.account == account:
            return bundle
    return None


def run_bundle(run_id, account=None):
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("Invalid workflow id")
    prefix = "intersection-github-archive-" + str(run_id) + "-a"
    for release in releases():
        if not release["tag_name"].startswith(prefix):
            continue
        bundle = release_bundle(release)
        if account is None or bundle.selected_account == account:
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
    release = _json(API + "/releases/tags/" + quote(tag, safe=""), os.environ["GITHUB_TOKEN"])
    asset = _asset(release)
    remote = _download(asset)
    if not hmac.compare_digest(hashlib.sha256(remote).digest(), hashlib.sha256(wrapped).digest()):
        raise RuntimeError("GitHub remote ciphertext SHA256 readback failed")
    check = _make_bundle(tag, decrypt(remote, key))
    if check.selected_platform not in ("bluesky", "mastodon"):
        raise RuntimeError("Invalid independently verified GitHub ZIP")
    return {"state": "GITHUB_TEMP_SHA_VERIFIED", "bytes": len(remote),
            "sha256": hashlib.sha256(source).hexdigest(), "key": tag}
