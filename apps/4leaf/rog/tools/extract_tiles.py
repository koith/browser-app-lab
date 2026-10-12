#!/usr/bin/env python3
"""Restore original 4LEAF tile types from Dice/DMP.pak 16-byte CP949 cells.
Original file layout: 272 header bytes, u32 palette count, N*128-byte
TIS palette entries, then width*height*16-byte grid. Route index comes
from original Dice/DMP.pak companion {map_id}.mve.
"""
from pathlib import Path
import struct,sys,json
KINDS={
'시작':'start','종료':'goal','더미':'normal','연습':'practice',
'3칸전진':'boost','4칸전진':'boost4','감옥':'prison','랜덤한번':'random',
'바뀌는랜덤':'joker','상자':'chest','완드':'attribute','검':'attribute',
'컵':'attribute','디스크':'attribute','싸움':'arena','어빌리티':'ability',
'소울풀':'ability100','워프1':'warp','워프3':'warp','워프4':'warp',
'불운':'spade','4리프':'clover','사느냐죽느냐':'doa',
'신의저주':'curse','신의축복':'blessing'}
ATTRS={'완드':'WANDS','검':'SWORDS','컵':'CUPS','디스크':'DISKS'}
def unpack(pak):
 b=pak.read_bytes();count=struct.unpack_from('<I',b)[0]^0xffffffff
 if not 0<count<10000:raise ValueError('Invalid PAK header')
 base=4+count*28;prev=0;out={}
 for i in range(count):
  e=b[4+28*i:32+28*i]
  name=bytes(x^255 for x in e[:24]).split(b'\0')[0].decode('cp949','replace')
  end=(struct.unpack_from('<I',e,24)[0]^0xffffffff)+1
  if not prev<end<=len(b)-base:raise ValueError('Invalid PAK entry')
  out[name]=b[base+prev:base+end];prev=end
 return out
def decode(pak):
 files=unpack(pak);maps={};stats={}
 for filename,data in files.items():
  if not filename.endswith('.dmp'):continue
  key=filename[:4];mve=files.get(key+'.mve')
  if not mve:continue
  width,height=struct.unpack_from('<II',data);num=struct.unpack_from('<I',data,272)[0]
  if not(4<=width<=80 and 4<=height<=80):continue
  start=276+128*num
  if len(data)!=start+width*height*16:raise ValueError('Tile layout mismatch '+key)
  tiles=[]
  for i in range(width*height):
   raw=data[start+i*16:start+(i+1)*16]
   tiles.append(raw.split(b'\0')[0].decode('cp949','replace').strip())
  path_count=struct.unpack_from('<I',mve,8)[0];rows=[]
  for i in range(path_count):
   direction,x,y,warp,group,target=struct.unpack_from('<6I',mve,12+24*i)
   if not(x<width and y<height):raise ValueError('Out of map bounds '+key)
   name=tiles[y*width+x]
   if name and name not in KINDS:print('UNRECOGNIZED_TILE',key,repr(name))
   typ=KINDS.get(name,'normal');item={'type':typ}
   if typ=='warp':item['warpGroup']=name[-1]
   if name in ATTRS:item['attribute']=ATTRS[name]
   rows.append(item)
  if rows[0]['type']!='start' or not any(v['type']=='goal' for v in rows):raise ValueError('Invalid source map '+key)
  maps[key]=rows
  stats[key]={'cells':len(rows),'dimensions':[width,height],
              'special':sum(x['type'] not in ('normal','practice','start') for x in rows),
              'warp':sum(x['type']=='warp' for x in rows)}
 return maps,stats
if __name__=='__main__':
 maps,meta=decode(Path(sys.argv[1]))
 if len(maps)<24:raise ValueError('Missing original map collection')
 out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
 (out/'tiles.js').write_text('window.ORIGINAL_LEAF_TILES='+json.dumps(maps,ensure_ascii=False,separators=(',',':'))+';\n')
 (out/'tiles-summary.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 print('AUTHENTIC_TILE_MAPS',len(maps),'ORIGINAL_SPECIAL_TILES',sum(m['special'] for m in meta.values()))
