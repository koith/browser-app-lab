"""Regression: a larger decoded frame is NOT necessarily higher-quality."""
import hashlib,json,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from merge_higher_resolution import merge,select_match,paired_optical_relation

assert select_match([(2,.6,'same',0),(3,3.3,'nearby-pose',0)])[2]=='same'
assert select_match([(2,.6,'pose',0),(2,.7,'other-pose',0)]) is None
assert select_match([(2,2,'pose',0),(3,9,'other-pose',0)]) is None
assert select_match([(0,4,'nearby-pose',0),(4,.6,'same',0)])[2]=='same'

with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 def edition(name,size,ai=False):
  folder=root/name;folder.mkdir()
  image=Image.new('RGB',size,(38,80,120))
  d=ImageDraw.Draw(image);w,h=size
  d.rectangle((w//4,h//4,w*3//4,h*3//4),fill=(200,160,70))
  d.rectangle((0,0,w//5,h//3),fill=(5,210,30))
  img=folder/'photo.png';image.save(img)
  raw=img.read_bytes()
  p={'number':1,'file':'photo.png','url':'https://cdn.jliji.com/photo.png',
     'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
     'width':size[0],'height':size[1]}
  (folder/'manifest.json').write_text(json.dumps({
     'id':'work','title':'work','expected':1,'ai_enhanced':ai,'images':[p]}))
  return folder

 def add_real_detail(folder):
  file=folder/'photo.png'
  with Image.open(file) as src: image=src.copy()
  d=ImageDraw.Draw(image)
  for y in range(0,image.height,13):
   d.line((0,y,image.width,y+5),fill=(108,110,115),width=1)
  image.save(file)
  meta=json.loads((folder/'manifest.json').read_text())
  raw=file.read_bytes()
  meta['images'][0].update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
  (folder/'manifest.json').write_text(json.dumps(meta))
  return raw

 primary=edition('small',(600,900))
 larger=edition('large_no_new_optical_detail',(1200,1800))
 assert paired_optical_relation(primary/'photo.png',larger/'photo.png') is None
 fake=merge(primary,larger,root/'fake-result')
 assert not fake['higher_resolution_web_replacements']
 assert (root/'fake-result'/fake['images'][0]['file']).read_bytes()==(primary/'photo.png').read_bytes(),\
  'A 4K-sized same-detail file must not displace the previous original'
 detailed=edition('true_detail',(1200,1800))
 real_bytes=add_real_detail(detailed)
 assert paired_optical_relation(primary/'photo.png',detailed/'photo.png')=='higher'
 result=merge(primary,detailed,root/'real-detail-result')
 assert len(result['higher_resolution_web_replacements'])==1
 assert result['higher_resolution_web_replacements'][0]['reason']=='measured_higher_optical_detail'
 assert (root/'real-detail-result'/result['images'][0]['file']).read_bytes()==real_bytes
 assert not result['publisher_original_verified']
 retained=merge(detailed,primary,root/'retained')
 assert not retained['higher_resolution_web_replacements']
 assert (root/'retained'/retained['images'][0]['file']).read_bytes()==real_bytes
 ai=edition('artificial',(2400,3600),True)
 try:merge(primary,ai,root/'ai-rejected')
 except ValueError as error:assert 'AI' in str(error)
 else:raise AssertionError('AI enlargement replaced a non-AI original')
 assert not (root/'ai-rejected'/'manifest.json').exists()
 # A sideways actual image must keep its original compressed bytes.
 landscape=edition('landscape',(900,600))
 side=edition('sideways',(1800,1200))
 add_real_detail(side)
 with Image.open(side/'photo.png') as im:
  im.rotate(-90,expand=True).save(side/'rotated.png')
 raw=(side/'rotated.png').read_bytes()
 m=json.loads((side/'manifest.json').read_text())
 m['images'][0].update(file='rotated.png',width=1200,height=1800,
                      bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 (side/'manifest.json').write_text(json.dumps(m))
 rotated=merge(landscape,side,root/'orientation-selected')
 assert len(rotated['higher_resolution_web_replacements'])==1
 assert rotated['images'][0]['display_rotation'] in (90,270)
 assert (root/'orientation-selected'/rotated['images'][0]['file']).read_bytes()==raw

print('REAL_MEASURED_OPTICAL_DETAIL_WIN_FAKE_UPSCALE_BLOCK_AI_BLOCK_ORIENTATION_PASS')
