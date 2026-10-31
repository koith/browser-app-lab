#!/usr/bin/env python3
"""All-frame audit regression: synthetic bytes only; NOT original recovery proof."""
import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("leaf_full_audit",
    ROOT / "tools" / "dump-original-paks.py")
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


def pack(members):
    body = b""
    directory = b""
    for name, blob in members:
        body += blob
        filename = name.encode("ascii").ljust(24, b"\\x00")
        directory += bytes(x ^ 255 for x in filename)
        directory += struct.pack("<I", (len(body) - 1) ^ 0xffffffff)
    return struct.pack("<I", len(members) ^ 0xffffffff) + directory + body


def obs(frame_count=2, broken=False):
    header = bytearray(132)
    struct.pack_into("<H", header, 70, frame_count)
    frames = bytearray()
    for frame in range(frame_count):
        payload = struct.pack("<HHBB", 1, 0, 11, 1) + bytes([frame + 1]) * 45
        if broken and frame == frame_count - 1:
            payload = payload[:9]
        frames += struct.pack("<IHHhh", len(payload), 50, 1, 0, 0) + payload
    return bytes(header + frames + bytes(range(256)) * 3)


class FullFrameSourceAudit(unittest.TestCase):
    def test_all_native_frames_attempted_not_twelve_sampled(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "OBS.pak").write_bytes(pack([("1040.obs", obs(15))]))
            summary = auditor.collect(root, root / "result", ["0040"])
            self.assertEqual(summary["totalNativeDeclaredFrames"], 15)
            self.assertEqual(summary["totalAttemptedFrames"], 15)
            self.assertEqual(summary["strictDecodedFrames"], 15)
            self.assertFalse(summary["exportLimitReached"])
            report = json.loads((root / "result/full-frame-report.json").read_text())
            self.assertEqual(len(report["packs"][0]["members"][0]["frames"]), 15)
            self.assertEqual(len(list((root / "result/frames/OBS.pak").glob("*.png"))), 15)
            self.assertEqual(report["packs"][0]["members"][0]["identityStatus"], "UNVERIFIED")

    def test_incomplete_member_does_not_invent_missing_palette(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "OBS2.pak").write_bytes(pack([("1042.obs", obs(3, broken=True))]))
            summary = auditor.collect(root, root / "result", ["0042"])
            self.assertEqual(summary["strictDecodedFrames"], 0)
            self.assertEqual(summary["unparsedDeclaredFrames"], 3)
            self.assertIn("palette", json.dumps(summary).lower() if False else
                          (json.loads((root / "result/full-frame-report.json").read_text())
                           ["packs"][0]["members"][0]["parseError"]).lower())

    def test_rle_failure_recorded_as_failure_not_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            damaged = bytearray(obs(1))
            damaged[132 + 12 + 4] = 40  # Run length exceeds 50-wide source canvas
            (root / "OBS3.pak").write_bytes(pack([("1043.obs", bytes(damaged))]))
            summary = auditor.collect(root, root / "result")
            self.assertEqual(summary["strictDecodedFrames"], 0)
            self.assertEqual(summary["failedFrameDecodes"], 1)


if __name__ == "__main__":
    unittest.main()
