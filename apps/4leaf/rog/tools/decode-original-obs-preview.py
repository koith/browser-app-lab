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

def source_scanlines(body,w,h):
    # In original OBS frame data, each bitmap row begins with a four-byte
    # RLE header: first low byte is roughly 90..127, high bytes <=3.
    # Find the unique header threshold for EXACTLY h rows and validate the
    # uncompressed literal run lengths against the original frame width.
    # Verified on real 1025.obs (73 rows) and 1045.obs (82 rows).
    for low in range(127,-1,-1):
        starts=[]
        for i in range(len(body)-3):
            a,b,c,d=body[i:i+4]
            if low<=a<=128 and b<=3 and c<=min(75,w+30) and d<=3:
                starts.append(i)
        if len(starts)!=h or starts[0]!=0:continue
        widths=[(starts[k+1] if k+1<h else len(body))-p-4
                for k,p in enumerate(starts)]
        if all(1<=length<=w for length in widths):
            return starts,widths,low
    raise ValueError(f'Could not find {h} exact native scanline headers in {len(body)} bytes')

def guess_frame(raw,w,h,palette):
    starts,lengths,threshold=source_scanlines(raw,w,h)
    out=bytearray(w*h)
    # Exact 8-bit palette values and exact run length are source decoded.
    # Horizontal run origin is provisionally centered, as in the
    # independently verified TIS decoder, until the 4-byte source flags
    # are fully understood. Never claim exact per-pixel registration yet.
    for row,(at,length) in enumerate(zip(starts,lengths)):
        x=(w-length)//2
        out[row*w+x:row*w+x+length]=raw[at+4:at+4+length]
    image=Image.frombytes('P',(w,h),bytes(out))
    image.putpalette(palette)
    image.info['transparency']=0
    return image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM),{
      'selectedRows':len(starts),'first':starts[:4],'last':starts[-3:],
      'threshold':threshold,'rowMin':min(lengths),'rowMax':max(lengths),
      'decoder':'source-exact-8bit-run-length; provisional centered row placement'}


def main():
    pak=Path(sys.argv[1]);orig=dict(pak_entries(pak.read_bytes()))
    for name in ('1025.obs','1040.obs','1042.obs','1045.obs','0074.obs','1199.obs','1254.obs'):
        if name not in orig:continue
        dat=orig[name];frames=member_frames(dat)
        if not frames:print('ORIGINAL_OBS_FRAMES_BLOCKED '+name);continue
        # OBS palette starts immediately AFTER the advertised first pose group's
    # exact frame bytes; the final 768-byte footer is NOT the RGB palette.
    paletteAt=132+sum(12+len(body) for body,_,_,_,_ in frames)
    palette=dat[paletteAt:paletteAt+768]
    if len(palette)!=768:raise ValueError('Missing original OBS 256×RGB palette')
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
