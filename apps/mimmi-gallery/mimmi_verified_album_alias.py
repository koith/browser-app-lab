"""Reconcile the same published photo work by exact SHA frame anchors.

Do NOT append a same-frame JPEG recompression to the end of a photobook.
Source frame positions are aligned to owner slots using dominant SHA anchors.
Only previously unoccupied aligned slots can be imported.
"""
from collections import Counter

def align(targets, source, public, owner):
    known = {}
    for manifest in (owner, public):
        for album in manifest["albums"]:
            rec = known.setdefault(album["id"], {"hash_to_positions": {}, "slots": set()})
            for ordinal, photo in enumerate(album.get("images", []), 1):
                position = photo.get("number")
                if type(position) is not int or position < 1:
                    position = ordinal
                rec["hash_to_positions"].setdefault(photo["sha256"], set()).add(position)
                rec["slots"].add(position)

    original = {a["id"]: a for a in source["albums"]}
    converted, proof = [], []
    for album in targets:
        images = original.get(album["id"], {}).get("samples", [])
        source_by_sha = {p["sha256"]: p.get("number", n)
                         for n, p in enumerate(images, 1)}
        ranked = sorted(
            ((sum(sha in rec["hash_to_positions"] for sha in source_by_sha), aid)
             for aid, rec in known.items()), reverse=True
        )
        best, aid = ranked[0] if ranked else (0, "")
        competing = ranked[1][0] if len(ranked) > 1 else 0
        if best < 3 or competing > max(1, best // 4):
            continue
        rec = known[aid]
        offsets = Counter()
        for sha, source_pos in source_by_sha.items():
            if type(source_pos) is not int:
                continue
            for owner_pos in rec["hash_to_positions"].get(sha, ()):
                offsets[owner_pos - source_pos] += 1
        if not offsets:
            continue
        offset, agreement = offsets.most_common(1)[0]
        # Must have a dominant number mapping, not just the same work title.
        if agreement < 3 or agreement < best * 0.75:
            proof.append({"source": album["id"], "album": aid,
                          "status": "ambiguous_frame_numbering", "shared_sha": best})
            continue
        additions, alternate_frames = [], 0
        for item in album["images"]:
            source_number = item.get("number")
            if type(source_number) is not int:
                continue
            aligned_number = source_number + offset
            if not 1 <= aligned_number <= 20000:
                continue
            # Different SHA at a populated ordinal normally means a re-encode
            # or alternate edition. Do not create a duplicate new frame.
            if aligned_number in rec["slots"]:
                alternate_frames += 1
                continue
            rec["slots"].add(aligned_number)
            rec["hash_to_positions"].setdefault(item["sha256"], set()).add(aligned_number)
            additions.append({**item, "number": aligned_number})
        proof.append({"source": album["id"], "album": aid, "shared_sha": best,
                      "aligned_offset": offset, "anchor_agreement": agreement,
                      "excluded_occupied_frame_variants": alternate_frames,
                      "new_numbered_slots": len(additions)})
        if additions:
            converted.append({**album, "id": aid, "images": additions,
                              "expected": None})
    return converted, proof
