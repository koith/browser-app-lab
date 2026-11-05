#!/usr/bin/env python3
"""R15: extract only source-referenced OBS effect *candidates*, not invented art.

Input is the unshield-extracted, SHA1-verified original 2002 client on CI.
The 97 recovered CHR bodies carry 17 (or 15) native action slots. Events
[tick,type,member,dx,dy] in those slots are byte-verified, but whether a
referenced member is a drawn effect, its action role, and tick->ms are not.
Output:
  original/OBS/duel-effects/manifest.js (only complete, strict decoded PNGs)
  original/OBS/duel-effects/<pak>-<member>-NNN.png
  docs/evidence/r15/duel-effect-source-audit.json (also records ALL failures)
  artifact/contact-sheets/ (upside-down stored -> upright display only)
  artifact/source-audit.json
No Windows program executes; never synthesize or reuse another character.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROG = HERE.parent
SOURCE = ROG / "docs/evidence/source-maps/actor-native-anim-runtime.json"
SOURCE_SHA1 = "86526d89679ae39b85fe9808da97ad871b7888d9"
SEEDS = ("1096", "1097", "1098", "1099", "1101", "1102", "1112", "1114", "1118", "1124")
MAX_MEMBERS = 65  # round 2: exhaust all unique 1000+ original source event references
MAX_FRAMES_PER_MEMBER = 256  # OBS 1095 legitimately declares 172 native frames
MAX_PNG_BYTES = 32000000
EXPECTED_PACKS = ("obs.pak", "obs2.pak", "obs3.pak")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def codec_module():
    spec = importlib.util.spec_from_file_location(
        "r15_source_decoder", HERE / "decode-original-obs-bulk.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def source_references(doc):
    """Extract native event values, with no semantic assumptions."""
    refs = defaultdict(lambda: {"cards": set(), "slots": Counter(), "types": Counter(),
                                "events": []})
    all_slots = Counter()
    for card, record in doc["cards"].items():
        for anim in record["animations"]:
            slot = int(anim["index"])
            all_slots[slot] += 1
            for event in anim.get("events", []):
                if len(event) != 5:
                    raise ValueError("Unexpected source event width: " + str((card, slot, event)))
                tick, kind, member, dx, dy = map(int, event)
                if not 1000 <= member <= 9999:
                    continue
                key = str(member)
                r = refs[key]
                r["cards"].add(card)
                r["slots"][slot] += 1
                r["types"][kind] += 1
                r["events"].append([card, slot, tick, kind, dx, dy])
    return refs, all_slots

def choose(refs):
    # Unique high-frequency references first; 0/1 may be event parameters,
    # not OBS member IDs. The seed list comes ONLY from actual source events.
    candidates = [s for s in SEEDS if s in refs]
    extra = sorted((k for k in refs if k not in candidates),
                   key=lambda k: (-len(refs[k]["events"]), int(k)))
    return (candidates + extra)[:MAX_MEMBERS]

def find_packs(resources):
    packs = {}
    for f in resources.rglob("*"):
        if not f.is_file() or f.name.lower() not in EXPECTED_PACKS:
            continue
        if "dice" not in [x.lower() for x in f.parts]:
            continue
        pack = f.name.lower()
        if pack in packs:
            raise ValueError("Ambiguous original source pack path: " + pack)
        packs[pack] = f
    if set(packs) != set(EXPECTED_PACKS):
        raise FileNotFoundError("Unshielded Dice source packs missing: "
                                + repr(sorted(set(EXPECTED_PACKS)-set(packs))))
    return packs

def frames_as_png(codec, blob):
    frames, palette = codec.unpack_frames(blob)
    if len(frames) > MAX_FRAMES_PER_MEMBER:
        raise ValueError("Too many source frames: " + str(len(frames)))
    decoded = []
    for index, (body, w, h, ox, oy) in enumerate(frames):
        image, diagnostic = codec.decode_rows(
            body, w, h, palette, minimum_opaque_pixels=0, alpha_from_runs=True)
        if diagnostic["opaquePixels"] <= 0:
            raise ValueError("Zero opaque source pixels at frame " + str(index))
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=True)
        payload = stream.getvalue()
        decoded.append((payload, {"index": index, "width": w, "height": h,
                                  "originX": ox, "originY": oy,
                                  "sha256": sha(payload),
                                  "opaquePixels": diagnostic["opaquePixels"],
                                  "bodySHA256": sha(body)}))
    return decoded

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resources", type=Path, required=True)
    ap.add_argument("--artifact", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, required=True)
    args = ap.parse_args()
    raw = SOURCE.read_bytes()
    doc = json.loads(raw)
    refs, slot_counts = source_references(doc)
    targets = choose(refs)
    packs = find_packs(args.resources)
    codec = codec_module()
    # Preserve a consistent snapshot of source PAKs, no fuzzy indexing.
    found = defaultdict(list)
    pack_sha = {}
    for pak, p in sorted(packs.items()):
        data = p.read_bytes()
        pack_sha[pak] = sha(data)
        for member_name, payload in codec.source_members(data):
            match = re.fullmatch(r"(\d{4})\.obs", member_name.lower())
            if match and match[1] in targets:
                found[match[1]].append((pak, member_name, payload))
    root = args.repo_root / "apps/4leaf/rog"
    output = root / "original/OBS/duel-effects"
    evidence_path = root / "docs/evidence/r15/duel-effect-source-audit.json"
    output.mkdir(parents=True, exist_ok=True)
    args.artifact.mkdir(parents=True, exist_ok=True)
    report = {"generatedFrom": "SHA1-verified 2002 client, no Windows code executed",
              "originalInstallerSHA1": SOURCE_SHA1,
              "runtimeDataSHA256": sha(raw),
              "referenceSlots": dict(sorted(slot_counts.items())),
              "packSHA256": pack_sha,
              "candidateSelection": {"seeds": list(SEEDS), "max": MAX_MEMBERS,
                                     "members": targets},
              "effects": {}, "deferred": [],
              "semanticRole": "UNVERIFIED; OBS source pixels and original event tuple VERIFIED"}
    manifest = {}
    total_png_bytes = 0
    for member in targets:
        r = refs[member]
        item = {"cards": sorted(r["cards"]), "count": len(r["events"]),
                "slots": dict(sorted(r["slots"].items())),
                "types": dict(sorted(r["types"].items())),
                "sourceCandidates": [pak for pak, _, _ in found.get(member, [])],
                "status": "UNVERIFIED", "frames": 0}
        report["effects"][member] = item
        candidates = found.get(member, [])
        if len(candidates) != 1:
            item["status"] = "MISSING" if not candidates else "AMBIGUOUS-PACK"
            continue
        pak, native_name, body = candidates[0]
        try:
            decoded = frames_as_png(codec, body)
            size = sum(len(png) for png, _ in decoded)
            if total_png_bytes + size > MAX_PNG_BYTES:
                item["status"] = "SIZE-GATE"
                continue
            frame_records = []
            for payload, metadata in decoded:
                name = pak.split(".")[0] + "-" + member + "-" + str(metadata["index"]).zfill(3) + ".png"
                dst = output / name
                dst.write_bytes(payload)
                frame_records.append({
                    **metadata, "url": "./original/OBS/duel-effects/" + name})
            total_png_bytes += size
            original = pak.replace(".pak", ".pak/") + native_name
            manifest[original] = {"originalMember": original,
                "sourceSHA256": sha(body),
                "status": "SOURCE-PIXELS-VERIFIED/ROLE-UNVERIFIED",
                "nativeEvents": r["events"],
                "frames": frame_records}
            item.update(status="SOURCE-PIXELS-VERIFIED/ROLE-UNVERIFIED",
                        frames=len(frame_records), sourceBytesSHA256=sha(body),
                        pngBytes=size, originalMember=original)
        except (ValueError, OverflowError, MemoryError) as e:
            item["status"] = "DECODER-FAILED"
            item["error"] = str(e)[:350]
    output.joinpath("manifest.js").write_text(
        "/* R15 source OBS native events, no claimed semantic action labels. */\n"
        "window.ORIGINAL_LEAF_DUEL_EFFECTS=" +
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) +
        ";\n", encoding="utf-8")
    report["summary"] = {
        "candidateMembers": len(targets), "decodedMembers": len(manifest),
        "sourceFrames": sum(len(m["frames"]) for m in manifest.values()),
        "outputPNGBytes": total_png_bytes,
        "missingMembers": sorted(k for k, v in report["effects"].items() if v["status"] == "MISSING"),
        "decoderFailedMembers": sorted(k for k, v in report["effects"].items() if v["status"] == "DECODER-FAILED")}
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(text, encoding="utf-8")
    args.artifact.joinpath("source-audit.json").write_text(text, encoding="utf-8")
    print("R15_SOURCE_EFFECTS", json.dumps(report["summary"], ensure_ascii=False))
    # Missing or unsupported sources are evidence, NOT a fabricated PASS.
    # Exit nonzero only for corrupt input/logic, not for genuine absent art.
    return 0

if __name__ == "__main__":
    sys.exit(main())
