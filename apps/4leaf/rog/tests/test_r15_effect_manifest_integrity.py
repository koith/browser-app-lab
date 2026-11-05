#!/usr/bin/env python3
"""Verify every R15 archived OBS effect PNG against its own source manifest.

This is independent of the extractor's exit code and checks the GitHub tree
after commit. No fake or mismatched frame, size, source member or event may
pass as historic 2002 source. No EXE/DLL code executed.
"""
import hashlib
import json
import re
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
EFFECTS=ROOT/"original/OBS/duel-effects"
AUDIT=ROOT/"docs/evidence/r15/duel-effect-source-audit.json"
RUNTIME=ROOT/"docs/evidence/source-maps/actor-native-anim-runtime.json"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load_manifest():
    text=(EFFECTS/"manifest.js").read_text(encoding="utf-8")
    prefix="window.ORIGINAL_LEAF_DUEL_EFFECTS="
    assert text.startswith("/* R15 source OBS native events, no claimed semantic action labels. */\n"+prefix)
    return json.loads(text.split(prefix,1)[1].removesuffix(";\n"))

class TestR15OriginalEffects(unittest.TestCase):
    def test_archive_pixels_and_exact_events(self):
        manifest=load_manifest()
        audit=json.loads(AUDIT.read_text(encoding="utf-8"))
        runtime=json.loads(RUNTIME.read_text(encoding="utf-8"))
        events={}
        for card,data in runtime["cards"].items():
            for anim in data["animations"]:
                for raw in anim.get("events",[]):
                    if len(raw)!=5:continue
                    tick,typ,member,dx,dy=map(int,raw)
                    if member<1000:continue
                    events.setdefault(str(member),[]).append([card,anim["index"],tick,typ,dx,dy])
        count=0
        for source,member in manifest.items():
            self.assertRegex(source,r"^(obs|obs2|obs3)\.pak/\d{4}\.obs$")
            self.assertEqual(member["originalMember"],source)
            self.assertEqual(member["status"],"SOURCE-PIXELS-VERIFIED/ROLE-UNVERIFIED")
            self.assertRegex(member["sourceSHA256"],r"^[0-9a-f]{64}$")
            numeric=source.rsplit("/",1)[1][:-4]
            self.assertEqual(sorted(member["nativeEvents"]),sorted(events[numeric]),
                             "native event tuple was changed or assigned to wrong body")
            seen=set()
            for i,row in enumerate(member["frames"]):
                self.assertEqual(row["index"],i,"native source frames must remain contiguous")
                url=row["url"]
                self.assertRegex(url,r"^\./original/OBS/duel-effects/(obs|obs2|obs3)-\d{4}-\d{3}\.png$")
                path=ROOT/url.removeprefix("./")
                # A verified event reference must not silently borrow a
                # different PAK, member or keyframe PNG (even if both files
                # contain valid source bytes and their own SHA).
                expected=source.split(".")[0]+"-"+numeric+"-"+str(i).zfill(3)+".png"
                self.assertEqual(path.name,expected,"cross-member native image substitution")
                self.assertTrue(path.is_file(),str(path))
                data=path.read_bytes()
                self.assertEqual(sha(data),row["sha256"],str(path))
                self.assertEqual(row["bodySHA256"].__len__(),64)
                self.assertNotIn(path.name,seen);seen.add(path.name)
                with Image.open(path) as image:
                    self.assertEqual(image.format,"PNG")
                    self.assertEqual(image.mode,"RGBA")
                    self.assertEqual(image.size,(row["width"],row["height"]))
                    self.assertGreater(image.getchannel("A").getbbox()[2],0)
                count+=1
            self.assertGreater(len(seen),0)
        self.assertEqual(len(manifest),audit["summary"]["decodedMembers"])
        self.assertEqual(count,audit["summary"]["sourceFrames"])
        self.assertGreaterEqual(len(manifest),28,"R15 round-1 native members must remain present")
        self.assertGreaterEqual(count,420,"R15 round-1 source frames must not be discarded")
        self.assertEqual(sum(len(m["frames"]) for m in manifest.values()),count)
        self.assertEqual(audit["originalInstallerSHA1"],"86526d89679ae39b85fe9808da97ad871b7888d9")
        self.assertEqual(sha(RUNTIME.read_bytes()),audit["runtimeDataSHA256"])
        # New candidate IDs can be non-OBS sound/effect references. Their
        # absence is valid negative source evidence, never a synthetic PNG.
        self.assertEqual(set(audit["summary"]["missingMembers"]) &
                         {"1096","1097","1098","1099","1101","1102","1112","1114","1118","1124"},set())
        self.assertTrue(all(key.isdigit() for key in audit["summary"]["missingMembers"]))

if __name__=="__main__":
    unittest.main()
