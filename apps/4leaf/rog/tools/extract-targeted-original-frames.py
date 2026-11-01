#!/usr/bin/env python3
"""Targeted, verifiable extraction of the original 4LEAF Dice UI members and
chessman action evidence from the SHA1-verified 2002 client.

Inputs : unshield resource directory (contains Dice/OBS.pak, OBS2.pak, OBS3.pak)
Outputs:
  REPO_OUT/original/OBS/ui/<member>-NNN.png   EVERY frame of the UI members that
                                             the game uses (1171 D6, 1167 numerals, 1223 D4),
                                             decoded with alpha_from_runs=True
  REPO_OUT/original/OBS/ui/manifest.js       window.ORIGINAL_LEAF_UI_FRAMES
  REPO_OUT/original/OBS/ui/report.json       counts, SHA-256, regression vs old PNGs
  ARTIFACT/members/<pak>/<member>.json        per-frame geometry for EVERY member
  ARTIFACT/members/<pak>/<member>.png         contact sheet (upright) for review
  ARTIFACT/actions/<member>.gif               37-frame chessmen as an index-ordered
                                             animation with frame numbers, for
                                             action-table review
  ARTIFACT/d4-candidates.json                 members whose frames look like small
                                             square/triangular dice sprites

Only the three verified UI members go to the repository (small, used by the game). Everything
else stays in the short-lived Actions artifact. No Windows code is executed.
Action / direction labels are NOT asserted here.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("leaf_obs_codec_t", HERE / "decode-original-obs-bulk.py")
codec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codec)

UI_MEMBERS = {"1171.obs": "d6", "1167.obs": "score-numerals", "1223.obs": "d4"}
PACKS = ("obs.pak", "obs2.pak", "obs3.pak")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def decode_member(blob):
    """Return (frames_info, images, palette, error). Every frame is attempted;
    a failing frame is recorded, never skipped silently."""
    try:
        frames, palette = codec.unpack_frames(blob)
    except ValueError as exc:
        return [], {}, None, str(exc)
    info, images = [], {}
    for index, (body, w, h, ox, oy) in enumerate(frames):
        rec = {"index": index, "width": w, "height": h, "originX": ox, "originY": oy,
               "bodyBytes": len(body), "bodySHA256": sha(body)}
        try:
            img, diag = codec.decode_rows(body, w, h, palette, minimum_opaque_pixels=0,
                                          alpha_from_runs=True)
            rec["opaquePixels"] = diag["opaquePixels"]
            rec["status"] = "DECODED"
            images[index] = img
        except (ValueError, OverflowError) as exc:
            rec["status"] = "FAILED"
            rec["error"] = str(exc)[:200]
        info.append(rec)
    return info, images, palette, None


def contact_sheet(images, path, cell=96, cols=10):
    if not images:
        return
    keys = sorted(images)
    rows = (len(keys) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 14)), (52, 56, 96))
    d = ImageDraw.Draw(sheet)
    for k, idx in enumerate(keys):
        im = images[idx].transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if im.width > cell - 4 or im.height > cell - 4:
            im.thumbnail((cell - 4, cell - 4))
        x, y = (k % cols) * cell, (k // cols) * (cell + 14)
        sheet.paste(im, (x + (cell - im.width) // 2, y + cell - 2 - im.height), im)
        d.text((x + 3, y + cell), str(idx), fill=(255, 220, 90))
    sheet.save(path, optimize=True)


def action_gif(images, info, path):
    """Index-ordered animation on a shared canvas aligned by native origin, so
    a reviewer sees real limb motion and sequence boundaries."""
    if not images:
        return
    geo = {r["index"]: r for r in info}
    left = min(geo[i]["originX"] for i in images)
    top = min(geo[i]["originY"] for i in images)
    right = max(geo[i]["originX"] + geo[i]["width"] for i in images)
    bottom = max(geo[i]["originY"] + geo[i]["height"] for i in images)
    W, H = right - left + 8, bottom - top + 22
    frames = []
    for i in sorted(images):
        canvas = Image.new("RGB", (W, H), (52, 56, 96))
        im = images[i].transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        canvas.paste(im, (geo[i]["originX"] - left + 4, geo[i]["originY"] - top + 4), im)
        ImageDraw.Draw(canvas).text((3, H - 15), "frame %d" % i, fill=(255, 220, 90))
        frames.append(canvas.resize((W * 2, H * 2), Image.NEAREST))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=160, loop=0)


def d4_score(info, images):
    """Heuristic only: small near-square frames with few colours (a die body).
    Used to rank candidates for human review, never to label a member."""
    small = [r for r in info if r.get("status") == "DECODED" and 20 <= r["width"] <= 90
             and 20 <= r["height"] <= 90 and 0.7 <= r["width"] / r["height"] <= 1.4]
    if not small:
        return 0.0
    return round(len(small) / max(1, len(info)), 3)


def regression(old_path, new_img):
    """Compare an already published PNG with the new run-alpha decode."""
    if not old_path.exists():
        return {"old": None}
    old = Image.open(old_path).convert("RGBA")
    new = new_img.convert("RGBA")
    if old.size != new.size:
        return {"old": old_path.as_posix(), "sizeMatch": False}
    a, b = old.load(), new.load()
    diff = alpha_only = 0
    for y in range(old.height):
        for x in range(old.width):
            if a[x, y] != b[x, y]:
                diff += 1
                if a[x, y][3] == 0 and b[x, y][3] == 255 and a[x, y][:3] == b[x, y][:3]:
                    alpha_only += 1
    return {"old": old_path.as_posix(), "sizeMatch": True, "differentPixels": diff,
            "onlyIndex0MadeOpaque": alpha_only, "identical": diff == 0}


def run(resource_dir, repo_root, artifact):
    paks = sorted(p for p in resource_dir.rglob("*") if p.is_file() and p.name.lower() in PACKS)
    if not paks:
        raise SystemExit("no OBS/OBS2/OBS3 pak under " + str(resource_dir))
    ui_dir = repo_root / "apps/4leaf/rog/original/OBS/ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (artifact / "members").mkdir(parents=True, exist_ok=True)
    (artifact / "actions").mkdir(parents=True, exist_ok=True)
    report = {"format": "4LEAF_TARGETED_ORIGINAL_V1", "alpha": "written-runs",
              "packs": [], "ui": {}, "members": 0, "declaredFrames": 0,
              "decodedFrames": 0, "failedFrames": 0, "unparsedMembers": [],
              "actionGifs": 0}
    manifest, d4 = {}, []
    for pak in paks:
        data = pak.read_bytes()
        report["packs"].append({"name": pak.name, "sha256": sha(data)})
        for name, blob in codec.source_members(data):
            if not name.lower().endswith(".obs"):
                continue
            report["members"] += 1
            info, images, palette, error = decode_member(blob)
            stem = Path(name).stem
            meta = {"pak": pak.name, "member": name, "sourceSHA256": sha(blob),
                    "declaredFrames": len(info) if not error else None,
                    "parseError": error, "frames": info}
            target = artifact / "members" / pak.stem
            target.mkdir(parents=True, exist_ok=True)
            (target / (stem + ".json")).write_text(json.dumps(meta, indent=1))
            if error:
                report["unparsedMembers"].append({"pak": pak.name, "member": name, "error": error})
                continue
            report["declaredFrames"] += len(info)
            report["decodedFrames"] += len(images)
            report["failedFrames"] += len(info) - len(images)
            contact_sheet(images, target / (stem + ".png"))
            if len(info) == 37:
                action_gif(images, info, artifact / "actions" / (pak.stem + "-" + stem + ".gif"))
                report["actionGifs"] += 1
            score = d4_score(info, images)
            is_ui = pak.name.lower() == "obs.pak" and name.lower() in UI_MEMBERS
            if score >= 0.5 and not is_ui:
                d4.append({"pak": pak.name, "member": name, "score": score, "frames": len(info)})
            role = UI_MEMBERS.get(name.lower()) if pak.name.lower() == "obs.pak" else None
            if not role:
                continue
            frames = []
            checks = []
            for rec in info:
                if rec["status"] != "DECODED":
                    continue
                img = images[rec["index"]]
                payload = png_bytes(img)
                fname = "%s-%03d.png" % (stem, rec["index"])
                (ui_dir / fname).write_bytes(payload)
                frames.append({"index": rec["index"], "url": "./original/OBS/ui/" + fname,
                               "width": rec["width"], "height": rec["height"],
                               "originX": rec["originX"], "originY": rec["originY"],
                               "sha256": sha(payload)})
                old = repo_root / "apps/4leaf/rog/original/OBS/bulk" / ("%s-%02d.png" % (stem, rec["index"]))
                corrected = repo_root / "apps/4leaf/rog/original/OBS/d6-colorkey-corrected" / ("%s-%02d.png" % (stem, rec["index"]))
                checks.append({"index": rec["index"], "vsLegacyBulk": regression(old, img),
                               "vsCorrected": regression(corrected, img)})
            manifest[stem] = {"role": role, "pak": pak.name, "member": name,
                              "sourceSHA256": sha(blob), "declaredFrames": len(info),
                              "frames": frames}
            report["ui"][stem] = {"declared": len(info), "written": len(frames),
                                  "allWritten": len(frames) == len(info), "regression": checks}
    js = ("/* Original Dice/OBS.pak UI members (written-run alpha). Generated by\n"
          " * tools/extract-targeted-original-frames.py from the SHA1-verified 2002 client.\n"
          " * 1171 = D6 (0-5 result faces), 1167 = score numerals.\n"
          " * 1223 = D4 (0-3 result faces); subsequent frame playback timing INFERRED. */\n"
          "window.ORIGINAL_LEAF_UI_FRAMES=" + json.dumps(manifest, indent=1, sort_keys=True) + ";\n")
    (ui_dir / "manifest.js").write_text(js)
    d4.sort(key=lambda r: -r["score"])
    (artifact / "d4-candidates.json").write_text(json.dumps(d4, indent=1))
    report["d4CandidateCount"] = len(d4)
    (ui_dir / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    (artifact / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("resource_dir", type=Path)
    ap.add_argument("repo_root", type=Path)
    ap.add_argument("artifact_dir", type=Path)
    a = ap.parse_args(argv)
    r = run(a.resource_dir, a.repo_root, a.artifact_dir)
    print("LEAF_TARGETED_EXTRACT " + json.dumps({k: r[k] for k in (
        "members", "declaredFrames", "decodedFrames", "failedFrames", "actionGifs",
        "d4CandidateCount")} | {"ui": {k: {x: v[x] for x in ("declared", "written", "allWritten")}
                                       for k, v in r["ui"].items()},
                                "unparsed": len(r["unparsedMembers"])}))
    for stem, v in r["ui"].items():
        if not v["allWritten"]:
            raise SystemExit("UI member %s not fully decoded: %s" % (stem, v))


if __name__ == "__main__":
    main()
