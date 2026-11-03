#!/usr/bin/env python3
"""Regression: Render must serve every local JS and JSON needed by both Pages galleries.

The HTML is forwarded live from Pages but the Render portal explicitly allows
individual same-origin assets. A stale allowlist breaks both gallery UIs.
Keep this test network-free and fail closed for arbitrary/private files.
"""
from pathlib import Path
import re

from gateway.portal import ALLOWED_ASSETS, SAFE_ASSET, SAFE_IMAGE

ROOT=Path(__file__).resolve().parents[3]
assert "saved-photo-union.js" in ALLOWED_ASSETS, "Render must serve the SHA-photo union script"
for model in ("mimmi", "yui"):
    base=ROOT/"apps"/f"{model}-gallery"
    page=(base/"index.html").read_text(encoding="utf-8")
    scripts=set(re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']', page))
    fetched=set(re.findall(r'\bfetch\(\s*["\']([^"\']+)["\']', page))
    assets={p.split("?",1)[0] for p in scripts|fetched}
    assert assets <= ALLOWED_ASSETS, (model,"Render will 404 a gallery dependency",assets-ALLOWED_ASSETS)
    assert (base/"saved-photo-union.js").is_file(), (model,"missing SHA union source")
    assert scripts, (model,"no JS scripts checked")

for disallowed in (
    ".env", "Dockerfile", "portal.py", "requirements.txt", "api-secret.txt",
    "gallery-owner-originals.json", "anything.js", "secrets/key.json",
):
    assert disallowed not in ALLOWED_ASSETS, "A private/non-gallery asset must not be exposed"
assert SAFE_ASSET.fullmatch("saved-photo-union.js")
assert not SAFE_IMAGE.fullmatch("saved-photo-union.js")
print("RENDER_PUBLIC_GALLERY_SCRIPT_ALLOWLIST_BOTH_MODELS_PASS")
