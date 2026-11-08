"""Restore only a SHA-verified immutable account index for the free viewer.

The worker is run with a hard process-group deadline by the parent gateway.
It never prints private account data, cloud paths, or provider error strings.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys

from account_index_job import latest_manifest, load_snapshot

def restore_snapshot(target: Path) -> None:
    if not os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE"):
        raise RuntimeError("private index reader unavailable")
    info = latest_manifest()
    if info is None:
        raise RuntimeError("no verified private snapshot manifest")
    target.parent.mkdir(parents=True, exist_ok=True)
    load_snapshot(target, info)  # Enforces manifest SHA256 before opening SQLite.
    os.chmod(target, 0o600)
    with sqlite3.connect("file:" + str(target) + "?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("invalid remote account index database")
        if conn.execute("SELECT count(*) FROM accounts").fetchone()[0] <= 0:
            raise RuntimeError("no remote indexed public accounts")
        if conn.execute("SELECT count(*) FROM observed").fetchone()[0] <= 0:
            raise RuntimeError("no remote public observations")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("invalid private index output")
    try:
        restore_snapshot(Path(sys.argv[1]))
    except Exception:
        # Never echo exception text, private paths, records, or backend URLs.
        raise SystemExit("PRIVATE_INDEX_SNAPSHOT_UNAVAILABLE") from None
