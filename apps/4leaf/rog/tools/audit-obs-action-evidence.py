#!/usr/bin/env python3
"""Rank original OBS frame-sequence evidence without inventing actions/directions.

Reads the private full-frame-report.json produced by dump-original-paks.py.
Writes JSON only: no original binaries or PNGs are published by this tool.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def geometry_runs(frames):
    """Split the native frame order into runs of near-identical canvas size.
    A run boundary is only a candidate sequence boundary (size jumps when a
    pose/direction changes); it does NOT name an action or a direction."""
    runs, current = [], None
    for f in frames:
        geo = f.get("geometry")
        if not geo or len(geo) < 4:
            current = None
            continue
        w, h = geo[0], geo[1]
        if current and abs(w - current["w"]) <= max(3, current["w"] * 0.15) and \
                abs(h - current["h"]) <= max(3, current["h"] * 0.15) and f.get("index") == current["last"] + 1:
            current["last"] = f["index"]
            current["count"] += 1
        else:
            current = {"first": f.get("index"), "last": f.get("index"), "count": 1, "w": w, "h": h}
            runs.append(current)
    return [{"frames": [r["first"], r["last"]], "count": r["count"], "size": [r["w"], r["h"]]} for r in runs]


def analyze(report):
    if report.get("format") != "4LEAF_OBS_EXHAUSTIVE_FORENSICS_V1":
        raise ValueError("Unsupported original OBS report format")
    members = []
    unreadable = []
    totals = Counter()
    for pack in report.get("packs", []):
        for member in pack.get("members", []):
            if member.get("kind") != "OBS_UNCLASSIFIED_NATIVE_MEMBER":
                continue
            header = member.get("header") or {}
            frames = member.get("frames", [])
            declared = header.get("nativeFrameCount")
            statuses = Counter(f.get("status", "UNKNOWN") for f in frames)
            total = sum(statuses.values())
            totals.update(statuses)
            if not isinstance(declared, int) or declared < 1:
                # Keep unreadable members visible instead of silently dropping them.
                unreadable.append({"pack": pack.get("name"), "member": member.get("name"),
                                   "cardIdCandidate": member.get("cardIdCandidate"),
                                   "declared": declared,
                                   "parseError": member.get("parseError") or header.get("error")})
                continue
            indices = [f.get("index") for f in frames]
            contiguous = indices == list(range(len(frames)))
            strict = statuses["STRICT_DECODED"]
            candidate = (
                declared == 37 and contiguous and total == declared
                and strict == declared
            )
            members.append({
                "pack": pack.get("name"), "member": member.get("name"),
                "cardIdCandidate": member.get("cardIdCandidate"),
                "declared": declared, "parsed": total,
                "strictDecoded": strict,
                "quarantined": statuses["QUARANTINED_LOW_OPACITY_SOURCE"],
                "failed": statuses["FAILED"],
                "unparsed": max(0, declared - total),
                "paletteTailBytes": header.get("paletteTailByteCount"),
                "paletteTailHexPrefix": header.get("paletteTailFirst64Hex"),
                "complete37FrameSequenceCandidate": candidate,
                "geometryRuns": geometry_runs(frames),
                "historicalActionMapping": "UNVERIFIED",
                "historicalDirectionMapping": "UNVERIFIED",
            })
    members.sort(key=lambda m: (
        not m["complete37FrameSequenceCandidate"],
        -(m["declared"] - m["unparsed"]), m["pack"] or "", m["member"] or ""
    ))
    return {
        "format": "4LEAF_OBS_ACTION_EVIDENCE_V1",
        "sourceReportFormat": report["format"],
        "warning": "37 consecutive decoded frames do not establish historical actions, directions, or frame timing.",
        "membersInspected": len(members),
        "unreadableMembers": unreadable,
        "complete37FrameCandidates": sum(m["complete37FrameSequenceCandidate"] for m in members),
        "observedFrameStatuses": dict(totals),
        "members": members,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("full_frame_report", type=Path)
    p.add_argument("output_json", type=Path)
    a = p.parse_args()
    data = analyze(json.loads(a.full_frame_report.read_text(encoding="utf-8")))
    a.output_json.parent.mkdir(parents=True, exist_ok=True)
    a.output_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OBS_ACTION_EVIDENCE", data["membersInspected"], data["complete37FrameCandidates"])


if __name__ == "__main__":
    main()
