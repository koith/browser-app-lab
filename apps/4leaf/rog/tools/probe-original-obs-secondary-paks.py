#!/usr/bin/env python3
"""Read-only source-original chessman recovery across ALL 2002 Dice/OBS*.pak.

The revival previously audited only OBS.pak. The source installer also has
OBS2.pak (53 entries) and OBS3.pak (26 entries), and source OBS3 duplicates
1134.obs, missing from the currently published body manifest.

This probe creates strict-decoder PNG *candidates* in a temporary directory.
Never changes the live game's manifest, invented X scanline offsets, or
native action mapping. Every generated file remains quarantined until
reviewed and explicitly merged as source pixels with correct provenance.
"""
import hashlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MODULE=Path(__file__).with_name("decode-original-obs-bulk.py")
spec=importlib.util.spec_from_file_location("obs_source_codec",MODULE)
codec=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=codec
spec.loader.exec_module(codec)

def manifest_ids():
    directory=ROOT/"original/OBS"
    ids=set()
    for filename in ("animation-manifest.js","animation-extra.js"):
        text=(directory/filename).read_text(encoding="utf-8")
        ids.update(re.findall(r'^\s*"(\d{4})":\s*\{',text,re.M))
    return ids

def scan(folder,target):
    cards={c["id"] for c in json.loads((ROOT/"original/chessmen.json").read_text(encoding="utf-8"))}
    recovered=manifest_ids()
    missing=cards-recovered
    report={"source":"SHA1-confirmed 2002 4LEAF v0.96d original installer",
       "classification":"STRICT SOURCE PNG CANDIDATES / QUARANTINED NOT LIVE",
       "availableCards":len(cards),"publishedBodies":len(cards-missing),
       "missingBefore":sorted(missing),"paks":{},"newStrictCandidates":[]}
    for pack in ("OBS.pak","OBS2.pak","OBS3.pak"):
        files=list(folder.rglob(pack))
        if len(files)!=1:
            raise ValueError("Require exactly one authentic "+pack+" in source installer; found "+str(len(files)))
        data=files[0].read_bytes()
        entries=[]
        for name,member in codec.source_members(data):
            if not re.fullmatch(r"1\d{3}\.obs",name.lower()):continue
            cid=f"{int(name[:4])-1000:04d}"
            if cid not in missing:continue
            item={"member":name,"cardId":cid,"sourceSHA256":hashlib.sha256(member).hexdigest(),"strictFrames":[]}
            try:
                frames,palette=codec.unpack_frames(member)
            except ValueError as exc:
                item["failure"]=str(exc)
                entries.append(item);continue
            for index in codec.FRAMES:
                if index>=len(frames):continue
                pixels,w,h,ox,oy=frames[index]
                try:
                    img,confidence=codec.decode_rows(pixels,w,h,palette)
                except ValueError:continue
                buffer=io.BytesIO()
                img.save(buffer,format="PNG",optimize=True)
                png=buffer.getvalue()
                rel=f"{pack.removesuffix('.pak')}/{name.removesuffix('.obs')}-{index:02}.png"
                out=target/rel
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(png)
                item["strictFrames"].append({"index":index,"dimensions":[w,h],
                   "origin":[ox,oy],"sha256":hashlib.sha256(png).hexdigest(),
                   "relativePath":rel,"provisional":confidence["decoder"]})
            entries.append(item)
            if item["strictFrames"]:
                report["newStrictCandidates"].append({"pack":pack,**item})
        report["paks"][pack]={"sourceSHA256":hashlib.sha256(data).hexdigest(),
          "cardMembersPreviouslyMissing":len(entries),
          "strictRecoverableMembers":sum(bool(e["strictFrames"]) for e in entries),
          "entries":entries}
    (target/"secondary-pak-probe.json").write_text(json.dumps(report,ensure_ascii=False,
        indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("ORIGINAL_OBS_ALL_THREE_PACKS "+json.dumps({
      "sourcePaks":{k:{"previouslyMissing":v["cardMembersPreviouslyMissing"],
       "strictRecoverable":v["strictRecoverableMembers"]} for k,v in report["paks"].items()},
      "newStrictCandidates":[{"pack":v["pack"],"card":v["cardId"],
        "frames":len(v["strictFrames"])} for v in report["newStrictCandidates"]],
      "missingBefore":len(missing),
      "stillMissingAfterStrict":len(missing-
        {v["cardId"] for v in report["newStrictCandidates"]}),
      "productionFilesChanged":0},ensure_ascii=False))
    return report

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("Usage: probe-original-obs-secondary-paks.py source-root quarantine-output")
    scan(Path(sys.argv[1]),Path(sys.argv[2]))
