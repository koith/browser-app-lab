#!/usr/bin/env python3
"""Read-only 2003 4Leaf096d ChatMap/MapData/MapInfo/MapObject PAK member audit.
Writes an evidence JSON, never executes or redistributes original client files.
Original PAK index names and offsets use per-byte inversion.
"""
import hashlib, json, struct, sys
from pathlib import Path

root=Path(sys.argv[1])
out=Path(sys.argv[2])
out.parent.mkdir(exist_ok=True,parents=True)
result={"schemaVersion":1,"source":"original-4Leaf096d-2003-01-21",
 "sourceStatus":"installer/static-bytes-read-only",
 "packs":[],"candidateLiveSceneArt":[]}
groups=["ChatMap","MapData","MapInfo","MapObject","ChatTown","ChatRoom"]
for group in groups:
    file=root/(group+".pak")
    entry={"pak":group,"status":"unavailable","members":[]}
    result["packs"].append(entry)
    if not file.is_file():
        continue
    raw=file.read_bytes()
    entry["sha256"]=hashlib.sha256(raw).hexdigest()
    entry["bytes"]=len(raw)
    if len(raw)<4:
        entry["status"]="bad header"
        continue
    count=struct.unpack_from("<I",raw)[0]^0xffffffff
    if not 0<count<10000 or len(raw)<4+28*count:
        entry["status"]="invalid member count"
        entry["decodedMemberCount"]=count
        continue
    entry["decodedMemberCount"]=count
    offset=4+count*28
    last=0
    try:
        for i in range(count):
            item=raw[4+i*28:4+(i+1)*28]
            filename=bytes(c^255 for c in item[:24]).split(b"\x00")[0].decode("cp949","replace")
            end=(struct.unpack_from("<I",item,24)[0]^0xffffffff)+1
            if not filename or end<=last or offset+end>len(raw):
                raise ValueError("bad member at "+str(i))
            data=raw[offset+last:offset+end]
            last=end
            sig=data[:16]
            kind=(
                "GIF" if sig.startswith((b"GIF87a",b"GIF89a")) else
                "BMP" if sig.startswith(b"BM") else
                "PNG" if sig.startswith(b"\x89PNG\r\n\x1a\n") else
                "JPEG" if sig[:3]==b"\xff\xd8\xff" else
                "RIFF" if sig.startswith(b"RIFF") else
                "UNKNOWN")
            info={"name":filename,"bytes":len(data),
                "sha256":hashlib.sha256(data).hexdigest(),
                "signature":sig.hex(),"kind":kind}
            if kind=="BMP" and len(data)>=26:
                info["pixels"]=list(struct.unpack_from("<ii",data,18))
            elif kind=="GIF" and len(data)>=10:
                info["pixels"]=list(struct.unpack_from("<HH",data,6))
            elif kind=="PNG" and len(data)>=24:
                info["pixels"]=list(struct.unpack_from(">II",data,16))
            entry["members"].append(info)
            if group in groups[:4] and kind in ("BMP","GIF","PNG","JPEG"):
                result["candidateLiveSceneArt"].append(
                    {"pak":group,**info})
        if offset+last!=len(raw):
            entry["trailingBytes"]=len(raw)-offset-last
        entry["status"]="index-verified"
    except ValueError as e:
        entry["status"]="index-invalid"
        entry["error"]=str(e)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
for pack in result["packs"]:
    print("ORIGINAL_096D_PAK",pack["pak"],pack["status"],
        "members",len(pack["members"]), "bytes",pack.get("bytes",0))
    for member in pack["members"][:65]:
        print(" ",member["name"],member["bytes"],member["kind"],member.get("pixels"))
print("CANDIDATE_SCENE_ART",len(result["candidateLiveSceneArt"]))
