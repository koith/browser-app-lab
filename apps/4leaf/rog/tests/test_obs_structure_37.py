#!/usr/bin/env python3
"""Calibrated check against 45 original 37-frame sprites; not independent validation."""
import importlib.util, json, re, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("obs_structure",ROOT/"tools/obs_structure.py")
S=importlib.util.module_from_spec(sp)
sp.loader.exec_module(S)
def synthetic_segment():
    def box(w,h):
        im=np.zeros((h,w,4),np.uint8); im[...,3]=255
        return im,-w//2,-h
    frames=[box(20,40),box(20,41),box(21,40),box(60,20),box(61,20),box(60,21),box(10,70),box(10,71)]
    assert S.segment(frames)==[(0,2),(3,5),(6,7)]
def main():
    synthetic_segment()
    _,ids=S.load_checked_in_member(ROOT,"0040")
    assert len(ids)==45,len(ids)
    txt=(ROOT/"genesis-chessman-actors.js").read_text()
    block=re.search(r"STRUCTURAL_37=Object\.freeze\(new Set\(\[(.*?)\]\)\)",txt,re.S).group(1)
    expected=set(re.findall(r"'(\d{4})'",block))
    detected=set()
    for card in ids:
        frames,_=S.load_checked_in_member(ROOT,card)
        if S.test_layout_37(frames)["matches"]:
            detected.add(card)
    assert detected==expected,{"onlyDetected":sorted(detected-expected),"onlyRuntime":sorted(expected-detected)}
    assert set(ids)-detected=={"0084","0085","0086"}
    print("OBS STRUCTURE 37 PASS",json.dumps({"members":len(ids),"layoutMatches":len(detected),"rejected":sorted(set(ids)-detected)}))
if __name__=="__main__":
    main()
