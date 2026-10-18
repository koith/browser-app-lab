#!/usr/bin/env python3
"""Read-only source SPR discovery for unused 2002 Dice/IMG.pak members.

roll.spr and eventRoll1.spr are confirmed original GUI sprites, NOT 3D die
models. Unused winBattle/winResult/etc. may restore GUI visuals. Filename
alone cannot verify the original function.
All decoded images remain isolated from the live game as quarantine assets.
"""
import hashlib,importlib.util,io,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location("orig_img_codec",
    Path(__file__).with_name("decode-original-img-spr.py"))
codec=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=codec
spec.loader.exec_module(codec)

def scan(source,target):
    report={"source":"2002 archive Dice/IMG.pak","sourceSHA256":hashlib.sha256(source.read_bytes()).hexdigest(),
     "status":"STRICT SPR RGBA CANDIDATES / QUARANTINE ONLY","members":[],
     "publish":False,"original3DDiceRecovered":False}
    for name,raw in codec.members(source.read_bytes()):
        if not name.lower().endswith(".spr"):continue
        entry={"name":name,"sha256":hashlib.sha256(raw).hexdigest(),"frames":[]}
        try:
            frames,palette=codec.frames(raw)
        except ValueError as error:
            entry["error"]=str(error);report["members"].append(entry);continue
        entry["declaredFrames"]=len(frames)
        for i,w,h,ox,oy,body in frames:
            try:
                image,opaque,runs=codec.sprite_rgba(body,w,h,palette)
            except ValueError as error:
                entry.setdefault("decodeErrors",[]).append({"index":i,"error":str(error)})
                continue
            data=io.BytesIO()
            image.save(data,format="PNG",optimize=True)
            png=data.getvalue()
            rel=f"{Path(name).stem}/{i:02}.png"
            output=target/rel
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(png)
            entry["frames"].append({"index":i,"size":[w,h],"origin":[ox,oy],
               "pixels":opaque,"runs":runs,"sha256":hashlib.sha256(png).hexdigest(),
               "quarantinePNG":rel})
        report["members"].append(entry)
    target.mkdir(parents=True,exist_ok=True)
    (target/"source-spr-probe.json").write_text(json.dumps(report,ensure_ascii=False,
       indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("ORIGINAL_IMG_SPR_14_MEMBERS_AUDIT "+json.dumps({
       "members":len(report["members"]),"strictDecoded":{m["name"]:len(m["frames"])
        for m in report["members"] if m["frames"]},
       "notDecoded":{m["name"]:m.get("error",m.get("decodeErrors"))
        for m in report["members"] if not m["frames"]},
       "original3DDiceRecovered":False},ensure_ascii=False))
    return report
if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("Usage: probe-original-img-extra-spr.py Dice/IMG.pak quarantine-output")
    scan(Path(sys.argv[1]),Path(sys.argv[2]))
