#!/usr/bin/env python3
"""Original 2002 4LEAF Dice OBS source full-body sprite preview decoder.

OBS holds actual Genesis War chessman animation, not chat avatar:
u32 group version; count at offset70; frame table at offset132 with
frame records length/u16width/u16height/s16origins; 8-bit palette runs.
This is a PROBE: only accept decoded art after visual regression and
independent source picture comparison, never claim heuristic output exact.
"""
import sys,struct,io,json,base64,hashlib
from pathlib import Path
from PIL import Image

def pak_entries(raw):
    n=struct.unpack_from('<I',raw,0)[0]^0xffffffff
    assert 0<n<=2000
    off=4+28*n;last=0
    for i in range(n):
        row=raw[4+28*i:4+28*(i+1)]
        name=bytes(x^255 for x in row[:24]).split(b'\0')[0].decode('cp949','replace')
        end=(struct.unpack_from('<I',row,24)[0]^0xffffffff)+1
        assert last<end<=len(raw)-off
        yield name,raw[off+last:off+end]
        last=end
def member_frames(raw):
    if len(raw)<132:return []
    n=struct.unpack_from('<H',raw,70)[0]
    if not 1<=n<=200:return []
    cursor=132;frames=[]
    for i in range(n):
        if cursor+12>len(raw):return []
        size,w,h,ox,oy=struct.unpack_from('<IHHhh',raw,cursor)
        if not (1<=w<=300 and 1<=h<=300 and size>0 and cursor+12+size<=len(raw)):return []
        frames.append((raw[cursor+12:cursor+12+size],w,h,ox,oy))
        cursor+=12+size
    return frames

def candidates(body,w):
    raw=[]
    for i in range(len(body)-4):
        a=body[i];b=body[i+1];c=body[i+2];d=body[i+3]
        if a>128 or b>3 or d>3 or c>min(90,w+25):continue
        x=128-a if a>w else a
        if x<0 or x>=w:continue
        raw.append((i,x,c,a,b,d))
    return raw

def guess_frame(raw,w,h,palette):
    markers=candidates(raw,w)
    if not markers:raise ValueError('source row markers absent')
    origins=[c for c in markers if c[0]<15]
    if not origins:raise ValueError('No header at frame origin')
    marks=[origins[0]]
    for _ in range(h+5):
        cur=marks[-1]; choices=[]
        for c in markers:
            if c[0]<=cur[0]+5:continue
            if c[0]>cur[0]+w+4:break
            span=c[0]-cur[0]-4
            if cur[1]+span>w:continue
            if abs(c[1]-cur[1])>24:continue
            pen=abs(span-(w-cur[1]-4)) + abs(c[1]-cur[1])*.8 + abs(c[2]-cur[2])*.25
            choices.append((pen,c))
        if not choices:break
        marks.append(min(choices,key=lambda v:v[0])[1])
    if not 8<=len(marks)<=h:raise ValueError(f'unsupported OBS rows {len(marks)}/{h}')
    pixels=bytearray(w*h)
    yshift=(h-len(marks))//2
    for i,m in enumerate(marks):
        start=m[0]+4
        end=marks[i+1][0] if i+1<len(marks) else len(raw)-4
        vals=raw[start:end]
        if m[1]+len(vals)>w:raise ValueError('source line too wide')
        pixels[(yshift+i)*w+m[1]:(yshift+i)*w+m[1]+len(vals)]=vals
    image=Image.frombytes('P',(w,h),bytes(pixels))
    image.putpalette(palette)
    image.info['transparency']=0
    return image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM),{
      'selectedRows':len(marks),'first':marks[:4],'last':marks[-3:],
      'decoder':'experimental-paletted-index-scanlines'}

def main():
    pak=Path(sys.argv[1]);orig=dict(pak_entries(pak.read_bytes()))
    for name in ('1025.obs','1040.obs','1042.obs','1045.obs','0074.obs','1199.obs','1254.obs'):
        if name not in orig:continue
        dat=orig[name];frames=member_frames(dat)
        if not frames:print('ORIGINAL_OBS_FRAMES_BLOCKED '+name);continue
        palette=dat[-768:]
        report={'name':name,'frames':len(frames),'sourceSHA256':hashlib.sha256(dat).hexdigest()}
        print('ORIGINAL_OBS_PREVIEW_FRAMES '+json.dumps(report,separators=(',',':')))
        for idx in (0,1,2,3,10,18,25,30):
            if idx>=len(frames):continue
            body,w,h,x,y=frames[idx]
            try:image,m=guess_frame(body,w,h,palette)
            except Exception as e:print('ORIGINAL_OBS_DECODER_UNCERTAIN '+name+' '+str(idx)+' '+str(e));continue
            out=io.BytesIO();image.save(out,'PNG',optimize=True)
            print('ORIGINAL_OBS_PIXELS_PREVIEW '+json.dumps({
              'source':name,'frame':idx,'w':w,'h':h,'offset':[x,y],
              'sha256':hashlib.sha256(out.getvalue()).hexdigest(),
              'pngBase64':base64.b64encode(out.getvalue()).decode('ascii'),
              'provenance':m},separators=(',',':')))
if __name__=='__main__':main()
