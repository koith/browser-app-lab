#!/usr/bin/env python3
"""Extended, read-only decode of original OBS/OBS2/OBS3 members (round 7).

Targets what the first-pass decoders leave behind, using the SHA1-verified
installer (86526d89679ae39b85fe9808da97ad871b7888d9). No Windows code runs.

1. WIDE FRAMES. unpack_frames() rejects width/height > 300, so 1154 (320x320),
   1182 (438x75) and 1186 (478x30 at frame 8) fail although the run stream
   uses a 640 stride. Here width <= 640, height <= 480. A frame record whose
   body is shorter than the 4-byte run header (1175: n=2) is kept as an
   EMPTY frame (status EMPTY, no pixels), never invented.
2. EMBEDDED FRAME CHAINS. Bytes after the 768-byte palette ("trailer") are
   scanned for further chains of frame records <IHHhh>+body that decode
   completely with the member palette or with a 768-byte palette that
   follows the chain. 1171 D6 (118 KB trailer), 1223 D4 (63 KB), 1094
   (580 KB), 1133-1136, 1102 carry far more bytes than their first frames.
   Every accepted chain is exported (QUARANTINED: role unknown).
3. TRAILER TABLES. Trailer sizes of same-frame-count members differ by
   multiples of 18 bytes (e.g. 3810/3828/3846/3864), i.e. a variable count
   of fixed records. For each trailer the tool reports the byte period with
   the strongest self-similarity and, for period 18, per-field u16 ranges and
   the fields whose values never exceed the member's frame count (frame
   index candidates). Raw trailer bytes (<= 16 KiB) are written as hex so the
   table can be decoded offline; larger ones keep SHA-256 + first 4 KiB.
4. OBS2/OBS3 CHARACTER-SIZE MEMBERS (>= 20 frames, max side >= 48 px) are
   exported in full, QUARANTINED, no card assigned, with block proposals.
5. CHR records (472 bytes) are written as hex for offline field decoding.

Outputs (repository, data branch only):
  original/OBS/recovered-wide/          frames of members that failed before
  original/OBS/embedded/                frames found in trailers
  original/OBS/obs23-actors/            OBS2/OBS3 character-size members
  each with manifest.js, every PNG with SHA-256, native origin and size
  docs/evidence/obs-trailers/trailers.json, chr.json, summary.json
"""
import argparse
import hashlib
import importlib.util
import io
import json
import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codec = _load("leaf_ext_codec", "decode-original-obs-bulk.py")
structure = _load("leaf_ext_structure", "obs_structure.py")

PACKS = ("obs.pak", "obs2.pak", "obs3.pak")
MAX_W, MAX_H, MAX_FRAMES = 640, 480, 512
HEX_LIMIT = 16 * 1024
PERIODS = range(2, 65)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def plausible(n, w, h, remaining):
    return 1 <= w <= MAX_W and 1 <= h <= MAX_H and 0 <= n <= 4 * MAX_W * MAX_H and 12 + n <= remaining


def read_chain(data, cursor, count=None):
    """Parse up to `count` frame records (all while plausible if None).
    Returns (records, end_cursor)."""
    records = []
    while count is None or len(records) < count:
        if cursor + 12 > len(data):
            break
        n, w, h, ox, oy = struct.unpack_from("<IHHhh", data, cursor)
        if not plausible(n, w, h, len(data) - cursor):
            break
        records.append((data[cursor + 12:cursor + 12 + n], w, h, ox, oy))
        cursor += 12 + n
    return records, cursor


def decode_record(body, w, h, palette):
    if len(body) < 4:
        return None, "EMPTY"
    try:
        img, _ = codec.decode_rows(body, w, h, palette, minimum_opaque_pixels=0, alpha_from_runs=True)
        return img, "DECODED"
    except (ValueError, OverflowError) as exc:
        return None, "FAILED:" + str(exc)[:120]


def unpack_member(blob):
    """Relaxed primary parse. Returns (frames, palette, trailer, error)."""
    if len(blob) < 132:
        return [], None, b"", "header truncated"
    count = struct.unpack_from("<H", blob, 70)[0]
    if not 1 <= count <= MAX_FRAMES:
        return [], None, b"", "implausible frame count %d" % count
    records, cursor = read_chain(blob, 132, count)
    if len(records) != count:
        return [], None, b"", "frame %d of %d not plausible at %d" % (len(records), count, cursor)
    palette = blob[cursor:cursor + 768]
    if len(palette) != 768:
        return [], None, b"", "palette missing"
    return records, palette, blob[cursor + 768:], None


def scan_embedded(trailer, palette, min_frames=2, limit=1 << 20):
    """Find chains of >= min_frames frame records inside a trailer that all
    decode. RLE validity does not depend on the palette, so the first record
    is tried before parsing further. Colours use the member palette; whether
    768 bytes follow the chain (a possible own palette) is only recorded."""
    chains = []
    pos = 0
    data = trailer[:limit]
    while pos + 12 <= len(data):
        n, w, h, ox, oy = struct.unpack_from("<IHHhh", data, pos)
        if not (6 <= n and plausible(n, w, h, len(data) - pos) and abs(ox) <= 2 * w and abs(oy) <= 2 * h):
            pos += 1
            continue
        first, status = decode_record(data[pos + 12:pos + 12 + n], w, h, palette)
        if status != "DECODED":
            pos += 1
            continue
        records, end = read_chain(data, pos)
        decoded = [(first, status)] + [decode_record(r[0], r[1], r[2], palette) for r in records[1:]]
        good = 0
        for _, st in decoded:
            if st != "DECODED":
                break
            good += 1
        if good >= min_frames:
            records, decoded = records[:good], decoded[:good]
            end = pos + sum(12 + len(r[0]) for r in records)
            chains.append({"offset": pos, "frames": good, "palette": "member",
                           "bytesAfterChain": len(data) - end, "records": records, "decoded": decoded})
            pos = end
        else:
            pos += 1
    return chains


def periodicity(data, limit=8192):
    b = np.frombuffer(data[:limit], np.uint8)
    if len(b) < 64:
        return None
    scores = {p: float((b[p:] == b[:-p]).mean()) for p in PERIODS if p < len(b) // 2}
    # Multiples of the true period score as high or higher: take the
    # smallest period within 90% of the best score.
    top = max(scores.values())
    best = min(p for p, v in scores.items() if v >= 0.9 * top)
    return {"bestPeriod": best, "score": round(scores[best], 3), "period18": round(scores.get(18, 0.0), 3)}


def record_fields(data, frames, period=18):
    """u16 field statistics for the longest suffix that is whole records."""
    usable = len(data) - (len(data) % period)
    start = len(data) % period
    if usable < period * 2:
        return None
    recs = np.frombuffer(data[start:start + usable], "<u2").reshape(-1, period // 2)
    fields = []
    for i in range(recs.shape[1]):
        col = recs[:, i]
        fields.append({"field": i, "byteOffset": i * 2, "min": int(col.min()), "max": int(col.max()),
                       "distinct": int(len(np.unique(col))),
                       "frameIndexCandidate": bool(frames and col.max() < frames and len(np.unique(col)) > 1)})
    return {"leadingBytes": start, "records": int(recs.shape[0]), "fields": fields}


def export(images, stem, folder, rog, extra):
    target = rog / "original/OBS" / folder
    target.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, (img, status, w, h, ox, oy) in enumerate(images):
        row = {"index": index, "width": w, "height": h, "originX": ox, "originY": oy, "status": status}
        if img is not None:
            payload = png_bytes(img)
            name = "%s-%03d.png" % (stem, index)
            (target / name).write_bytes(payload)
            row.update({"url": "./original/OBS/%s/%s" % (folder, name), "sha256": sha(payload)})
        frames.append(row)
    return dict(extra, frames=frames)


def write_manifest(rog, folder, variable, data, note):
    if not data:
        return
    path = rog / "original/OBS" / folder / "manifest.js"
    path.write_text("/* %s */\nwindow.%s=%s;\n" % (note, variable, json.dumps(data, indent=1, sort_keys=True)),
                    encoding="utf-8")


def upright_rgba(img):
    return np.flipud(np.array(img.convert("RGBA")))


def run(resources, repo):
    rog = repo / "apps/4leaf/rog"
    evidence = rog / "docs/evidence/obs-trailers"
    evidence.mkdir(parents=True, exist_ok=True)
    trailers, wide, embedded, actors = {}, {}, {}, {}
    summary = {"installerSHA1": "86526d89679ae39b85fe9808da97ad871b7888d9", "packs": [],
               "members": 0, "primaryParseErrors": [], "wideRecovered": {}, "emptyFrames": 0,
               "embeddedChains": {}, "obs23ActorMembers": {}, "trailerPeriod18Best": 0,
               "claims": {"actionTableDecoded": False, "embeddedRole": "UNKNOWN/QUARANTINED",
                          "obs23CardAssignment": None}}
    paks = sorted(p for p in resources.rglob("*") if p.is_file() and p.name.lower() in PACKS)
    if not paks:
        raise SystemExit("no OBS*.pak under " + str(resources))
    for pak in paks:
        raw = pak.read_bytes()
        summary["packs"].append({"name": pak.name, "sha256": sha(raw)})
        for name, blob in codec.source_members(raw):
            if not name.lower().endswith(".obs"):
                continue
            summary["members"] += 1
            stem = Path(name).stem
            key = pak.stem.lower() + "/" + stem
            records, palette, trailer, error = unpack_member(blob)
            if error:
                summary["primaryParseErrors"].append({"member": key, "error": error})
                continue
            decoded = [(*decode_record(b, w, h, palette), w, h, ox, oy) for b, w, h, ox, oy in records]
            summary["emptyFrames"] += sum(1 for d in decoded if d[1] == "EMPTY")
            strict_fail = False
            try:
                codec.unpack_frames(blob)
            except ValueError:
                strict_fail = True
            if strict_fail and all(d[1] in ("DECODED", "EMPTY") for d in decoded):
                wide[key] = export(decoded, pak.stem.lower() + "-" + stem, "recovered-wide", rog,
                                   {"originalMember": pak.name + "/" + name, "sourceSHA256": sha(blob),
                                    "frameCount": len(decoded)})
                summary["wideRecovered"][key] = len(decoded)
            # trailer
            info = {"frames": len(records), "trailerBytes": len(trailer), "trailerSHA256": sha(trailer),
                    "periodicity": periodicity(trailer),
                    "record18": record_fields(trailer, len(records))}
            if len(trailer) <= HEX_LIMIT:
                info["hex"] = trailer.hex()
            else:
                info["first4KiBHex"] = trailer[:4096].hex()
            if info["periodicity"] and info["periodicity"]["bestPeriod"] == 18:
                summary["trailerPeriod18Best"] += 1
            chains = scan_embedded(trailer, palette)
            info["embeddedChains"] = [{"offset": c["offset"], "frames": c["frames"], "palette": c["palette"],
                                       "bytesAfterChain": c["bytesAfterChain"]} for c in chains]
            for k, c in enumerate(chains):
                ck = "%s-%s-c%d" % (pak.stem.lower(), stem, k)
                rows = [(img, s, w, h, ox, oy) for (img, s), (_, w, h, ox, oy) in zip(c["decoded"], c["records"])]
                embedded[ck] = export(rows, ck, "embedded", rog,
                                      {"originalMember": pak.name + "/" + name, "trailerOffset": c["offset"],
                                       "palette": c["palette"], "status": "QUARANTINED/role-unknown"})
                summary["embeddedChains"][ck] = c["frames"]
            trailers[key] = info
            # OBS2/OBS3 character-size members
            ok = [d for d in decoded if d[1] == "DECODED"]
            if (pak.name.lower() != "obs.pak" and len(records) >= 20 and len(ok) == len(records)
                    and max(max(d[2], d[3]) for d in ok) >= 48):
                seq = [(upright_rgba(d[0]), d[4], d[5]) for d in ok]
                actors[key] = export(decoded, pak.stem.lower() + "-" + stem, "obs23-actors", rog,
                                     {"originalMember": pak.name + "/" + name, "sourceSHA256": sha(blob),
                                      "frameCount": len(records), "assignedCard": None,
                                      "blockProposal": structure.segment(seq),
                                      "status": "QUARANTINED/character-size/no-card-evidence"})
                summary["obs23ActorMembers"][key] = len(records)
    # CHR records
    chr_hex = {}
    for p in resources.rglob("*"):
        if p.is_file() and p.name.lower() == "chr.pak":
            for name, blob in codec.source_members(p.read_bytes()):
                if name.lower().endswith(".chr"):
                    chr_hex[name] = blob.hex()
    write_manifest(rog, "recovered-wide", "ORIGINAL_LEAF_OBS_WIDE_RECOVERED", wide,
                   "Members that failed the 300px limit, decoded with 640-stride limits. EMPTY = 0-pixel frame record.")
    write_manifest(rog, "embedded", "ORIGINAL_LEAF_OBS_EMBEDDED", embedded,
                   "Frame chains found after the member palette. QUARANTINED: role unknown.")
    write_manifest(rog, "obs23-actors", "ORIGINAL_LEAF_OBS23_ACTORS", actors,
                   "OBS2/OBS3 character-size members. QUARANTINED: no card assignment without byte evidence.")
    (evidence / "trailers.json").write_text(json.dumps(trailers, indent=0, sort_keys=True), encoding="utf-8")
    (evidence / "chr.json").write_text(json.dumps({"recordBytes": sorted({len(v) // 2 for v in chr_hex.values()}),
                                                    "records": chr_hex}, indent=0, sort_keys=True), encoding="utf-8")
    summary["chrRecords"] = len(chr_hex)
    summary["exportedFrames"] = {
        "recoveredWide": sum(sum(1 for f in v["frames"] if "url" in f) for v in wide.values()),
        "embedded": sum(sum(1 for f in v["frames"] if "url" in f) for v in embedded.values()),
        "obs23Actors": sum(sum(1 for f in v["frames"] if "url" in f) for v in actors.values())}
    (evidence / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    print("OBS_EXTENDED_DECODE", json.dumps({k: summary[k] for k in ("members", "wideRecovered", "emptyFrames",
                                                                     "embeddedChains", "exportedFrames",
                                                                     "trailerPeriod18Best", "chrRecords")}))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("resources")
    ap.add_argument("repo")
    a = ap.parse_args()
    run(Path(a.resources), Path(a.repo))
