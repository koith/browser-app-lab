#!/usr/bin/env python3
"""Measure ChatRoom UI anchors by template matching ORIGINAL sprite pieces.

The same matcher runs on the 2004 screenshots (apps/4leaf/assets/chat.jpg,
chat_ref.jpg; room4) and on 794x528 captures of the web app, so every anchor
difference is measured with one independent method, not by eye. Pieces come
from ChatRoom/userlist.png and ChatRoom/scrollbar.png (green / alpha keys
excluded). Usage: chatroom-anchor-audit.py capture.png [...] [--json out]
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ATLAS = {
    "userlist": ROOT / "original/ChatRoom/userlist.png",
    "scrollbar": ROOT / "original/ChatRoom/scrollbar.png",
}
# name: (atlas, x0, y0, x1, y1, search region x0,y0,x1,y1)
PIECES = {
    "panelOuterTL": ("userlist", 0, 0, 6, 6, (600, 0, 660, 40)),
    "panelOuterBR": ("userlist", 14, 14, 20, 20, (750, 110, 794, 150)),
    "panelHeader": ("userlist", 21, 0, 78, 16, (605, 0, 700, 40)),
    "panelMenuEq": ("userlist", 32, 21, 47, 35, (740, 0, 794, 40)),
    "panelInnerTL": ("userlist", 0, 21, 5, 26, (610, 20, 650, 50)),
    "panelInnerBR": ("userlist", 12, 32, 17, 38, (750, 110, 794, 145)),
    "listArrows": ("scrollbar", 14, 1, 25, 18, (740, 95, 790, 135)),
    "logArrows": ("scrollbar", 1, 1, 12, 18, (390, 50, 430, 120)),
    "logTrack": ("scrollbar", 17, 21, 22, 30, (395, 0, 430, 40)),
}


def load(path):
    return np.array(Image.open(path).convert("RGBA")).astype(int)


def piece(atlas, x0, y0, x1, y1):
    p = atlas[y0:y1, x0:x1]
    key = (p[..., 0] == 0) & (p[..., 1] == 255) & (p[..., 2] == 0)
    return p[..., :3], (p[..., 3] > 0) & ~key


def match(img, pc, region):
    rgb, m = pc
    h, w = m.shape
    x0, y0, x1, y1 = region
    best = None
    for y in range(y0, min(y1, img.shape[0]) - h + 1):
        for x in range(x0, min(x1, img.shape[1]) - w + 1):
            d = float(np.abs(img[y:y + h, x:x + w] - rgb)[m].mean())
            if best is None or d < best[0]:
                best = (d, x, y)
    return {"x": best[1], "y": best[2], "meanAbsError": round(best[0], 2)}


def audit(path):
    img = np.array(Image.open(path).convert("RGB")).astype(int)
    assert img.shape[:2] == (528, 794), (path, img.shape)
    atlases = {k: load(v) for k, v in ATLAS.items()}
    return {name: match(img, piece(atlases[a], *box), region)
            for name, (a, *rest) in PIECES.items()
            for box, region in [(tuple(rest[:4]), rest[4])]}


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    out = None
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        args.remove(out)
    result = {str(p): audit(p) for p in args}
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
