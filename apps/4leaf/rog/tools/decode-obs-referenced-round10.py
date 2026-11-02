#!/usr/bin/env python3
"""Original-byte-only round 10 OBS recovery: source CHR bodies, effects, palettes, animation tables.
Input is unshield's unpacked, SHA1-verified 2002 archive; no Windows binary runs.
Action labels and milliseconds remain UNVERIFIED. No missing member is fabricated.
"""
from pathlib import Path
import hashlib, importlib.util, io, json, struct, sys

HERE=Path(__file__).resolve().parent
def source_module():
    p=HERE/"decode-original-obs-bulk.py"
    spec=importlib.util.spec_from_file_location("leaf_original_bulk",p)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module
codec=source_module()
sha=lambda b:hashlib.sha256(b).hexdigest()
MISSING={
 ("obs",str(n)) for n in range(1025,1040)
}|{("obs","1041"),("obs","1057"),("obs2","1212"),("obs3","1256")}
CARD_BODIES={("obs",str(n)) for n in range(1025,1084)}|{
 ("obs2",str(n)) for n in range(1199,1222)}|{
 ("obs3",str(n)) for n in range(1254,1268)}|{("obs3","1276")}
assert len(MISSING)==19

def member_blocks(blob):
    if len(blob)<4:raise ValueError("member header truncated")
    count=struct.unpack_from("<I",blob)[0]
    if not 1<=count<=64:raise ValueError("invalid block count")
    p,blocks=4,[]
    for i in range(count):
        if p+128>len(blob):raise ValueError("block header truncated")
        frames_count=struct.unpack_from("<H",blob,p+66)[0]
        if frames_count>2048:raise ValueError("implausible frame count")
        p+=128;frames=[]
        for j in range(frames_count):
            if p+12>len(blob):raise ValueError("frame header truncated")
            n,w,h,ox,oy=struct.unpack_from("<IHHhh",blob,p)
            if n>64*1024*1024 or not 1<=w<=1024 or not 1<=h<=1024 or p+12+n>len(blob):
                raise ValueError("invalid frame bounds")
            frames.append((j,blob[p+12:p+12+n],w,h,ox,oy))
            p+=12+n
        if p+768>len(blob):raise ValueError("block palette truncated")
        pal=blob[p:p+768];p+=768
        blocks.append((frames,pal))
    return blocks,blob[p:]

def parse_actions(tail):
    if len(tail)<4:raise ValueError("missing action table")
    count=struct.unpack_from("<I",tail)[0]
    if count>1024:raise ValueError("invalid action count")
    p,items=4,[]
    for idx in range(count):
        if p+8>len(tail):raise ValueError("action truncated")
        duration,records=struct.unpack_from("<II",tail,p);p+=8
        if records>16384 or p+18*records>len(tail):raise ValueError("invalid key table")
        keys,events=[],[]
        for j in range(records):
            a=struct.unpack_from("<9H",tail,p);p+=18
            if a[1]==3:keys.append([a[0],a[4]])
            elif a[1]!=1:
                x,y=(a[5]-65536 if a[5]>=32768 else a[5],
                     a[6]-65536 if a[6]>=32768 else a[6])
                events.append([a[0],a[1],a[3],x,y])
        undefined=duration==0xffffffff and not keys
        # 0xFFFFFFFF + zero keyframes is a missing action slot, NOT looping.
        if duration==0xffffffff and keys:raise ValueError("empty-slot marker contains keys")
        items.append({"index":idx,"ticks":duration,"keys":keys,"events":events,
                      "undefined":undefined})
    rest=tail[p:]
    if not(rest==b"" or rest==bytes(34) or
           (len(rest)==162 and rest[:32]==bytes(32) and
            rest[32:34]==bytes([8,0]) and rest[34:]==bytes(128))):
        raise ValueError("unrecognized action trailer (%s bytes)"%len(rest))
    return items

def png_bytes(body,w,h,palette):
    try:
        img,_=codec.decode_rows(body,w,h,palette,minimum_opaque_pixels=0,alpha_from_runs=True)
        out=io.BytesIO();img.save(out,format="PNG",optimize=True)
        return out.getvalue(),None
    except (ValueError,OverflowError,IndexError) as e:return None,str(e)[:140]

def main(resources,repository):
    root=repository/"apps/4leaf/rog"
    outref=root/"original/OBS/referenced"
    outblocks=root/"original/OBS/blocks"
    evidence=root/"docs/evidence/obs-blocks"
    for d in (outref,outblocks,evidence):d.mkdir(parents=True,exist_ok=True)
    packfiles=sorted(p for p in resources.rglob("*") if p.is_file() and p.name.lower() in
                     {"obs.pak","obs2.pak","obs3.pak"})
    if len(packfiles)!=3:raise SystemExit("expected original OBS/OBS2/OBS3 archives: "+str(packfiles))
    all_members={};tables={};failed=[];effects=set()
    for pak in packfiles:
        pk=pak.stem.lower()
        for name,raw in codec.source_members(pak.read_bytes()):
            if not name.lower().endswith(".obs"):continue
            key=(pk,Path(name).stem)
            if key in all_members:raise ValueError("duplicate source OBS member "+str(key))
            try:
                blocks,tail=member_blocks(raw)
                actions=parse_actions(tail)
                all_members[key]=(blocks,raw,actions)
                tables["/".join(key)]={"blockCount":len(blocks),
                      "blockFrames":[len(x[0]) for x in blocks],"animations":actions,
                      "sourceSHA256":sha(raw)}
                if key in CARD_BODIES:
                    for a in actions:
                        for e in a["events"]:
                            if 1000<=e[2]<3000:effects.add(str(e[2]))
            except (ValueError,struct.error) as e:
                failed.append({"member":"/".join(key),"error":str(e)})
    refer=MISSING|{(pk,member) for pk in ("obs","obs2","obs3")
                   for member in effects if (pk,member) in all_members}
    # Two source-member effect anchors are mandatory independent of heuristic labels.
    refer|={("obs","1112"),("obs","1114")}
    refs,blocks_manifest={},{}
    recorded=0;ref_png=0;block_png=0
    for key,(blocks,raw,actions) in all_members.items():
        pak,member=key
        is_ref=key in refer
        is_split=len(blocks)>1
        if not is_ref and not is_split:continue
        record={"originalMember":pak.upper()+".pak/"+member+".obs",
                "sourceSHA256":sha(raw),"blocks":[]}
        selected=range(len(blocks)) if is_split else (0,)
        for bi in selected:
            frames,palette=blocks[bi]
            rows=[]
            for fi,body,w,h,ox,oy in frames:
                row={"index":fi,"width":w,"height":h,"originX":ox,
                     "originY":oy}
                if (is_ref and bi==0) or is_split:
                    content,error=png_bytes(body,w,h,palette)
                    if content is None:row["error"]=error
                    else:
                        folder="referenced" if is_ref and bi==0 else "blocks"
                        filename="%s-%s-%s%03d.png"%(pak,member,"" if folder=="referenced" else "b%d-"%bi,fi)
                        target=(outref if folder=="referenced" else outblocks)/filename
                        target.write_bytes(content)
                        row.update({"url":"./original/OBS/"+folder+"/"+filename,
                                    "sha256":sha(content)})
                        if folder=="referenced":ref_png+=1
                        else:block_png+=1
                rows.append(row)
            record["blocks"].append({"block":bi,"paletteSHA256":sha(palette),
                                     "frameCount":len(rows),"frames":rows})
        if is_ref:refs["/".join(key)]=record
        if is_split:blocks_manifest["/".join(key)]=record
        recorded+=1
    def save_manifest(folder,name,data):
        if data:
            (folder/"manifest.js").write_text(
                "/* Original OBS member bytes, palette and per-frame SHA256. */\n"
                +"window."+name+"="+json.dumps(data,sort_keys=True,separators=(",",":"))+";\n",encoding="utf-8")
    save_manifest(outref,"ORIGINAL_LEAF_OBS_REFERENCED",refs)
    save_manifest(outblocks,"ORIGINAL_LEAF_OBS_BLOCKS",blocks_manifest)
    (evidence/"animation-tables.json").write_text(json.dumps(tables,sort_keys=True),encoding="utf-8")
    recovered=[("/".join(key)) for key in sorted(MISSING)
               if "/".join(key) in refs and
               any("sha256" in f for b in refs["/".join(key)]["blocks"] for f in b["frames"])]
    pending=[("/".join(key)) for key in sorted(MISSING) if "/".join(key) not in recovered]
    summary={"installerSHA1":"86526d89679ae39b85fe9808da97ad871b7888d9",
       "memberCount":len(all_members),"tableDecoded":len(tables),
       "tableFailed":failed,"sourceMissingBodies":19,"recoveredMissingBodies":len(recovered),
       "recoveredMembers":recovered,"stillMissing":pending,"referencedMembers":len(refs),
       "referencedPNG":ref_png,"blockMembers":len(blocks_manifest),"blockPNG":block_png,
       "effectMemberNumbers":sorted(effects),
       "nativeActionLabels":"INFERRED","originalTickMilliseconds":"UNVERIFIED",
       "emptyActionMarker":"0xFFFFFFFF and no keys = undefined (VERIFIED)",
       "diceResultSequence":"UNVERIFIED"}
    (evidence/"round10-extract-summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    print("4LEAF_ROUND10_ORIGINAL_EXTRACT",json.dumps({k:summary[k] for k in
          ("memberCount","tableDecoded","recoveredMissingBodies","stillMissing",
           "referencedMembers","referencedPNG","blockMembers","blockPNG")}))
    if ref_png<1 or len(recovered)<1:raise SystemExit("no new original CHR bodies were recovered")
    if len(all_members)<200:raise SystemExit("original census implausibly small")
    return 0

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("usage: decoder resources-dir checkout-root")
    sys.exit(main(Path(sys.argv[1]),Path(sys.argv[2])))
