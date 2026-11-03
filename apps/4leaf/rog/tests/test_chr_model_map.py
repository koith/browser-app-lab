#!/usr/bin/env python3
"""ORIGINAL-data test: CHR record offset 260 is the body's OBS member number.

Reads the raw CHR bytes (docs/evidence/obs-trailers/chr.json, SHA1-verified
installer) directly - independent of the builder - and checks:
 - every record has a 4-digit ASCII member number at +260,
 - the CP949 name at +196 and the stats at +452 still decode as before,
 - every card except 0156 names a member present in OBS/OBS2/OBS3,
 - no two cards share a body; the OBS2 range is 0125+k -> 1199+k,
 - card-body-map.json / quantity-reconciliation.json agree with the bytes.
Run: python3 apps/4leaf/rog/tests/test_chr_model_map.py
"""
import json
import re
from pathlib import Path

ROG = Path(__file__).resolve().parents[1]
MAPS = ROG / "docs/evidence/source-maps"


def main():
    records = json.loads((ROG / "docs/evidence/obs-trailers/chr.json").read_text(encoding="utf-8"))["records"]
    assert len(records) == 119
    cards = {c["id"]: c for c in json.loads((ROG / "original/chessmen.json").read_text(encoding="utf-8"))}
    members = {m["member"][:-4] for m in json.loads((ROG / "docs/evidence/obs-census/census.json").read_text(encoding="utf-8"))["members"]}
    body = {}
    for name, hexraw in records.items():
        raw = bytes.fromhex(hexraw)
        assert len(raw) == 472
        field = raw[260:324].split(b"\0")[0].decode("ascii")
        assert re.fullmatch(r"1\d{3}", field), (name, field)
        cid = name[:4]
        if cid in cards:
            assert raw[196:260].split(b"\0")[0].decode("cp949") == cards[cid]["name"], cid
            body[cid] = field
    assert set(body) == set(cards)
    missing = sorted(c for c, m in body.items() if m not in members)
    assert missing == ["0156"], missing
    present = [m for c, m in body.items() if m in members]
    assert len(present) == len(set(present)) == 97, "a body is shared by two cards"
    assert all(body["0%d" % (125 + k)] == str(1199 + k) for k in range(23))
    assert body["0040"] == "1025" and body["0088"] == "1071" and body["0091"] == "1074" and body["0170"] == "1267"
    m = json.loads((MAPS / "card-body-map.json").read_text(encoding="utf-8"))["cards"]
    assert {c: r["bodyMember"] for c, r in m.items()} == body
    q = json.loads((MAPS / "quantity-reconciliation.json").read_text(encoding="utf-8"))
    assert q["distinctCardBodies"] == 97 and q["schema17Members"] == 86 and q["schema17UsedByCards"] == 85
    assert q["schema17Unreferenced"] == ["OBS.pak/1166"] and q["cardBodiesNotSchema17"] == 12
    assert q["old54"]["stillACardBody"] + len(q["old54"]["actuallyNonCardBodies"]) + len(q["old54"]["neitherCardNorRecord"]) == 54
    print("CHR MODEL MAP PASS", json.dumps({"cards": len(body), "bodiesPresent": 97, "missing": missing,
                                           "unpublished": len(q["cardBodiesNotYetPublished"])}))


if __name__ == "__main__":
    main()
