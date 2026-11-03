#!/usr/bin/env python3
"""Round-8 native maps: rebuild from original data must be byte-identical and
the measured facts must hold. Covers ORIGINAL data only (no synthetic part).
Run: python3 apps/4leaf/rog/tests/test_native_maps.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROG = Path(__file__).resolve().parents[1]
OUT = ROG / "docs/evidence/source-maps"
FILES = ["actor-native-action-map.json", "dice-native-sequences.json", "actor-native-anim-runtime.json",
         "card-mapping-candidates.json", "ledger-events-round8.json", "card-body-map.json",
         "quantity-reconciliation.json", "action-semantics-evidence.json"]


def main():
    before = {f: (OUT / f).read_bytes() for f in FILES}
    for tool in ("decode-obs-anim-table.py", "decode-chr-model-map.py", "build-native-maps.py"):
        subprocess.run([sys.executable, str(ROG / "tools" / tool)], check=True, capture_output=True)
    for f in FILES:
        assert (OUT / f).read_bytes() == before[f], f + " differs from a fresh rebuild"
    dice = json.loads(before["dice-native-sequences.json"])
    for die, faces in (("D6", 6), ("D4", 4)):
        g = dice[die]["groups"]
        assert g["facesPerDie"] == faces and all(g["checks"].values()), (die, g)
    assert {k: v["frames"] for k, v in dice["D6"]["extraBlocks"].items()} == {"obs-1171-c0": 16, "obs-1171-c1": 16, "obs-1171-c2": 6}
    assert {k: v["frames"] for k, v in dice["D4"]["extraBlocks"].items()} == {"obs-1223-c0": 9, "obs-1223-c1": 16}
    rt = json.loads(before["actor-native-anim-runtime.json"])["cards"]
    assert len(rt) == 97 and all(v["animations"] for v in rt.values())
    assert rt["0088"]["member"] == "obs/1071" and rt["0087"]["member"] == "obs/1070"
    a = rt["0056"]["animations"]                       # card 0056 -> member 1040
    assert rt["0056"]["member"] == "obs/1040"
    assert [k[1] for k in a[3]["keys"]] == [3, 5, 6, 7, 8] and [k[0] for k in a[3]["keys"]] == [0, 3, 6, 9, 12]
    assert a[12]["keys"][:6] == [[0, 33], [3, 33], [6, 33], [9, 34], [12, 35], [15, 36]]
    cand = json.loads(before["card-mapping-candidates.json"])
    assert cand["status"].startswith("SUPERSEDED") and cand["verifiedCardBodies"] == 97 and cand["missing"] == ["0156"]
    assert "NOT demonstrated" in before["ledger-events-round8.json"].decode()
    sem = json.loads(before["action-semantics-evidence.json"])["schemas"]
    assert sem["17"]["cards"] == 85 and sem["15"]["cards"] == 12
    print("NATIVE MAPS PASS", json.dumps({"runtimeCards": len(rt), "dice": "D6/D4 groups verified",
                                         "schema17": 85, "schema15": 12}))


if __name__ == "__main__":
    main()
