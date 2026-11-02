#!/usr/bin/env python3
"""Rebuild docs/evidence/source-maps from the original data and require the
committed files to be identical (no hand edits), every listed frame file to
hash to its recorded SHA-256, and the key counts measured on 2026-11-02.
Run: python3 apps/4leaf/rog/tests/test_source_evidence.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROG = Path(__file__).resolve().parents[1]
OUT = ROG / "docs/evidence/source-maps"
FILES = ["actor-frame-audit.json", "actor-action-map.json", "missing-resources.json", "dice-animation-map.json",
         "dice-rule-evidence.json", "board-layout-evidence.json", "game-rules-evidence.json",
         "screen-reference-catalog.json"]


def main():
    before = {f: (OUT / f).read_bytes() for f in FILES}
    assert len(json.loads(before["screen-reference-catalog.json"])["references"]) == 11
    subprocess.run([sys.executable, str(ROG / "tools/build-source-evidence.py")], check=True, capture_output=True)
    for f in FILES:
        assert (OUT / f).read_bytes() == before[f], f + " differs from a fresh rebuild"
    audit = json.loads(before["actor-frame-audit.json"])
    for cid, card in audit["cards"].items():
        for fr in card.get("frames", []):
            assert hashlib.sha256((ROG / fr["file"][2:]).read_bytes()).hexdigest() == fr["sha256"], (cid, fr["file"])
    s = audit["summary"]
    assert (s["cards"], s["withOriginalBody"], s["completeAllFrames"]) == (98, 54, 54), s
    action = json.loads(before["actor-action-map.json"])["summary"]
    assert action["layout37Verified"] == 44 and {"0042", "0045", "0088"} <= set(action["layout37"]), action
    assert {"0084", "0085", "0086"} <= set(action["otherLayouts"])
    missing = json.loads(before["missing-resources.json"])
    assert sorted(missing["absentFromAllPacks"]) == ["0091", "0126", "0129", "0132", "0157", "0168"]
    board = json.loads(before["board-layout-evidence.json"])
    assert board["routes"] == 26 and board["titled"] == 25 and board["untitled"] == ["0170"] and board["startCellCode13"]
    rules = json.loads(before["game-rules-evidence.json"])
    assert rules["specialCells"]["10"]["count"] == 129 and rules["specialCells"]["10"]["param5IsInRouteTarget"] == 129
    dice = json.loads(before["dice-animation-map.json"])["members"]
    assert {k: v["publishedFrames"] for k, v in dice.items()} == {"1167": 25, "1171": 28, "1223": 22}
    print("SOURCE EVIDENCE PASS", json.dumps({"bodies": s["withOriginalBody"], "frames": s["publishedFrames"],
                                              "layout37": action["layout37Verified"]}))


if __name__ == "__main__":
    main()
