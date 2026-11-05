#!/usr/bin/env python3
"""Upright-vs-inverted pixel check of LIVE rendered TIS tiles (round 13).

Input: a directory of Chromium crops written by tests/dmp-26-map-render-audit.cjs
(one <art>.png per distinct art, camera scale 1, pawns/overlays hidden).
For each crop, compare its opaque-pixel RGB against the stored Tiles/<art>.png
(a) flipped back (the expected upright art; storage is bottom-up) and
(b) as stored. Report mean absolute error over the art's opaque pixels.
PASS when the upright error is at most 0.8x the inverted error (a WEB
rule). Terrain shows through alpha edges, so only alpha>200 pixels count.
Usage: tis-orientation-compare.py <crops-dir> <rog-dir> [out.json]
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RATIO = 0.8  # upright must beat inverted by >=20% (INFERRED WEB rule; overlays/terrain add noise)


def main():
    crops, rog = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for crop in sorted(crops.glob("*.png")):
        art = crop.stem
        src = Image.open(rog / "original/Tiles" / (art + ".png")).convert("RGBA")
        shot = np.asarray(Image.open(crop).convert("RGB").resize(src.size), dtype=float)
        stored = np.asarray(src, dtype=float)
        upright = stored[::-1]
        res = {}
        for name, ref in (("upright", upright), ("inverted", stored)):
            mask = ref[:, :, 3] > 200
            res[name] = round(float(np.abs(shot[mask] - ref[:, :, :3][mask]).mean()), 2)
        res.update(art=art, pass_=res["upright"] <= RATIO * res["inverted"])
        rows.append(res)
    out = {"method": "MAE over alpha>200 pixels, Chromium crop vs Tiles PNG (flipped back / as stored)",
           "rule": "upright MAE <= 0.8 x inverted MAE", "arts": len(rows),
           "pass": sum(r["pass_"] for r in rows), "rows": rows}
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(text + "\n", encoding="utf-8")
    print(text if len(rows) < 3 else json.dumps({k: out[k] for k in ("arts", "pass")}))
    for r in rows:
        if not r["pass_"]:
            print("FAIL", r)
    return 0 if rows and all(r["pass_"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
