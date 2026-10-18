#!/usr/bin/env python3
"""Recover source-authentic 2002 4LEAF OBS chessman pixels for live Dice play.

Input is a SHA1-verified installer-extracted Dice/OBS.pak provided by the CI
runner. Native client EXE/DLL are NEVER executed. Output consists solely of
selected transparent PNG frame samples + source-provenance JS manifest.

Important: scanline origin is still PROVISIONAL: opaque source byte runs and
RGB palette are genuine, but native 4-byte horizontal-run location encoding
and action/direction group semantics have not yet been independently decoded.
Do not label these pixels/pose sequences as pixel-perfect original playback.
"""
import sys, json, re, struct, hashlib, io
from pathlib import Path
from PIL import Image

FRAMES=(0,1,2,3,10,18,25,30)
MAX_SPRITE_FRAMES=128
MAX_TOTAL_IMAGES=1000
MAX_TOTAL_PNG_BYTES=14000000

def source_members(data):
    if len(data)<32:raise ValueError("Not an OBS source archive")
    count=struct.unpack_from("<I",data,0)[0]^0xffffffff
    if not 1<=count<=1500:raise ValueError("Invalid source PAK entry count")
    first=4+count*28
    if first>=len(data):raise ValueError("Truncated PAK source header")
    last=0
    for i in range(count):
        entry=data[4+28*i:4+28*(i+1)]
        name=bytes(n^255 for n in entry[:24]).split(b"\0")[0].decode("ascii","replace")
        end=(struct.unpack_from("<I",entry,24)[0]^0xffffffff)+1
        if end<=last or first+end>len(data):raise ValueError("Bad source entry "+name)
        yield name,bytes(data[first+last:first+end])
        last=end
    if first+last!=len(data):raise ValueError("PAK index does not cover entire source archive")

def unpack_frames(source):
    if len(source)<132:raise ValueError("OBS header truncated")
    count=struct.unpack_from("<H",source,70)[0]
    if not 1<=count<=MAX_SPRITE_FRAMES:raise ValueError("Implausible OBS frame count")
    cursor=132; frames=[]
    for i in range(count):
        if cursor+12>len(source):raise ValueError("Truncated OBS frame header")
        n,w,h,ox,oy=struct.unpack_from("<IHHhh",source,cursor)
        if not (10<=w<=300 and 10<=h<=300 and 10<n<=250000 and cursor+12+n<=len(source)):
            raise ValueError("OBS frame geometry invalid")
        frames.append((source[cursor+12:cursor+12+n],w,h,ox,oy))
        cursor+=12+n
    palette=source[cursor:cursor+768]
    if len(palette)!=768:raise ValueError("Missing native 256-colour OBS palette")
    return frames,palette

def decode_rows(body,width,height,palette):
    # Only accept exact-height source row marker sequences with every native
    # indexed pixel run fitting into its declared frame width.
    for low in (20,24,28,32,16,12,8,4,0):
        starts=[0]
        for i in range(1,len(body)-3):
            a,b,c,d=body[i:i+4]
            if low<=a<=128 and b==2 and c<=min(90,width+30) and d<=3:
                starts.append(i)
        if len(starts)!=height:continue
        spans=[(starts[k+1] if k+1<height else len(body))-p-4 for k,p in enumerate(starts)]
        if not all(1<=length<=width for length in spans):continue
        raw=bytearray(width*height)
        for y,(at,n) in enumerate(zip(starts,spans)):
            # In the current extraction 4-byte run X-origin is still
            # undecoded. Centre placement is *inferred*, NOT source-verified.
            x=(width-n)//2
            raw[y*width+x:y*width+x+n]=body[at+4:at+4+n]
        sprite=Image.frombytes("P",(width,height),bytes(raw))
        sprite.putpalette(palette)
        sprite.info["transparency"]=0
        img=sprite.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        rgba=img.tobytes()
        opaque=sum(1 for i in range(3,len(rgba),4) if rgba[i]!=0)
        if opaque<45:raise ValueError("Native sprite contains insufficient visible pixels")
        return img,{"sourceRows":height,"decoder":"palette-and-byte-run-verified;x-centre-and-orientation-provisional","markerThreshold":low,"opaquePixels":opaque}
    raise ValueError("No strict full-height native scanline solution")

def main():
    if len(sys.argv)!=4:
        raise SystemExit("Usage: decode-original-obs-bulk.py OBS.pak chessmen.json original/OBS")
    archive=Path(sys.argv[1]); cards=Path(sys.argv[2]); out=Path(sys.argv[3])
    deck={str(c["id"]):c for c in json.loads(cards.read_text(encoding="utf-8"))}
    recovered={}; statistics={"source":archive.name,"archiveSHA256":hashlib.sha256(archive.read_bytes()).hexdigest(),
        "members":0,"cardMembers":0,"accepted":0,"framePNGs":0,"bytes":0,
        "staticOnly":0,"multiFrameSamples":0,"rejected":{}}
    target=out/"bulk"
    source=archive.read_bytes()
    for name,data in source_members(source):
        statistics["members"]+=1
        if not re.fullmatch(r"1[0-9]{3}\.obs",name.lower()):continue
        cid=f"{int(name[:4])-1000:04d}"
        if cid not in deck or cid in ("0042","0045"):continue
        statistics["cardMembers"]+=1
        try:frames,palette=unpack_frames(data)
        except ValueError as exc:
            statistics["rejected"][name]=str(exc);continue
        images=[]
        for i in FRAMES:
            if i>=len(frames):continue
            body,w,h,ox,oy=frames[i]
            try:img,confidence=decode_rows(body,w,h,palette)
            except ValueError:continue
            buf=io.BytesIO();img.save(buf,format="PNG",optimize=True)
            payload=buf.getvalue()
            images.append({"index":i,"sourceName":f"{Path(name).stem}-{i:02d}.png",
                "payload":payload,"width":w,"height":h,"originX":ox,"originY":oy,
                "sha256":hashlib.sha256(payload).hexdigest(),"decode":confidence})
        # A single FULLY strict original source frame still restores the
        # ACTUAL Genesis chessman pixels and beats the invented CSS proxy.
        # Never animate a 1-frame character or label it as an idle pose.
        # Keep zero-frame-missing and one-frame-only explicitly unverified.
        if not images:
            statistics["rejected"][name]="no strictly decoded source frames"
            continue
        if statistics["framePNGs"]+len(images)>MAX_TOTAL_IMAGES:break
        if statistics["bytes"]+sum(len(f["payload"]) for f in images)>MAX_TOTAL_PNG_BYTES:break
        target.mkdir(parents=True,exist_ok=True)
        frameRefs=[]
        for item in images:
            (target/item["sourceName"]).write_bytes(item["payload"])
            frameRefs.append({"index":item["index"],"url":"./original/OBS/bulk/"+item["sourceName"],
                "width":item["width"],"height":item["height"],
                "originX":item["originX"],"originY":item["originY"],
                "sha256":item["sha256"]})
        if len(frameRefs)==1:
            statistics["staticOnly"]+=1
        else:
            statistics["multiFrameSamples"]+=1
        recovered[cid]={"name":deck[cid].get("name",""),"sourcePak":"OBS.pak",
            "originalMember":name,"sourceSHA256":hashlib.sha256(data).hexdigest(),
            "originalAnimationCount":len(frames),"poseMapping":"UNVERIFIED; native action-table not yet decoded",
            "horizontalScanlineOrigin":"PROVISIONAL; inferred centred rows",
            "hasVerifiedFrameZero":any(f["index"]==0 for f in frameRefs),
            "fallbackAction":"EARLIEST SOURCE FRAME ONLY; action unverified",
            "singleFrameStillOnly":len(frameRefs)==1,
            "frames":frameRefs}
        statistics["accepted"]+=1
        statistics["framePNGs"]+=len(images)
        statistics["bytes"]+=sum(len(f["payload"]) for f in images)
    # Deterministic, sorted, valid JavaScript; no html/screenshot compositing.
    manifest="/* Genuine original Dice/OBS.pak indexed palette frame pixels.\n"+\
      " * PROVISIONAL scanline X placement & action labels.\n"+\
      " * NEVER reuse as ChatTown Registry avatars. */\n"+\
      "window.ORIGINAL_LEAF_OBS_FRAMES=Object.assign(\n"+\
      " window.ORIGINAL_LEAF_OBS_FRAMES||{},\n"+\
      json.dumps(recovered,ensure_ascii=False,indent=2,sort_keys=True)+"\n);\n"
    (out/"animation-extra.js").write_text(manifest,encoding="utf-8")
    (out/"bulk-source-report.json").write_text(
        json.dumps(statistics,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("SOURCE_OBS_BULK_RECOVERY "+json.dumps({k:v for k,v in statistics.items() if k!="rejected"}))
    print("SOURCE_OBS_BULK_CARDS "+json.dumps(list(recovered.keys()),ensure_ascii=False))
    print("SOURCE_OBS_BULK_REJECTED_COUNT "+str(len(statistics["rejected"])))
    if not recovered:raise ValueError("No strictly decoded source chessman animation group")

if __name__=="__main__":
    main()
