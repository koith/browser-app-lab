#!/usr/bin/env python3
"""Reproducible census of original OBS/OBS2/OBS3, CHR and binary evidence.

Works only on SHA1-verified 2002 client extracted with unshield. No Win32
execution, synthetic frames, or speculative actor/card assignments.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
PACKS = {"obs.pak", "obs2.pak", "obs3.pak"}
CHR_RECORD = 472
STARTS = [0, 3, 9, 11, 14, 20, 22, 25, 31, 33]
PATTERNS = {
    "blockStarts": [0, 3, 9, 11, 14, 20, 22, 25, 31, 33],
    "blockEndsInclusive": [2, 8, 10, 13, 19, 21, 24, 30, 32, 36],
    "blockEndsExclusive": [3, 9, 11, 14, 20, 22, 25, 31, 33, 37],
    "blockLengths": [3, 6, 2, 3, 6, 2, 3, 6, 2, 4],
}

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

codec = load("leaf_census_codec", "decode-original-obs-bulk.py")
structure = load("leaf_census_structure", "obs_structure.py")

def sha(b):
    return hashlib.sha256(b).hexdigest()

def member_bytes(blob):
    count = struct.unpack_from("<H", blob, 70)[0]
    cursor = 132
    for _ in range(count):
        length = struct.unpack_from("<I", blob, cursor)[0]
        cursor += 12 + length
    return blob[:132], blob[cursor + 768:]

def decode_member(blob):
    frames, palette = codec.unpack_frames(blob)
    recs = []
    for i, (data, w, h, ox, oy) in enumerate(frames):
        row = {"index": i, "width": w, "height": h,
               "originX": ox, "originY": oy, "bodyBytes": len(data),
               "bodySHA256": sha(data)}
        try:
            img, diag = codec.decode_rows(data, w, h, palette, minimum_opaque_pixels=0,
                                          alpha_from_runs=True)
            row.update(status="DECODED", image=img, opaquePixels=diag["opaquePixels"])
        except (ValueError, OverflowError) as exc:
            row.update(status="FAILED", error=str(exc)[:200])
        recs.append(row)
    return recs, palette

def upright(rec):
    return np.flipud(np.array(rec["image"].convert("RGBA")))

def find_patterns(data, minimum=5):
    hits = []
    for label, seq in PATTERNS.items():
        for width, fmt in ((1, "B"), (2, "<H"), (4, "<I")):
            for start in range(len(seq) - minimum + 1):
                needle = b"".join(struct.pack(fmt, v) for v in seq[start:start+minimum])
                pos = data.find(needle)
                while pos >= 0:
                    k = start + minimum
                    end = pos + len(needle)
                    while k < len(seq) and data[end:end+width] == struct.pack(fmt, seq[k]):
                        k += 1
                        end += width
                    hits.append({"pattern": label, "width": width, "offset": pos, "items": [start, k-1]})
                    pos = data.find(needle, pos+1)
    best = {}
    for hit in hits:
        key = (hit["pattern"], hit["width"], hit["offset"]-hit["items"][0]*hit["width"])
        if key not in best or hit["items"][1]-hit["items"][0] > best[key]["items"][1]-best[key]["items"][0]:
            best[key] = hit
    return sorted(best.values(), key=lambda v:(v["offset"],v["pattern"]))

def chr_offset_tests(records):
    ids = sorted(records)
    matches = []
    for width, fmt in ((2, "<H"), (1, "B")):
        for off in range(CHR_RECORD-width+1):
            values = {i:struct.unpack_from(fmt,records[i],off)[0]
                      for i in ids if len(records[i]) >= off+width}
            if not values:
                continue
            for name, fn in (("cardNumber",lambda x:x),("member1NNN",lambda x:1000+x)):
                hit = [i for i,v in values.items() if v == fn(int(i))]
                frac = len(hit)/len(values)
                if frac >= .5:
                    matches.append({"offset":off,"width":width,"hypothesis":name,
                                    "fraction":round(frac,3),"misses":sorted(set(values)-set(hit))[:40]})
    return matches

def chr_member_refs(records, members):
    nums = {}
    for pak,name in members:
        stem = Path(name).stem
        if stem.isdigit():
            nums.setdefault(int(stem), []).append(pak+"/"+name)
    result = {}
    for card,blob in records.items():
        hits = []
        for off in range(len(blob)-1):
            v = struct.unpack_from("<H",blob,off)[0]
            if v >= 1000 and v in nums:
                hits.append({"offset":off,"value":v,"members":nums[v]})
        if hits:
            result[card] = hits
    return result

def export_frames(recs, stem, folder, url_prefix):
    folder.mkdir(parents=True, exist_ok=True)
    frames = []
    for rec in recs:
        if rec["status"] != "DECODED":
            continue
        dst = "%s-%02d.png" % (stem,rec["index"])
        buf = io.BytesIO()
        rec["image"].save(buf,format="PNG",optimize=True)
        payload = buf.getvalue()
        (folder/dst).write_bytes(payload)
        frames.append({"index":rec["index"],"url":url_prefix+dst,
                       "width":rec["width"],"height":rec["height"],
                       "originX":rec["originX"],"originY":rec["originY"],
                       "sha256":sha(payload)})
    return frames

def write_manifest(folder, var, data, comment):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"manifest.js").write_text("/* "+comment+" */\nwindow."+var+"="+
        json.dumps(data,indent=1,sort_keys=True)+";\n",encoding="utf-8")

def contact_sheet(recs, dst, cell=96, cols=10):
    decoded = [r for r in recs if r["status"]=="DECODED"]
    if not decoded:
        return
    sheet = Image.new("RGB",(cols*cell,((len(decoded)+cols-1)//cols)*(cell+14)),(52,56,96))
    draw = ImageDraw.Draw(sheet)
    for n,r in enumerate(decoded):
        im = r["image"].transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if im.width>cell-4 or im.height>cell-4:
            im.thumbnail((cell-4,cell-4))
        x,y = (n%cols)*cell,(n//cols)*(cell+14)
        sheet.paste(im,(x+(cell-im.width)//2,y+cell-2-im.height),im)
        draw.text((x+3,y+cell),str(r["index"]),fill=(255,220,90))
    dst.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(dst,optimize=True)

def checked_in(root):
    rog=root/"apps/4leaf/rog"
    cards={row["id"] for row in json.loads((rog/"original/chessmen.json").read_text())}
    txt=(rog/"original/OBS/action-full/manifest.js").read_text()
    complete=set(re.findall(r'^ "(\d{4})": \{',txt,re.M))
    actors=(rog/"genesis-chessman-actors.js").read_text()
    block=re.search(r"NON_ACTOR_OBS=Object\.freeze\(\{(.*?)\}\)",actors,re.S)
    non_actor=set(re.findall(r"'(\d{4})'",block.group(1))) if block else set()
    return rog,cards,complete,non_actor

def run(resources,root,artifact):
    rog,cards,complete,non_actor=checked_in(root)
    artifact.mkdir(parents=True,exist_ok=True)
    census={"format":"4LEAF_ACTOR_CENSUS_V1","alpha":"written-runs",
            "installerSHA1":"86526d89679ae39b85fe9808da97ad871b7888d9",
            "packs":[],"members":[],"chr":{},"binaries":[],
            "exports":{"actionFullExt":{},"obs23Candidates":{}},"src04Bulk":{},
            "claims":{"exeActionTableDecoded":False,"candidateCardAssignment":"only with CHR byte evidence",
                      "layoutTest":"structure of pixels, INFERRED"}}
    paks=sorted(p for p in resources.rglob("*") if p.is_file() and p.name.lower() in PACKS)
    if not paks:
        raise SystemExit("no OBS*.pak under "+str(resources))
    member_names=[]
    ext,candidates={},{}
    for pak in paks:
        raw=pak.read_bytes()
        census["packs"].append({"name":pak.name,"sha256":sha(raw),"bytes":len(raw)})
        for name,blob in codec.source_members(raw):
            if not name.lower().endswith(".obs"):
                continue
            member_names.append((pak.name,name))
            stem=Path(name).stem
            row={"pak":pak.name,"member":name,"sourceSHA256":sha(blob),"bytes":len(blob)}
            try:
                frames,palette=decode_member(blob)
                header,trailer=member_bytes(blob)
            except (ValueError,struct.error) as err:
                row["parseError"]=str(err)[:200]
                census["members"].append(row)
                continue
            good=[r for r in frames if r["status"]=="DECODED"]
            row.update(frames=len(frames),decoded=len(good),
                maxSize=[max((r["width"] for r in good),default=0),
                         max((r["height"] for r in good),default=0)],
                headerHex=header.hex(),trailerBytes=len(trailer),
                trailerSHA256=sha(trailer),
                headerPatternHits=find_patterns(header),
                trailerPatternHits=find_patterns(trailer))
            seq=[(upright(r),r["originX"],r["originY"]) for r in good] if len(good)==len(frames) else []
            if seq:
                row["layout37"]=structure.test_layout_37(seq) if len(seq)==37 else None
                row["blockProposal"]=structure.segment(seq) if len(seq)>1 else [[0,0]]
            path=artifact/"trailers"/(pak.stem+"-"+stem+".bin")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(header+b"--TRAILER--"+trailer)
            contact_sheet(frames,artifact/"sheets"/(pak.stem+"-"+stem+".png"))
            card="0"+stem[1:] if stem.isdigit() and len(stem)==4 and stem[0]=="1" else None
            is_obs=pak.name.lower()=="obs.pak"
            if is_obs and card in cards and card not in complete and card not in non_actor and len(good)==len(frames) and good:
                f=export_frames(frames,stem,rog/"original/OBS/action-full-ext","./original/OBS/action-full-ext/")
                ext[card]={"originalMember":"OBS.pak/"+name,"sourceSHA256":sha(blob),
                           "frameCount":len(f),"frames":f,
                           "layout37":bool((row.get("layout37") or {}).get("matches")),
                           "blockProposal":row.get("blockProposal"),"actionTable":"UNDECODED"}
                census["exports"]["actionFullExt"][card]=len(f)
            if not is_obs and len(frames)==37 and len(good)==37 and (row.get("layout37") or {}).get("matches"):
                key=pak.stem.lower()+"-"+stem
                f=export_frames(frames,key,rog/"original/OBS/obs23-candidates","./original/OBS/obs23-candidates/")
                candidates[key]={"originalMember":pak.name+"/"+name,"sourceSHA256":sha(blob),
                                 "frames":f,"assignedCard":None,"status":"QUARANTINED-candidate/layout-37-pixels"}
                census["exports"]["obs23Candidates"][key]=37
            if is_obs:
                lost,compared=0,0
                for r in good:
                    path=rog/"original/OBS/bulk"/("%s-%02d.png"%(stem,r["index"]))
                    if not path.exists():
                        continue
                    prev=np.array(Image.open(path).convert("RGBA"))
                    new=np.array(r["image"].convert("RGBA"))
                    if prev.shape==new.shape:
                        lost+=int(((new[...,3]>0)&(prev[...,3]==0)).sum())
                        compared+=1
                if compared:
                    census["src04Bulk"][stem]={"framesCompared":compared,"legacyDroppedPixels":lost}
            census["members"].append(row)
    recs={}
    for pak in resources.rglob("*"):
        if pak.is_file() and pak.name.lower()=="chr.pak":
            for name,blob in codec.source_members(pak.read_bytes()):
                if name.lower().endswith(".chr") and name[:4].isdigit():
                    recs[name[:4]]=blob
    folder=artifact/"chr"
    folder.mkdir(exist_ok=True)
    for card,blob in recs.items():
        (folder/(card+".bin")).write_bytes(blob)
    census["chr"]={"records":len(recs),"recordBytes":sorted({len(v) for v in recs.values()}),
                   "offsetTests":chr_offset_tests(recs) if recs else [],
                   "memberRefs":chr_member_refs(recs,[(pak,n) for pak,n in member_names if pak.lower()!="obs.pak"]),
                   "patternHits":{c:hit for c,hit in ((c,find_patterns(v)) for c,v in recs.items()) if hit}}
    for path in sorted(resources.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".dll",".exe"):
            payload=path.read_bytes()
            census["binaries"].append({"file":str(path.relative_to(resources)),
                                       "sha256":sha(payload),"bytes":len(payload),
                                       "patternHits":find_patterns(payload)[:200]})
    if ext:
        write_manifest(rog/"original/OBS/action-full-ext","ORIGINAL_LEAF_EXT_ACTION_FRAMES",ext,
                       "Complete original card-body frames; action table UNDECODED")
    if candidates:
        write_manifest(rog/"original/OBS/obs23-candidates","ORIGINAL_LEAF_OBS23_CANDIDATES",candidates,
                       "QUARANTINED OBS2/OBS3 candidates; no card assignment without CHR evidence")
    dest=rog/"docs/evidence/obs-census"
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"census.json").write_text(json.dumps(census,indent=1,sort_keys=True),encoding="utf-8")
    summary={"members":len(census["members"]),
             "members37":sum(1 for r in census["members"] if r.get("frames")==37),
             "layout37Matches":sum(1 for r in census["members"] if (r.get("layout37") or {}).get("matches")),
             "actionFullExt":census["exports"]["actionFullExt"],"obs23Candidates":len(candidates),
             "chrRecords":len(recs),"chrOffsetTests":len(census["chr"]["offsetTests"]),
             "binaryPatternHits":{r["file"]:len(r["patternHits"]) for r in census["binaries"]},
             "trailerPatternHitMembers":sum(1 for r in census["members"] if r.get("trailerPatternHits")),
             "src04BulkDroppedPixels":sum(v["legacyDroppedPixels"] for v in census["src04Bulk"].values())}
    (artifact/"summary.json").write_text(json.dumps(summary,indent=1))
    print("ORIGINAL_ACTOR_CENSUS",json.dumps(summary))
    return census,summary

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for arg in ("resources","repo","artifact"):
        parser.add_argument(arg)
    args=parser.parse_args()
    run(Path(args.resources),Path(args.repo),Path(args.artifact))
