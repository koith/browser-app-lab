#!/usr/bin/env python3
"""Synthetic end-to-end test of tools/decode-obs-extended.py (no original bytes).

Covers: a 320-px-wide member and a member with a 2-byte empty frame record,
both rejected by the strict decoder and recovered here; an embedded frame
chain hidden after the palette behind an 18-byte record table; an OBS2
character-size member exported as quarantined; a small OBS2 member left out;
CHR records written as hex; period-18 detection and a frame-index field.
Run: python3 apps/4leaf/rog/tests/test_decode_obs_extended.py
"""
import importlib.util
import json
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ext", ROOT / "tools/decode-obs-extended.py")
ext = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ext)


def encode(mask, colour=7):
    runs = []
    h, w = mask.shape
    for y in range(h):
        x = 0
        while x < w:
            if mask[y, x]:
                s = x
                while x < w and mask[y, x]:
                    x += 1
                runs.append((y * 640 + s, bytes([colour]) * (x - s)))
            else:
                x += 1
    body = struct.pack("<HH", len(runs), runs[0][0])
    end = runs[0][0]
    for k, (cursor, px) in enumerate(runs):
        if k:
            body += struct.pack("<H", cursor - end)
        body += bytes([len(px) // 4, len(px) % 4]) + px
        end = cursor + len(px)
    return body


def rect(w, h, x0=0, y0=0, x1=None, y1=None):
    m = np.zeros((h, w), bool)
    m[y0:y1 or h, x0:x1 or w] = True
    return m


def frame_record(mask, empty=False):
    h, w = mask.shape
    body = b"\x00\x00" if empty else encode(mask)
    return struct.pack("<IHHhh", len(body), w, h, -(w // 2), -h) + body


def member(frames, trailer=b"", empties=()):
    header = bytearray(132)
    struct.pack_into("<H", header, 70, len(frames))
    out = bytes(header)
    for i, m in enumerate(frames):
        out += frame_record(m, empty=i in empties)
    return out + bytes(range(256)) * 3 + trailer


def pak(entries):
    raw = struct.pack("<I", len(entries) ^ 0xFFFFFFFF)
    payload = b""
    for name, blob in entries:
        payload += blob
        raw += bytes(c ^ 255 for c in name.encode().ljust(24, b"\0")) + struct.pack("<I", (len(payload) - 1) ^ 0xFFFFFFFF)
    return raw + payload


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        res = tmp / "res/Dice"
        res.mkdir(parents=True)
        repo = tmp / "repo"
        (repo / "apps/4leaf/rog").mkdir(parents=True)
        # 18-byte record table: field 1 is a frame index < 3, then a hidden chain
        table = b"".join(struct.pack("<9H", 5, i % 3, 100 + i, 0, 0, 0, 0, 0, 7) for i in range(40))
        hidden = frame_record(rect(30, 30, 5, 5, 25, 25)) + frame_record(rect(30, 30, 0, 10)) + frame_record(rect(28, 32, 4, 0, 24))
        d6 = member([rect(40, 40, 5, 5, 35, 35)] * 3, trailer=b"\x01\x02" + table + hidden + b"\xff" * 9)
        (res / "OBS.pak").write_bytes(pak([
            ("1154.obs", member([rect(320, 40, 10, 5, 300, 35), rect(320, 40, 0, 0, 320, 20)])),
            ("1175.obs", member([rect(10, 10), rect(20, 30, 2, 2, 18, 28)], empties={0})),
            ("1171.obs", d6),
            ("1040.obs", member([rect(30, 60, 5, 0, 25)] * 4)),
        ]))
        (res / "OBS2.pak").write_bytes(pak([
            ("1201.obs", member([rect(50, 60, 5 + (i % 3), 0, 40) for i in range(24)])),
            ("1224.obs", member([rect(21, 23)])),
        ]))
        (res / "CHR.pak").write_bytes(pak([("0040.chr", bytes(472)), ("0125.chr", bytes(range(236)) * 2)]))
        summary = ext.run(tmp / "res", repo)
        rog = repo / "apps/4leaf/rog"
        assert summary["members"] == 6, summary["members"]
        assert summary["wideRecovered"] == {"obs/1154": 2, "obs/1175": 2}, summary["wideRecovered"]
        assert summary["emptyFrames"] == 1
        wide = (rog / "original/OBS/recovered-wide/manifest.js").read_text()
        assert '"status": "EMPTY"' in wide and "obs-1154-001.png" in wide
        assert (rog / "original/OBS/recovered-wide/obs-1154-000.png").exists()
        assert summary["embeddedChains"] == {"obs-1171-c0": 3}, summary["embeddedChains"]
        assert len(list((rog / "original/OBS/embedded").glob("obs-1171-c0-*.png"))) == 3
        assert summary["obs23ActorMembers"] == {"obs2/1201": 24}, summary["obs23ActorMembers"]
        actors = (rog / "original/OBS/obs23-actors/manifest.js").read_text()
        assert '"assignedCard": null' in actors and "QUARANTINED" in actors
        trailers = json.loads((rog / "docs/evidence/obs-trailers/trailers.json").read_text())
        t = trailers["obs/1171"]
        assert t["hex"].startswith("0102") and t["embeddedChains"][0]["frames"] == 3
        # period-18 table: best period on the table bytes and a frame-index field
        table_only = ext.record_fields(table, 3)
        assert table_only["records"] == 40 and table_only["fields"][1]["frameIndexCandidate"] is True
        assert ext.periodicity(table)["bestPeriod"] == 18
        chr_json = json.loads((rog / "docs/evidence/obs-trailers/chr.json").read_text())
        assert chr_json["recordBytes"] == [472] and len(chr_json["records"]) == 2
        assert summary["claims"]["actionTableDecoded"] is False
        print("OBS EXTENDED DECODE SYNTHETIC PASS", json.dumps(summary["exportedFrames"]))


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print("OBS EXTENDED DECODE SYNTHETIC FAILED", error)
        sys.exit(1)
