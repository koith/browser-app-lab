#!/usr/bin/env python3
"""Decode the ORIGINAL OBS animation tables from checked-in trailer bytes.

Format established from the SHA1-verified installer data (census.json header
bytes + docs/evidence/obs-trailers/trailers.json):

  member  = u32 blockCount | block * blockCount | animation table
  block   = 128-byte header (u16 frameCount at +66; the first block's header
            is bytes 4..131 of the member, so its count sits at member +70)
            | frameCount * (u32 n, u16 w, u16 h, s16 originX, s16 originY, n body bytes)
            | 768-byte RGB palette (each block has its OWN palette)
  table   = u32 animationCount
            | animationCount * (u32 durationTicks, u32 recordCount,
                                recordCount * 18-byte record)
            | ending: 34 zero bytes (223), 162 bytes with 8 at +32 (3), none (1)
  record  = 9 * u16: [time, type, a, b, value, c, d, e, f]
            type 3 -> show frame `value` from `time` on
            type 1 -> control record (0,1,4,1,9,...)
            other  -> event; `b` is an OBS member number (effect), `value`
                      a flag and c/d signed offsets (spawn position)

The "trailer" stored by decode-obs-extended.py is everything after the first
block's palette, i.e. blocks 2..N followed by the animation table. For the
227 members whose trailer is stored in full, this tool parses blocks and the
table and checks that every byte is consumed (34 zero tail bytes allowed).
Writes docs/evidence/source-maps/actor-native-action-map.json.
Run: python3 apps/4leaf/rog/tools/decode-obs-anim-table.py
"""
import json
import struct
import sys
from pathlib import Path

ROG = Path(__file__).resolve().parents[1]
RECORD = 18
FRAME_KEY, CONTROL = 3, 1


def parse_blocks(trailer, block_count):
    pos, blocks = 0, []
    for b in range(block_count - 1):
        if pos + 128 > len(trailer):
            raise ValueError("block %d header truncated" % (b + 2))
        count = struct.unpack_from("<H", trailer, pos + 66)[0]
        p = pos + 128
        frames = []
        for _ in range(count):
            if p + 12 > len(trailer):
                raise ValueError("block %d frame truncated" % (b + 2))
            n, w, h, ox, oy = struct.unpack_from("<IHHhh", trailer, p)
            frames.append({"width": w, "height": h, "originX": ox, "originY": oy, "bodyBytes": n, "offset": p})
            p += 12 + n
        if p + 768 > len(trailer):
            raise ValueError("block %d palette truncated" % (b + 2))
        blocks.append({"block": b + 2, "trailerOffset": pos, "frameCount": count, "paletteOffset": p,
                       "frames": frames})
        pos = p + 768
    return blocks, trailer[pos:]


def parse_table(table):
    if len(table) < 4:
        raise ValueError("table truncated")
    count = struct.unpack_from("<I", table, 0)[0]
    pos, anims = 4, []
    for a in range(count):
        if pos + 8 > len(table):
            raise ValueError("animation %d header truncated" % a)
        duration, records = struct.unpack_from("<II", table, pos)
        pos += 8
        if pos + RECORD * records > len(table):
            raise ValueError("animation %d records truncated" % a)
        recs = [struct.unpack_from("<9H", table, pos + RECORD * r) for r in range(records)]
        pos += RECORD * records
        keys = [{"time": r[0], "frame": r[4]} for r in recs if r[1] == FRAME_KEY]
        events = [{"time": r[0], "type": r[1], "member": r[3], "flag": r[4],
                   "offsetX": struct.unpack("<h", struct.pack("<H", r[5]))[0],
                   "offsetY": struct.unpack("<h", struct.pack("<H", r[6]))[0],
                   "raw": list(r)} for r in recs if r[1] not in (FRAME_KEY, CONTROL)]
        control = [list(r) for r in recs if r[1] == CONTROL]
        anims.append({"index": a, "durationTicks": duration, "records": records, "frameKeys": keys,
                      "events": events, "control": control})
    return anims, table[pos:]


def tail_variant(rest):
    """Known endings after the table (all observed in original data)."""
    if not rest.strip(b"\0") and len(rest) in (0, 34):
        return "zero%d" % len(rest)
    if len(rest) == 162 and rest[32:34] == b"\x08\x00" and not (rest[:32] + rest[34:]).strip(b"\0"):
        return "162-with-8-at-32"
    return None


def decode(trailer, block_count):
    blocks, table = parse_blocks(trailer, block_count)
    anims, rest = parse_table(table)
    return blocks, anims, rest


def main():
    census = json.loads((ROG / "docs/evidence/obs-census/census.json").read_text(encoding="utf-8"))
    trailers = json.loads((ROG / "docs/evidence/obs-trailers/trailers.json").read_text(encoding="utf-8"))
    out, stats = {}, {"membersWithFullTrailer": 0, "decoded": 0, "failed": [], "tailZero34": 0,
                      "blockCountMatchesChains": 0, "animationCounts": {}}
    for m in census["members"]:
        if m.get("parseError"):
            continue
        key = m["pak"].lower().replace(".pak", "") + "/" + m["member"][:-4]
        t = trailers.get(key)
        if not t or "hex" not in t:
            continue
        stats["membersWithFullTrailer"] += 1
        block_count = bytes.fromhex(m["headerHex"])[0]
        try:
            blocks, anims, rest = decode(bytes.fromhex(t["hex"]), block_count)
        except ValueError as exc:
            stats["failed"].append({"member": key, "error": str(exc)})
            continue
        variant = tail_variant(rest)
        if variant is None:
            stats["failed"].append({"member": key, "error": "unconsumed %d bytes" % len(rest)})
            continue
        stats.setdefault("tailVariants", {})[variant] = stats.get("tailVariants", {}).get(variant, 0) + 1
        stats["decoded"] += 1
        stats["tailZero34"] += int(len(rest) == 34 and not rest.strip(b"\0"))
        stats["blockCountMatchesChains"] += int(block_count == 1 + len(t.get("embeddedChains", [])))
        stats["animationCounts"][str(len(anims))] = stats["animationCounts"].get(str(len(anims)), 0) + 1
        out[key] = {"frames": m["frames"], "blockCount": block_count,
                    "extraBlocks": [{k: v for k, v in b.items() if k != "frames"} for b in blocks],
                    "animationCount": len(anims), "animations": anims,
                    "tailBytes": len(rest), "tailVariant": variant}
    chessman = sorted(k for k, v in out.items() if v["animationCount"] == 17)
    result = {
        "format": "OBS member = u32 blockCount | blocks(128-byte header, frames, own 768-byte palette) | "
                  "u32 animCount | anims(u32 durationTicks, u32 n, n * 18-byte records) | 34 zero bytes",
        "evidence": {"structure": "VERIFIED: every byte of %d stored member trailers parses" % stats["decoded"],
                     "frameKeysAndTicks": "VERIFIED (original table)",
                     "tickDuration": "UNVERIFIED (relative ticks only; EXE clock not decoded)",
                     "actionNames": "INFERRED from per-direction frame blocks; the table has indexes, not names",
                     "eventTypes": "UNVERIFIED meaning; member numbers are OBS effect members"},
        "stats": stats, "chessmanSchema17": chessman, "members": out}
    target = ROG / "docs/evidence/source-maps/actor-native-action-map.json"
    target.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    print("OBS ANIMATION TABLES", json.dumps({k: stats[k] for k in ("membersWithFullTrailer", "decoded",
                                                                    "tailVariants", "animationCounts")},
                                             sort_keys=True), "failed", len(stats["failed"]),
          "chessman17", len(chessman))
    return 0 if not stats["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
