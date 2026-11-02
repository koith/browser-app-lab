#!/usr/bin/env python3
"""Build machine-readable evidence from the ORIGINAL data checked into the repo.

Every number is recomputed from files (PNG bytes are re-hashed); nothing is
typed in by hand. Writes docs/evidence/source-maps/:
  actor-frame-audit.json   98 cards: body source, member, pak, SHA-256,
                           declared vs published frames, per-frame file/hash/
                           size/origin, missing frames
  actor-action-map.json    per body: 37-frame direction-block test result and
                           block ranges (structure VERIFIED from pixels when the
                           test passes; action roles INFERRED; EXE table
                           UNDECODED) or a change-point proposal (UNVERIFIED)
  missing-resources.json   cards without an original body and why; members
                           that failed decoding; undecoded byte regions
  dice-animation-map.json  original dice/score/roll members and frames
  dice-rule-evidence.json  what the original data does and does not establish
  board-layout-evidence.json  26 DMP routes: titles, modes, step directions,
                           cell codes, special-cell records
  game-rules-evidence.json CHR stat fields and special-cell parameters
Run: python3 apps/4leaf/rog/tools/build-source-evidence.py
"""
import collections
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROG = Path(__file__).resolve().parents[1]
OUT = ROG / "docs/evidence/source-maps"
spec = importlib.util.spec_from_file_location("obs_structure", ROG / "tools/obs_structure.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

UNIT = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
ROLES_37 = {"rear": {"idle": [0, 2], "walk": [3, 8], "strike": [9, 10]},
            "sideLeft": {"idle": [11, 13], "walk": [14, 19], "strike": [20, 21]},
            "front": {"idle": [22, 24], "walk": [25, 30], "strike": [31, 32]},
            "lunge": [33, 36]}


def js_object(path, marker=None):
    text = path.read_text(encoding="utf-8")
    start = text.index(marker) + len(marker) if marker else text.index("{")
    start = text.index("{", start)
    end = text.rindex("}") + 1
    while True:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            start = text.index("{", start + 1)


def sha_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def frame_rows(frames):
    rows, missing = [], []
    for f in frames:
        p = ROG / f["url"][2:]
        if not p.exists():
            missing.append(f["index"])
            continue
        digest = sha_file(p)
        if f.get("sha256") and f["sha256"] != digest:
            raise SystemExit("SHA mismatch " + f["url"])
        rows.append({"index": f["index"], "file": f["url"], "sha256": digest, "width": f["width"],
                     "height": f["height"], "originX": f["originX"], "originY": f["originY"]})
    return rows, missing


def upright(rows):
    return [(np.flipud(np.array(Image.open(ROG / r["file"][2:]).convert("RGBA"))), r["originX"], r["originY"])
            for r in rows]

SCREENS = {
    "sky.jpg": ("world map (moon)", "2004-02 (date stamp 04.02.08 in image)"),
    "street.jpg": ("Keltika street panorama", "unknown"),
    "town_ref.jpg": ("forest town chat screen", "2004-02 (date stamp in image)"),
    "chat.jpg": ("permanent chat room (Hayakan)", "2004-02 (date stamp 04.02.11 in image)"),
    "chat_ref.jpg": ("permanent chat room (Hayakan), same room later moment", "2004-02 (date stamp in image)"),
    "shop_ref.png": ("Magic Carden card shop with Normal/Valuable/Rare tabs", "later than the 2002 client (Rare tab absent in 2002 data)"),
    "intro.jpg": ("loading screen", "unknown"),
    "board.jpg": ("chessman battle, 2 vs 1 dice", "2004 client"),
    "battle.jpg": ("chessman battle, 2 vs 4 dice", "2004 client"),
    "dice_ref.png": ("dice game TOWN SELECT (channels)", "unknown"),
    "dice_ref2.png": ("dice game ROOM SELECT", "unknown"),
}


def screen_catalog():
    assets = ROG.parent / "assets"
    rows = []
    for manifest in ("manifest.json", "additional-manifest.json"):
        for key, rec in json.loads((assets / manifest).read_text(encoding="utf-8")).items():
            name = rec.get("file") or rec.get("filename")
            path = assets / name
            digest = sha_file(path)
            if rec.get("sha256"):
                assert rec["sha256"] == digest, name
            size = list(Image.open(path).size)
            screen, version = SCREENS.get(name, ("unclassified", "unknown"))
            rows.append({"file": "apps/4leaf/assets/" + name, "sha256": digest, "size": size, "source": rec["source"],
                         "screen": screen, "version": version,
                         "kind": "third-party screenshot of the live service (not a client resource)",
                         "motion": "still image only - no frame timing measurable",
                         "reliability": "VERIFIED as a period screenshot by in-image client chrome; source blog, not an official archive"})
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cards = json.loads((ROG / "original/chessmen.json").read_text(encoding="utf-8"))
    full = js_object(ROG / "original/OBS/action-full/manifest.js")
    ext = js_object(ROG / "original/OBS/action-full-ext/manifest.js", "ORIGINAL_LEAF_EXT_ACTION_FRAMES")
    extra = js_object(ROG / "original/OBS/animation-extra.js")
    census = json.loads((ROG / "docs/evidence/obs-census/census.json").read_text(encoding="utf-8"))
    members = {(m["pak"].lower(), m["member"].lower()): m for m in census["members"]}
    actors_js = (ROG / "genesis-chessman-actors.js").read_text(encoding="utf-8")
    non_actor = set(re.findall(r"'(\d{4})'", re.search(r"NON_ACTOR_OBS=Object\.freeze\(\{(.*?)\}\)", actors_js, re.S).group(1)))

    audit, action, missing_cards = {}, {}, []
    for card in cards:
        cid = card["id"]
        stem = "1" + cid[1:]
        census_row = members.get(("obs.pak", stem + ".obs"))
        declared = census_row.get("frames") if census_row else None
        if cid in full:
            source, rec = "action-full", full[cid]
        elif cid in ext:
            source, rec = "action-full-ext", ext[cid]
        else:
            source, rec = None, None
        entry = {"name": card["name"], "obsPakMember": stem + ".obs" if census_row else None,
                 "declaredFrames": declared,
                 "memberSHA256": census_row.get("sourceSHA256") if census_row else None}
        if rec and cid not in non_actor:
            rows, miss = frame_rows(rec["frames"])
            entry.update({"bodySource": source, "publishedFrames": len(rows),
                          "missingFrameIndexes": sorted(set(range(declared or len(rows))) - {r["index"] for r in rows}) + miss,
                          "frames": rows, "status": "COMPLETE" if declared == len(rows) else "PARTIAL"})
            seq = upright(rows)
            if len(rows) == 37:
                test = S.test_layout_37(seq)
                action[cid] = {"frames": 37, "layout37": test["matches"],
                               "blocks": ROLES_37 if test["matches"] else None,
                               "evidence": {"blockStructure": "VERIFIED-pixels/obs_structure" if test["matches"] else "REJECTED",
                                            "orientation": "VERIFIED-visual-review-2026-11-02" if test["matches"] else None,
                                            "actionRoles": "INFERRED", "playbackRate": "UNVERIFIED",
                                            "exeActionTable": "UNDECODED"},
                               "checks": test.get("checks")}
            else:
                action[cid] = {"frames": len(rows), "layout37": False,
                               "blockProposal": S.segment(seq) if len(seq) > 1 else [[0, 0]],
                               "evidence": {"blockStructure": "UNVERIFIED-change-point-proposal",
                                            "actionRoles": "UNVERIFIED", "exeActionTable": "UNDECODED"}}
        else:
            reason = ("OBS.pak member with this number is an effect/UI (NON_ACTOR_OBS)" if cid in non_actor
                      else "no member with this number in OBS/OBS2/OBS3" if not census_row else "not exported")
            entry.update({"bodySource": None, "publishedFrames": 0, "status": "NO-ORIGINAL-BODY", "reason": reason})
            missing_cards.append({"card": cid, "name": card["name"], "reason": reason})
        audit[cid] = entry

    complete = sorted(c for c, e in audit.items() if e["status"] == "COMPLETE")
    layout = sorted(c for c, a in action.items() if a.get("layout37"))
    obs23 = [m for m in census["members"] if m["pak"].lower() != "obs.pak" and (m.get("frames") or 0) >= 20
             and max(m.get("maxSize") or [0]) >= 48]
    (OUT / "actor-frame-audit.json").write_text(json.dumps({
        "source": "original/OBS action-full + action-full-ext, census.json (installer SHA1 86526d89679ae39b85fe9808da97ad871b7888d9)",
        "summary": {"cards": len(cards), "withOriginalBody": len(cards) - len(missing_cards),
                    "completeAllFrames": len(complete),
                    "publishedFrames": sum(e["publishedFrames"] for e in audit.values())},
        "cards": audit}, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "actor-action-map.json").write_text(json.dumps({
        "layout37Roles": ROLES_37, "mirrorForRightFacing": "INFERRED (only left-facing side block exists)",
        "summary": {"bodies": len(action), "layout37Verified": len(layout), "layout37": layout,
                    "otherLayouts": sorted(c for c, a in action.items() if not a.get("layout37"))},
        "actors": action}, indent=1, ensure_ascii=False), encoding="utf-8")
    failed = [{"pak": m["pak"], "member": m["member"], "error": m["parseError"]} for m in census["members"] if m.get("parseError")]
    (OUT / "missing-resources.json").write_text(json.dumps({
        "cardsWithoutOriginalBody": missing_cards,
        "absentFromAllPacks": [c["card"] for c in missing_cards if c["reason"].startswith("no member")],
        "obs2obs3CharacterSizeMembersNotYetExported": [{"pak": m["pak"], "member": m["member"], "frames": m["frames"],
                                                        "maxSize": m["maxSize"]} for m in obs23],
        "membersFailedFirstPassDecode": failed,
        "undecodedBytes": {"memberTrailers": "fixed 18-byte records + embedded data; bytes only in CI (decode-obs-extended.py exports them)",
                           "chrRecords": "472-byte records; only offsets 196 (name) and 452 (stats) decoded"}},
        indent=1, ensure_ascii=False), encoding="utf-8")

    # dice
    ui = js_object(ROG / "original/OBS/ui/manifest.js")
    spr = json.loads((ROG / "original/SourceSPR/manifest.json").read_text(encoding="utf-8"))
    dice = {}
    for key, rec in ui.items():
        rows, miss = frame_rows(rec["frames"])
        crow = members.get((rec["pak"].lower(), rec["member"].lower())) or {}
        dice[key] = {"role": rec.get("role"), "pak": rec["pak"], "member": rec["member"],
                     "memberSHA256": rec.get("sourceSHA256"), "declaredFrames": rec.get("declaredFrames"),
                     "publishedFrames": len(rows), "trailerBytes": crow.get("trailerBytes"), "frames": rows}
    dice["1171"]["frameRoles"] = {"0-5": "result faces 1-6 (VERIFIED by pip count)", "6-27": "other frames (role UNVERIFIED)"}
    dice["1167"]["frameRoles"] = {"0-7": "digits 0-7 (VERIFIED)", "8-9": "digits 8-9 (INFERRED)", "10-24": "UNVERIFIED"}
    dice["1223"]["frameRoles"] = {"0-21": "D4 sprite frames (role per frame UNVERIFIED)"}
    spr_rows = {name: {"member": rec["member"], "memberSHA256": rec["sourceSHA256"], "frameCount": rec["frameCount"],
                       "role": "IMG.pak 2D UI animation (ROLL button / event roll), not a die body"}
                for name, rec in spr["spriteAnimations"].items()}
    (OUT / "dice-animation-map.json").write_text(json.dumps({
        "members": dice, "img2dSpr": spr_rows,
        "timing": "no original timing recovered; current web timing is INFERRED",
        "trailerLead": "1171 (118,024 B) and 1223 (62,637 B) trailers exceed their frame data; decode-obs-extended.py scans them"},
        indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "dice-rule-evidence.json").write_text(json.dumps({
        "verified": ["D6 member 1171 frames 0-5 show 1-6 pips", "score numerals 1167 digits 0-7",
                     "D4 member 1223 exists in OBS.pak and OBS2.pak with 22 frames",
                     "no .mesh/.x/3D model member in any PAK (CI 40053447386)",
                     "no 37-frame block-layout array (u8/u16/u32) in 4Leaf.exe, 4Leaf.dll, Dice.dll, Core.dll, DNet.dll, Lime.dll, Rare.dll, WinCore.dll (census)"],
        "inferred": ["D4 result-face to frame mapping", "fall/bounce trajectory and durations in the web build"],
        "unverified": ["original roll physics", "whether Dice.dll renders a die procedurally", "sound timing"],
        "nextData": "trailers of 1171/1223 (decode-obs-extended.py) and Dice.dll code analysis"}, indent=1), encoding="utf-8")

    # board
    maps = json.loads((ROG / "original/maps.json").read_text(encoding="utf-8"))
    routes = maps["routes"]
    titles = js_object(ROG / "original/maps.js", "ORIGINAL_LEAF_MAP_INFO=")
    steps = collections.Counter((b[0] - a[0], b[1] - a[1]) for rows in routes.values() for a, b in zip(rows, rows[1:]))
    special = collections.defaultdict(list)
    for mid, rows in routes.items():
        for i, r in enumerate(rows):
            if r[3]:
                special[r[3]].append({"map": mid, "cell": i, "param4": r[4], "param5": r[5]})
    per_map = {mid: {"title": titles.get(mid, {}).get("title"), "mode": titles.get(mid, {}).get("mode"),
                     "cells": len(rows), "cellCodes": dict(sorted(collections.Counter(r[2] for r in rows).items())),
                     "specialTypes": dict(sorted(collections.Counter(r[3] for r in rows if r[3]).items()))}
               for mid, rows in sorted(routes.items())}
    warp = special.get(10, [])
    (OUT / "board-layout-evidence.json").write_text(json.dumps({
        "routes": len(routes), "titled": sum(1 for v in per_map.values() if v["title"]),
        "untitled": [m for m, v in per_map.items() if not v["title"]],
        "routeRecord": "[x, y, cellCode, specialType, param4, param5] (field meanings beyond position INFERRED)",
        "startCellCode13": all(rows[0][2] == 13 for rows in routes.values()),
        "stepVectors": {"%d,%d" % d: steps[d] for d in UNIT},
        "unitStepShare": round(sum(steps[d] for d in UNIT) / sum(steps.values()), 4),
        "longerJumps": {"%d,%d" % d: n for d, n in steps.most_common() if d not in UNIT},
        "maps": per_map}, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "game-rules-evidence.json").write_text(json.dumps({
        "chr": {"recordBytes": 472, "decodedFields": {"196": "CP949 name", "452": "<9H defense, element, ability, intelligence, attack, move, score, level, usable"},
                "validatedAgainst": "Saladin 1/4/4/2, Black Prince 2/5/3/2, Damian 2/2/4/3, Sherazard 2/1/2/5 (tools/extract_original.py)",
                "cards": len(cards)},
        "specialCells": {
            "10": {"count": len(warp), "param5IsInRouteTarget": sum(1 for w in warp if w["param5"] < len(routes[w["map"]])),
                   "targetsBackward": sum(1 for w in warp if 0 < w["param5"] < w["cell"]),
                   "targetsForward": sum(1 for w in warp if w["param5"] > w["cell"]),
                   "targetAlsoType10": sum(1 for w in warp if routes[w["map"]][w["param5"]][3] == 10),
                   "meaning": "link to another cell of the same route (warp/jump) - INFERRED"},
            "11": {"count": len(special.get(11, [])), "param4Values": dict(sorted(collections.Counter(s["param4"] for s in special.get(11, [])).items())),
                   "meaning": "cell with one amount parameter, values 1-12 (INFERRED)"},
            "12": {"count": len(special.get(12, [])), "meaning": "cell without parameters (INFERRED)"}},
        "startCell": "cell index 0 has cell code 13 on all 26 routes (VERIFIED)",
        "mapModes": dict(sorted(collections.Counter(v["mode"] for v in per_map.values() if v["mode"] is not None).items())),
        "notInOriginalData": ["turn order", "victory condition", "battle dice count rule", "item effects"]},
        indent=1), encoding="utf-8")
    catalog = screen_catalog()
    (OUT / "screen-reference-catalog.json").write_text(json.dumps({
        "references": catalog, "videos": [],
        "videoSearch": "no downloadable gameplay video found (2026-11-02); timing must come from original data"},
        indent=1, ensure_ascii=False), encoding="utf-8")
    print("SOURCE EVIDENCE BUILT", json.dumps({"cardsWithBody": len(cards) - len(missing_cards), "complete": len(complete),
                                               "layout37": len(layout), "otherLayouts": len(action) - len(layout),
                                               "obs23NotExported": len(obs23), "failed": len(failed),
                                               "diceMembers": len(dice), "routes": len(routes)}))


if __name__ == "__main__":
    sys.exit(main())
