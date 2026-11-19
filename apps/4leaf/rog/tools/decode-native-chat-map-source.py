#!/usr/bin/env python3
"""STATIC-only original 4Leaf096d ChatTown MapData SPR and MapInfo MAP forensic decode.
Generate cropped contact sheets/geometry for source-to-web restoration.
Never execute legacy EXE/DLL, invent coordinates, or mark original equivalence.
"""
import hashlib, io, importlib.util, json, re, struct, sys
from pathlib import Path
from PIL import Image, ImageDraw

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("obs_native_map_codec",here/"decode-original-obs-bulk.py")
codec=importlib.util.module_from_spec(spec)
spec.loader.exec_module(codec)
root=Path(sys.argv[1]); out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
def members(path):
    raw=path.read_bytes()
    count=struct.unpack_from("<I",raw)[0]^0xffffffff
    if not 0<count<10000:raise ValueError("invalid PAK index")
    base=4+count*28;last=0
    for i in range(count):
        ent=raw[4+i*28:4+(i+1)*28]
        name=bytes(x^255 for x in ent[:24]).split(b"\0")[0].decode("cp949","replace")
        end=(struct.unpack_from("<I",ent,24)[0]^0xffffffff)+1
        if end<=last or base+end>len(raw):raise ValueError("bad member offset")
        yield name,raw[base+last:base+end]
        last=end
    if base+last!=len(raw):raise ValueError("PAK member index size mismatch")
def parse_spr(raw):
    idx=raw.find(b"FAST.PAL.COLORKEY")
    if idx<0:raise ValueError("Missing original FAST.PAL.COLORKEY")
    src=raw[idx:]
    count=struct.unpack_from("<H",src,66)[0]
    if count<1 or count>1024:raise ValueError("implausible native frame count: "+str(count))
    cursor=128;rows=[]
    for i in range(count):
        if cursor+12>len(src):raise ValueError("Truncated frame header "+str(i))
        size,w,h,ox,oy=struct.unpack_from("<IHHhh",src,cursor)
        if size<6 or size>2_000_000 or w<1 or w>640 or h<1 or h>1200 or cursor+12+size>len(src):
            raise ValueError("Invalid frame geometry: "+str((i,size,w,h,ox,oy)))
        rows.append((i,size,w,h,ox,oy,src[cursor+12:cursor+12+size]))
        cursor+=12+size
    palette=src[cursor:cursor+768]
    if len(palette)!=768:raise ValueError("Missing original palette")
    return rows,palette,len(src)-cursor-768
def contact(name,frames,canvascols=8):
    if not frames:return None
    cellw,cellh=104,120
    cols=min(canvascols,len(frames));rows=(len(frames)+cols-1)//cols
    sheet=Image.new("RGB",(cols*cellw,rows*cellh),(34,39,67));draw=ImageDraw.Draw(sheet)
    for n,(idx,img,geo) in enumerate(frames):
        v=img.copy()
        v.thumbnail((cellw-8,cellh-24))
        px=(n%cols)*cellw+(cellw-v.width)//2
        py=(n//cols)*cellh+(cellh-18-v.height)//2
        sheet.paste(v,(px,py),v)
        draw.text((n%cols*cellw+4,n//cols*cellh+cellh-19),f"{idx}: {geo[0]}x{geo[1]}",fill=(232,230,195))
    target=out/(name.lower()+"-contact.png")
    sheet.save(target,optimize=True)
    return target.name
report={"schemaVersion":1,"client":"4Leaf096d 2003 InstallShield",
 "codec":"FAST.PAL.COLORKEY-640-stride", "mapScenes":{}, "sprites":{}}
for fname in ("MapInfo.pak","MapData.pak","MapObject.pak"):
    p=root/fname
    if not p.exists():continue
    for name,blob in members(p):
        group=fname[:-4]
        if name.lower().endswith(".map"):
            strv=lambda b:b.split(b"\0")[0].decode("cp949","replace")
            report["mapScenes"][name]={
                "sourcePack":group,"sourceSha256":hashlib.sha256(blob).hexdigest(),
                "bytes":len(blob),"initialStrings":[strv(blob[i:i+24]) for i in (0,24,48,72)],
                "first512Hex":blob[:512].hex(),
                "headerUint32":[struct.unpack_from("<I",blob,i)[0] for i in range(0,160,4)],
                "uniqueByteCount":len(set(blob))}
            continue
        if not name.lower().endswith(".spr"):continue
        key=group+"/"+name
        rec={"sourceSha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob),
             "status":"unverified","frames":[]}
        report["sprites"][key]=rec
        try:
            frames,palette,tail=parse_spr(blob)
            rec["nativeFrameCount"]=len(frames);rec["paletteTailBytes"]=tail
            sheet=[]
            # Record every declared frame; decode FIRST 24 for visual inspection.
            for idx,size,w,h,ox,oy,body in frames:
                item={"index":idx,"packetBytes":size,"width":w,"height":h,"originX":ox,"originY":oy}
                rec["frames"].append(item)
                if idx<24:
                    try:
                        img,diagnostic=codec.decode_rows(body,w,h,palette,
                           minimum_opaque_pixels=0,alpha_from_runs=True,
                           allow_zero_length_row_end=True)
                        item["status"]="decoded"
                        item["opaquePixels"]=diagnostic["opaquePixels"]
                        sheet.append((idx,img,(w,h)))
                    except Exception as e:item["status"]="decode-failed";item["error"]=str(e)[:180]
            rec["contactSheet"]=contact(group+"-"+Path(name).stem,sheet)
            rec["status"]="source-frame-metadata-verified"
        except Exception as e:rec["error"]=str(e)[:300];rec["status"]="not-decoded"
(out/"native-chatmap-source-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
print("REAL_ORIGINAL_CT_MAPS",len([k for k in report["mapScenes"] if k.startswith("CT_")]))
print("REAL_ORIGINAL_KT_MAPS",len([k for k in report["mapScenes"] if k.startswith("KT_")]))
for k,v in report["sprites"].items():print("SPRITE",k,v["status"],v.get("nativeFrameCount"),v.get("contactSheet"),v.get("error",""))
print("NATIVE_MAP_SCENE_DECODER_EVIDENCE_READY",len(report["sprites"]))
print("NATIVE_ORIGINAL_SPR_FRAME_DECODED",sum(1 for v in report["sprites"].values() for f in v["frames"] if f.get("status")=="decoded"))
print("NATIVE_ORIGINAL_SPR_FRAME_FAILED",sum(1 for v in report["sprites"].values() for f in v["frames"] if f.get("status")=="decode-failed"))
