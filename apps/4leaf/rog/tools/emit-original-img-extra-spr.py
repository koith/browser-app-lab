#!/usr/bin/env python3
"""Promote strictly source-verified 2002 IMG.pak GUI sprite PNGs from quarantine.

The source ZIP is SHA1 checked in CI. Each full-resolution PNG must match
the SHA256 and native dimensions from the strict palette/640-video-stride
decoder report. Existing roll/eventRoll1 button files are not duplicated.
This publishes native 2D scene art, never claims a 3D die or 3D mesh.
"""
import hashlib,json,shutil,sys
from pathlib import Path
from PIL import Image

ORIGINAL_MEMBERS={
 "avatar.spr":32,"avatar2.spr":1,"avatar3.spr":32,
 "eventRoll1.spr":16,"menu.spr":9,"minipanel.spr":4,
 "roll.spr":4,"selector.spr":7,"teamIcon.spr":4,
 "winAbility.spr":6,"winBattle.spr":2,"winDoa.spr":1,
 "winJail.spr":1,"winResult.spr":1
}
EXISTING={"eventRoll1.spr","roll.spr"}
def emit(quarantine,destination):
    manifest=json.loads((quarantine/"source-spr-probe.json").read_text())
    entries=manifest["members"]
    assert len(entries)==14 and {x["name"] for x in entries}==set(ORIGINAL_MEMBERS)
    assert all(len(x["frames"])==ORIGINAL_MEMBERS[x["name"]] for x in entries)
    assert sum(len(x["frames"]) for x in entries)==120
    output={"source":"2002 Dice/IMG.pak","sourceSHA256":manifest["sourceSHA256"],
      "decoder":"STRICT-PAL-640-VIDEO-RLE","classifiedNative2DOnly":True,
      "original3DDiceMeshRecovered":False,"sprites":{}}
    copied=0
    for m in entries:
        name=m["name"]
        if name in EXISTING:continue
        frames=[]
        for item in m["frames"]:
            index=item["index"]
            source=quarantine/item["quarantinePNG"]
            assert source.is_file() and source.stat().st_size>100
            data=source.read_bytes()
            assert hashlib.sha256(data).hexdigest()==item["sha256"]
            with Image.open(source) as im:
                assert im.format=="PNG" and im.mode=="RGBA"
                assert im.size==tuple(item["size"])
                alphaMin,alphaMax=im.getchannel("A").getextrema()
                assert alphaMax==255 and 0<=alphaMin<=255
                # Genuine source icons can be fully opaque; don't require
                # a transparent background for every original SPR member.
            filename=f"{Path(name).stem}-{index:02d}.png"
            target=destination/filename
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            copied+=1
            frames.append({"index":index,"url":"./original/SourceSPRExtra/"+filename,
              "width":item["size"][0],"height":item["size"][1],
              "originX":item["origin"][0],"originY":item["origin"][1],
              "sha256":item["sha256"],"originalOpaquePixels":item["pixels"]})
        output["sprites"][name]={"originalMember":name,
           "sourceSHA256":m["sha256"],"nativeFrameCount":len(frames),
           "frames":frames}
    assert copied==100,(copied,len(output["sprites"]))
    assert output["sprites"]["winBattle.spr"]["frames"][1]["width"]==355
    assert output["sprites"]["winBattle.spr"]["frames"][1]["height"]==113
    assert output["sprites"]["winAbility.spr"]["frames"][0]["width"]==330
    assert output["sprites"]["winAbility.spr"]["frames"][0]["height"]==284
    (destination/"manifest.json").write_text(
      json.dumps(output,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("ORIGINAL_2002_IMG_GUI_PUBLISHED "+json.dumps(
      {"members":len(output["sprites"]),"verifiedFrames":copied,
       "winBattlePodium":[355,113],"winAbilityMagicStage":[330,284],
       "source3DMeshClaimed":False}))
if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("Usage: emit-original-img-extra-spr.py quarantine-folder dest-sourcePNG-folder")
    emit(Path(sys.argv[1]),Path(sys.argv[2]))
