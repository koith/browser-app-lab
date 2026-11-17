#!/usr/bin/env python3
"""Rebuild a compact, derived 4LEAF backlog index without rewriting history.

Usage:
  python3 apps/4leaf/rog/docs/build_restoration_active.py
  python3 apps/4leaf/rog/docs/build_restoration_active.py --check

The 580KB historical ledger remains canonical. This index contains ONLY
the currently unresolved acceptance items and small source pointers.
Never update task states here; change RESTORATION_LEDGER.json first.
"""
import argparse
import json
from pathlib import Path

SOURCE = Path(__file__).with_name("RESTORATION_LEDGER.json")
TARGET = Path(__file__).with_name("RESTORATION_ACTIVE.json")


def build():
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    tasks = raw["tasks"]
    counts = {state: sum(x.get("status") == state for x in tasks)
              for state in ("done", "in_progress", "todo", "blocked")}
    active = []
    for task in tasks:
        if task.get("status") == "done":
            continue
        context = " ".join(str(task.get("current") or "").split())
        active.append({
            "id": task["id"],
            "priority": task.get("priority"),
            "title": task.get("title"),
            "status": task.get("status"),
            "acceptance": task.get("acceptance") or [],
            "currentTail": ("…" if len(context) > 280 else "") + context[-280:],
            "evidence": (task.get("evidence") or [])[-2:],
            "lastReviewed": task.get("lastReviewed"),
        })
    return {
        "schemaVersion": 1,
        "sourceOfTruth": "apps/4leaf/rog/docs/RESTORATION_LEDGER.json",
        "warning": "Derived index only. Never treat this file as an independent task ledger.",
        "sourceUpdatedAt": raw.get("updatedAt"),
        "counts": {"total": len(tasks), **counts, "active": len(active)},
        "historicalEventsNotDuplicated": len(raw.get("events", [])),
        "active": active,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    expected = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != expected:
            raise SystemExit("RESTORATION_ACTIVE.json is stale. Rebuild from source.")
        print("4LEAF active backlog index verified")
        return
    TARGET.write_text(expected, encoding="utf-8")
    print("Wrote", TARGET, "bytes=", len(expected.encode("utf-8")))


if __name__ == "__main__":
    main()
