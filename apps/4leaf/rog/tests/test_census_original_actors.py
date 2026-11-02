#!/usr/bin/env python3
"""Synthetic PAK/OBS/CHR/DLL end-to-end census test without original installation."""
import importlib.util, json, struct, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("census",ROOT/"tools/census-original-actors.py")
C=importlib.util.module_from_spec(sp)
sp.loader.exec_module(C)

def encode(mask,colour):
    h,w=mask.shape
    runs=[]
    for y in range(h):
        x=0
        while x<w:
            if not mask[y,x]:
                x+=1;continue
            start=x
            while x<w and mask[y,x]:x+=1
            runs.append((y*640+start,bytes(colour(y,i) for i in range(start,x))))
    out=struct.pack("<HH",len(runs),runs[0][0])
    end=runs[0][0]
    for n,(at,px) in enumerate(runs):
        if n:out+=struct.pack("<H",at-end)
        out+=bytes((len(px)//4,len(px)%4))+px
        end=at+len(px)
    return out

def member(masks,trailer=b"",colour=lambda y,x:7):
    header=bytearray(132);struct.pack_into("<H",header,70,len(masks))
    out=bytes(header)
    for mask in masks:
        data=encode(mask,colour);h,w=mask.shape
        out+=struct.pack("<IHHhh",len(data),w,h,-w//2,-h)+data
    return out+bytes(range(256))*3+trailer

def pak(entries):
    raw=struct.pack("<I",len(entries)^0xffffffff);body=b""
    for name,data in entries:
        body+=data
        raw+=bytes(v^255 for v in name.encode().ljust(24,b"\0"))+struct.pack("<I",(len(body)-1)^0xffffffff)
    return raw+body

def shape(face,phase=0):
    mask=np.zeros((48,40),bool)
    if face=="rear":mask[6:46,12:28]=True
    elif face=="side":
        mask[6:46,10:22]=True;mask[14:20,22:36]=True
    else:
        mask[6:46,11:29]=True;mask[8:14,4:11]=True
    mask[0:6,16:24]=True
    if phase:
        shift=[0,8,14,8,0,-8][phase%6]
        mask[40:48,:]=False
        mask[40:48,max(0,14+shift):max(0,20+shift)]=True
        mask[40:48,22-shift//2:26-shift//2]=True
    return mask

def layout():
    frames=[]
    for face in ("rear","side","front"):
        frames+=[shape(face),shape(face),shape(face)]
        frames+=[shape(face,phase=i) for i in range(1,7)]
        frames+=[shape(face,2),shape(face,4)]
    frames+=[shape("side",i) for i in (1,2,3,4)]
    assert len(frames)==37
    return frames

def main():
    with tempfile.TemporaryDirectory() as t:
        root=Path(t); res=root/"source/Dice";res.mkdir(parents=True)
        rog=root/"repo/apps/4leaf/rog"
        (rog/"original/OBS/action-full").mkdir(parents=True)
        (rog/"original/OBS/bulk").mkdir(parents=True)
        (rog/"original/chessmen.json").write_text(json.dumps([{"id":c} for c in ("0040","0087","0099")]))
        (rog/"original/OBS/action-full/manifest.js").write_text('window.DATA={\n "0040": {"frames": []}\n};\n')
        (rog/"genesis-chessman-actors.js").write_text("const NON_ACTOR_OBS=Object.freeze({'0099':'effect'});")
        m87=member([shape("front",i%6) for i in range(13)],colour=lambda y,x:0 if x==11 else 9)
        recs,_=C.decode_member(m87)
        old=np.array(recs[0]["image"].convert("RGBA"))
        lost=int((old[...,3]>0)[:,11].sum())
        old[:,11,3]=0
        Image.fromarray(old).save(rog/"original/OBS/bulk/1087-00.png")
        trailer=b"\x11\x22"+bytes(C.STARTS[:7])+b"\x99"
        (res/"OBS.pak").write_bytes(pak([("1040.obs",member(layout())),("1087.obs",m87),("1099.obs",member([shape("front")]*3))]))
        (res/"OBS2.pak").write_bytes(pak([("2001.obs",member(layout(),trailer=trailer))]))
        (res/"OBS3.pak").write_bytes(pak([("3001.obs",member([shape("front")]*37))]))
        def chr_record(card,ref=0):
            r=bytearray(472)
            struct.pack_into("<H",r,10,int(card))
            struct.pack_into("<H",r,12,1000+int(card))
            if ref:struct.pack_into("<H",r,300,ref)
            return bytes(r)
        (res/"CHR.pak").write_bytes(pak([(c+".chr",chr_record(c,2001 if c=="0087" else 0)) for c in ("0040","0087","0099")]))
        (root/"source/Dice.dll").write_bytes(b"MZ"+b"\0"*100+struct.pack("<10H",*C.STARTS)+b"\0"*50)
        data,summary=C.run(root/"source",root/"repo",root/"artifact")
        assert summary["actionFullExt"]=={"0087":13},summary
        assert summary["obs23Candidates"]==1,summary
        assert (rog/"original/OBS/obs23-candidates/obs2-2001-36.png").exists()
        assert not list((rog/"original/OBS/obs23-candidates").glob("obs3-*"))
        assert '"assignedCard": null' in (rog/"original/OBS/obs23-candidates/manifest.js").read_text()
        kinds={row["member"]:(row.get("layout37") or {}).get("matches") for row in data["members"]}
        assert kinds=={"1040.obs":True,"1087.obs":None,"1099.obs":None,"2001.obs":True,"3001.obs":False},kinds
        img=np.array(Image.open(rog/"original/OBS/action-full-ext/1087-00.png").convert("RGBA"))
        assert int((img[...,3]>0)[:,11].sum())==lost>0
        assert data["src04Bulk"]["1087"]=={"framesCompared":1,"legacyDroppedPixels":lost}
        offsets={(x["offset"],x["hypothesis"]) for x in data["chr"]["offsetTests"] if x["fraction"]==1.0}
        assert (10,"cardNumber") in offsets and (12,"member1NNN") in offsets,offsets
        assert data["chr"]["memberRefs"]["0087"][0]["value"]==2001
        assert any(x["pattern"]=="blockStarts" and x["width"]==2 for x in data["binaries"][0]["patternHits"])
        assert any(x["pattern"]=="blockStarts" and x["width"]==1 for x in next(x for x in data["members"] if x["member"]=="2001.obs")["trailerPatternHits"])
        assert data["claims"]["exeActionTableDecoded"] is False
        print("CENSUS SYNTHETIC PASS",json.dumps(summary))
if __name__=="__main__":
    main()
