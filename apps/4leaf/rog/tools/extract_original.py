#!/usr/bin/env python3
"""Extract original 4LEAF client art assets from historic InstallShield CAB.
Maintains the original GIF/BMP sources separately from UI screenshot references.
Only content assets needed to render a dynamic interactive app are copied.
"""
from pathlib import Path
from PIL import Image
import io,json,re,sys
ROOT=Path(sys.argv[1]);DEST=Path(sys.argv[2]);DEST.mkdir(parents=True,exist_ok=True)
KEEP_ALL={'MainFrame','WorldMap','CardShop','ChatRoom','ChatTown','MainStreet','KnightTown','Gif','IMG','Room','Map','D1Region','Region','Registry'}
OTHER={'CardData'}
KEEP_IMG={'bgtile','abilitybar','avatarback','chatwnd','menu','topbar','selector','title','minimap','groupbutton','dialog','eventmsgbox','menumenu','columnTop','loading'}
def extract_pak(pak):
 raw=pak.read_bytes();count=int.from_bytes(raw[:4],'little')^0xffffffff
 if not 0<count<4000 or len(raw)<4+28*count:raise ValueError(f'invalid {pak}')
 head=4+28*count;last=0
 for i in range(count):
  b=raw[4+i*28:4+(i+1)*28]
  name=bytes(v^255 for v in b[:24]).split(b'\x00')[0].decode('cp949','replace')
  end=(int.from_bytes(b[24:],'little')^0xffffffff)+1
  if end<=last or end>len(raw)-head:raise ValueError(f'bad offset {pak}/{name}')
  yield name,raw[head+last:head+end]
  last=end
 if last!=len(raw)-head:raise ValueError(f'bad size {pak}')
asset_count=0; manifest=[]
for pak in sorted(ROOT.rglob('*.pak')):
 group=pak.stem
 if group not in KEEP_ALL|OTHER:continue
 for name,data in extract_pak(pak):
  ext=Path(name).suffix.lower()
  if ext not in {'.gif','.bmp','.png','.jpg','.jpeg'}:continue
  if group=='IMG' and Path(name).stem.lower() not in KEEP_IMG:continue
  if group=='Registry' and not (name.lower().startswith('sava') or 'avatardialog' in name.lower()):continue
  try:
   original=Image.open(io.BytesIO(data));original.load()
  except Exception as e:
   print('BAD_IMAGE',group,name,str(e)[:100]);continue
  if original.width>2800 or original.height>1400:continue
  transparent=original.convert('RGBA')
  # Bright green is the original engine's sprite transparency/chroma key,
  # but must NOT erase genuine green game map artwork.
  is_sprite=((group in {'MainStreet','Registry'} and name.lower() not in {'back.gif','worldmapback.gif'}) or (group=='Gif') or (group=='CardShop' and 'back' not in name.lower()) or (group=='ChatRoom' and name.lower().startswith(('roomicon','scrollbar','chatbar','talkbox','ring','combob'))))
  if is_sprite:
   px=transparent.load()
   for y in range(transparent.height):
    for x in range(transparent.width):
     r,g,b,a=px[x,y]
     if g>175 and g>r*1.50 and g>b*1.28 and (r<80 and b<140):
      px[x,y]=(r,g,b,0)
  sub=DEST/group
  sub.mkdir(exist_ok=True,parents=True)
  name_safe=Path(name).stem.lower()+'.png'
  output=sub/name_safe
  transparent.save(output,optimize=True)
  item={'original':f'{group}/{name}','image':f'{group}/{name_safe}','width':original.width,'height':original.height}
  manifest.append(item)
  asset_count+=1
  if asset_count%100==0:print('ASSETS_CONVERTED',asset_count)
(DEST/'manifest.json').write_text(json.dumps({'source':'Archived 4Leaf original client installer, extracted from data1.cab / *.pak','original_source':'https://archive.org/details/4leaf','resources':manifest},ensure_ascii=False,indent=2))
print('TOTAL_AUTHENTIC_ASSETS',asset_count)
print('GROUPS',{x:sum(1 for m in manifest if m['image'].startswith(x+'/')) for x in sorted(KEEP_ALL|OTHER)})
