#!/usr/bin/env python3
"""Probe source 2002 sprite boundaries / RLE row markers without executing game."""
import struct,sys,os,json
from pathlib import Path

def get_member(pak,name):
    raw=Path(pak).read_bytes()
    count=struct.unpack_from('<I',raw,0)[0]^0xffffffff
    base=4+count*28
    previous=0
    for i in range(count):
        at=4+i*28
        record=raw[at:at+28]
        filename=bytes(v^255 for v in record[:24]).split(b'\0')[0].decode('cp949','replace')
        end=(struct.unpack_from('<I',record,24)[0]^0xffffffff)+1
        if filename.lower()==name.lower():
            return raw[base+previous:base+end]
        previous=end
    raise KeyError(name)

def rows(body):
    return [i for i in range(len(body)-4) if body[i+1] in (0,1,2,3) and 15<=body[i+2]<=45 and body[i+3] in (1,3)]

def inspect_run_table(body,width=None,height=None):
    at=0
    rows=[]
    while at+4<=len(body) and len(rows)<15000:
        length=int.from_bytes(body[at:at+2],'little')
        index=int.from_bytes(body[at+2:at+4],'little')
        if length==0 or at+4+length>len(body):
            return {'error':'invalid/overlong span','at':at,'run':len(rows),
                'spanLen':length,'pixelOffset':index,'first':rows[:7],'tail':body[at:at+20].hex()}
        if width and height and index+length>width*height:
            return {'error':'span out of frame','at':at,'run':len(rows),
                'length':length,'pixelOffset':index,'pixels':width*height,'first':rows[:7]}
        rows.append((index,length))
        at+=4+length
    return {'spans':len(rows),'consumed':at,'bodyBytes':len(body),
      'exact':at==len(body),'tail':body[at:at+14].hex(),
      'first':rows[:10],'last':rows[-3:]}


def candidate_boundaries(body,w,h):
    if len(body)<10:return []
    base_offset=int.from_bytes(body[2:4],'little')
    near=[]
    for j in range(48,min(len(body)-5,700)):
        le=int.from_bytes(body[j:j+2],'little')
        off=int.from_bytes(body[j+2:j+4],'little')
        if 1<=le<=w+15 and base_offset<off<w*h and off<base_offset+w*6:
            near.append((j,le,off))
    return near[:60]

def probe(raw,name):
    at=raw.find(b'FAST.PAL.COLORKEY')
    if at<0:raise ValueError("missing sprite signature")
    src=raw[at:]
    count=struct.unpack_from('<H',src,66)[0]
    cursor=128
    records=[]
    for i in range(count):
        if cursor+12>len(src):raise ValueError("truncated frame")
        length,w,h,x,y=struct.unpack_from('<IHHhh',src,cursor)
        body=src[cursor+12:cursor+12+length]
        hits=rows(body)
        marks=[(p,body[p:p+8].hex()) for p in hits[:14]]
        records.append({
            'index':i,'dataOffset':cursor,'length':length,'width':w,'height':h,'origin':[x,y],
            'runLayoutGuess':inspect_run_table(body,w,h),'possibleRunHeaders':candidate_boundaries(body,w,h),'bodyHead':body[:80].hex(),'bodyTail':body[-48:].hex(),
            'rowMarkerCandidates':len(hits),'rowMarksFirst14':marks,
            'uniqueBytes':len(set(body)), 'paletteIndexColor0':src[-768:-765].hex()
        })
        cursor+=12+length
        if cursor>len(src):raise ValueError("frame out of bounds")
    return {'name':name,'size':len(raw),'signatureAt':at,'frameCount':count,
        'frames':records,'paletteAt':at+len(src)-768,
        'endCursor':at+cursor,'remaining':len(src)-cursor,
        'tailHex':src[cursor:cursor+32].hex(),
        'paletteFirst':src[-768:-740].hex(),
        'paletteLast':src[-30:].hex()}
def diagnostics(pak,member,label):
    try:
        raw=get_member(pak,member)
        info=probe(raw,member)
        frame=info['frames'][0]
        sig=raw.find(b'FAST.PAL.COLORKEY')
        body=raw[sig+140:sig+140+frame['length']]
        candidates=[]
        for i in range(len(body)-4):
            if body[i+1]<=3 and body[i+3]<=3:
                candidates.append((i, int.from_bytes(body[i:i+2],'little'),
                    int.from_bytes(body[i+2:i+4],'little')))
        stable=[]
        for at,x,y in candidates:
            if 4<=x%256<=240 and 0<y%256<150 and len(stable)<130:
                stable.append([at,x,y])
        print('SOURCE_SPR_ROW_DIAGNOSTIC '+json.dumps({
            'member':label,'size':len(body),
            'frameWidth':frame['width'],'frameHeight':frame['height'],
            'allCandidates':len(candidates),
            'firstCandidates':stable[:115],
            'rawPrefix':[body[i:i+16].hex() for i in [0,8,16,19,24,32,40,48,72,80,120,150] if i<len(body)],
        },separators=(',',':')))
    except Exception as exc:print('SOURCE_SPR_ROW_ERROR '+label+' '+str(exc))

if __name__=='__main__':
    pak=sys.argv[1]
    diagnostics(pak,'roll.spr','roll')
    diagnostics(pak,'minipanel.spr','minipanel')
    diagnostics(pak,'eventRoll1.spr','eventRoll1')
    for name in ['roll.spr','eventRoll1.spr','avatar.spr','winBattle.spr','minipanel.spr']:
        try:
            raw=get_member(pak,name)
            if name=='roll.spr':
                src=raw[raw.find(b'FAST.PAL.COLORKEY'):]
                length=struct.unpack_from('<I',src,128)[0]
                import base64
                # Print raw first frame BEFORE massive 16-frame diagnostics so
                # actual palette/pixel codec analysis survives log limits.
                print('ORIGINAL_SPR_ROLL_DEBUG_BASE64 '+base64.b64encode(src[140:140+length]).decode('ascii'))
                print('ORIGINAL_SPR_ROLL_PALETTE_BASE64 '+base64.b64encode(src[-768:]).decode('ascii'))
            print('SOURCE_SPR_FRAME_LAYOUT '+json.dumps(probe(raw,name),separators=(',',':')))
        except Exception as exc:print('SOURCE_SPR_ERROR '+name+' '+str(exc))
