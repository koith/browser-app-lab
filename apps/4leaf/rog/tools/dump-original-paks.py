#!/usr/bin/env python3
"""Quarantined, exhaustive native OBS frame inventory for SHA-verified 2002 client.

Unlike the production sampler this attempts EVERY declared native frame in
OBS.pak, OBS2.pak and OBS3.pak. Failed frames remain failed; decoded pixels are
not assigned invented actor identities, directions, actions or playback rates.
Output MUST remain a short-lived Actions artifact, never a public Git commit.
No archived Windows executable or DLL is executed.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path

SCRIPT = Path(__file__).with_name("decode-original-obs-bulk.py")
spec = importlib.util.spec_from_file_location("leaf_obs_codec", SCRIPT)
codec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)

EXPECTED_PRIOR_MANIFEST_FRAMES = 2853
MAX_EXPORTED_IMAGES = 7000
MAX_EXPORTED_BYTES = 256 * 1024 * 1024
ALLOWED_PACKS = ("obs.pak", "obs2.pak", "obs3.pak")


def classify(message):
    s = message.lower()
    if "palette" in s:
        return "PALETTE_OR_FRAME_BOUNDARY"
    if "frame geometry" in s or "frame header" in s:
        return "FRAME_STRUCTURE"
    if "run" in s or "packet" in s or "source buffer" in s:
        return "RLE_PACKET_OR_COORDINATE"
    if "transparent" in s:
        return "LOW_OPACITY"
    if "entry" in s or "pak" in s:
        return "PAK_CONTAINER"
    return "UNKNOWN_CODEC_FAILURE"


def member_probe(data):
    result = {"sourceLength": len(data), "sourceSHA256": hashlib.sha256(data).hexdigest(),
              "headerFirst32Hex": data[:32].hex(), "nativeFrameCount": None,
              "paletteTailByteCount": None, "frames": [], "error": None}
    if len(data) < 132:
        result["error"] = "OBS header truncated"
        return result
    count = struct.unpack_from("<H", data, 70)[0]
    result["nativeFrameCount"] = count
    if count < 1 or count > codec.MAX_SPRITE_FRAMES:
        result["error"] = "Implausible OBS frame count"
        return result
    cursor = 132
    for index in range(count):
        if cursor + 12 > len(data):
            result["error"] = "Truncated OBS frame header at index " + str(index)
            return result
        n, width, height, ox, oy = struct.unpack_from("<IHHhh", data, cursor)
        result["frames"].append({"index": index, "offset": cursor, "byteLength": n,
                                 "width": width, "height": height,
                                 "originX": ox, "originY": oy})
        if not (1 <= width <= 300 and 1 <= height <= 300 and
                6 <= n <= 250000 and cursor + 12 + n <= len(data)):
            result["error"] = "OBS frame geometry invalid at index " + str(index)
            return result
        cursor += 12 + n
    if cursor + 768 > len(data):
        result["error"] = "Missing native 256-colour OBS palette at frame boundary"
        return result
    result["paletteSHA256"] = hashlib.sha256(data[cursor:cursor + 768]).hexdigest()
    result["paletteTailByteCount"] = len(data) - cursor - 768
    result["paletteTailFirst64Hex"] = data[cursor + 768:cursor + 832].hex()
    return result


def collect(archive_dir, output_dir, card_ids=None):
    card_ids = set(card_ids or [])
    files = sorted((p for p in archive_dir.rglob("*") if p.is_file() and
                    p.name.lower() in ALLOWED_PACKS), key=lambda p: (p.name.lower(), str(p)))
    if not files:
        raise ValueError("No OBS/OBS2/OBS3 original PAK files in extracted client")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {"format": "4LEAF_OBS_EXHAUSTIVE_FORENSICS_V1",
               "evidenceLevel": "FULL_ORIGINAL_BYTES_REQUIRED",
               "priorManifestFrames": EXPECTED_PRIOR_MANIFEST_FRAMES,
               "frameCountComparison": "OBS-only counts may differ from a multi-source manifest",
               "packs": [], "totalNativeDeclaredFrames": 0,
               "totalAttemptedFrames": 0, "strictDecodedFrames": 0,
               "failedFrameDecodes": 0, "unparsedDeclaredFrames": 0,
               "exportedPNGBytes": 0, "exportLimitReached": False,
               "actorIdentityUnverified": True, "directionActionMappingUnverified": True}
    for pack in files:
        data = pack.read_bytes()
        entry = {"name": pack.name, "sha256": hashlib.sha256(data).hexdigest(),
                 "memberCount": 0, "members": [], "containerError": None}
        summary["packs"].append(entry)
        try:
            members = list(codec.source_members(data))
        except ValueError as exc:
            entry["containerError"] = str(exc)
            continue
        entry["memberCount"] = len(members)
        for filename, blob in members:
            record = {"name": filename, "sourceSHA256": hashlib.sha256(blob).hexdigest(),
                      "cardIdCandidate": None, "identityStatus": "UNVERIFIED"}
            entry["members"].append(record)
            match = re.fullmatch(r"1([0-9]{3})\.obs", filename.lower())
            if not match:
                record["kind"] = "NON_OBS_MEMBER"
                continue
            cid = match.group(1).zfill(4)
            record["cardIdCandidate"] = cid if cid in card_ids else None
            record["kind"] = "OBS_UNCLASSIFIED_NATIVE_MEMBER"
            probe = member_probe(blob)
            record["header"] = {k: v for k, v in probe.items() if k != "frames"}
            declared = probe["nativeFrameCount"]
            if not isinstance(declared, int) or not 1 <= declared <= codec.MAX_SPRITE_FRAMES:
                record["parseError"] = probe["error"]
                continue
            summary["totalNativeDeclaredFrames"] += declared
            if probe["error"] is not None:
                record["parseError"] = probe["error"]
                summary["unparsedDeclaredFrames"] += declared
                continue
            try:
                frames, palette = codec.unpack_frames(blob)
            except ValueError as exc:
                record["parseError"] = str(exc)
                summary["unparsedDeclaredFrames"] += declared
                continue
            record["frames"] = []
            for index, (body, width, height, ox, oy) in enumerate(frames):
                summary["totalAttemptedFrames"] += 1
                state = {"index": index, "geometry": [width, height, ox, oy],
                         "sourceFrameSHA256": hashlib.sha256(body).hexdigest()}
                try:
                    image, diagnostic = codec.decode_rows(body, width, height, palette)
                except (ValueError, OverflowError) as exc:
                    state["status"] = "FAILED"
                    state["errorClass"] = classify(str(exc))
                    state["error"] = str(exc)
                    summary["failedFrameDecodes"] += 1
                else:
                    state["status"] = "STRICT_DECODED"
                    state["decoder"] = diagnostic["decoder"]
                    summary["strictDecodedFrames"] += 1
                    if (summary["strictDecodedFrames"] <= MAX_EXPORTED_IMAGES and
                            not summary["exportLimitReached"]):
                        # filename is normalized to member sequence; do not trust
                        # archive paths as output paths.
                        import io
                        buffer = io.BytesIO()
                        image.save(buffer, format="PNG", optimize=True)
                        content = buffer.getvalue()
                        if summary["exportedPNGBytes"] + len(content) <= MAX_EXPORTED_BYTES:
                            target_dir = output_dir / "frames" / pack.name
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target = target_dir / (str(len(entry["members"]) - 1).zfill(4) +
                                                   "-f" + str(index).zfill(3) + ".png")
                            target.write_bytes(content)
                            summary["exportedPNGBytes"] += len(content)
                            state["artifactPath"] = target.relative_to(output_dir).as_posix()
                            state["pngSHA256"] = hashlib.sha256(content).hexdigest()
                        else:
                            summary["exportLimitReached"] = True
                    else:
                        summary["exportLimitReached"] = True
                record["frames"].append(state)
    summary["missingVsPrior2853"] = EXPECTED_PRIOR_MANIFEST_FRAMES - summary["strictDecodedFrames"]
    (output_dir / "full-frame-report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("unshield_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--cards", type=Path, default=None)
    args = parser.parse_args()
    cards = []
    if args.cards:
        cards = [c["id"] for c in json.loads(args.cards.read_text(encoding="utf-8"))]
    summary = collect(args.unshield_directory, args.output_directory, cards)
    print("ORIGINAL_OBS_FULL_AUDIT", json.dumps({
        k: summary[k] for k in ("totalNativeDeclaredFrames", "totalAttemptedFrames",
                                "strictDecodedFrames", "failedFrameDecodes",
                                "unparsedDeclaredFrames", "exportedPNGBytes",
                                "exportLimitReached")}, sort_keys=True))
    if summary["totalAttemptedFrames"] == 0:
        raise RuntimeError("No source frame payloads parsed; full recovery NOT verified")


if __name__ == "__main__":
    main()
