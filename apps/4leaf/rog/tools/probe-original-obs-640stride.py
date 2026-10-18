#!/usr/bin/env python3
"""Read-only proof of candidate 640-wide video-buffer skip encoding in OBS.pak.

Existing production decoders center native palette rows because their x
position is unknown. Here we test an independent hypothesis: each 2-byte
little-endian word before the ORIGINAL source palette stream expresses a
skip from the previous run in a 640-wide virtual framebuffer. The first
word initializes a source scanline offset. Never publish guessed sprites
without checking width, entire-row coverage and source action identity.
"""
import sys, json, struct, importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location(
  "sourceobs",(ROOT/"decode-original-obs-bulk.py").as_posix())
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)

def test_stride(body,width,height,low,headerBytes=2,screenPitch=640):
    positions=[0]
    for i in range(1,len(body)-3):
        a,b,c,d=body[i:i+4]
        if low<=a<=128 and b==2 and c<=min(90,width+30) and d<=3:
            positions.append(i)
    if len(positions)!=height:return None
    payload=[(positions[j+1] if j+1<height else len(body))-at-headerBytes
             for j,at in enumerate(positions)]
    if not all(1<=length<=width+2 for length in payload):return None
    x=[0]
    for row in range(1,height):
        skip=struct.unpack_from("<H",body,positions[row])[0]
        x.append(x[-1]+payload[row-1]+skip-screenPitch)
    min_x=min(x)
    extent=max(offset+length for offset,length in zip(x,payload))-min_x
    plausible=extent<=width and abs(x[-1]-x[0])<=width
    return {"threshold":low,"height":height,"width":width,
      "headerBytes":headerBytes,"pitch":screenPitch,
      "nativeRunWidths":payload[:8],"nativeSkipWords":[
         struct.unpack_from("<H",body,p)[0] for p in positions[:8]],
      "offsetFromFirst":[v-x[0] for v in x[:8]],
      "extent":extent,"range":[min_x,max(x)],
      "fitsSourceFrame":plausible,
      "minWidthRemaining":width-extent,
      "hypothesis":"PREVIEW-ONLY/640-pitch/2-byte-run-skip"}

def main():
    if len(sys.argv)!=4:
        raise SystemExit("usage: probe-original-obs-640stride.py OBS.pak chessmen.json report.json")
    pak=Path(sys.argv[1]).read_bytes()
    deck={str(v["id"]) for v in json.loads(Path(sys.argv[2]).read_text())}
    report=json.loads(Path(sys.argv[3]).read_text())
    samples=[]
    for name,raw in module.source_members(pak):
        if not name.endswith(".obs"):continue
        try:
            cid=f"{int(name[:4])-1000:04d}"
            frames,palette=module.unpack_frames(raw)
        except (ValueError,IndexError):continue
        if cid not in deck:continue
        for frameNo in (0,1,2,3,10):
            if frameNo>=len(frames):continue
            body,w,h,ox,oy=frames[frameNo]
            options=[d for header in (4,2)
                for pitch in (638,639,640,641,642,643,644)
                for low in (20,24,28,32,16,12,8,4,0)
                if (d:=test_stride(body,w,h,low,header,pitch))]
            if not options:continue
            best=sorted(options,key=lambda d:(not d["fitsSourceFrame"],
                  abs(d["width"]-d["extent"]),abs(d["threshold"]-20)))[0]
            samples.append({"member":name,"id":cid,"frame":frameNo,
             "size":[w,h],"origin":[ox,oy],**best})
    fitting=[s for s in samples if s["fitsSourceFrame"]]
    groups={}; rejects=set(report.get("rejected",{}))
    for record in samples:
        key="previouslyRejected" if record["member"] in rejects else "previouslyAccepted"
        group=groups.setdefault(key,{"frames":0,"fitting":0,"examples":[]})
        group["frames"]+=1
        if record["fitsSourceFrame"]:group["fitting"]+=1
        if len(group["examples"])<12:group["examples"].append({
            "member":record["member"],"frame":record["frame"],"size":record["size"],
            "extent":record["extent"],"fitting":record["fitsSourceFrame"],
            "header":record["headerBytes"],"pitch":record["pitch"],
            "runWidths":record["nativeRunWidths"][:3],
            "skips":record["nativeSkipWords"][:3],"x":record["offsetFromFirst"][:3]})
    # Record combinations; reject a source hypothesis if the majority of
    # strict original frames do not fit their declared native width.
    byVariant={}
    for v in samples:
        key=str(v["headerBytes"])+"/"+str(v["pitch"])
        agg=byVariant.setdefault(key,{"sampled":0,"fits":0})
        agg["sampled"]+=1
        agg["fits"]+=int(v["fitsSourceFrame"])
    result={"codec":"hypothesis-only: 2- or 4-byte OBS header with 638..644 pitch",
        "source":"SHA-verified 2002 Dice/OBS.pak",
        "strictFrameSamples":len(samples),
        "sourceFittingSamples":len(fitting),
        "bestVariantHistogram":byVariant,
        "groups":groups,
        "candidateFrames":[{"member":s["member"],"index":s["frame"],
            "width":s["width"],"height":s["height"],
            "extent":s["extent"],"fits":s["fitsSourceFrame"]}
             for s in fitting[:100]]}
    print("OBS_640STRIDE_PROOF "+json.dumps(
        {k:v for k,v in result.items() if k!="candidateFrames"},ensure_ascii=False))
    Path("/tmp/leaf-obs-640stride-proof.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
