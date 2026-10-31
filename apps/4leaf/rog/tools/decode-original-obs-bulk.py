#!/usr/bin/env python3
"""Recover source-authentic 2002 4LEAF OBS chessman pixels for live Dice play.

Input is a SHA1-verified installer-extracted Dice/OBS.pak provided by the CI
runner. Native client EXE/DLL are NEVER executed. Output consists solely of
selected transparent PNG frame samples + source-provenance JS manifest.

Native indexed pixels and per-row x positions are reconstructed by the
same strict 640-stride VIDEO RLE as the already verified original ROLL SPR.
Original action/direction-to-frame semantics and the 2002 3D placement
remain UNKNOWN; do not claim original animation-timeline fidelity.
"""
import sys, json, re, struct, hashlib, io
from pathlib import Path
from PIL import Image

# Recover the contiguous source-native 0..7 block, not a guessed animation label. 
# Later 10/18/25/30 are source samples; their action identities remain unknown.
FRAMES=tuple(range(8))+(10,18,25,30)
MAX_SPRITE_FRAMES=256  # Original 1095.obs explicitly declares 172 native frames
MAX_TOTAL_IMAGES=1300
MAX_TOTAL_PNG_BYTES=17000000

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
        if not (1<=w<=300 and 1<=h<=300 and 6<=n<=250000 and cursor+12+n<=len(source)):
            raise ValueError("OBS frame geometry invalid; index="+str(i)+
                             " cursor="+str(cursor)+" declared="+str((n,w,h,ox,oy))+
                             " memberBytes="+str(len(source)))
        frames.append((source[cursor+12:cursor+12+n],w,h,ox,oy))
        cursor+=12+n
    palette=source[cursor:cursor+768]
    # OBS members carry extra metadata after their 768-byte RGB palette;
    # unlike IMG/roll.spr they do not end exactly at that palette.
    # The frame record cursor is exact; compare and report native trailing
    # byte count independently rather than rejecting all 2002 chessmen.
    if len(palette)!=768:
        raise ValueError("Missing native 256-colour OBS palette at frame boundary")
    return frames,palette

def decode_rows(body,width,height,palette,minimum_opaque_pixels=45):
    """Decode the exact 2002 FAST.PAL.COLORKEY 640-stride run stream.

    Same native packet format as verified Dice/IMG.pak roll.spr:
      u16 runCount; u16 initialOffset;
      first packet = byteLengthHi * 4 + byteLengthLo, palette pixels;
      next packets = u16 transparentSkip, byteLengthHi*4+byteLengthLo,
                     source palette pixels.
    All packet boundaries, 640-wide screen-row destinations, source bounds,
    source palette, and final cursor are checked. Nothing is centered,
    interpolated, inferred from a false image-row marker, or rendered
    beyond its native recorded width/height.
    """
    if len(body)<6 or len(palette)!=768:
        raise ValueError("OBS 640-stride source packet or RGB palette truncated")
    run_count, cursor=struct.unpack_from("<HH",body,0)
    if not 1<=run_count<=40000:
        raise ValueError("OBS 640-stride invalid native run count")
    pos=4
    pixels=bytearray(width*height)
    opaque=0
    for run in range(run_count):
        if run:
            if pos+2>len(body):
                raise ValueError("OBS 640-stride transparent skip truncated")
            cursor+=struct.unpack_from("<H",body,pos)[0]
            pos+=2
        if pos+2>len(body):
            raise ValueError("OBS 640-stride palette packet truncated")
        length=body[pos]*4+body[pos+1]
        if body[pos+1]>3:
            raise ValueError("OBS 640-stride encoded sub-byte length invalid")
        pos+=2
        if pos+length>len(body):
            raise ValueError("OBS 640-stride palette data truncated")
        y,x=divmod(cursor,640)
        if y>=height or x>=width or x+length>width:
            raise ValueError("OBS source buffer packet outside frame "+
                             str((run,x,y,length,width,height)))
        if length:
            palette_run=body[pos:pos+length]
            pixels[y*width+x:y*width+x+length]=palette_run
            opaque+=sum(i!=0 for i in palette_run)
        pos+=length
        cursor+=length
    if pos!=len(body):
        raise ValueError("OBS native RLE does not consume every source byte")
    # Source OBS may occupy only a SPARSE SUB-RECTANGLE of its declared
    # animation canvas: genuine 1128.obs 239x222 frame 0 stops at native
    # framebuffer y=114. The other 107 transparent rows were NEVER sent as
    # payload, just as authentic 1171.obs omits right-edge transparent x.
    # We have already checked every packet's exact encoded byte length,
    # source palette values and legal framebuffer coordinate. Requiring
    # the final pixel to reach the bottom-right invents a constraint that
    # rejects genuine sparse source animation frames.
    if cursor<=0 or cursor>(height-1)*640+width:
        raise ValueError("OBS source last VIDEO packet exceeds native canvas")
    if not 0<=minimum_opaque_pixels<=45:
        raise ValueError("Invalid native opacity admission threshold")
    if opaque<minimum_opaque_pixels:
        raise ValueError("OBS native source too transparent after strict decoding")
    img=Image.frombytes("P",(width,height),bytes(pixels))
    img.putpalette(palette)
    img.info["transparency"]=0
    image=img.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return image,{"sourceRows":height,
       "decoder":"VERIFIED-640-STRIDE-PALETTE-RLE/exact-run-cursor-and-width",
       "videoStride":640,"nativePackets":run_count,"opaquePixels":opaque,
       "scanlineX":"ORIGINAL-VIDEO-RUN-CURSOR; NOT CENTERED"}



def record_native_row_headers(frame_data,width,height):
    """Describe (not yet interpret) raw 4-byte OBS scanline headers.
    Pixel scanline positions require a separate codec-proof; avoid
    assigning source x via guesswork when presenting real archive bytes.
    """
    for low in (20,24,28,32,16,12,8,4,0):
        starts=[0]
        for i in range(1,len(frame_data)-3):
            a,b,c,d=frame_data[i:i+4]
            if low<=a<=128 and b==2 and c<=min(90,width+30) and d<=3:
                starts.append(i)
        if len(starts)!=height:continue
        spans=[(starts[k+1] if k+1<height else len(frame_data))-at-4
               for k,at in enumerate(starts)]
        if not all(1<=v<=width for v in spans):continue
        return {
            "headerWordInterpretation":"UNVERIFIED/DO-NOT-USE-AS-LIVE-COORDINATE",
            "threshold":low,"nativeHeight":height,"headers":[
                {"row":row,"bytes":frame_data[at:at+4].hex(),
                 "word0":struct.unpack_from("<H",frame_data,at)[0],
                 "word1":struct.unpack_from("<H",frame_data,at+2)[0],
                 "actualPayload":spans[row],
                 "centeredWebFallbackX":(width-spans[row])//2}
                for row,at in list(enumerate(starts))[:4] +
                    list(enumerate(starts))[-3:]
            ]
        }
    return None


def inspect_rejected_member(source, frames=None):
    """Read-only byte-structure probe for the still-missing original bodies.
    Never converts guesses to accepted game sprites; records candidate row
    header distributions so a future codec repair can be verified.
    """
    if frames is None:
        headers=[]
        for off in (66,68,70,72,74):
            if off+2<=len(source):
                headers.append({"offset":off,"count":struct.unpack_from("<H",source,off)[0]})
        geometries=[]
        for off in (124,128,132,136,140):
            if off+12<=len(source):
                n,w,h,ox,oy=struct.unpack_from("<IHHhh",source,off)
                geometries.append({"offset":off,"length":n,"width":w,
                    "height":h,"ox":ox,"oy":oy,
                    "plausible":10<=w<=300 and 10<=h<=300 and 10<n<=250000})
        return {"headers":headers,"geometries":geometries,
                "sourceLength":len(source)}
    probes=[]
    for index in FRAMES:
        if index>=len(frames):continue
        body,w,h,ox,oy=frames[index]
        candidates=[]
        for markerHigh in (0,1,2,3):
            for low in (0,8,16,20,28,32):
                starts=[0]
                for i in range(1,len(body)-3):
                    a,b,c,d=body[i:i+4]
                    if a>=low and a<=128 and b==markerHigh and c<=min(90,w+30) and d<=3:
                        starts.append(i)
                spans=[(starts[j+1] if j+1<len(starts) else len(body))-p-4
                    for j,p in enumerate(starts)]
                valid=sum(1 for v in spans if 1<=v<=w)
                # Sorted by full source-row reconstruction closeness and
                # in-bounds pixel payload; never guess action frames.
                candidates.append({"marker":markerHigh,"threshold":low,
                    "rows":len(starts),"valid":valid,
                    "deviation":abs(len(starts)-h),
                    "maxSpan":max(spans) if spans else -1})
        best=sorted(candidates,key=lambda p:(p["deviation"],
            -(p["valid"]/max(1,p["rows"])),p["marker"]!=2,
            abs(p["threshold"]-20)))[:5]
        probes.append({"frame":index,"width":w,"height":h,"origin":[ox,oy],
            "length":len(body),"head":body[:16].hex(),
            "nearby":best})
    return {"sampled":probes}


def main():
    if len(sys.argv)!=4:
        raise SystemExit("Usage: decode-original-obs-bulk.py OBS.pak chessmen.json original/OBS")
    archive=Path(sys.argv[1]); cards=Path(sys.argv[2]); out=Path(sys.argv[3])
    deck={str(c["id"]):c for c in json.loads(cards.read_text(encoding="utf-8"))}
    recovered={}; statistics={"source":archive.name,"archiveSHA256":hashlib.sha256(archive.read_bytes()).hexdigest(),
        "members":0,"cardMembers":0,"accepted":0,"framePNGs":0,"bytes":0,
        "staticOnly":0,"multiFrameSamples":0,"rejected":{},
        "decodeDiagnostics":{}}
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
            statistics["rejected"][name]=str(exc)
            statistics["decodeDiagnostics"][name]=inspect_rejected_member(data)
            continue
        images=[]
        failures=[]
        for i in FRAMES:
            if i>=len(frames):continue
            body,w,h,ox,oy=frames[i]
            try:img,confidence=decode_rows(body,w,h,palette)
            except ValueError as err:
                failures.append({"frame":i,"shape":[w,h],"reason":str(err),
                    "sourceFirst8":body[:8].hex()})
                continue
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
            statistics["decodeDiagnostics"][name]={
                "nativeVideoRLEFailures":failures,
                "legacyRowMarkerHeuristic":inspect_rejected_member(data,frames)}
            if name in ("1046.obs","1072.obs","1094.obs"):
                print("OBS_NATIVE_RLE_DIAGNOSTIC",name,json.dumps(failures))
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
        # Persist SOURCE header bytes only for inspection. The current X
        # placement remains provisional and not the historical EXE formula.
        first=next((i for i in images if i["index"]==0),images[0])
        firstBody,firstW,firstH,_,_=frames[first["index"]]
        headerProbe=record_native_row_headers(firstBody,firstW,firstH)
        if headerProbe:
            statistics.setdefault("sourceRLEHeaders",{})[name]=headerProbe
        recovered[cid]={"name":deck[cid].get("name",""),"sourcePak":"OBS.pak",
            "originalMember":name,"sourceSHA256":hashlib.sha256(data).hexdigest(),
            "originalAnimationCount":len(frames),"poseMapping":"UNVERIFIED; native action-table not yet decoded",
            "horizontalScanlineOrigin":"ORIGINAL-640-VIDEO-RLE exact destination",
            "hasVerifiedFrameZero":any(f["index"]==0 for f in frameRefs),
            "fallbackAction":"EARLIEST SOURCE FRAME ONLY; action unverified",
            "singleFrameStillOnly":len(frameRefs)==1,
            "frames":frameRefs}
        statistics["accepted"]+=1
        statistics["framePNGs"]+=len(images)
        statistics["bytes"]+=sum(len(f["payload"]) for f in images)
    # Deterministic, sorted, valid JavaScript; no html/screenshot compositing.
    manifest="/* Genuine original Dice/OBS.pak indexed palette frame pixels.\n"+\
      " * VERIFIED native 640-stride source pixel X; action labels UNVERIFIED.\n"+\
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
