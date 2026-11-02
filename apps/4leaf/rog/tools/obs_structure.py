#!/usr/bin/env python3
"""Structural analysis of decoded original OBS frame sequences (no invention).

Input: the frames of ONE member as (RGBA uint8 array upright, originX, originY).
Every frame is placed on a shared canvas by its native origin, the opaque
silhouette is compared frame-to-frame (1 - IoU), and the sequence is tested
against the 37-frame direction-block layout found on the 2002 actors:

  rear  idle 0-2   walk 3-8    strike 9-10
  side  idle 11-13 walk 14-19  strike 20-21      (side faces left)
  front idle 22-24 walk 25-30  strike 31-32
  lunge 33-36

The layout test only says the PIXELS change the way that layout predicts;
it is evidence of structure, not a decoded EXE action table (INFERRED).
For non-37 members `segment()` proposes change-point blocks for review.
"""
import json
import sys
from pathlib import Path

import numpy as np

LAYOUT_37 = {
    "idle": [(0, 2), (11, 13), (22, 24)],
    "walk": [(3, 8), (14, 19), (25, 30)],
    "strike": [(9, 10), (20, 21), (31, 32)],
    "lunge": [(33, 36)],
}
DIRECTION_STARTS = (0, 11, 22)


def canvas(frames, pad=4):
    """Place frames by native origin on one canvas -> list of bool masks."""
    left = min(ox for _, ox, _ in frames)
    top = min(oy for _, _, oy in frames)
    right = max(ox + img.shape[1] for img, ox, _ in frames)
    bottom = max(oy + img.shape[0] for img, _, oy in frames)
    w, h = right - left + 2 * pad, bottom - top + 2 * pad
    masks = []
    for img, ox, oy in frames:
        m = np.zeros((h, w), bool)
        y, x = oy - top + pad, ox - left + pad
        m[y:y + img.shape[0], x:x + img.shape[1]] = img[..., 3] > 0
        masks.append(m)
    return masks


def distance(a, b):
    union = (a | b).sum()
    return 0.0 if union == 0 else float(1.0 - (a & b).sum() / union)


def mirror_asymmetry(img, origin_x):
    """1 - IoU of a frame's silhouette with its mirror about the origin x."""
    m = img[..., 3] > 0
    h, w = m.shape
    half = max(abs(origin_x), abs(origin_x + w)) + 1
    c = np.zeros((h, 2 * half), bool)
    x0 = half + origin_x
    c[:, x0:x0 + w] = m
    return distance(c, c[:, ::-1])


def consecutive(masks):
    return [distance(masks[i], masks[i + 1]) for i in range(len(masks) - 1)]


def test_layout_37(frames):
    """Return evidence dict; `matches` True only if every check passes."""
    if len(frames) != 37:
        return {"matches": False, "reason": "frame count %d != 37" % len(frames)}
    masks = canvas(frames)
    d = consecutive(masks)
    idle_intra = [d[i] for a, b in LAYOUT_37["idle"] for i in range(a, b)]
    walk_intra = [d[i] for a, b in LAYOUT_37["walk"] for i in range(a, b)]
    boundaries = [d[b] for _, b in LAYOUT_37["idle"]]
    direction_jumps = [distance(masks[s - 1], masks[s]) for s in DIRECTION_STARTS[1:]]
    def mean(xs):
        return float(np.mean(xs)) if xs else 0.0
    cross = []
    for i, (a, _) in enumerate(LAYOUT_37["idle"]):
        own = mean([distance(masks[a], masks[k]) for k in range(LAYOUT_37["walk"][i][0], LAYOUT_37["walk"][i][1] + 1)])
        other = mean([distance(masks[a], masks[o]) for j, (o, _) in enumerate(LAYOUT_37["idle"]) if j != i])
        cross.append((own, other))
    asym = [mean([mirror_asymmetry(*frames[i][:2]) for i in range(a, b + 1)]) for a, b in LAYOUT_37["idle"]]
    checks = {
        "idleSmallerThanWalk": max(idle_intra) < mean(walk_intra) + 0.05 and mean(idle_intra) < mean(walk_intra),
        "idleToWalkBoundaryJump": all(b > mean(idle_intra) for b in boundaries),
        "directionChangeJump": all(j > mean(idle_intra) for j in direction_jumps),
        "hasFacingShape": max(asym) > 0.15,
    }
    idle_closer_to_own_walk = sum(own < other for own, other in cross)
    return {
        "matches": bool(all(checks.values())),
        "checks": {k: bool(v) for k, v in checks.items()},
        "idleIntraMax": round(max(idle_intra), 3),
        "idleIntraMean": round(mean(idle_intra), 3),
        "walkIntraMean": round(mean(walk_intra), 3),
        "boundaries": [round(b, 3) for b in boundaries],
        "directionJumps": [round(j, 3) for j in direction_jumps],
        "idleMirrorAsymmetry": [round(a, 3) for a in asym],
        "idleCloserToOwnWalkCount": int(idle_closer_to_own_walk),
    }


def segment(frames, factor=1.6):
    """Change-point proposal: split where the step change is `factor` x the
    sequence median. Returns [(start, end)] blocks for REVIEW only."""
    masks = canvas(frames)
    d = consecutive(masks)
    if not d:
        return [(0, 0)]
    cut = float(np.median(d)) * factor
    blocks, start = [], 0
    for i, v in enumerate(d):
        if v > cut:
            blocks.append((start, i))
            start = i + 1
    blocks.append((start, len(frames) - 1))
    return blocks


def load_checked_in_member(root, member_id):
    """Upright frames of a checked-in action-full member (PNG stored bottom-up)."""
    from PIL import Image
    text = (root / "original/OBS/action-full/manifest.js").read_text(encoding="utf-8")
    start = text.index("{")
    data = None
    while data is None:
        try:
            data = json.loads(text[start:text.rindex("}") + 1])
        except json.JSONDecodeError:
            start = text.index("{", start + 1)
    out = []
    for f in data[member_id]["frames"]:
        img = np.flipud(np.array(Image.open(root / f["url"][2:]).convert("RGBA")))
        out.append((img, f["originX"], f["originY"]))
    return out, sorted(data)


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    _, ids = load_checked_in_member(root, "0040")
    report = {}
    for member in ids:
        frames, _ = load_checked_in_member(root, member)
        report[member] = test_layout_37(frames)
    print(json.dumps(report, indent=1))
