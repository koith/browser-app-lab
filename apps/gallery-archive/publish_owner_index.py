#!/usr/bin/env python3
"""Publish *metadata only* for already SHA-verified Yui/Mimmi TeraBox media.

GitHub Pages can show all stored album counts at first paint, instead of
displaying the 10-photo GitHub preview until a sleeping Render process wakes.
No image bytes, cloud storage keys, cookies, private source URLs or credentials
are written to this public JSON index. Original photos stay separate on TeraBox.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ID = re.compile(r"[a-z0-9][a-z0-9-]{1,99}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
MODELS = ("yui", "mimmi")


def clean_catalog(catalog: dict, model: str) -> dict:
    if model not in MODELS or catalog.get("schema_version") != 1 or catalog.get("model") != model:
        raise ValueError("Invalid owner catalog schema/model")
    if catalog.get("storage") != "owner-private-terabox-sha-verified-bytes":
        raise ValueError("Refusing unverified owner inventory")
    albums = catalog.get("albums")
    if not isinstance(albums, list) or not albums:
        raise ValueError("Owner album list unavailable")
    out = []
    ids = set()
    total = 0
    for album in albums:
        aid = album.get("id", "")
        if not isinstance(aid, str) or not ID.fullmatch(aid) or aid in ids:
            raise ValueError("Invalid or duplicated album ID")
        ids.add(aid)
        title = album.get("title")
        if not isinstance(title, str) or not 1 <= len(title) <= 350:
            raise ValueError("Unknown private album title")
        source_photos = album.get("images")
        if not isinstance(source_photos, list) or not source_photos:
            raise ValueError("Owner album does not contain stored original media")
        seen = set()
        images = []
        for photo in source_photos:
            n, sha, count = photo.get("number"), photo.get("sha256"), photo.get("bytes")
            width, height = photo.get("width"), photo.get("height")
            key = photo.get("key", "")
            if (type(n) is not int or not 1 <= n <= 25000 or n in seen
                    or not isinstance(sha, str) or not SHA.fullmatch(sha)
                    or type(count) is not int or not 1000 <= count <= 35000000
                    or type(width) is not int or type(height) is not int
                    or not 100 <= width <= 25000 or not 100 <= height <= 25000
                    or not isinstance(key, str) or not key.startswith("originals/" + aid + "/")
                    or ".." in key or "\\" in key):
                raise ValueError("Owner catalog has an invalid original file entry")
            seen.add(n)
            result = {"number": n, "sha256": sha, "bytes": count,
                      "width": width, "height": height}
            preview = photo.get("preview")
            if preview:
                preview_sha = photo.get("preview_sha256")
                if not isinstance(preview_sha, str) or not SHA.fullmatch(preview_sha):
                    raise ValueError("Stored preview is missing SHA-256")
                result["preview"] = True
                result["preview_sha256"] = preview_sha
            if photo.get("display_rotation") in (90, 270):
                result["display_rotation"] = photo["display_rotation"]
            images.append(result)
        images.sort(key=lambda p: p["number"])
        expected = album.get("expected")
        item = {"id": aid, "title": title, "images": images}
        if type(expected) is int and expected > 0:
            item["expected"] = expected
        if isinstance(album.get("publisher"), str) and len(album["publisher"]) < 100:
            item["publisher"] = album["publisher"]
        out.append(item)
        total += len(images)
    out.sort(key=lambda a: a["id"])
    return {
        "schema_version": 1,
        "model": model,
        "storage": "sha-verified-owner-metadata-only",
        "physical_originals_indexed": total,
        "albums": out,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--model", choices=MODELS, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    catalog = json.loads(args.input.read_text(encoding="utf-8"))
    index = clean_catalog(catalog, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n"
    # Never log a SHA hash or the album names. Only the public gallery count.
    args.output.write_text(serialized, encoding="utf-8")
    print("OWNER_STATIC_GALLERY_METADATA_ONLY",
          json.dumps({"model": args.model,
                      "albums":len(index["albums"]),
                      "physical_originals_indexed":index["physical_originals_indexed"],
                      "index_bytes":len(serialized.encode("utf-8"))}),flush=True)


if __name__ == "__main__":
    main()
