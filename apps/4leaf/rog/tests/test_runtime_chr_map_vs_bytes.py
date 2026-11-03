#!/usr/bin/env python3
"""ORIGINAL-data cross-check of the runtime card->body map (#522).

Loads chr-body-source-map.js in node, reads every CHR record's +260 member
number straight from docs/evidence/obs-trailers/chr.json (raw bytes of
Dice/CHR.pak, SHA1-verified installer), and requires all 98 cards to agree,
the OBS pak to be the one that actually contains the member (census.json),
0156 -> 1222 marked missing, and the named key cases to hold.
Run: python3 apps/4leaf/rog/tests/test_runtime_chr_map_vs_bytes.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROG = Path(__file__).resolve().parents[1]
KEY_CASES = {"0088": "1071", "0087": "1070", "0091": "1074", "0170": "1267", "0056": "1040",
             "0040": "1025", "0125": "1199", "0147": "1221", "0157": "1254", "0171": "1276"}


def runtime_map():
    script = ("global.window=global;require(%r);const m=window.__LEAF_CHR_BODY_MAP__;"
              "process.stdout.write(JSON.stringify(m.cards))" % str(ROG / "chr-body-source-map.js"))
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    records = json.loads((ROG / "docs/evidence/obs-trailers/chr.json").read_text(encoding="utf-8"))["records"]
    cards = {c["id"] for c in json.loads((ROG / "original/chessmen.json").read_text(encoding="utf-8"))}
    census = json.loads((ROG / "docs/evidence/obs-census/census.json").read_text(encoding="utf-8"))["members"]
    where = {}
    for m in census:
        where.setdefault(m["member"][:-4], set()).add(m["pak"].replace(".pak", ""))
    raw = {n[:4]: bytes.fromhex(h)[260:324].split(b"\0")[0].decode("ascii") for n, h in records.items()}
    rt = runtime_map()
    assert set(rt) == cards, sorted(set(rt) ^ cards)
    mismatches = []
    for card in sorted(cards):
        r = rt[card]
        if r.get("member") != raw[card]:
            mismatches.append((card, r.get("member"), raw[card]))
            continue
        if raw[card] in where:
            assert r.get("pak") in where[raw[card]], (card, r.get("pak"), where[raw[card]])
        else:
            assert r.get("missing") is True and r.get("pak") is None, (card, r)
    assert not mismatches, mismatches
    for card, member in KEY_CASES.items():
        assert raw[card] == member and rt[card]["member"] == member, (card, raw[card], rt[card])
    assert raw["0156"] == "1222" and "1222" not in where
    print("RUNTIME CHR MAP VS BYTES PASS", json.dumps({"cards": len(cards), "agree": len(cards),
                                                      "missing": ["0156->1222"], "keyCases": len(KEY_CASES)}))


if __name__ == "__main__":
    main()
