#!/usr/bin/env python3
"""Original-data test: the runtime module carries the decoded original tables.

Chain: original OBS/OBS2/OBS3 members --(CI decode, test_decode_obs_blocks.py on
227 real trailers)--> actor-native-anim-runtime.json --(generator)-->
native-card-action-sequences.js.  This test checks the last link for all 97
CHR bodies and pins byte-derived facts the old hard-coded table got wrong.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
SLOTS = [0, 1, 2, 3, 4, 5, 12]


def pair(s, i):
    return B62.index(s[i]) * 62 + B62.index(s[i + 1])


def parse_module():
    text = (ROOT / "native-card-action-sequences.js").read_text(encoding="utf-8")
    raw = re.search(r'const RAW="(.*?)";', text).group(1).split("\\n")
    out = {}
    for line in raw:
        m = re.fullmatch(r"(0\d{3})=(obs[23]?)/(\d{4})/(\d+)/(.+)", line)
        assert m, line
        anims = []
        for s in m.group(5).split("|"):
            if s == "-":
                anims.append(None)
                continue
            keys = [[pair(s, i), pair(s, i + 2)] for i in range(2, len(s), 4)]
            anims.append({"ticks": pair(s, 0), "keys": keys})
        out[m.group(1)] = {"member": m.group(2) + "/" + m.group(3), "effects": int(m.group(4)), "anims": anims}
    return text, out


def main():
    r = subprocess.run([sys.executable, str(ROOT / "tools/build-native-card-action-module.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    text, mod = parse_module()
    data = json.loads((ROOT / "docs/evidence/source-maps/actor-native-anim-runtime.json").read_text())
    body = json.loads((ROOT / "docs/evidence/source-maps/card-body-map.json").read_text())
    assert len(mod) == len(data["cards"]) == 97
    checked = 0
    for card, c in data["cards"].items():
        m = mod[card]
        assert m["member"] == c["member"], card
        anims = {a["index"]: a for a in c["animations"]}
        for slot, enc in zip(SLOTS, m["anims"]):
            a = anims[slot]
            if a["ticks"] == 0xFFFFFFFF:
                assert enc is None and not a["keys"], (card, slot)
            else:
                assert enc == {"ticks": a["ticks"], "keys": a["keys"]}, (card, slot)
            checked += 1
        assert m["effects"] == len(anims[12]["events"])
    # CHR +260 linkage of the module rows equals the byte-derived card map.
    paks = {"OBS.pak": "obs", "OBS2.pak": "obs2", "OBS3.pak": "obs3"}
    for card, m in mod.items():
        row = body["cards"][card]
        assert m["member"] == paks[row["bodyPak"]] + "/" + row["bodyMember"], (card, row["bodyMember"], m["member"])
    # Byte facts the #522 hard-coded 'classic' table contradicted.
    a0074 = mod["0074"]["anims"]
    assert [k[1] for k in a0074[0]["keys"]] == [22, 23, 24], "body 1057 slot 0 starts on 22, not 0"
    assert [k[1] for k in a0074[2]["keys"]] == [0, 1, 2], "body 1057 front/rear are swapped vs the 41 others"
    classic = [c for c, m in mod.items() if m["member"].startswith("obs/")]
    same = [c for c in classic if [k[1] for k in mod[c]["anims"][0]["keys"]] == [0, 1, 2]]
    assert len(classic) == 59 and len(same) == 58, (len(classic), len(same))
    # Anim 12 (duel lunge, role INFERRED): exact original keys.
    assert mod["0078"]["anims"][6] == {"ticks": 27, "keys": [[0, 33], [3, 33], [6, 33], [9, 34], [12, 35],
                                                             [15, 36], [18, 36], [21, 36], [24, 36]]}
    assert mod["0125"]["anims"][6] == {"ticks": 22, "keys": []}, "0125 lunge slot has no keys"
    assert [k[0] for k in mod["0126"]["anims"][6]["keys"]] == [0, 3, 6, 9, 14, 17, 20], "non-uniform ticks kept"
    # 0135: walk slots are finite but keyless -> the module may not invent a walk.
    assert all(mod["0135"]["anims"][i] == {"ticks": 18, "keys": []} for i in (3, 4, 5))
    assert "UNVERIFIED" in text and "INFERRED" in text and "effect events are NOT played" in text
    print("NATIVE CARD ACTION MODULE ORIGINAL TABLE PASS",
          json.dumps({"bodies": len(mod), "slotsChecked": checked, "classicBodies": len(classic),
                      "body1057FrontRearSwapped": True}))


if __name__ == "__main__":
    main()
