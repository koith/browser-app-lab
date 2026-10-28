"""Verify photo matching, byte preservation and exclusion of artificial enlargements."""
import hashlib,json,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from merge_higher_resolution import merge,select_match

assert select_match([(2,.6,'same',0),(3,3.3,'nearby-pose',0)])[2]=='same'
assert select_match([(2,.6,'pose',0),(2,.7,'other-pose',0)]) is None
assert select_match([(2,2,'pose',0),(3,9,'other-pose',0)]) is None
assert select_match([(0,4,'nearby-pose',0),(4,.6,'same',0)])[2]=='same'

with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 def edition(name,size,ai=False):
  folder=root/name;folder.mkdir();image=Image.new('RGB',size,(38,80,120));draw=ImageDraw.Draw(image)
  draw.rectangle((size[0]//4,size[1]//4,size[0]*3//4,size[1]*3//4),fill=(200,160,70))
  draw.rectangle((0,0,size[0]//5,size[1]//3),fill=(5,210,30))
  path=folder/'photo.png';image.save(path);raw=path.read_bytes()
  m={'id':'work','title':'work','expected':1,'ai_enhanced':ai,'images':[{'number':1,'file':'photo.png','url':'https://cdn.jliji.com/photo.png','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'width':size[0],'height':size[1]}]}
  (folder/'manifest.json').write_text(json.dumps(m));return folder
 primary=edition('small',(600,900));larger=edition('larger',(1200,1800));out=root/'selected'
 result=merge(primary,larger,out)
 assert len(result['higher_resolution_web_replacements'])==1
 assert (out/result['images'][0]['file']).read_bytes()==(larger/'photo.png').read_bytes()
 assert not result['publisher_original_verified']
 # A second encoded/watermarked source for the same canonical pose must not
 # masquerade as ambiguity between different poses and suppress an upgrade.
 variants=edition('variants',(1200,1800))
 with Image.open(variants/'photo.png') as image:
  ImageDraw.Draw(image).rectangle((1140,1740,1199,1799),fill=(245,245,245))
  image.save(variants/'variant.png')
 m=json.loads((variants/'manifest.json').read_text());raw=(variants/'variant.png').read_bytes()
 m['images'].append({**m['images'][0],'number':2,'file':'variant.png',
                     'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 (variants/'manifest.json').write_text(json.dumps(m))
 selected=merge(primary,variants,root/'variant-selected')
 assert len(selected['images'])==1 and len(selected['higher_resolution_web_replacements'])==1
 retained=merge(larger,primary,root/'retained')
 assert not retained['higher_resolution_web_replacements']
 ai=edition('artificial',(2400,3600),True)
 try:merge(primary,ai,root/'ai-rejected')
 except ValueError as error:assert 'AI' in str(error)
 else:raise AssertionError('Artificial enlargement replaced a non-AI file')
 assert not (root/'ai-rejected'/'manifest.json').exists()
 # Some observed CDNs store landscape photos sideways without EXIF. Compare
 # the complete frame in memory, preserve those response bytes and annotate
 # the display rotation instead of recompressing a corrected image.
 landscape=edition('landscape',(900,600))
 side=edition('sideways',(1800,1200))
 path=side/'photo.png'
 with Image.open(path) as image:
  image.rotate(-90,expand=True).save(side/'rotated.png')
 raw=(side/'rotated.png').read_bytes()
 m=json.loads((side/'manifest.json').read_text())
 m['images'][0].update(file='rotated.png',width=1200,height=1800,
                       bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 (side/'manifest.json').write_text(json.dumps(m))
 rotated=merge(landscape,side,root/'orientation-selected')
 assert len(rotated['higher_resolution_web_replacements'])==1
 assert rotated['images'][0]['display_rotation'] in (90,270)
 assert (root/'orientation-selected'/rotated['images'][0]['file']).read_bytes()==raw
print('MATCHED_LARGER_BYTES_PRESERVED_SMALLER_AND_AI_COPIES_REJECTED_PASS')
