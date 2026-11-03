#!/usr/bin/env python3
"""Ensure HTML first-paint covers are exactly files already saved and verified.

Early album anchors are temporary, functional hash links; the existing full
SHA union replaces these cards after all manifests have loaded. Nothing
from research/source URLs or TeraBox-only storage may be prepainted.
"""
from __future__ import annotations

from html.parser import HTMLParser
import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]

class Covers(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "a" and attr.get("data-fast-cover") == "1":
            if self.current is not None:
                raise AssertionError("Nested first-paint card")
            self.current = {"card": attr, "img": None}
            self.cards.append(self.current)
        elif tag == "img" and self.current is not None:
            assert self.current["img"] is None
            self.current["img"] = attr

    def handle_endtag(self, tag):
        if tag == "a":
            self.current = None

for model in ("mimmi", "yui"):
    base = ROOT / "apps" / f"{model}-gallery"
    parser = Covers()
    parser.feed((base / "index.html").read_text(encoding="utf-8"))
    assert 1 <= len(parser.cards) <= 12, (model, len(parser.cards))
    catalog = json.loads((base / "stored-albums.json").read_text(encoding="utf-8"))
    exclusions = json.loads((base / "identity-exclusions.json").read_text(encoding="utf-8"))
    excluded_ids = set(exclusions.get("excluded_album_ids", []) + exclusions.get("excluded_source_ids", []))
    excluded_sha = set(exclusions.get("excluded_image_sha256", []))
    stored = {a["id"]:a for a in catalog["albums"]}
    ids = set()
    bytes_in_first_viewport = 0
    for index, row in enumerate(parser.cards):
        c, img = row["card"], row["img"]
        assert img is not None
        aid = c["data-id"]
        assert aid not in ids and aid not in excluded_ids, (model, aid)
        ids.add(aid)
        assert c["href"] == "#album=" + aid or unquote(c["href"]) == "#album=" + aid
        album = stored[aid]
        matches = [p for p in album["images"]
                   if p["sha256"] == c["data-fast-sha"] and p["url"] == img["src"]]
        assert len(matches) == 1, (model, aid, "not a physically stored exact-SHA cover")
        p = matches[0]
        assert p["sha256"] not in excluded_sha
        assert img["src"].startswith(f"stored-albums/{aid}/")
        disk = base / img["src"]
        assert disk.is_file(), (model, img["src"])
        # The manifest's hash, bytes, and dimensions are not proof that the
        # actual committed image is intact. Validate its physical bytes and
        # decoded pixels before calling the prepaint cache safe.
        raw = disk.read_bytes()
        assert len(raw) == p["bytes"], (model, aid, "incorrect physical file size")
        assert hashlib.sha256(raw).hexdigest() == p["sha256"], (
            model, aid, "physical file does not match SHA manifest")
        with Image.open(BytesIO(raw)) as actual:
            actual.load()
            assert actual.size == (p["width"], p["height"]), (
                model, aid, "decoded pixels differ from saved catalog")
        assert img["width"] == str(p["width"]) and img["height"] == str(p["height"])
        assert img["decoding"] == "async"
        assert img["loading"] == ("eager" if index < 4 else "lazy")
        assert img["referrerpolicy"] == "no-referrer"
        if index < 4:
            bytes_in_first_viewport += p["bytes"]
    # Prepainting must not flood the first screen with large original transfers.
    assert bytes_in_first_viewport <= 1_500_000, (model, bytes_in_first_viewport)
    print("SAVED_SHA_HTML_FIRST_PAINT_COVERS_PASS",
          json.dumps({"model": model, "covers": len(parser.cards),
                      "eager_image_bytes": bytes_in_first_viewport}))

print("BOTH_GALLERIES_NO_REMOTE_OR_UNVERIFIED_PREPAINT_PHOTOS_PASS")
