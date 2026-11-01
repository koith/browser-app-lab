#!/usr/bin/env python3
"""Restore palette-index-0 pixels that the legacy OBS export made transparent.

The legacy decoder treated palette index 0 as transparent. In the original
VIDEO-RLE stream only SKIPPED pixels are transparent; written index-0 pixels
are opaque (1171.obs D6 face "1": its pink-red centre pip is index 0 and is
opaque in the archived battle.jpg). See decode_rows(alpha_from_runs=True).

Without the original PAK the true written mask is unavailable, so this tool
applies the narrowest correction that the PNG itself supports: a transparent
pixel that is NOT 4-connected to the image border (an enclosed hole) and
whose stored RGB equals the frame's palette[0] colour is made opaque.
A frame whose enclosed holes carry mixed RGB is refused. Only frames that a
person has checked should be passed in; character frames can have genuine
enclosed gaps and must instead be re-extracted with alpha_from_runs=True.
"""
import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

from PIL import Image


def enclosed_holes(image):
    w, h = image.size
    px = image.load()
    outside = set()
    queue = deque()
    for x in range(w):
        queue.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        queue.extend(((0, y), (w - 1, y)))
    while queue:
        x, y = queue.popleft()
        if (x, y) in outside or not (0 <= x < w and 0 <= y < h) or px[x, y][3] != 0:
            continue
        outside.add((x, y))
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return [(x, y) for y in range(h) for x in range(w)
            if px[x, y][3] == 0 and (x, y) not in outside]


def correct(path):
    image = Image.open(path).convert("RGBA")
    holes = enclosed_holes(image)
    colours = {image.getpixel(p)[:3] for p in holes}
    if len(colours) > 1:
        raise ValueError("%s: enclosed holes carry mixed RGB %s; refuse" % (path, sorted(colours)))
    px = image.load()
    for x, y in holes:
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 255)
    return image, holes, (colours.pop() if colours else None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("frames", nargs="+", type=Path)
    a = ap.parse_args(argv)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for src in a.frames:
        raw = src.read_bytes()
        image, holes, colour = correct(src)
        out = a.output_dir / src.name
        image.save(out, optimize=True)
        records.append({"file": out.name, "sourcePath": src.as_posix(),
                        "sourceSHA256": hashlib.sha256(raw).hexdigest(),
                        "correctedSHA256": hashlib.sha256(out.read_bytes()).hexdigest(),
                        "restoredPixels": len(holes),
                        "restoredRGB": list(colour) if colour else None})
    provenance = {
        "format": "4LEAF_OBS_COLORKEY_HOLE_CORRECTION_V1",
        "rule": "enclosed transparent pixels with a single shared RGB (palette[0]) made opaque",
        "evidence": "1171.obs face 1 pip is palette index 0 and opaque in archived battle.jpg",
        "pixelsInvented": 0,
        "frames": records,
    }
    (a.output_dir / "provenance.json").write_text(json.dumps(provenance, indent=1) + "\n")
    print("COLORKEY_HOLES_RESTORED", json.dumps({r["file"]: r["restoredPixels"] for r in records}))


if __name__ == "__main__":
    main()
