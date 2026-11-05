#!/usr/bin/env python3
"""Synthetic offline validation of R15 OBS source-effect extraction.
Never substitute generated art for historic OBS evidence."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "source_effect_extractor", HERE / "tools/extract-duel-source-effects.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class EffectExtraction(unittest.TestCase):
    def test_reference_events_and_slot_histogram(self):
        fixture = {"cards": {
            "0040": {"animations": [
                {"index": 12, "keys": [[0, 0]], "events": [[12, 9, 1096, -17, 11],
                                                         [0, 31, 0, 0, 0]]},
                {"index": 13, "keys": [[0, 1]], "events": [[3, 10, 1099, 28, -65]]}]},
            "0042": {"animations": [
                {"index": 13, "keys": [[0, 1]], "events": [[3, 10, 1099, 31, -61]]}]}}}
        refs, slots = mod.source_references(fixture)
        self.assertEqual(slots[13], 2)
        self.assertEqual(set(refs), {"1096", "1099"})
        self.assertEqual(refs["1099"]["slots"][13], 2)
        self.assertEqual(sorted(refs["1099"]["cards"]), ["0040", "0042"])
        self.assertEqual(mod.choose(refs), ["1096", "1099"])

    def test_reject_ambiguous_event_layout(self):
        with self.assertRaisesRegex(ValueError, "Unexpected source event"):
            mod.source_references({"cards": {"0040": {"animations": [
                {"index": 13, "events": [[3, 10, 1099]]}]}}})

    def test_missing_and_duplicate_native_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Dice"
            folder.mkdir()
            for n in mod.EXPECTED_PACKS:
                (folder / n).write_bytes(n.encode())
            found = mod.find_packs(Path(tmp))
            self.assertEqual(sorted(found), sorted(mod.EXPECTED_PACKS))
            duplicate = Path(tmp) / "copy/Dice"
            duplicate.mkdir(parents=True)
            (duplicate / "OBS.pak").write_bytes(b"other")
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                mod.find_packs(Path(tmp))
            (duplicate / "OBS.pak").unlink()
            (folder / "obs3.pak").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "missing"):
                mod.find_packs(Path(tmp))

    def test_strict_frames_and_source_hash(self):
        from PIL import Image
        class FakeCodec:
            def unpack_frames(self, blob):
                return [(b"native-source-body", 2, 2, -1, -2)], b"\x01"*768
            def decode_rows(self, body, w, h, palette, minimum_opaque_pixels=0,
                            alpha_from_runs=False):
                self_args = (w, h, len(palette), minimum_opaque_pixels, alpha_from_runs)
                if self_args != (2, 2, 768, 0, True):
                    raise ValueError("decoder not configured for verified alpha runs")
                return Image.new("RGBA", (w, h), (222, 0, 18, 255)), {"opaquePixels": 4}
        recs = mod.frames_as_png(FakeCodec(), b"whole-member")
        self.assertEqual(len(recs), 1)
        png, row = recs[0]
        self.assertEqual(row["bodySHA256"], mod.sha(b"native-source-body"))
        self.assertEqual(row["index"], 0)
        self.assertEqual(row["originX"], -1)
        self.assertEqual(row["originY"], -2)
        self.assertEqual(row["sha256"], mod.sha(png))
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")

if __name__ == "__main__":
    unittest.main()
