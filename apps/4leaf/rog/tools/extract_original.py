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

# Authentic movement paths: <number>.mve files consist of a 12-byte heading
# followed by 24-byte coordinate/direction records. The source map graph
# coordinates, not an invented spiral, control chessmen positions.
import struct
original_routes={}
original_meta={}
path_file=ROOT/'Dice'/'DMP.pak'
if path_file.exists():
 for name,data in extract_pak(path_file):
  if not name.lower().endswith('.mve') or len(data)<12:continue
  count=struct.unpack_from('<I',data,8)[0]
  variants=struct.unpack_from('<I',data,0)[0]
  if count>3000 or len(data)<12+count*24:continue
  records=[]
  for i in range(count):
   direction,x,y,warp,arg,target=struct.unpack_from('<6I',data,12+24*i)
   records.append([int(x),int(y),int(direction),int(warp),int(arg),int(target)])
  original_routes[name[:4]]=records
  original_meta[name[:4]]={'length':count,'variants':variants,'size':len(data)}
(DEST/'maps.js').write_text('window.ORIGINAL_LEAF_MAPS='+json.dumps(original_routes,separators=(',',':'))+';\n')
(DEST/'maps.json').write_text(json.dumps({'routes':original_routes,'info':original_meta},indent=2))
print('AUTHENTIC_DICE_MAP_MOVEMENT_ROUTES',len(original_routes),original_meta)

# The genuine MapList.d1 is exactly 25 fixed-length (1048-byte) records
# plus a 4-byte trailer. Every record includes a 4-byte map ID, mode and
# legacy CP949 title. Preserve canonical title↔map graph associations.
import struct
map_list=ROOT/'Dice'/'MapList.d1'
actual_map_names={}
if map_list.exists():
 raw=map_list.read_bytes()
 for offset in range(0,len(raw)-1047,1048):
  map_id,mode=struct.unpack_from('<II',raw,offset)
  title=raw[offset+8:offset+128].split(b'\0')[0].decode('cp949','replace').strip()
  if title and str(map_id).zfill(4) in original_routes:
   actual_map_names[str(map_id).zfill(4)]={'title':title,'mode':mode}
 with (DEST/'maps.js').open('a') as f:
  f.write('window.ORIGINAL_LEAF_MAP_INFO='+json.dumps(actual_map_names,ensure_ascii=False,separators=(',',':'))+';\n')
 print('AUTHENTIC_MAP_TITLES',len(actual_map_names),actual_map_names)

# Recover exact original 4LEAF chessman IDs, names and stats from Dice/CHR.pak.
# CHR documents are 472-byte Borland records. At offsets 196 and 452
# are the CP949 caption and packed movement/attack/defense/intelligence fields.
# Offsets validated against Saladin 1/4/4/2, Black Prince 2/5/3/2,
# Damian 2/2/4/3, and Sherazard 2/1/2/5.
chr_pak=ROOT/'Dice'/'CHR.pak'
if chr_pak.exists():
 recovered=[]
 for filename,dat in extract_pak(chr_pak):
  if not filename.lower().endswith('.chr') or len(dat)<470:continue
  rawname=dat[196:255].split(b'\0',1)[0]
  try: name=rawname.decode('cp949').strip()
  except UnicodeDecodeError:continue
  if not name or len(name)>22:continue
  try:
   defense,element,ability,intelligence,attack,move,score,level,usable=struct.unpack_from('<9H',dat,452)
  except Exception:continue
  if not (1<=move<=2 and 1<=attack<=6 and 1<=defense<=6 and 0<=intelligence<=5):continue
  if usable==0 and filename[:4] in ('0105','0106','0107','0108','0109','0110','0114','0152'):continue
  recovered.append({'id':filename[:4],'name':name,'move':move,'atk':attack,'def':defense,'int':intelligence,'element':element,'abilityId':ability,'score':score,'level':level,'usable':usable})
 (DEST/'chessmen.js').write_text('window.ORIGINAL_LEAF_CHESSMEN='+json.dumps(recovered,ensure_ascii=False,separators=(',',':'))+';\n')
 (DEST/'chessmen.json').write_text(json.dumps(recovered,ensure_ascii=False,indent=2))
 print('AUTHENTIC_CHESSMEN',len(recovered))
 for x in recovered:print('CHESSMAN',x['id'],x['name'],x['move'],x['atk'],x['def'],x['int'],x['abilityId'])
