#!/usr/bin/env python3
"""Synthetic regression for tools/extract-targeted-original-frames.py.
No original 4LEAF bytes: builds XOR-indexed PAKs with the 2002 grammar."""
import importlib.util
import json
import pathlib
import struct
import sys
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("leaf_targeted", ROOT / "tools/extract-targeted-original-frames.py")
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool
spec.loader.exec_module(tool)


def rle(width, height, rows):
    """rows: list of (y, x, bytes). Returns a 640-stride body."""
    body = bytearray(struct.pack("<HH", len(rows), rows[0][0] * 640 + rows[0][1]))
    cursor = rows[0][0] * 640 + rows[0][1]
    for i, (y, x, data) in enumerate(rows):
        pos = y * 640 + x
        if i:
            body += struct.pack("<H", pos - cursor)
            cursor = pos
        body += bytes((len(data) // 4, len(data) % 4)) + data
        cursor += len(data)
    return bytes(body)


def square(size, value, hole=False):
    rows = []
    for y in range(size):
        data = bytearray([value] * size)
        if hole and y == size // 2:
            data[size // 2] = 0          # written palette index 0 (like the "1" pip)
        rows.append((y, 0, bytes(data)))
    return size, size, rle(size, size, rows)


def member(frames, bad_at=None):
    out = bytearray(132)
    struct.pack_into("<H", out, 70, len(frames))
    for i, (w, h, body) in enumerate(frames):
        out += struct.pack("<IHHhh", len(body), 0 if i == bad_at else w, h, -w // 2, -h) + body
    out += bytes(c for x in range(256) for c in (x, 255 - x, 7))
    return bytes(out)


def pak(entries):
    index = bytearray(struct.pack("<I", len(entries) ^ 0xFFFFFFFF))
    blob = bytearray()
    for name, data in entries:
        blob += data
        index += bytes(b ^ 0xFF for b in name.encode().ljust(24, b"\0"))
        index += struct.pack("<I", (len(blob) - 1) ^ 0xFFFFFFFF)
    return bytes(index + blob)


class Targeted(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        res = t / "res" / "Dice"
        res.mkdir(parents=True)
        d6 = [square(30, 9, hole=(i == 0)) for i in range(28)]
        numerals = [square(40, 20 + i) for i in range(25)]
        chessman = [square(24, 40 + i) for i in range(37)]
        (res / "OBS.pak").write_bytes(pak([
            ("1171.obs", member(d6)), ("1167.obs", member(numerals)),
            ("1040.obs", member(chessman)), ("1046.obs", member(chessman[:5], bad_at=2)),
            ("0074.obs", b"\x01" * 166)]))
        (res / "OBS2.pak").write_bytes(pak([("1199.obs", member([square(40, 3) for _ in range(6)]))]))
        self.repo = t / "repo"
        bulk = self.repo / "apps/4leaf/rog/original/OBS/bulk"
        bulk.mkdir(parents=True)
        # Legacy export of 1171 frame 0: same pixels, but index-0 pixel transparent.
        legacy = tool.codec.decode_rows(d6[0][2], 30, 30, bytes(c for x in range(256) for c in (x, 255 - x, 7)),
                                        minimum_opaque_pixels=0)[0]
        legacy.save(bulk / "1171-00.png")
        self.art = t / "art"
        self.report = tool.run(t / "res", self.repo, self.art)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_ui_frame_written_with_manifest(self):
        ui = self.repo / "apps/4leaf/rog/original/OBS/ui"
        self.assertEqual(len(list(ui.glob("1171-*.png"))), 28)
        self.assertEqual(len(list(ui.glob("1167-*.png"))), 25)
        js = (ui / "manifest.js").read_text()
        data = json.loads(js[js.index("UI_FRAMES=") + 10:js.rindex(";")])
        self.assertEqual(len(data["1171"]["frames"]), 28)
        self.assertEqual(data["1167"]["frames"][9]["url"], "./original/OBS/ui/1167-009.png")
        self.assertTrue(self.report["ui"]["1171"]["allWritten"])

    def test_written_index0_is_opaque_and_regression_explains_the_only_difference(self):
        img = Image.open(self.repo / "apps/4leaf/rog/original/OBS/ui/1171-000.png").convert("RGBA")
        self.assertEqual(img.getpixel((15, 30 - 1 - 15))[3], 255)
        check = self.report["ui"]["1171"]["regression"][0]["vsLegacyBulk"]
        self.assertEqual(check["differentPixels"], 1)
        self.assertEqual(check["onlyIndex0MadeOpaque"], 1)

    def test_all_members_inventoried_including_broken_and_secondary_pak(self):
        self.assertEqual(self.report["members"], 6)
        names = {u["member"] for u in self.report["unparsedMembers"]}
        self.assertEqual(names, {"1046.obs", "0074.obs"})
        self.assertTrue((self.art / "members/OBS2/1199.png").exists())
        self.assertTrue((self.art / "members/OBS/1046.json").exists())

    def test_37_frame_member_gets_action_gif(self):
        gif = Image.open(self.art / "actions/OBS-1040.gif")
        self.assertEqual(gif.n_frames, 37)
        self.assertEqual(self.report["actionGifs"], 1)

    def test_d4_candidates_exclude_ui_members(self):
        cands = json.loads((self.art / "d4-candidates.json").read_text())
        members = {c["member"] for c in cands}
        self.assertNotIn("1171.obs", members)
        self.assertIn("1199.obs", members)


if __name__ == "__main__":
    unittest.main()
