#!/usr/bin/env python3
"""Card -> original body from the ORIGINAL CHR records (Dice/CHR.pak).

472-byte CHR record fields found in docs/evidence/obs-trailers/chr.json
(hex of every record, SHA1-verified installer):
  0    ASCII author id          64  ASCII timestamp      128 ASCII version
  196  CP949 name (decoded before)
  260  ASCII OBS member number of the character's BODY   <- decoded here
  324  CP949 constellation (or "NULL")
  452  9 x u16 stats (decoded before)
The member number at +260 replaces the old project convention
"card 0NNN = OBS.pak member 1NNN", which was wrong (e.g. card 0088
Sherazard -> 1071, not the golem 1088).
Writes docs/evidence/source-maps/card-body-map.json and quantity-reconciliation.json.
Run: python3 apps/4leaf/rog/tools/decode-chr-model-map.py
"""
import hashlib
import json
import re
from pathlib import Path

ROG = Path(__file__).resolve().parents[1]
OUT = ROG / "docs/evidence/source-maps"


def text(raw, a, b, enc="ascii"):
    return raw[a:b].split(b"\0")[0].decode(enc, "replace")


def js(path):
    t = path.read_text(encoding="utf-8")
    return json.loads(t[t.index("={") + 1:t.rindex(";")])


def main():
    chr_records = json.loads((ROG / "docs/evidence/obs-trailers/chr.json").read_text(encoding="utf-8"))["records"]
    cards = {c["id"]: c for c in json.loads((ROG / "original/chessmen.json").read_text(encoding="utf-8"))}
    census = json.loads((ROG / "docs/evidence/obs-census/census.json").read_text(encoding="utf-8"))
    amap = json.loads((OUT / "actor-native-action-map.json").read_text(encoding="utf-8"))["members"]
    pack_sha = {p["name"]: p["sha256"] for p in census["packs"]}
    members = {}
    for m in census["members"]:
        members.setdefault(m["member"][:-4], []).append({"pak": m["pak"], "frames": m.get("frames"),
                                                         "sha256": m["sourceSHA256"]})
    # published frame sets: action-full/-ext are keyed by '0'+member[1:], obs23-actors by pak/member
    published = {}
    for folder in ("action-full", "action-full-ext"):
        p = ROG / "original/OBS" / folder / "manifest.js"
        t = p.read_text(encoding="utf-8")
        data = json.loads(t[t.index("{"):t.rindex("}") + 1]) if folder == "action-full" else js(p)
        for key, rec in data.items():
            published[("obs.pak", "1" + key[1:])] = {"folder": folder, "key": key, "frames": len(rec["frames"])}
    for key, rec in js(ROG / "original/OBS/obs23-actors/manifest.js").items():
        pak, mem = key.split("/")
        published[(pak + ".pak", mem)] = {"folder": "obs23-actors", "key": key, "frames": len(rec["frames"])}

    rows = {}
    for name, hexraw in sorted(chr_records.items()):
        raw = bytes.fromhex(hexraw)
        rid = name[:4]
        body = text(raw, 260, 324)
        found = members.get(body, [])
        body_pak = found[0]["pak"] if found else None
        table = amap.get(body_pak.lower().replace(".pak", "") + "/" + body) if body_pak else None
        pub = published.get((body_pak.lower(), body)) if body_pak else None
        rows[rid] = {
            "name": text(raw, 196, 260, "cp949"), "isCard": rid in cards,
            "bodyMember": body, "bodyPak": body_pak,
            "bodyPaks": [f["pak"] for f in found], "bodyFrames": found[0]["frames"] if found else None,
            "bodySHA256": found[0]["sha256"] if found else None,
            "animationCount": table["animationCount"] if table else None,
            "published": pub, "constellation": text(raw, 324, 388, "cp949"),
            "provenance": {"chrPak": "Dice/CHR.pak", "chrRecord": name, "chrRecordSHA256": hashlib.sha256(raw).hexdigest(),
                           "offsets": {"name": 196, "bodyMember": 260, "constellation": 324, "stats": 452},
                           "bodyPakSHA256": pack_sha.get(body_pak) if body_pak else None,
                           "installerSHA1": "86526d89679ae39b85fe9808da97ad871b7888d9",
                           "level": "VERIFIED" if found else "VERIFIED-ABSENT"},
            "status": ("VERIFIED-CHR+member-present" if found else "CHR-names-member-absent-from-all-packs")}
    card_rows = {k: v for k, v in rows.items() if v["isCard"]}
    assert set(card_rows) == set(cards), sorted(set(cards) ^ set(card_rows))
    (OUT / "card-body-map.json").write_text(json.dumps({
        "source": "Dice/CHR.pak record offset 260 (ASCII OBS member number), SHA1-verified installer",
        "evidence": "VERIFIED: original record field; all values are OBS member numbers; names match bodies "
                    "(e.g. 0091 Iron Mask -> 1074 masked knight, 0170 Black Prince -> 1267 dark knight)",
        "supersedes": "card 0NNN = OBS.pak member 1NNN convention (wrong for every card)",
        "cards": card_rows, "nonCardRecords": {k: v for k, v in rows.items() if not v["isCard"]}},
        indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    body_set = {(v["bodyPak"], v["bodyMember"]) for v in card_rows.values() if v["bodyPak"]}
    schema17 = {(k.split("/")[0].upper().replace("OBS", "OBS") + ".pak" if False else
                 {"obs": "OBS.pak", "obs2": "OBS2.pak", "obs3": "OBS3.pak"}[k.split("/")[0]], k.split("/")[1])
                for k, v in amap.items() if v["animationCount"] == 17}
    old54 = {("OBS.pak", "1" + c[1:]) for c in json.loads((OUT / "actor-frame-audit.json").read_text(encoding="utf-8"))["cards"]
             if json.loads((OUT / "actor-frame-audit.json").read_text(encoding="utf-8"))["cards"][c].get("bodySource")}
    npc_bodies = {(v["bodyPak"], v["bodyMember"]) for v in rows.values() if not v["isCard"] and v["bodyPak"]}
    unpublished = sorted("%s/%s" % b for b in body_set if (b[0].lower(), b[1]) not in published)
    rec = {
        "cards": len(cards),
        "cardsWithBodyMemberPresent": sum(1 for v in card_rows.values() if v["bodyPak"]),
        "cardsWithBodyMissing": sorted(k for k, v in card_rows.items() if not v["bodyPak"]),
        "distinctCardBodies": len(body_set),
        "cardBodiesPublishedAsPNG": len(body_set) - len(unpublished),
        "cardBodiesNotYetPublished": unpublished,
        "schema17Members": len(schema17),
        "schema17UsedByCards": len(schema17 & body_set),
        "schema17UsedByNonCardRecordsOnly": sorted("%s/%s" % b for b in (schema17 & npc_bodies) - body_set),
        "schema17Unreferenced": sorted("%s/%s" % b for b in schema17 - body_set - npc_bodies),
        "cardBodiesNotSchema17": len(body_set - schema17),
        "old54": {"members": len(old54),
                  "stillACardBody": len(old54 & body_set),
                  "actuallyNonCardBodies": sorted("%s/%s" % b for b in (old54 & npc_bodies) - body_set),
                  "neitherCardNorRecord": sorted("%s/%s" % b for b in old54 - body_set - npc_bodies)},
        "old52NewBodies": "superseded: the 86 schema-17 members split as above",
        "duplicateCardBodies": sorted({v["bodyMember"] for v in card_rows.values() if v["bodyPak"]
                                       and sum(1 for w in card_rows.values() if w["bodyMember"] == v["bodyMember"]) > 1})}
    (OUT / "quantity-reconciliation.json").write_text(json.dumps(rec, indent=1, sort_keys=True), encoding="utf-8")
    print("CHR MODEL MAP", json.dumps({k: (v if not isinstance(v, list) or len(v) < 8 else len(v)) for k, v in rec.items()
                                       if k != "old54"}, ensure_ascii=False), "old54", json.dumps(
        {k: (v if not isinstance(v, list) else len(v)) for k, v in rec["old54"].items()}))


if __name__ == "__main__":
    main()
