#!/usr/bin/env python3
"""Synthetic verification of the round-10 original-byte parser. Real source tests run in Actions."""
import importlib.util,struct
from pathlib import Path
f=Path(__file__).resolve().parents[1]/"tools/decode-obs-referenced-round10.py"
spec=importlib.util.spec_from_file_location("round10",f)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert len(m.MISSING)==19 and ("obs","1025") in m.MISSING and ("obs3","1256") in m.MISSING
assert ("obs","1222") not in m.MISSING
def frame_action(ticks,indices):
    records=b"".join(struct.pack("<9H",t,3,0,0,n,0,0,0,0) for t,n in indices)
    return struct.pack("<II",ticks,len(indices))+records
blob=struct.pack("<I",2)+frame_action(0xffffffff,[])+frame_action(9,[(0,0),(3,1),(6,2)])+bytes(34)
a=m.parse_actions(blob)
assert len(a)==2 and a[0]["undefined"] and a[0]["keys"]==[]
assert not a[1]["undefined"] and a[1]["keys"]==[[0,0],[3,1],[6,2]]
raw=bytearray(4)+bytearray(128)
struct.pack_into("<I",raw,0,1)
struct.pack_into("<H",raw,4+66,1)
raw+=struct.pack("<IHHhh",4,2,2,-3,11)+bytes(4)+bytes(range(256))*3
raw+=struct.pack("<I",1)+frame_action(0xffffffff,[])+bytes(34)
blocks,tail=m.member_blocks(raw)
assert len(blocks)==1 and blocks[0][0][0][2:]==(2,2,-3,11)
assert len(blocks[0][1])==768 and m.parse_actions(tail)[0]["undefined"]
print("ROUND10 SOURCE PARSER SYNTHETIC PASS: member blocks, own palette, empty action")
