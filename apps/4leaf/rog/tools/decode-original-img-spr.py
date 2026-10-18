#!/usr/bin/env python3
"""Source-authentic 2002 4LEAF Dice/IMG.pak FAST.PAL.COLORKEY SPR extraction.

Decoded against verified original roll.spr from original archive:
- record header u16 count, u16 first-video-buffer offset
- first packet: quarter-byte length (a*4+b) + palette index bytes
- remaining packets: u16 transparent skip + quarter-byte length + pixels
- source scanlines use a FIXED 640-byte stride even when logical sprite width
  is 158 or 69 (2002 native video-buffer convention).
- transparent index 0; source 256x RGB palette appended after the frames.

This is NOT Ragnarok SPR. Refuse corrupt runs or invented color data.
Only inspect archive bytes. The original executable is never run.
"""
import sys, json, re, io, hashlib, struct
from pathlib import Path
from PIL import Image

VIDEO_STRIDE=640
SUPPORTED=('roll.spr','eventRoll1.spr')
def u16(buf,i):
    if i+2>len(buf): raise ValueError('Truncated unsigned short')
    return struct.unpack_from('<H',buf,i)[0]
def u32(buf,i):
    if i+4>len(buf): raise ValueError('Truncated unsigned integer')
    return struct.unpack_from('<I',buf,i)[0]

def members(data):
    if len(data)<32:raise ValueError('Short original IMG.pak')
    count=u32(data,0)^0xffffffff
    if not 1<=count<=2000:raise ValueError('Invalid original PAK index count')
    base=4+count*28
    if base>=len(data):raise ValueError('Truncated original PAK')
    previous=0
    for i in range(count):
        entry=data[4+i*28:4+(i+1)*28]
        name=bytes(c^255 for c in entry[:24]).split(b'\\0')[0].decode('cp949','replace')
        end=(u32(entry,24)^0xffffffff)+1
        if end<=previous or base+end>len(data):raise ValueError('Invalid member '+name)
        yield name,bytes(data[base+previous:base+end])
        previous=end
    if base+previous!=len(data):raise ValueError('Incomplete IMG source index')

def frames(raw):
    start=raw.find(b'FAST.PAL.COLORKEY')
    if start<0:raise ValueError('Not source FAST.PAL.COLORKEY SPR')
    data=raw[start:]
    count=u16(data,66)
    if not 1<=count<=64:raise ValueError('Implausible SPR animation count')
    cursor=128
    out=[]
    for i in range(count):
        if cursor+12>len(data):raise ValueError('Short original SPR frame header')
        n,w,h,ox,oy=struct.unpack_from('<IHHhh',data,cursor)
        if not (1<=n<=100000 and 1<=w<=VIDEO_STRIDE and 1<=h<=1024
                and cursor+12+n<=len(data)):
            raise ValueError('Source SPR frame out of bounds')
        out.append((i,w,h,ox,oy,data[cursor+12:cursor+12+n]))
        cursor+=12+n
    palette=data[cursor:cursor+768]
    if len(palette)!=768 or cursor+768!=len(data):
        raise ValueError('Missing/trailing true 256-colour source palette')
    return out,palette

def sprite_rgba(blob,w,h,palette):
    if len(blob)<10:raise ValueError('Source palette run too short')
    count=u16(blob,0)
    if not 1<=count<=2048:raise ValueError('Invalid source run count')
    cursor=u16(blob,2)
    pos=4
    indices=bytearray(w*h)
    opaque=0
    for i in range(count):
        if i:
            cursor+=u16(blob,pos)
            pos+=2
        if pos+2>len(blob):raise ValueError('Truncated palette packet')
        length=blob[pos]*4+blob[pos+1]
        pos+=2
        if pos+length>len(blob):raise ValueError('Palette packet truncated')
        y,x=divmod(cursor,VIDEO_STRIDE)
        if y>=h or (length and x+length>w):
            raise ValueError('Source SPR scanline outside true image dimensions: '+
                             str((i,x,y,length,w,h)))
        if length:
            indices[y*w+x:y*w+x+length]=blob[pos:pos+length]
            opaque+=sum(c!=0 for c in blob[pos:pos+length])
        pos+=length
        cursor+=length
    if pos!=len(blob):raise ValueError('Unconsumed source sprite run bytes')
    # Final transparent skip reaches the end of the last source scanline.
    if cursor!=(h-1)*VIDEO_STRIDE+w:
        raise ValueError('RLE video-buffer end marker inconsistent with source bounds: '+
                         str((cursor,(h-1)*VIDEO_STRIDE+w)))
    if opaque<25:raise ValueError('Unexpected transparent original sprite')
    rgba=Image.new('RGBA',(w,h))
    rgba.putdata([
        (palette[3*p],palette[3*p+1],palette[3*p+2],255 if p else 0)
        for p in indices
    ])
    return rgba,opaque,count

def main():
    if len(sys.argv)!=3:raise SystemExit('Usage: decode-original-img-spr.py Dice/IMG.pak original/SourceSPR')
    src,out=Path(sys.argv[1]),Path(sys.argv[2])
    data=src.read_bytes()
    found={name.lower():raw for name,raw in members(data) if name.lower() in SUPPORTED}
    if set(found)!=set(SUPPORTED):raise ValueError('Missing genuine source SPR entries: '+str(set(SUPPORTED)-set(found)))
    out.mkdir(parents=True,exist_ok=True)
    report={'source':'Dice/IMG.pak','archiveSHA256':hashlib.sha256(data).hexdigest(),
            'videoStride':VIDEO_STRIDE,'decoder':'verified-640-byte-video-RLE',
            'spriteAnimations':{}}
    for name in SUPPORTED:
        raw=found[name]
        allframes,palette=frames(raw)
        entry={'member':name,'sourceSHA256':hashlib.sha256(raw).hexdigest(),
               'frameCount':len(allframes),'frames':[]}
        for i,w,h,ox,oy,body in allframes:
            image,opaque,count=sprite_rgba(body,w,h,palette)
            filename=Path(name).stem+'-'+str(i).zfill(2)+'.png'
            output=out/filename
            buff=io.BytesIO()
            image.save(buff,format='PNG',optimize=True)
            payload=buff.getvalue()
            output.write_bytes(payload)
            entry['frames'].append({
                'index':i,'url':'./original/SourceSPR/'+filename,
                'width':w,'height':h,'originX':ox,'originY':oy,
                'runs':count,'opaquePixels':opaque,
                'sha256':hashlib.sha256(payload).hexdigest()
            })
        report['spriteAnimations'][name]=entry
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('SOURCE_2002_IMG_SPR_DECODE '+json.dumps({
        'sprites':{n:{'frames':v['frameCount'],
                       'first':v['frames'][0]['url']}
                   for n,v in report['spriteAnimations'].items()},
        'archiveSHA256':report['archiveSHA256']
    }))
if __name__=='__main__':main()
