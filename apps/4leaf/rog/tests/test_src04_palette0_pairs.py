#!/usr/bin/env python3
"""Check original bulk vs run-alpha OBS decodes, including legacy dropped index-0 pixels."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def manifest(path):
    text=path.read_text(encoding="utf-8")
    start=text.index("{")
    end=text.rindex("}")+1
    while True:
        try:return json.loads(text[start:end])
        except json.JSONDecodeError:start=text.index("{",start+1)
def main():
    full=manifest(ROOT/"original/OBS/action-full/manifest.js")
    pairs=lost_pairs=lost_total=0; per_member={}
    for card,row in sorted(full.items()):
        stem="1"+card[1:]
        for frame in row["frames"]:
            legacy=ROOT/"original/OBS/bulk"/("%s-%02d.png"%(stem,frame["index"]))
            if not legacy.exists():continue
            new=np.array(Image.open(ROOT/frame["url"][2:]).convert("RGBA"))
            old=np.array(Image.open(legacy).convert("RGBA"))
            label="%s/%s"%(card,frame["index"])
            assert new.shape==old.shape,label
            new_opaque=new[...,3]>0; old_opaque=old[...,3]>0
            assert not (old_opaque & ~new_opaque).any(),label
            shared=new_opaque & old_opaque
            assert (new[...,:3][shared]==old[...,:3][shared]).all(),label
            lost=new_opaque & ~old_opaque
            if lost.any():
                colors={tuple(c) for c in new[...,:3][lost]}
                assert len(colors)==1,(label,len(colors))
                lost_pairs+=1; lost_total+=int(lost.sum())
                per_member[card]=per_member.get(card,0)+int(lost.sum())
            pairs+=1
    assert pairs>=540,pairs
    # #522 moved the full-frame lookup into chr-body-source-map.js.
    runtime=(ROOT/"genesis-chessman-actors.js").read_text()+(ROOT/"chr-body-source-map.js").read_text()
    assert "ORIGINAL_LEAF_FULL_ACTION_FRAMES" in runtime
    print("SRC04 PALETTE0 PAIR AUDIT PASS",json.dumps({"pairs":pairs,"pairsWithLegacyIndex0Loss":lost_pairs,"lostPixels":lost_total,"members":per_member}))
if __name__=="__main__":
    main()
