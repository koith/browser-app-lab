"""Read-only exact inventory comparison before any Cloudflare media reads.

A matching owner index means the already-deployed gallery is complete:
rebuilding it cannot improve coverage and must be skipped.
"""
import json
from pathlib import Path
import re

from cloudflare_assets_snapshot import KIND, MODELS, signature

_ALBUM = re.compile(r"[a-z0-9][a-z0-9-]{1,99}")


def local_owner_inventory(root):
    root = Path(root)
    inventory = {}
    for model in MODELS:
        doc = json.loads((root / f"apps/{model}-gallery/owner-index.json").read_text())
        if doc.get("model") != model or not isinstance(doc.get("albums"), list):
            raise ValueError("OWNER_INDEX_INVALID")
        rows = {}
        for album in doc["albums"]:
            aid = album.get("id")
            if not isinstance(aid, str) or not _ALBUM.fullmatch(aid) or not isinstance(album.get("images"), list):
                raise ValueError("OWNER_ALBUM_INVALID")
            for photo in album["images"]:
                number = photo.get("number")
                if type(number) is not int or not 0 < number < 10000:
                    raise ValueError("OWNER_NUMBER_INVALID")
                key = (aid, number)
                if key in rows:
                    raise ValueError("OWNER_INDEX_DUPLICATE")
                rows[key] = photo
        inventory[model] = rows
    return inventory


def inventory_delta(existing, owner):
    """Determine additions without changing or silently dropping existing media."""
    if set(existing) != set(MODELS) or set(owner) != set(MODELS):
        raise ValueError("MODEL_SET_MISMATCH")
    missing, retained = {}, {}
    for model in MODELS:
        catalog = existing[model]
        if (catalog.get("archive_kind") != KIND or catalog.get("schema_version") != 1
                or catalog.get("model") != model or not isinstance(catalog.get("albums"), list)):
            raise ValueError("EXISTING_REPLICA_CATALOG_INVALID")
        published = {}
        for album in catalog["albums"]:
            aid = album.get("id")
            if not isinstance(aid, str) or not _ALBUM.fullmatch(aid) or not isinstance(album.get("images"), list):
                raise ValueError("EXISTING_REPLICA_ALBUM_INVALID")
            for photo in album["images"]:
                number = photo.get("number")
                if type(number) is not int or not 0 < number < 10000:
                    raise ValueError("EXISTING_REPLICA_PHOTO_INVALID")
                key = (aid, number)
                filename = photo.get("key")
                if key in published:
                    raise ValueError("EXISTING_REPLICA_DUPLICATE")
                if (not isinstance(filename, str) or not filename.startswith(f"originals/{aid}/")
                        or not re.fullmatch(r"[A-Za-z0-9/_ .-]{1,1023}", filename)
                        or any(seg in ("", ".", "..") for seg in filename.split("/"))):
                    raise ValueError("EXISTING_REPLICA_KEY_INVALID")
                published[key] = photo
        for key, prior in published.items():
            if key not in owner[model]:
                raise ValueError("REFUSE_TO_DROP_EXISTING_ORIGINAL")
            if signature(prior) != signature(owner[model][key]):
                raise ValueError("REFUSE_TO_REPLACE_EXISTING_ORIGINAL")
        missing[model] = {key: row for key, row in owner[model].items() if key not in published}
        retained[model] = len(published)
    return missing, retained
