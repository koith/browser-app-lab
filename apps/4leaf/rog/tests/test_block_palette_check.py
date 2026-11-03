#!/usr/bin/env python3
"""ORIGINAL-data check behind the round-9 correction of the dice palette claim.

For the two multi-block members whose extra-block bytes are stored in full
(OBS2 1228, 1238), decode block 2 from those bytes with ITS OWN palette and
compare with original/OBS/embedded PNGs (painted with block 0's palette):
alpha and colours are identical, so a per-block palette defect is not shown
by any stored bytes. The D6/D4 blocks remain UNVERIFIED until CI records their
palettes (tools/decode-obs-blocks.py).
Run: python3 apps/4leaf/rog/tests/test_block_palette_check.py
"""
import importlib.util
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

ROG = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codec", ROG / "tools/decode-original-obs-bulk.py")
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)


def main():
    trailers = json.loads((ROG / "docs/evidence/obs-trailers/trailers.json").read_text(encoding="utf-8"))
    t = (ROG / "original/OBS/embedded/manifest.js").read_text(encoding="utf-8")
    emb = json.loads(t[t.index("={") + 1:t.rindex(";")])
    checked = 0
    for key, ek in (("obs2/1228", "obs2-1228-c0"), ("obs2/1238", "obs2-1238-c0")):
        tr = bytes.fromhex(trailers[key]["hex"])
        count = struct.unpack_from("<H", tr, 66)[0]
        p, frames = 128, []
        for _ in range(count):
            n, w, h, ox, oy = struct.unpack_from("<IHHhh", tr, p)
            frames.append((tr[p + 12:p + 12 + n], w, h))
            p += 12 + n
        palette = tr[p:p + 768]
        assert len(palette) == 768 and count == len(emb[ek]["frames"])
        for i, (body, w, h) in enumerate(frames):
            img, _ = codec.decode_rows(body, w, h, palette, minimum_opaque_pixels=0, alpha_from_runs=True)
            new = np.array(img.convert("RGBA"))
            old = np.array(Image.open(ROG / emb[ek]["frames"][i]["url"][2:]).convert("RGBA"))
            # Unwritten (transparent) pixels carry palette index 0's RGB and are
            # invisible; compare alpha everywhere and colour where opaque.
            assert (new[..., 3] == old[..., 3]).all(), (key, i, "alpha")
            opaque = new[..., 3] > 0
            assert (new[..., :3][opaque] == old[..., :3][opaque]).all(), (key, i, "colour")
            checked += 1
    print("BLOCK PALETTE CHECK PASS", json.dumps({"framesCompared": checked, "identical": True,
                                                 "diceBlocks": "UNVERIFIED (bytes not stored)"}))


if __name__ == "__main__":
    main()
