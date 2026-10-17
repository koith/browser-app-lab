#!/usr/bin/env python3
"""Read exact 2002 4LEAF IMG *.bmp sprites, never run its 2002 executable.

Outputs small PNGs only for native game UI widgets absent from previous
curated IMG extraction (okcancelbut/scrollButton/stats). Audits source
dimensions and indexed palette transparency rather than guessing UI art.
Binaries stay runner-private; generated PNG is logged for source placement.
"""
import sys,json,struct,base64,io
from PIL import Image
from pathlib import Path
pak=Path(sys.argv[1]).read_bytes()
count=struct.unpack_from('<I',pak,0)[0]^0xffffffff
assert 0<count<1000
base=4+28*count
last=0
wanted={'okcancelbut.bmp','scrollbutton.bmp','stats.bmp'}
found=set()
for i in range(count):
    row=pak[4+i*28:4+(i+1)*28]
    name=bytes(b^255 for b in row[:24]).split(b'\0')[0].decode('ascii','replace')
    end=(struct.unpack_from('<I',row,24)[0]^0xffffffff)+1
    assert last<end<=len(pak)-base
    if name.lower() in wanted:
        raw=pak[base+last:base+end]
        assert raw[:2]==b'BM'
        im=Image.open(io.BytesIO(raw));im.load()
        assert 0<im.width<=1200 and 0<im.height<=1200
        b=io.BytesIO()
        im.convert('RGBA').save(b,format='PNG',optimize=True)
        png=b.getvalue()
        print('ORIGINAL_IMG_BMP_CONVERTED '+json.dumps({
            'source':name,'width':im.width,'height':im.height,
            'originalBytes':len(raw),'pngBytes':len(png),
            'pngBase64':base64.b64encode(png).decode('ascii'),
            'conversion':'genuine original BMP pixels; not screenshot or redrawn asset'
        },separators=(',',':')))
        found.add(name.lower())
    last=end
assert found==wanted,(found,wanted)
print('ORIGINAL_IMG_BMP_COVERAGE '+json.dumps(sorted(found)))
