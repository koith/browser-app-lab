#!/usr/bin/env python3
"""Experimental REAL 2002 4LEAF IMG.spr pixel extraction.

This is NOT an authored drawing, screenshot crop, or modern CSS facsimile.
Frame bytes + 256*3 palette come from SHA1-verified 2002 InstallShield
Dice/IMG.pak; the scanline-boundary decoder below is still under validation.

Never label output pixel-perfect until compared with source Windows player.
Runs only on original resource DATA, never executes its .exe or .dll.
"""
import os,struct,sys,json,io,hashlib,base64
from pathlib import Path
from PIL import Image

def entries(raw):
    count=struct.unpack_from('<I',raw,0)[0]^0xffffffff
    if not 1<=count<=1000:raise ValueError('Invalid original PAK')
    table=4+28*count
    last=0
    for index in range(count):
        record=raw[4+index*28:4+(index+1)*28]
        name=bytes(v^255 for v in record[:24]).split(b'\0')[0].decode('cp949','replace')
        end=(struct.unpack_from('<I',record,24)[0]^0xffffffff)+1
        if end<=last or table+end>len(raw):raise ValueError('Bad PAK span '+name)
        yield name,raw[table+last:table+end]
        last=end
    if last!=len(raw)-table:raise ValueError('PAK resource index does not exhaust file')

def scan_markers(b,w):
    # Original animation encodes opaque runs in bottom-up scanlines.
    # TIS examples have 97 headers / 97 rows. Other IMG sprites have
    # different horizontal transparent gaps and extra RLE control words.
    return [(i,b[i],b[i+2],b[i+1],b[i+3])
      for i in range(0,len(b)-4)
      if 0<=b[i]<w and b[i+1]<=3 and 0<b[i+2]<=min(65,w)
       and b[i+3]<=3]

def choose_markers(b,w,h):
    candidates=scan_markers(b,w)
    if not candidates:raise ValueError('No indexed row headers')
    # Exact TIS marker signature also works for some IMG atlases.
    exact=[c for c in candidates if 15<=c[2]<=45 and c[4] in (1,3)]
    if len(exact)==h:return exact,'proven-tis-like-row-markers'
    # For non-TIS sprites, calculate a path through real source row
    # headers with an expected maximum opaque width. The source x/flag
    # values must vary smoothly and NO row may write beyond its width.
    start=[c for c in candidates if c[0]<min(w//2,45)]
    if not start:raise ValueError('No scanline header at sprite origin')
    selected=[start[0]]
    while len(selected)<h+3:
        cur=selected[-1]
        nexts=[]
        for item in candidates:
            if item[0]<=cur[0]+5:continue
            if item[0]>cur[0]+w+4:break
            gap=item[0]-cur[0]-4
            if gap<2 or cur[1]+gap>w:continue
            dx=abs(item[1]-cur[1])
            dy=abs(item[2]-cur[2])
            if dx>max(42,int(w*.45)) or dy>max(15,int(w*.3)):continue
            ideal=max(3,w-cur[1]-int(w*.18))
            score=abs(gap-ideal)+dx*.72+dy*2.7
            if dx>max(18,int(w*.15)):score+=7
            nexts.append((score,item))
        if not nexts:break
        selected.append(min(nexts,key=lambda x:x[0])[1])
    if len(selected)<min(8,h//3) or len(selected)>h+2:
        raise ValueError(f'Ambiguous line count {len(selected)}/{h}')
    return selected,'source-row-heuristic-needs-native-player-comparison'

def decode_frame(b,w,h,palette):
    marks,method=choose_markers(b,w,h)
    if len(marks)>h:raise ValueError('Too many native rows')
    offset=max(0,(h-len(marks))//2)
    out=bytearray(w*h)
    lengths=[]
    for i,marker in enumerate(marks):
        start=marker[0]+4
        end=marks[i+1][0] if i+1<len(marks) else len(b)-4
        if end<=start:raise ValueError('Non-positive source scanline length')
        pixels=b[start:end]
        left=marker[1]
        if left+len(pixels)>w:raise ValueError('Source scanline exceeds width')
        if any(byte>255 for byte in pixels):raise ValueError('Not an indexed palette')
        at=(offset+i)*w+left
        out[at:at+len(pixels)]=pixels
        lengths.append(len(pixels))
    p=Image.frombytes('P',(w,h),bytes(out))
    p.putpalette(palette)
    p.info['transparency']=0
    return p.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM),{
      'method':method,'decodedRows':len(marks),'height':h,
      'payloadBytes':len(b),'rowPixelMin':min(lengths),
      'rowPixelMax':max(lengths),'firstMarker':list(marks[0]),
      'lastMarker':list(marks[-1])}

def sprite_file(dat,asset):
    at=dat.find(b'FAST.PAL.COLORKEY')
    if at<0:raise ValueError('No original FAST.PAL.COLORKEY signature: '+asset)
    src=dat[at:]
    count=struct.unpack_from('<H',src,66)[0]
    if count<1 or count>90:raise ValueError('Implausible animation count '+asset)
    palette=src[-768:]
    if len(palette)!=768:raise ValueError('Palette truncated')
    cursor=128
    frames=[]
    for i in range(count):
        if cursor+12>len(src)-768:raise ValueError('Frame record truncated')
        size,w,h,x,y=struct.unpack_from('<IHHhh',src,cursor)
        cursor+=12
        if not (10<=w<=400 and 10<=h<=400 and size>0 and cursor+size<=len(src)-768):
            raise ValueError('Bad sprite geometry/frame size')
        body=src[cursor:cursor+size]
        cursor+=size
        bitmap,meta=decode_frame(body,w,h,palette)
        meta.update({'frame':i,'w':w,'h':h,'origin':[x,y]})
        frames.append((bitmap,meta))
    if cursor!=len(src)-768:raise ValueError('Frame bytes not contiguous with 256-color palette')
    return frames

def main():
    pak=Path(sys.argv[1]).read_bytes()
    out=Path(sys.argv[2]) if len(sys.argv)>2 else None
    contents=dict(entries(pak))
    info={}
    for filename in ('roll.spr','eventRoll1.spr','minipanel.spr'):
        asset=contents[filename]
        try:frames=sprite_file(asset,filename)
        except Exception as exc:
            print('ORIGINAL_SPR_DECODE_BLOCKED '+filename+' '+str(exc))
            continue
        previews=[]
        for idx,(image,meta) in enumerate(frames):
            blob=io.BytesIO();image.save(blob,'PNG',optimize=True)
            encoded=base64.b64encode(blob.getvalue()).decode('ascii')
            base=Path(filename).stem.lower()
            file=f'{base}-{idx:02}.png'
            if out:
                (out/base).mkdir(exist_ok=True,parents=True)
                (out/base/file).write_bytes(blob.getvalue())
            previews.append(meta)
            if idx<4:
                print('ORIGINAL_SPR_DECODED_FRAME '+json.dumps({
                  'source':filename,'name':file,'width':image.width,
                  'height':image.height,'pngBase64':encoded,
                  'sha256':hashlib.sha256(blob.getvalue()).hexdigest(),
                  'metadata':meta},separators=(',',':')))
        info[filename]={'archiveMemberSHA256':hashlib.sha256(asset).hexdigest(),
          'frames':len(frames),'allFrames':previews}
        print('ORIGINAL_SPR_DECODE_SUMMARY '+json.dumps({'name':filename,
          'frames':len(frames),'first':previews[0]},separators=(',',':')))
    if out:
        out.mkdir(parents=True,exist_ok=True)
        (out/'manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    print('ORIGINAL_SPR_ASSETS_RESEARCH '+json.dumps({
       'decodedFiles':list(info.keys()),'originalFramesValidatedAgainstWindowsPlayer':False,
       'runnerSourceContentWasExecuted':False}))
if __name__=='__main__':main()
