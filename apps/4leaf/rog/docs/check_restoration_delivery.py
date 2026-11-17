#!/usr/bin/env python3
"""4LEAF completion-first ledger gate (never updates historical task states)."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "RESTORATION_LEDGER.json"
FOCUS = ROOT / "DELIVERY_FOCUS.json"
CLOSURES = ROOT / "DELIVERY_CLOSURES.json"
ACTIVE = ROOT / "RESTORATION_ACTIVE.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check():
    ledger, focus, closures, active = map(read, (LEDGER, FOCUS, CLOSURES, ACTIVE))
    tasks = ledger["tasks"]
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task IDs in canonical ledger")
    byid = {t["id"]: t for t in tasks}
    done = {t["id"] for t in tasks if t.get("status") == "done"}
    open_ids = set(ids) - done

    counts = active["counts"]
    for key, expected in (
        ("total", len(ids)), ("done", len(done)), ("active", len(open_ids)),
    ):
        if counts.get(key) != expected:
            raise ValueError(f"Active snapshot is stale: {key}, expected {expected}")
    if {t["id"] for t in active["active"]} != open_ids:
        raise ValueError("Active snapshot task IDs do not match the canonical ledger")
    if active.get("sourceUpdatedAt") != ledger.get("updatedAt"):
        raise ValueError("Active snapshot source timestamp differs; regenerate index")

    baseline = focus["baselineDone"]
    if len(baseline) != len(set(baseline)) or not set(baseline) <= set(ids):
        raise ValueError("Historical accepted IDs are duplicated or missing")
    selected = focus["activeFocus"]
    if not isinstance(selected, str) or selected not in open_ids:
        raise ValueError("Exactly one ACTIVE, genuinely incomplete task is required")
    future = focus["nextFocus"]
    if not isinstance(future, list) or len(future) != len(set(future)):
        raise ValueError("Next focus list must be ordered with no duplicates")
    if set(future) != (open_ids - {selected}):
        raise ValueError("Every remaining task must appear once in the next-focus order")

    new_done = done - set(baseline)
    recorded = closures["newClosures"]
    if set(recorded) != new_done:
        raise ValueError(
            "Do not close a task without complete acceptance evidence, "
            f"newly done={sorted(new_done)} evidence={sorted(recorded)}"
        )

    required = (
        "originalSource", "renewalSource", "referenceComparison",
        "implementedCommit", "chromiumRunUrl", "webkitRunUrl",
        "publicRunUrl", "publicVersion", "fullUserFlow",
    )
    run_url = re.compile(
        r"^https://github\.com/koith/browser-app-lab/actions/runs/\d+$"
    )
    for task_id, proof in recorded.items():
        for field in required:
            if not isinstance(proof.get(field), str) or not proof[field].strip():
                raise ValueError(f"{task_id}: missing {field} evidence")
        if not re.fullmatch(r"[0-9a-f]{40}", proof["implementedCommit"]):
            raise ValueError(f"{task_id}: record actual merged 40-digit commit")
        for field in ("chromiumRunUrl", "webkitRunUrl", "publicRunUrl"):
            if not run_url.fullmatch(proof[field]):
                raise ValueError(f"{task_id}: {field} must link an Actions run")
        if proof["renewalSource"] == "none":
            raise ValueError(f"{task_id}: unavailable renewal needs a reason and trace")
    print(f"4LEAF DELIVERY GATE PASS: {len(done)}/{len(ids)} done, "
          f"{len(open_ids)} pending, WIP=1: {selected}, "
          f"new accepted closures={len(new_done)}")


if __name__ == "__main__":
    check()
