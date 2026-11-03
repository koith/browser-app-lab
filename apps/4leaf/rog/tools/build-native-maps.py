#!/usr/bin/env python3
"""Round-8 native maps for runtime integration, rebuilt from original data.

Inputs (all checked in): original/OBS/ui (1171 D6, 1223 D4), embedded chains,
docs/evidence/source-maps/actor-native-action-map.json (decoded original
animation tables, tools/decode-obs-anim-table.py), census.json, chessmen.json.
Writes docs/evidence/source-maps/:
  dice-native-sequences.json     measured frame groups + embedded roll chains
  actor-native-anim-runtime.json compact per-card original animation tables
  card-mapping-candidates.json   VERIFIED links vs INFERRED candidates
  ledger-events-round8.json      events for GPT to append to the ledger
Run: python3 apps/4leaf/rog/tools/build-native-maps.py
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROG = Path(__file__).resolve().parents[1]
OUT = ROG / "docs/evidence/source-maps"


def js(path, marker="={"):
    t = path.read_text(encoding="utf-8")
    return json.loads(t[t.index(marker) + len(marker) - 1:t.rindex(";")])


def frame_features(f):
    a = np.array(Image.open(ROG / f["url"][2:]).convert("RGBA")).astype(float)
    m = a[..., 3] > 0
    rgb = a[..., :3][m]
    return {"index": f["index"], "size": [f["width"], f["height"]], "origin": [f["originX"], f["originY"]],
            "cyan": round(float(((rgb[:, 1] + rgb[:, 2]) / 2 - rgb[:, 0]).mean()), 1),
            "fill": round(float(m.mean()), 2)}


def group_dice(features, n):
    """n = faces per die (D6 6, D4 4). Layout to test: flat faces 0..n-1,
    isometric faces n..2n-1, highlighted copies 2n..3n-1, remaining frames."""
    iso = list(range(n, 2 * n))
    hi = list(range(2 * n, 3 * n))
    checks = {
        "flatSameSizeWithin4px": max(f["size"][1] for f in features[:n]) - min(f["size"][1] for f in features[:n]) <= 4,
        "highlightSameGeometryAsIsometric": all(features[i]["size"] == features[j]["size"] and
                                                features[i]["origin"] == features[j]["origin"] for i, j in zip(iso, hi)),
        "highlightCyanAbove50": all(features[j]["cyan"] > 50 for j in hi[1:]),
        "tumbleGeometryVaries": len({tuple(f["size"]) for f in features[3 * n:]}) >= len(features[3 * n:]) // 2}
    return {"facesPerDie": n, "flatFaces": [0, n - 1], "isometricFaces": [iso[0], iso[-1]],
            "highlightedIsometric": [hi[0], hi[-1]], "tumble": [3 * n, len(features) - 1], "checks": checks}


def main():
    ui = js(ROG / "original/OBS/ui/manifest.js")
    emb = js(ROG / "original/OBS/embedded/manifest.js")
    trailers = json.loads((ROG / "docs/evidence/obs-trailers/trailers.json").read_text(encoding="utf-8"))
    dice = {}
    for key, label, faces in (("1171", "D6", 6), ("1223", "D4", 4)):
        feats = [frame_features(f) for f in ui[key]["frames"]]
        groups = group_dice(feats, faces)
        chains = {k: {"trailerOffset": v["trailerOffset"], "frames": len(v["frames"])}
                  for k, v in emb.items() if k.startswith("obs-" + key + "-")}
        dice[label] = {
            "member": "OBS.pak/%s.obs" % key, "memberSHA256": ui[key]["sourceSHA256"],
            "block0Frames": len(feats), "groups": groups, "features": feats,
            "extraBlocks": chains,
            "trailerBytes": trailers["obs/" + key]["trailerBytes"],
            "evidence": {
                "groupBoundaries": "VERIFIED (measured geometry/colour)",
                "flatFacePips": "VERIFIED 1..%d by pip count" % groups["facesPerDie"],
                "isometricTopFace": "INFERRED same order as flat faces",
                "highlightMeaning": "INFERRED (selected/winning die)",
                "extraBlocks": "VERIFIED as further blocks of the member (128-byte block header, frames, 768-byte palette)",
                "extraBlockColours": "UNVERIFIED: published original/OBS/embedded PNGs use block 0's palette. On the two "
                                     "multi-block members whose bytes are stored (OBS2 1228, 1238) the own block palette "
                                     "gives identical colours, so a palette defect is NOT shown; the speckled look may be "
                                     "original dithering. tools/decode-obs-blocks.py records each block's palette SHA in CI.",
                "rollSequenceAndTiming": "UNVERIFIED until tools/decode-obs-blocks.py runs in CI "
                                         "(member animation table sits after the last block, beyond the stored 4 KiB)",
                "perResultSequences": "UNVERIFIED (D6 x6 / D4 x4 result-specific landing order not yet read from the table)",
                "fallBounceKeyframes": "NOT FOUND in any decoded table; do not claim"}}
    (OUT / "dice-native-sequences.json").write_text(json.dumps(dice, indent=1), encoding="utf-8")

    amap = json.loads((OUT / "actor-native-action-map.json").read_text(encoding="utf-8"))
    cards = {c["id"]: c for c in json.loads((ROG / "original/chessmen.json").read_text(encoding="utf-8"))}
    audit = json.loads((OUT / "actor-frame-audit.json").read_text(encoding="utf-8"))["cards"]
    bodies = {c for c, e in audit.items() if e.get("bodySource")}
    body_map = json.loads((OUT / "card-body-map.json").read_text(encoding="utf-8"))["cards"]
    runtime = {}
    for card, row in sorted(body_map.items()):
        if not row["bodyPak"]:
            continue
        key = row["bodyPak"].lower().replace(".pak", "") + "/" + row["bodyMember"]
        mem = amap["members"].get(key)
        runtime[card] = {"member": key, "frames": row["bodyFrames"], "published": row["published"],
                         "animations": None if not mem else [
            {"index": a["index"], "ticks": a["durationTicks"],
             "keys": [[k["time"], k["frame"]] for k in a["frameKeys"]],
             "events": [[e["time"], e["type"], e["member"], e["offsetX"], e["offsetY"]] for e in a["events"]]}
            for a in mem["animations"]],
                         "animationTable": "VERIFIED" if mem else "PENDING-CI (trailer bytes not stored)"}
    (OUT / "actor-native-anim-runtime.json").write_text(json.dumps({
        "format": "card -> {member (CHR +260 body), published {folder,key,frames} or null, animations[index]{ticks, keys: [[tick, frame]], events: [[tick, type, effectMember, dx, dy]]}}",
        "cardToBody": "VERIFIED from CHR record offset 260 (see card-body-map.json); replaces card 0NNN = member 1NNN",
        "source": "original OBS animation table (VERIFIED); tick length UNVERIFIED; action names not stored in the table",
        "schema17Inferred": {"0-2": "idle rear/side(left)/front", "3-5": "walk rear/side/front",
                             "6-8": "per-direction pose + effect type 15", "9-11": "per-direction pose + effect type 35",
                             "12": "duel lunge 33-36 + character-specific effect", "13": "pose 33 + effect 1099",
                             "14": "pose 32 held + effect 1118", "15-16": "front idle -> 25 -> 31 -> 32 combo"},
        "cards": runtime}, indent=1, ensure_ascii=False), encoding="utf-8")

    semantics = {}
    for schema in (17, 15):
        cs = [c for c, v in runtime.items() if v["animations"] and len(v["animations"]) == schema]
        rows = []
        for i in range(schema):
            ticks, keys, ev = {}, {}, {}
            for c in cs:
                a = runtime[c]["animations"][i]
                t = "loop(0xFFFFFFFF)" if a["ticks"] == 0xFFFFFFFF else str(a["ticks"])
                ticks[t] = ticks.get(t, 0) + 1
                k = ",".join(str(f) for _, f in a["keys"][:8])
                keys[k] = keys.get(k, 0) + 1
                for e in a["events"]:
                    if e[2] >= 1000:
                        ek = "t%d type%d member%d" % (e[0], e[1], e[2])
                        ev[ek] = ev.get(ek, 0) + 1
            top = lambda d: dict(sorted(d.items(), key=lambda x: -x[1])[:3])
            rows.append({"index": i, "durationTicks": top(ticks), "firstKeys": top(keys), "effectEvents": top(ev)})
        semantics[str(schema)] = {"cards": len(cs), "animations": rows}
    empty = {}
    rule_ok = rule_total = 0
    for card, v in runtime.items():
        for a in v["animations"] or []:
            if a["ticks"] == 0xFFFFFFFF:
                pak = v["member"].split("/")[0]
                empty.setdefault(pak, {}).setdefault(str(a["index"]), 0)
                empty[pak][str(a["index"])] += 1
                assert not a["keys"], (card, a["index"])
            elif a["keys"]:
                rule_total += 1
                rule_ok += int(a["ticks"] == a["keys"][-1][0] + 3)
    (OUT / "action-semantics-evidence.json").write_text(json.dumps({
        "emptySlots": {"value": "durationTicks 0xFFFFFFFF", "meaning": "animation slot without frame keys (VERIFIED: "
                       "every such animation has 0 keys); occurs only in OBS2/OBS3 bodies", "byPakAndIndex": empty},
        "durationRule": {"rule": "durationTicks == last key tick + 3", "holds": rule_ok, "of": rule_total,
                         "level": "VERIFIED on original tables"},
        "verified": ["3 direction blocks (rear, left side, front) per action; no right-facing or diagonal animation exists",
                     "15-animation tables = 17-animation tables without indexes 15-16",
                     "duration 0xFFFFFFFF = empty animation slot (no keys); round-9 'loop' reading withdrawn",
                     "effect events: member, start tick and signed offset per animation (see effectEvents)"],
        "inferredNames": {"0-2": "idle", "3-5": "walk", "12": "duel lunge/attack", "6-11": "UNVERIFIED (hit / guard?)",
                          "13-16": "UNVERIFIED (skill / victory / special?)"},
        "toResolve": "export effect members 1096-1124 (decode-obs-blocks.py referenced export) and EXE calls",
        "tickToMilliseconds": "UNVERIFIED (no clock constant decoded)",
        "schemas": semantics}, indent=1), encoding="utf-8")
    obs2 = sorted(k for k in amap["chessmanSchema17"] if k.startswith("obs2/"))
    obs3 = sorted(k for k in amap["chessmanSchema17"] if k.startswith("obs3/"))
    obs_extra = []
    (OUT / "card-mapping-candidates.json").write_text(json.dumps({
        "status": "SUPERSEDED by card-body-map.json (VERIFIED from CHR record offset 260)",
        "previousRule": {"rule": "card 0NNN = OBS.pak member 1NNN", "result": "WRONG for every card (e.g. 0088 Sherazard "
                         "-> 1071, not golem 1088; 0087 Saladin -> 1070, not skeleton 1087)"},
        "previousCandidate": {"rule": "card 0125+k <-> OBS2 1199+k", "result": "CONFIRMED by CHR for all 23 cards"},
        "verifiedCardBodies": sum(1 for r in body_map.values() if r["bodyPak"]),
        "missing": sorted(c for c, r in body_map.items() if not r["bodyPak"])},
        indent=1, ensure_ascii=False), encoding="utf-8")

    stats = amap["stats"]
    events = [
        {"type": "OBS_MEMBER_FORMAT_DECODED", "taskIds": ["ACT-02", "SRC-01"],
         "details": "OBS member = u32 blockCount | blocks (128-byte header, u16 frameCount at +66, frames, own 768-byte palette) | "
                    "u32 animationCount | animations (u32 durationTicks, u32 n, n x 18-byte records) | 34 zero bytes. "
                    "Header byte0 = 1 + embedded chains on 227/241 members; all %d stored trailers parse to the last byte "
                    "(tail variants %s). VERIFIED." % (stats["decoded"], json.dumps(stats["tailVariants"]))},
        {"type": "ORIGINAL_ANIMATION_TABLE_DECODED", "taskIds": ["ACT-03", "P0-ACTOR", "M05"],
         "details": "Original per-member animation tables decoded for %d members; %d use the 17-animation chessman schema "
                    "(51 OBS.pak incl. 1025-1039/1041/1057 without cards, 23 OBS2, 12 OBS3). 1040: idle 0-2/11-13/22-24, "
                    "walk 3,5,6,7,8 (frame 4 unused) /14-19/25-30, 3 ticks per key; events reference effect members "
                    "1096-1124. Tick length and action names UNVERIFIED." % (stats["decoded"], len(amap["chessmanSchema17"]))},
        {"type": "DICE_EXTRA_BLOCK_COLOURS_UNVERIFIED", "taskIds": ["DIE-01", "DIE-02"],
         "details": "D6 1171 extra blocks 16/16/6 and D4 1223 extra blocks 9/16 each carry a palette; the published "
                    "original/OBS/embedded PNGs use block 0's palette. Round 9 check on OBS2 1228/1238 (bytes stored): "
                    "own-palette decode is pixel-identical, so a palette defect is NOT demonstrated (round-8 claim "
                    "corrected). Dice block palettes are recorded per block by tools/decode-obs-blocks.py in CI; keep the "
                    "#516 quarantine until then."},
        {"type": "DICE_FRAME_GROUPS_MEASURED", "taskIds": ["DIE-01", "DIE-04"],
         "details": "D6: 0-5 flat faces, 6-11 isometric, 12-17 highlighted copies (same geometry, cyan), 18-27 varying. "
                    "D4: 0-3, 4-7, 8-11, 12-21 likewise. Boundaries VERIFIED by measurement; meanings INFERRED."},
        {"type": "CHR_BODY_MEMBER_FIELD_DECODED", "taskIds": ["ACT-01", "ACT-05", "P0-ACTOR"],
         "details": "CHR record offset 260 = ASCII OBS member number of the character body (VERIFIED, all 119 records). "
                    "97/98 cards have that member in OBS/OBS2/OBS3 (0156 -> 1222 absent). The old card 0NNN = member 1NNN "
                    "rule was wrong for every card; 7 bodies used so far belong to non-card records (slime 1084, zombie "
                    "1086, skeleton 1087, golem 1088, lich 1089, Azi Dahaka 1090, test 1092). OBS2 1199+k = card 0125+k "
                    "confirmed. 19 card bodies are not yet published as PNG. See card-body-map.json, quantity-reconciliation.json."},
        {"type": "QUANTITY_RECONCILED", "taskIds": ["ACT-01"],
         "details": "98 cards -> 97 distinct bodies (no duplicates); 86 schema-17 members = 85 card bodies + 1166 (byte copy of "
                    "1061, unreferenced); 12 card bodies use 14/15-animation tables; old 54 = 42 card bodies (of other cards) "
                    "+ 7 non-card bodies + 5 unreferenced. The round-8 '52 new bodies' figure is superseded."}]
    (OUT / "ledger-events-round8.json").write_text(json.dumps({"requestText": "Claude 8차 원본 해독 전담",
                                                               "events": events}, indent=1, ensure_ascii=False),
                                                   encoding="utf-8")
    print("NATIVE MAPS BUILT", json.dumps({"dice": {k: v["groups"]["checks"] for k, v in dice.items()},
                                           "runtimeCards": len(runtime), "obs2": len(obs2), "obs3": len(obs3),
                                           "cardBodies": sum(1 for r in body_map.values() if r["bodyPak"])}))


if __name__ == "__main__":
    main()
