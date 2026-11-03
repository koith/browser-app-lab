#!/usr/bin/env python3
"""Synthetic test of tools/decode-obs-blocks.py plus a check of the format on
the REAL checked-in data.

Synthetic (no original bytes): a 2-block member whose blocks use different
palettes must come out with each block's own colour, followed by an
animation table that must parse (frame keys, ticks, event member).
Real data: tools/decode-obs-anim-table.py must parse all 227 stored member
trailers to the last byte (this part IS original-data evidence).
Run: python3 apps/4leaf/rog/tests/test_decode_obs_blocks.py
"""
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROG = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("blocks", ROG / "tools/decode-obs-blocks.py")
blocks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blocks)


def body(w, h, index):
    runs = [(y * 640, bytes([index]) * w) for y in range(h)]
    out = struct.pack("<HH", len(runs), runs[0][0])
    end = runs[0][0]
    for k, (cursor, px) in enumerate(runs):
        if k:
            out += struct.pack("<H", cursor - end)
        out += bytes([len(px) // 4, len(px) % 4]) + px
        end = cursor + len(px)
    return out


def block(header_prefix, frames, colour):
    head = bytearray(128)
    struct.pack_into("<H", head, 66, len(frames))
    out = header_prefix + bytes(head)
    for w, h in frames:
        b = body(w, h, 5)
        out += struct.pack("<IHHhh", len(b), w, h, -(w // 2), -h) + b
    pal = bytearray(768)
    pal[15:18] = bytes(colour)          # palette index 5
    return out + bytes(pal)


def anim_table():
    rec = lambda *v: struct.pack("<9H", *v)
    a0 = rec(0, 3, 0, 0, 0, 9, 9, 9, 9) + rec(0, 1, 4, 1, 9, 9, 9, 9, 9) + rec(3, 3, 0, 0, 1, 9, 9, 9, 9)
    a1 = rec(0, 3, 0, 0, 1, 9, 9, 9, 9) + rec(0, 15, 2, 1112, 1, 65532, 65506, 0, 9)
    return struct.pack("<I", 2) + struct.pack("<II", 6, 3) + a0 + struct.pack("<II", 3, 2) + a1 + bytes(34)


def pak(entries):
    raw = struct.pack("<I", len(entries) ^ 0xFFFFFFFF)
    payload = b""
    for name, blob in entries:
        payload += blob
        raw += bytes(c ^ 255 for c in name.encode().ljust(24, b"\0")) + struct.pack("<I", (len(payload) - 1) ^ 0xFFFFFFFF)
    return raw + payload


def synthetic():
    member = struct.pack("<I", 2) + block(b"", [(10, 8), (12, 8)], (200, 0, 0)) + \
        block(b"", [(6, 6), (6, 7), (8, 6)], (0, 0, 200)) + anim_table()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "res").mkdir()
        (tmp / "res/OBS.pak").write_bytes(pak([("1171.obs", member)]))
        (tmp / "repo/apps/4leaf/rog/docs/evidence/source-maps").mkdir(parents=True)
        (tmp / "repo/apps/4leaf/rog/docs/evidence/source-maps/quantity-reconciliation.json").write_text(
            json.dumps({"cardBodiesNotYetPublished": ["OBS.pak/1171"]}))
        s = blocks.run(tmp / "res", tmp / "repo")
        assert s["referencedMembers"] == 1, s
        ref = (tmp / "repo/apps/4leaf/rog/original/OBS/referenced/manifest.js").read_text()
        assert '"obs/1171"' in ref and "obs-1171-001.png" in ref
        assert s["splitOK"] == 1 and s["multiBlockMembers"] == 1 and s["blockFrames"] == 5, s
        assert s["tableDecoded"] == 1 and s["tailVariants"] == {"zero34": 1}, s
        out = tmp / "repo/apps/4leaf/rog/original/OBS/blocks"
        red = np.array(Image.open(out / "obs-1171-b0-000.png").convert("RGBA"))
        blue = np.array(Image.open(out / "obs-1171-b1-002.png").convert("RGBA"))
        assert tuple(red[0, 0, :3]) == (200, 0, 0) and tuple(blue[0, 0, :3]) == (0, 0, 200), "own palette per block"
        t = json.loads((tmp / "repo/apps/4leaf/rog/docs/evidence/obs-blocks/animation-tables.json").read_text())["obs/1171"]
        assert t["blockFrames"] == [2, 3]
        assert [k["frame"] for k in t["animations"][0]["frameKeys"]] == [0, 1]
        assert t["animations"][0]["durationTicks"] == 6
        assert t["animations"][1]["events"][0]["member"] == 1112 and t["animations"][1]["events"][0]["offsetY"] == -30


def real_tables():
    r = subprocess.run([sys.executable, str(ROG / "tools/decode-obs-anim-table.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = json.loads((ROG / "docs/evidence/source-maps/actor-native-action-map.json").read_text())
    assert a["stats"]["decoded"] == 227 and not a["stats"]["failed"], a["stats"]
    assert len(a["chessmanSchema17"]) == 86
    m = a["members"]["obs/1040"]["animations"]
    assert [k["frame"] for k in m[3]["frameKeys"]] == [3, 5, 6, 7, 8]       # rear walk skips 4
    assert [k["frame"] for k in m[0]["frameKeys"]] == [0, 1, 2]
    return a["stats"]


if __name__ == "__main__":
    synthetic()
    stats = real_tables()
    print("OBS BLOCKS PASS", json.dumps({"synthetic": "PASS", "realTablesDecoded": stats["decoded"],
                                          "tailVariants": stats["tailVariants"]}))
