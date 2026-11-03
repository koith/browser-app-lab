#!/usr/bin/env python3
"""Block-structured decode of ORIGINAL OBS members (each block, its OWN palette).

decode-obs-extended.py found the extra frame chains (D6 1171: 16/16/6, D4
1223: 9/16 ...) but painted them with the FIRST block's palette. The member
format decoded in round 8 (tools/decode-obs-anim-table.py) shows that every
block carries its own 768-byte palette after its frames, so those PNGs have
correct pixel indexes but wrong colours. This tool re-decodes every member
with blockCount > 1 block by block with the right palette, and writes the
complete animation table of every member (also the ones whose trailer was too
large to store as hex), so D6/D4 roll sequences and tick timing come from the
original table.

Input : unshield output of the SHA1-verified installer (no Windows code runs).
Output: original/OBS/blocks/<pak>-<member>-b<block>-<frame>.png + manifest.js
        (window.ORIGINAL_LEAF_OBS_BLOCKS: per member blocks, frames, palette SHA)
        docs/evidence/obs-blocks/animation-tables.json (all members)
        docs/evidence/obs-blocks/summary.json
"""
import argparse
import hashlib
import importlib.util
import io
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codec = _load("leaf_blocks_codec", "decode-original-obs-bulk.py")
table = _load("leaf_blocks_table", "decode-obs-anim-table.py")
PACKS = ("obs.pak", "obs2.pak", "obs3.pak")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def split_member(blob):
    """-> (blocks[{header, frames[(body,w,h,ox,oy)], palette}], table_bytes)."""
    block_count = struct.unpack_from("<I", blob, 0)[0]
    if not 1 <= block_count <= 64:
        raise ValueError("implausible block count %d" % block_count)
    pos, blocks = 4, []
    for b in range(block_count):
        if pos + 128 > len(blob):
            raise ValueError("block %d header truncated" % b)
        count = struct.unpack_from("<H", blob, pos + 66)[0]
        p = pos + 128
        frames = []
        for _ in range(count):
            if p + 12 > len(blob):
                raise ValueError("block %d frame truncated" % b)
            n, w, h, ox, oy = struct.unpack_from("<IHHhh", blob, p)
            if p + 12 + n > len(blob):
                raise ValueError("block %d body truncated" % b)
            frames.append((blob[p + 12:p + 12 + n], w, h, ox, oy))
            p += 12 + n
        palette = blob[p:p + 768]
        if len(palette) != 768:
            raise ValueError("block %d palette truncated" % b)
        blocks.append({"frames": frames, "palette": palette, "offset": pos})
        pos = p + 768
    return blocks, blob[pos:]


def decode_frame(body, w, h, palette):
    if len(body) < 4:
        return None, "EMPTY"
    try:
        img, _ = codec.decode_rows(body, w, h, palette, minimum_opaque_pixels=0, alpha_from_runs=True)
        return img, "DECODED"
    except (ValueError, OverflowError) as exc:
        return None, "FAILED:" + str(exc)[:100]


def referenced_members(rog):
    """Card bodies not yet published + every effect member named by an event."""
    want = set()
    maps = rog / "docs/evidence/source-maps"
    q = maps / "quantity-reconciliation.json"
    if q.exists():
        for item in json.loads(q.read_text(encoding="utf-8"))["cardBodiesNotYetPublished"]:
            pak, mem = item.split("/")
            want.add((pak.lower(), mem))
    rt = maps / "actor-native-anim-runtime.json"
    if rt.exists():
        for card in json.loads(rt.read_text(encoding="utf-8"))["cards"].values():
            for a in card["animations"] or []:
                for e in a["events"]:
                    if 1000 <= e[2] < 3000:
                        want.add(("*", str(e[2])))
    return want


def run(resources, repo):
    rog = repo / "apps/4leaf/rog"
    wanted = referenced_members(rog)
    referenced = {}
    out_png = rog / "original/OBS/blocks"
    out_ev = rog / "docs/evidence/obs-blocks"
    out_ev.mkdir(parents=True, exist_ok=True)
    manifest, tables = {}, {}
    summary = {"installerSHA1": "86526d89679ae39b85fe9808da97ad871b7888d9", "members": 0, "splitOK": 0,
               "splitFailed": [], "multiBlockMembers": 0, "blockFrames": 0, "tableDecoded": 0,
               "tableFailed": [], "tailVariants": {}}
    paks = sorted(p for p in resources.rglob("*") if p.is_file() and p.name.lower() in PACKS)
    if not paks:
        raise SystemExit("no OBS*.pak under " + str(resources))
    for pak in paks:
        for name, blob in codec.source_members(pak.read_bytes()):
            if not name.lower().endswith(".obs"):
                continue
            summary["members"] += 1
            key = pak.stem.lower() + "/" + Path(name).stem
            try:
                blocks, tail = split_member(blob)
            except (ValueError, struct.error) as exc:
                summary["splitFailed"].append({"member": key, "error": str(exc)})
                continue
            summary["splitOK"] += 1
            try:
                anims, rest = table.parse_table(tail)
                variant = table.tail_variant(rest)
                if variant is None:
                    raise ValueError("unconsumed %d bytes" % len(rest))
                tables[key] = {"blockCount": len(blocks), "blockFrames": [len(b["frames"]) for b in blocks],
                               "animations": anims, "tailVariant": variant}
                summary["tableDecoded"] += 1
                summary["tailVariants"][variant] = summary["tailVariants"].get(variant, 0) + 1
            except ValueError as exc:
                summary["tableFailed"].append({"member": key, "error": str(exc)})
            stem_only = Path(name).stem
            if (pak.name.lower(), stem_only) in wanted or ("*", stem_only) in wanted:
                rdir = rog / "original/OBS/referenced"
                rdir.mkdir(parents=True, exist_ok=True)
                rows = []
                for fi, (body, w, h, ox, oy) in enumerate(blocks[0]["frames"]):
                    img, status = decode_frame(body, w, h, blocks[0]["palette"])
                    row = {"index": fi, "width": w, "height": h, "originX": ox, "originY": oy, "status": status}
                    if img is not None:
                        payload = png(img)
                        fname = "%s-%s-%03d.png" % (pak.stem.lower(), stem_only, fi)
                        (rdir / fname).write_bytes(payload)
                        row.update({"url": "./original/OBS/referenced/" + fname, "sha256": sha(payload)})
                    rows.append(row)
                referenced[key] = {"originalMember": pak.name + "/" + name, "sourceSHA256": sha(blob),
                                   "blocks": [{"block": 0, "paletteSHA256": sha(blocks[0]["palette"]),
                                               "frameCount": len(rows), "frames": rows}]}
            if len(blocks) < 2:
                continue
            summary["multiBlockMembers"] += 1
            stem = pak.stem.lower() + "-" + Path(name).stem
            rec = {"originalMember": pak.name + "/" + name, "sourceSHA256": sha(blob), "blocks": []}
            out_png.mkdir(parents=True, exist_ok=True)
            for bi, block in enumerate(blocks):
                rows = []
                for fi, (body, w, h, ox, oy) in enumerate(block["frames"]):
                    img, status = decode_frame(body, w, h, block["palette"])
                    row = {"index": fi, "width": w, "height": h, "originX": ox, "originY": oy, "status": status}
                    if img is not None:
                        payload = png(img)
                        fname = "%s-b%d-%03d.png" % (stem, bi, fi)
                        (out_png / fname).write_bytes(payload)
                        row.update({"url": "./original/OBS/blocks/" + fname, "sha256": sha(payload)})
                        summary["blockFrames"] += 1
                    rows.append(row)
                rec["blocks"].append({"block": bi, "paletteSHA256": sha(block["palette"]),
                                      "frameCount": len(rows), "frames": rows})
            manifest[key] = rec
    if manifest:
        (out_png / "manifest.js").write_text(
            "/* Original OBS members decoded block by block, each with its own palette. Block 0 = the\n"
            "   frames already published; blocks 1.. replace original/OBS/embedded colours. */\n"
            "window.ORIGINAL_LEAF_OBS_BLOCKS=" + json.dumps(manifest, indent=1, sort_keys=True) + ";\n",
            encoding="utf-8")
    if referenced:
        (rog / "original/OBS/referenced/manifest.js").write_text(
            "/* Original OBS members referenced by CHR (unpublished card bodies) or by animation events\n"
            "   (effects). Block 0, own palette. */\nwindow.ORIGINAL_LEAF_OBS_REFERENCED=" +
            json.dumps(referenced, indent=1, sort_keys=True) + ";\n", encoding="utf-8")
    summary["referencedMembers"] = len(referenced)
    (out_ev / "animation-tables.json").write_text(json.dumps(tables, indent=0, sort_keys=True), encoding="utf-8")
    (out_ev / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    print("OBS_BLOCK_DECODE", json.dumps({k: summary[k] for k in ("members", "splitOK", "multiBlockMembers",
                                                                  "blockFrames", "tableDecoded", "tailVariants")}),
          "splitFailed", len(summary["splitFailed"]), "tableFailed", len(summary["tableFailed"]))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("resources")
    ap.add_argument("repo")
    a = ap.parse_args()
    run(Path(a.resources), Path(a.repo))
