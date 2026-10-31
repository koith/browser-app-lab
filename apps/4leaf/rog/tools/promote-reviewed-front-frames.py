#!/usr/bin/env python3
"""Stage visually reviewed source OBS front-cycle frames on an ISOLATED branch.

Original PAK pixels come only from SHA-verified CI provenance. The 18 bodies'
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
    "0040", "0043", "0044", "0046", "0048",
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



def update_release_assets(sw_file, version_file, html_file):
    # New PNGs are independent of the original sampled bulk inventory.
    filenames = [str(1000 + int(cid)) + "-" + str(frame).zfill(2)
                 for cid in REVIEWED_IDS for frame in NEW_FRAMES]
    worker = sw_file.read_text(encoding="utf-8")
    new_list = "const NATIVE_OBS_FRONT_FILES='" + " ".join(filenames) + "'.split(' ');"
    anchor = "const NATIVE_TIS_FILES="
    if new_list in worker or "const NATIVE_OBS_FRONT_FILES=" in worker:
        raise ValueError("Refusing duplicate native front file inventory")
    if worker.count(anchor) != 1:
        raise ValueError("PWA native source table no longer uniquely identifiable")
    worker = worker.replace(anchor, new_list + "\n" + anchor)
    original = ".concat(ORIGINAL_SOURCE_SPR_FILES.map(id=>'./original/SourceSPR/'+id+'.png'))"
    if worker.count(original) != 1:
        raise ValueError("PWA asset map no longer uniquely identifiable")
    worker = worker.replace(original,
      ".concat(NATIVE_OBS_FRONT_FILES.map(id=>'./original/OBS/front-reviewed/'+id+'.png'))" +
      original)
    pattern = r"const REVISION='4leaf-revival-pwa-v([0-9]+)'"
    match = re.search(pattern, worker)
    if not match:
        raise ValueError("PWA revision not found")
    next_revision = "4leaf-revival-pwa-v" + str(int(match.group(1)) + 1)
    worker = re.sub(pattern, "const REVISION='" + next_revision + "'", worker, count=1)

    v = json.loads(version_file.read_text(encoding="utf-8"))
    if v["version"] != "0.86.0-beta.29" or v["pwaCache"] != "4leaf-revival-pwa-v116":
        raise ValueError("Unexpected release baseline; rebase and audit first")
    v["version"] = "0.86.0-beta.30"
    v["releaseDate"] = "2026-11-01"
    v["pwaCache"] = next_revision
    html = html_file.read_text(encoding="utf-8")
    marker = 'name="leaf-revival-version" content="0.86.0-beta.29"'
    if html.count(marker) != 1:
        raise ValueError("Could not match source HTML release marker")
    html = html.replace(marker, 'name="leaf-revival-version" content="' + v["version"] + '"')
    # Commit all release metadata only after all strict validators succeed.
    sw_file.write_text(worker, encoding="utf-8")
    version_file.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_file.write_text(html, encoding="utf-8")
    return {"newOfflineNativeFrames":len(filenames), "pwaCache":next_revision,
            "version":v["version"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_directory", type=Path)
    parser.add_argument("live_manifest", type=Path)
    parser.add_argument("live_png_dir", type=Path)
    parser.add_argument("--sw", type=Path, required=True)
    parser.add_argument("--version", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    args = parser.parse_args()
    result = import_reviewed(args.audit_directory, args.live_manifest, args.live_png_dir)
    result["release"] = update_release_assets(args.sw, args.version, args.html)
    print("REVIEWED_SOURCE_FRAME_PROMOTION", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
