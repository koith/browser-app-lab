#!/usr/bin/env python3
"""Verify original 2002 Genesis War chessman OBS animation frame boundaries.

Uses SHA1 authenticated InstallShield Dice/OBS(.2/.3).pak resources.
No .exe execution, no fabricated body models. Identify actual bitmaps
and frame offsets before attempting palette pixel reconstruction.
"""
import struct,sys,json
from pathlib import Path

def pak_members(p):
    source=Path(p).read_bytes()
    n=struct.unpack_from('<I',source)[0]^0xffffffff
    if not 0<n<=3000:raise ValueError('invalid archive')
    off=4+28*n;prev=0
    for i in range(n):
        e=source[4+28*i:4+28*(i+1)]
        name=bytes(x^255 for x in e[:24]).split(b'\0')[0].decode('cp949','replace')
        end=(struct.unpack_from('<I',e,24)[0]^0xffffffff)+1
        if not 0<=prev<end<=len(source)-off:raise ValueError('invalid member boundary')
        yield name,source[off+prev:off+end]
        prev=end

def probe(data):
    if len(data)<150:raise ValueError('OBS too short')
    headerLength=132
    firstType=struct.unpack_from('<I',data,0)[0]
    frameCount=struct.unpack_from('<H',data,70)[0]
    if not (1<=frameCount<=300):raise ValueError('no plausible animation frame count')
    offset=headerLength;frames=[]
    for f in range(frameCount):
        if offset+12>len(data):raise ValueError('frame '+str(f)+' header out of bounds')
        length,w,h,x,y=struct.unpack_from('<IHHhh',data,offset)
        if not (1<=w<=1000 and 1<=h<=1000 and
          0<=length<=w*h*3 and offset+12+length<=len(data)):
            raise ValueError('bad frame '+str(f)+': '+repr((offset,length,w,h,x,y)))
        frames.append({'index':f,'offset':offset,'size':length,'width':w,'height':h,'origin':[x,y],
                       'firstBytes':data[offset+12:offset+28].hex()})
        offset+=12+length
    tail=len(data)-offset
    remaining=data[offset:]
    return {'frames':frameCount,'type':firstType,'headerBytes':headerLength,
      'tailFirstHex':remaining[:96].hex(),
      'tailLastHex':remaining[-96:].hex(),
      'tailU32First':list(struct.unpack_from('<'+'I'*min(12,len(remaining)//4),remaining,0)) if remaining else [],
      'lastCursor':offset,'tailBytes':tail,'possiblePalette768':tail==768,
      'preview':frames[:12],
      'animationWidthRange':[min(x['width'] for x in frames),max(x['width'] for x in frames)],
      'animationHeightRange':[min(x['height'] for x in frames),max(x['height'] for x in frames)],
      'allFrameDimensions':[[f['width'],f['height']] for f in frames]}

def main():
    p=sys.argv[1]
    members=dict(pak_members(p))
    for name in ['1025.obs','1030.obs','1040.obs','1042.obs','1045.obs',
                 '0074.obs','1199.obs','1133.obs','1254.obs']:
        if name not in members:continue
        try:report=probe(members[name])
        except Exception as e:
            print('SOURCE_OBS_BOUNDARY_ERROR '+name+' '+str(e));continue
        print('SOURCE_OBS_CHESSMAN_LAYOUT '+json.dumps(
          {'pak':Path(p).name,'member':name,'size':len(members[name]),**report},
          separators=(',',':')))
if __name__=='__main__':main()
