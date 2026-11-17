#!/usr/bin/env python3
"""Read-only TeraBox storage census: report counts only, never names or bytes.

Consumes rclone lsjson --recursive --files-only and the authenticated same-model
catalog read separately by an operator-run GitHub Action. No image download,
media modification, file path disclosure or automatic ingestion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".tif", ".tiff")
ARCHIVE_EXT = (".zip", ".7z", ".rar", ".tar", ".gz", ".tgz")


def summarize(model: str, listing: object, catalog: object) -> dict:
    if model not in ("mimmi", "yui"):
        raise ValueError("UNSUPPORTED_OWNER_MODEL")
    if (not isinstance(catalog, dict) or catalog.get("model") != model
            or catalog.get("schema_version") != 1
            or not isinstance(catalog.get("albums"), list)):
        raise ValueError("OWNER_CATALOG_NOT_VERIFIED")
    if not isinstance(listing, list):
        raise ValueError("STORAGE_LIST_NOT_JSON_ARRAY")

    indexed = set()
    catalog_rows = 0
    rows_without_key = 0
    for album in catalog["albums"]:
        if not isinstance(album, dict) or not isinstance(album.get("images"), list):
            raise ValueError("OWNER_CATALOG_ALBUM_INVALID")
        for photo in album["images"]:
            if not isinstance(photo, dict):
                raise ValueError("OWNER_CATALOG_PHOTO_INVALID")
            catalog_rows += 1
            key = photo.get("key")
            if isinstance(key, str) and key.startswith("originals/") and not any(
                    part in ("", ".", "..") for part in key.split("/")):
                indexed.add(key)
            else:
                rows_without_key += 1

    actual = set()
    unindexed_originals = 0
    unindexed_other_images = 0
    unindexed_archive_files = 0
    original_bytes = 0
    unknown_size = 0
    for row in listing:
        if not isinstance(row, dict) or not isinstance(row.get("Path"), str):
            raise ValueError("STORAGE_LIST_ENTRY_INVALID")
        key = row["Path"].strip("/")
        if (not key or key.startswith("../") or
                any(part in ("", ".", "..") for part in key.split("/"))):
            raise ValueError("STORAGE_LIST_PATH_INVALID")
        if key in actual:
            raise ValueError("STORAGE_LIST_DUPLICATE_PATH")
        actual.add(key)
        if row.get("IsDir") is True:
            raise ValueError("STORAGE_LIST_UNEXPECTED_DIRECTORY")
        size = row.get("Size")
        if not isinstance(size, int) or size < 0:
            unknown_size += 1
            size = 0
        low = key.casefold()
        if key in indexed:
            original_bytes += size
        elif low.endswith(IMAGE_EXT):
            if key.startswith("originals/"):
                unindexed_originals += 1
            else:
                unindexed_other_images += 1
        elif low.endswith(ARCHIVE_EXT):
            unindexed_archive_files += 1

    return {
        "model": model,
        "catalog_album_count": len(catalog["albums"]),
        "catalog_photo_records": catalog_rows,
        "catalog_unique_file_keys": len(indexed),
        "catalog_records_without_valid_original_key": rows_without_key,
        "remote_file_count": len(actual),
        "catalog_referenced_files_found": len(indexed & actual),
        "catalog_referenced_files_missing": len(indexed - actual),
        "unindexed_original_image_candidates": unindexed_originals,
        "unindexed_other_image_candidates": unindexed_other_images,
        "unindexed_archive_candidates": unindexed_archive_files,
        "indexed_original_file_bytes_found": original_bytes,
        "remote_entries_without_size": unknown_size,
        "read_only": True,
        "media_downloaded": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=("mimmi", "yui"))
    parser.add_argument("--listing", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.listing.read_text(encoding="utf-8"))
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    result = summarize(args.model, inventory, catalog)
    print("OWNER_ARCHIVE_UNINDEXED_INVENTORY", json.dumps(
        result, sort_keys=True, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
