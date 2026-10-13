#!/usr/bin/env python3
"""Decode all 32 ORIGINAL 4LEAF Dice 145x97 isometric TIS card tiles.

Source: archived 4Leaf.exe InstallShield cabinet, 4Leaf_Files/Dice/TIS.pak.
These are real paletted FAST.PAL.COLORKEY sprite frames, not image searches,
redraws, CSS facsimiles or cropped historical screenshots.

PAK: XOR-FF header/count and 28-byte file entries.
TIS: proprietary resource metadata before FAST.PAL.COLORKEY.
SPR: 128-byte frame header; 12-byte width/height frame record; row-coded
bottom-up 8-bit indexed pixels and terminal 256*3 RGB palette.
Identical 11149-byte bitmap payloads share the same line offset template:
reusing it avoids false-positive row markers inside decorative glyph pixels.
"""
from pathlib import Path
from PIL import Image
import struct,json,sys

ROOT=Path(sys.argv[1])
OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True)

def entries(data):
    n=struct.unpack_from('<I',data)[0]^0xffffffff
    if not (1<n<5000):raise ValueError('Invalid PAK resource count')
    start=4+28*n;last=0
    for i in range(n):
        record=data[4+28*i:4+28*(i+1)]
        name=bytes(v^255 for v in record[:24]).split(b'\x00')[0].decode('cp949')
        end=(struct.unpack_from('<I',record,24)[0]^0xffffffff)+1
        if not(last<end<=len(data)-start):raise ValueError('Bad resource span '+name)
        yield name,data[start+last:start+end]
        last=end

def scanlines(raw):
    return [j for j in range(1,len(raw)-4)
            if raw[j+1] in (0,1,2,3) and 15<=raw[j+2]<=45
            and raw[j+3] in (1,3)]

def unwrap(raw):
    at=raw.find(b'FAST.PAL.COLORKEY')
    if at<0:raise ValueError('No original indexed sprite signature')
    file=raw[at:]
    count=struct.unpack_from('<H',file,66)[0]
    length,w,h,x,y=struct.unpack_from('<IHHhh',file,128)
    if not(0<count<=4 and w==145 and h==97 and 10000<=length<=17000):
        raise ValueError('Unexpected original TIS format')
    pixels=file[140:140+length]
    if len(pixels)!=length:raise ValueError('Truncated tile')
    return pixels,file[-768:],w,h,count,length

files=dict(entries((ROOT/'Dice'/'TIS.pak').read_bytes()))
assert '0006.tis' in files
template_pixels,_,_,h,_,_=unwrap(files['0006.tis'])
template=scanlines(template_pixels)
assert len(template)==h

manifest={}
for name,raw in sorted(files.items()):
    if not name.lower().endswith('.tis'):continue
    body,palette,w,h,frames,length=unwrap(raw)
    marks=template if length==11149 else scanlines(body)
    if len(marks)!=h:raise ValueError('Scanline count error '+name+': '+str(len(marks)))
    output=bytearray(w*h)
    for iy in range(h):
        segment=body[marks[iy]+4:marks[iy+1] if iy+1<h else len(body)]
        if len(segment)>w:raise ValueError('Invalid card row '+name)
        x=(w-len(segment))//2
        output[iy*w+x:iy*w+x+len(segment)]=segment
    image=Image.frombytes('P',(w,h),bytes(output))
    image.putpalette(palette)
    image.info['transparency']=0
    bitmap=image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if bitmap.getbbox() is None:raise ValueError('Empty source TIS card '+name)
    final=OUT/(Path(name).stem+'.png')
    bitmap.save(final,optimize=True)
    manifest[Path(name).stem]={'width':w,'height':h,'pixelEncoding':'8bit indexed sprite','frames':frames,'bytes':final.stat().st_size}
assert len(manifest)==32,('Expected all 32 original graphic pieces',len(manifest))

# DMP includes each tileset's original filename and CP949 label in
# 128-byte palette descriptors, with no inferred or invented tile labels.
label_to_graphic={}
for name,dat in entries((ROOT/'Dice'/'DMP.pak').read_bytes()):
    if not name.endswith('.dmp'):continue
    count=struct.unpack_from('<I',dat,272)[0]
    for j in range(count):
        rec=dat[276+j*128:276+(j+1)*128]
        filename=rec[:32].split(b'\x00')[0].decode('cp949','replace')
        label=rec[64:].split(b'\x00')[0].decode('cp949','replace')
        if filename.lower().endswith('.tis') and label and Path(filename).stem in manifest:
            stem=Path(filename).stem
            if label in label_to_graphic and label_to_graphic[label]!=stem:
                raise ValueError('Contradictory original Korean tile label '+label)
            label_to_graphic[label]=stem

# Original tiles.js expresses decoded CP949 DMP stage event categories.
# Retain every historical warp variant and all four elemental floor types.
types={
 '4칸전진':'boost4','3칸전진':'boost','4리프':'clover','어빌리티':'ability',
 '신의축복':'blessing','상자':'chest','컵':'attribute','신의저주':'curse',
 '디스크':'attribute','사느냐죽느냐':'doa','더미':'normal',
 '싸움':'arena','종료':'goal','감옥':'prison','바뀌는랜덤':'joker',
 '불운':'spade','소울풀':'ability100','시작':'start','검':'attribute',
 '완드':'attribute','워프1':'warp','워프3':'warp','워프4':'warp',
 '랜덤한번':'random','연습':'practice'
}
by_type={}
for label,id in sorted(label_to_graphic.items()):
    kind=types.get(label)
    if kind:by_type.setdefault(kind,{})[label]=id
data={'source':'Original 4Leaf client / Dice/TIS.pak plus Dice/DMP.pak palette index labels',
      'tiles':manifest,'originalNameToTileId':label_to_graphic,'byEventType':by_type}
(OUT/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(OUT/'art.js').write_text('window.ORIGINAL_LEAF_TILE_ART='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')
print('ORIGINAL 4LEAF GRAPHICS RESTORED:',len(manifest),'original isometric TIS tiles; mapped',len(label_to_graphic),'original Korean labels')
for label,id in sorted(label_to_graphic.items()):
    print('TILE ART',id,label)
