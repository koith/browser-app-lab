#!/usr/bin/env python3
"""SRC-04 original PAK run-alpha proof. Execute only with independently
SHA1-verified 2002 installer PAKs; never run original Windows code.

Every one of 97 published original CHR bodies is decoded AGAIN directly from
the original binary VIDEO RLE using the written-run alpha mask, and every
corresponding published PNG is compared at the full RGBA pixel level.
The missing 0156/OBS2-1222 is not invented. A separate legacy-vs-correct
comparison records palette-index-0 pixels which the legacy converter lost.
Historical action labels, MVE geometry and FPS are not proved here.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/"tools"
def load_script(name,filename):
    spec=importlib.util.spec_from_file_location(name,TOOLS/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

codec=load_script("native_640_codec","decode-original-obs-bulk.py")
extended=load_script("native_extended_codec","decode-obs-extended.py")
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
def js_map(path):
    source=path.read_text("utf8")
    begin=source.index("={")+1
    return json.loads(source[begin:source.rfind(";")])
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pak-dir",type=Path,required=True)
    ap.add_argument("--report",type=Path,default=Path("4leaf-src04-run-alpha-audit.json"))
    args=ap.parse_args()
    by_archive={}
    for pak in ("OBS.pak","OBS2.pak","OBS3.pak"):
        files=list(args.pak_dir.rglob(pak))
        if len(files)!=1:
            raise RuntimeError("%s expected one extracted source, got %d"%(pak,len(files)))
        raw=files[0].read_bytes()
        by_archive[pak]={name.lower():member for name,member in codec.source_members(raw)}
    assert [len(by_archive[k]) for k in ("OBS.pak","OBS2.pak","OBS3.pak")]==[166,53,26]
    bodymap=json.loads((ROOT/"docs/evidence/source-maps/card-body-map.json").read_text())
    assert bodymap["source"].startswith("Dice/CHR.pak")
    assert len(bodymap["cards"])==98
    manifests={
        "full":js_map(ROOT/"original/OBS/action-full/manifest.js"),
        "ext":js_map(ROOT/"original/OBS/action-full-ext/manifest.js"),
        "obs23":js_map(ROOT/"original/OBS/obs23-actors/manifest.js"),
        "referenced":js_map(ROOT/"original/OBS/referenced/chr-bodies-manifest.js")
    }
    cards=bodymap["cards"]
    published=0
    source_members=0
    palettes0=0
    lost_legacy=0
    diff=[]
    anomalies=[]
    affected=[]
    for card,record in sorted(cards.items()):
        member=record["bodyMember"]
        pak=record["bodyPak"]
        if card=="0156":
            assert member=="1222" and "1222.obs" not in by_archive["OBS2.pak"]
            continue
        assert pak in by_archive and member+".obs" in by_archive[pak],(card,pak,member)
        raw=by_archive[pak][member+".obs"]
        assert sha(raw)==record["bodySHA256"],"source-body SHA "+card
        frames,palette,trailer,error=extended.unpack_member(raw)
        assert error is None and frames and palette,(card,error)
        key="0"+member[1:]
        lookup=pak.replace(".pak","").lower()+"/"+member
        if pak=="OBS.pak":
            chosen=manifests["full"].get(key) or manifests["ext"].get(key)
        else:
            chosen=manifests["obs23"].get(lookup)
        if chosen is None:
            chosen=manifests["referenced"].get(lookup)
        assert chosen is not None,(card,"no source manifest",lookup)
        exported=chosen.get("frames")
        if exported is None:
            blocks=chosen.get("blocks")
            assert len(blocks)==1
            exported=blocks[0]["frames"]
        assert exported,(card,"empty published original")
        assert sha(raw)==record["bodySHA256"]
        source_members+=1
        for f in exported:
            i=f["index"]
            assert 0<=i<len(frames),(card,"invalid native frame",i,len(frames))
            body,w,h,ox,oy=frames[i]
            assert (w,h,ox,oy)==(f["width"],f["height"],f["originX"],f["originY"]),(card,i,"geometry")
            expected,_=codec.decode_rows(body,w,h,palette,minimum_opaque_pixels=0,
                                         alpha_from_runs=True)
            legacy,_=codec.decode_rows(body,w,h,palette,minimum_opaque_pixels=0,
                                       alpha_from_runs=False)
            expected=expected.convert("RGBA")
            legacy=legacy.convert("RGBA")
            pixels=expected.tobytes()
            before=legacy.tobytes()
            alpha_restored=0
            for n in range(3,len(pixels),4):
                if pixels[n]>0 and before[n]==0:alpha_restored+=1
            if alpha_restored:
                palettes0+=1;lost_legacy+=alpha_restored
                if len(affected)<50:affected.append([card,i,alpha_restored])
            url=f["url"]
            assert url.startswith("./original/OBS/"),(card,url)
            file=ROOT/url[2:]
            with Image.open(file) as im:
                published_rgba=im.convert("RGBA")
                if published_rgba.size!=(w,h) or published_rgba.tobytes()!=pixels:
                    if len(diff)<80:diff.append({"card":card,"frame":i,"path":url,
                        "expectedSize":[w,h],"actualSize":list(published_rgba.size),
                        "legacyIndexZeroWasLost":alpha_restored,
                        "publishedSHA256":sha(file.read_bytes()),
                        "manifestSHA256":f["sha256"]})
            if sha(file.read_bytes())!=f["sha256"]:
                anomalies.append({"card":card,"frame":i,"manifestShaMismatch":url})
            published+=1
    assert source_members==97,(source_members,"not all CHR source bodies")
    assert published>=3700,(published,"original published frame count unexpectedly small")
    report={
      "installerSHA1":"86526d89679ae39b85fe9808da97ad871b7888d9",
      "method":"decode 2002 original PAK with decode_rows(alpha_from_runs=True)",
      "sourceBodies":source_members,"sourceMissing":"0156/OBS2-1222",
      "sourceFramesCompared":published,"framesWithPalette0Filled":palettes0,
      "sourcePalette0PixelsLostByLegacy":lost_legacy,
      "exampleSourceRestorations":affected,
      "publishedFramePixelMismatches":diff,
      "manifestShaMismatches":anomalies,
      "historical3dAndActions":"UNVERIFIED"
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n","utf8")
    print("SRC04_NATIVE_PAK_ALPHA_REEXTRACTION_REPORT",
          json.dumps({k:v for k,v in report.items() if k not in
                      ("exampleSourceRestorations","publishedFramePixelMismatches","manifestShaMismatches")},
                     ensure_ascii=False))
    if diff or anomalies:
        raise AssertionError("Source-correct run-alpha differs from published frames: "+
                             str(len(diff))+" mismatches / "+str(len(anomalies))+
                             " invalid SHA. See saved report.")
    print("SRC04_ALL_97_CHR_NATIVE_RUN_ALPHA_PIXEL_MATCH_PASS")
if __name__=="__main__":
    main()
