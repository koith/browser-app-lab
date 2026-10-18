#!/usr/bin/env python3
"""Independent, non-production preview of otherwise rejected 2002 OBS bodies.

Never alters game assets or the accepted animation manifest. Samples only
authentic indexed/palette source bytes and documents inferred missing/extra
row header reconciliation. A preview MUST be inspected and gated before it
can become a character in the live game.
"""
import base64, importlib.util, io, json, sys
from pathlib import Path
from PIL import Image

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location(
    "original_obs_bulk",(HERE/"decode-original-obs-bulk.py").as_posix())
codec=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=codec
spec.loader.exec_module(codec)

def near_frame(body,w,h,palette):
    choices=[]
    for low in (20,24,28,32,16,12,8,4,0):
        starts=[0]
        for i in range(1,len(body)-3):
            a,b,c,d=body[i:i+4]
            if low<=a<=128 and b==2 and c<=min(90,w+30) and d<=3:
                starts.append(i)
        n=len(starts)
        # Only small, bounded mismatches can be studied visually; unknown
        # packet formats need a real codec, not arbitrary guessed rows.
        if abs(n-h)>3 or n<h-1:continue
        lens=[(starts[k+1] if k+1<n else len(body))-at-4
              for k,at in enumerate(starts)]
        if not all(1<=length<=w for length in lens):continue
        choices.append((abs(n-h),abs(low-20),low,starts,lens))
    if not choices:return None
    _,_,low,starts,lens=min(choices,key=lambda x:x[:2])
    raw=bytearray(w*h)
    # Quarantine: truncate only excess final scanlines, or leave one blank
    # scanline at bottom. Pixel indices within each line are genuine source
    # bytes. Placement within the frame is still inferred.
    for y,(at,n) in enumerate(zip(starts[:h],lens[:h])):
        x=(w-n)//2
        raw[y*w+x:y*w+x+n]=body[at+4:at+4+n]
    pal=Image.frombytes("P",(w,h),bytes(raw))
    pal.putpalette(palette)
    pal.info["transparency"]=0
    image=pal.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    rgba=image.tobytes()
    opaque=sum(1 for i in range(3,len(rgba),4) if rgba[i]>0)
    if opaque<45:return None
    return image,{"originalRowsDetected":len(starts),"nativeHeight":h,
                  "rowDelta":len(starts)-h,"rowThreshold":low,
                  "opaque":opaque,"confidence":"PROVISIONAL-NEAR-ROW/NOT-LIVE"}

def main():
    if len(sys.argv)!=5:
        raise SystemExit("Usage: probe-original-obs-near-rows.py OBS.pak chessmen.json report.json outdir")
    source=Path(sys.argv[1]).read_bytes()
    accepted={c["id"] for c in json.loads(Path(sys.argv[2]).read_text())}
    reject=json.loads(Path(sys.argv[3]).read_text())["rejected"]
    target=Path(sys.argv[4]);target.mkdir(parents=True,exist_ok=True)
    result={"source":"2002 OBS.pak","status":"experimental-preview-only",
            "members":{},"previewFrames":0}
    example_names={"1064.obs","1085.obs","1100.obs","1135.obs","1146.obs"}
    for name,data in codec.source_members(source):
        if name not in reject:continue
        cid=f"{int(name[:4])-1000:04d}"
        if cid not in accepted:continue
        try:frames,palette=codec.unpack_frames(data)
        except ValueError as error:
            result["members"][name]={"error":str(error)}
            continue
        candidates=[]
        for i in codec.FRAMES:
            if i>=len(frames) or len(candidates)>=3:continue
            body,w,h,ox,oy=frames[i]
            try:image,diag=near_frame(body,w,h,palette) or (None,None)
            except ValueError:continue
            if image is None:continue
            filename=name.replace(".obs","")+f"-{i:02}.png"
            out=target/filename
            image.save(out,format="PNG",optimize=True)
            candidates.append({"index":i,"file":filename,"size":[w,h],
                "origin":[ox,oy],**diag})
            result["previewFrames"]+=1
            if name in example_names and i==0:
                print("OBS_NEAR_ROW_PREVIEW_BASE64 "+name+" "+base64.b64encode(out.read_bytes()).decode("ascii"))
        result["members"][name]={"candidates":candidates}
    (target/"probe-report.json").write_text(
       json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OBS_NEAR_ROW_PROBE_SUMMARY "+json.dumps({
        "members":len(result["members"]),
        "candidateMembers":sum(bool(v.get("candidates")) for v in result["members"].values()),
        "frames":result["previewFrames"],
        "perMember":{k:len(v.get("candidates",[])) for k,v in result["members"].items()}
    },ensure_ascii=False))
if __name__=="__main__":main()
