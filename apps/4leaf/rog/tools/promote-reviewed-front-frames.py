#!/usr/bin/env python3
"""Stage visually reviewed source OBS front-cycle frames on an ISOLATED branch.

Original PAK pixels come only from SHA-verified CI provenance. The 19 bodies'
25/30 front frames were separately reviewed; intermediates 26..29 were visually
checked in 2026-11-01 contact sheets. These are authentic 2002 pixels, but
the actual EXE action table / native FPS remain UNKNOWN.
Never label a reconstructed WEB walk as historical native animation mapping.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

REVIEWED_IDS = (
    "0040", "0042", "0043", "0044", "0046", "0048",
    "0049", "0051", "0052", "0053", "0054", "0055",
    "0056", "0058", "0059", "0060", "0061", "0062", "0064"
)
NEW_FRAMES = (26, 27, 28, 29)
REFERENCE_FRAMES = (25, 30)


def import_reviewed(audit_directory, live_manifest, live_png_dir):
    report = json.loads((audit_directory / "full-frame-report.json").read_text(encoding="utf-8"))
    if report["exportLimitReached"]:
        raise ValueError("Cannot promote from capped/incomplete original source")
    source_packs = [p for p in report["packs"] if p["name"] == "OBS.pak" and
                    not p.get("containerError")]
    if len(source_packs) != 1:
        raise ValueError("Unique verified OBS.pak not found")
    source = {m["name"]: m for m in source_packs[0]["members"]}
    old_text = live_manifest.read_text(encoding="utf-8")
    start = old_text.index("{", old_text.index("window.ORIGINAL_LEAF_OBS_FRAMES=Object.assign"))
    end = old_text.rindex("}") + 1
    native = json.loads(old_text[start:end])
    staged = []
    for cid in REVIEWED_IDS:
        name = str(1000 + int(cid)) + ".obs"
        member = source.get(name)
        existing = native.get(cid)
        if not member or not existing:
            raise ValueError("Missing reviewed source identity: " + cid)
        if existing["originalMember"] != name:
            raise ValueError("Historical OBS member mismatch for " + cid)
        if existing["sourceSHA256"] != member["sourceSHA256"]:
            raise ValueError("Original OBS source SHA mismatch: " + cid)
        indexed = {f["index"]: f for f in member.get("frames", [])}
        prior = {f["index"]: f for f in existing["frames"]}
        for i in REFERENCE_FRAMES:
            expected = prior.get(i)
            observed = indexed.get(i)
            if not expected or not observed or observed["status"] != "STRICT_DECODED":
                raise ValueError("Reviewed 25/30 frame not present: " + cid)
            if expected["sha256"] != observed.get("pngSHA256"):
                raise ValueError("Pixel SHA mismatch with published source: " + cid + "/" + str(i))
        for i in NEW_FRAMES:
            if i in prior:
                raise ValueError("Duplicate source frame index: " + cid + "/" + str(i))
            observed = indexed.get(i)
            if not observed or observed["status"] != "STRICT_DECODED" or not observed.get("artifactPath"):
                raise ValueError("Missing strictly decoded source frame: " + cid + "/" + str(i))
            payload = (audit_directory / observed["artifactPath"]).read_bytes()
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Invalid PNG magic for " + cid)
            if hashlib.sha256(payload).hexdigest() != observed["pngSHA256"]:
                raise ValueError("Unverified PNG content for " + cid)
            dest = live_png_dir / (name[:-4] + "-" + str(i).zfill(2) + ".png")
            if dest.exists() and dest.read_bytes() != payload:
                raise ValueError("Refusing to overwrite distinct native pixel file " + str(dest))
            staged.append((dest, payload))
            w,h,ox,oy = observed["geometry"]
            prior[i] = {
                "index": i, "url": "./original/OBS/front-reviewed/" + dest.name,
                "width": w, "height": h, "originX": ox, "originY": oy,
                "sha256": observed["pngSHA256"]
            }
        existing["frames"] = sorted(prior.values(), key=lambda f: f["index"])
        existing["frontCycleEvidence"] = (
            "AUTHENTIC_SOURCE_PIXELS_25_TO_30; VISUAL_REVIEW_20261101; "
            "WEB_WALK_MAPPING_INFERRED; HISTORICAL_EXE_TIMING_UNKNOWN"
        )
    # All source identities and cross-checks must pass before modifying ANY file.
    live_png_dir.mkdir(parents=True, exist_ok=True)
    for dest, payload in staged:
        dest.write_bytes(payload)
    updated = old_text[:start] + json.dumps(native, ensure_ascii=False, indent=2,
                                            sort_keys=True) + old_text[end:]
    live_manifest.write_text(updated, encoding="utf-8")
    return {"reviewedModels":len(REVIEWED_IDS), "newSourceFrames":len(staged),
            "sourcePackSHA256":source_packs[0]["sha256"], "nativeActionMapping":"UNVERIFIED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_directory", type=Path)
    parser.add_argument("live_manifest", type=Path)
    parser.add_argument("live_png_dir", type=Path)
    args = parser.parse_args()
    print("REVIEWED_SOURCE_FRAME_PROMOTION",
          json.dumps(import_reviewed(args.audit_directory, args.live_manifest,
                                     args.live_png_dir), sort_keys=True))


if __name__ == "__main__":
    main()
