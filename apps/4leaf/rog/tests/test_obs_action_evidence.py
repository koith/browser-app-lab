#!/usr/bin/env python3
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tools/audit-obs-action-evidence.py"
spec = importlib.util.spec_from_file_location("obs_evidence", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def frames(count, bad=None):
    return [{"index": i, "status": "FAILED" if i == bad else "STRICT_DECODED"} for i in range(count)]

def member(name, count, items):
    return {"kind": "OBS_UNCLASSIFIED_NATIVE_MEMBER", "name": name,
            "header": {"nativeFrameCount": count}, "frames": items}

def test():
    report = {"format": "4LEAF_OBS_EXHAUSTIVE_FORENSICS_V1",
              "packs": [{"name": "OBS.pak", "members": [
                  member("1040.obs", 37, frames(37)),
                  member("1041.obs", 37, frames(36)),
                  member("1042.obs", 37, frames(37, bad=9)),
                  member("1043.obs", 8, frames(8))]}]}
    result = mod.analyze(report)
    assert result["complete37FrameCandidates"] == 1
    assert result["members"][0]["member"] == "1040.obs"
    assert result["observedFrameStatuses"]["FAILED"] == 1
    assert all(m["historicalActionMapping"] == "UNVERIFIED" for m in result["members"])

if __name__ == "__main__":
    test()
    print("PASS")
