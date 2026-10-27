"""Verify photo matching, byte preservation and exclusion of artificial enlargements."""
import hashlib,json,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from merge_higher_resolution import merge

with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 def edition(name,size,ai=False):
  folder=root/name;folder.mkdir();image=Image.new('RGB',size,(38,80,120));draw=ImageDraw.Draw(image)
  draw.rectangle((size[0]//4,size[1]//4,size[0]*3//4,size[1]*3//4),fill=(200,160,70))
  path=folder/'photo.png';image.save(path);raw=path.read_bytes()
  m={'id':'work','title':'work','expected':1,'ai_enhanced':ai,'images':[{'number':1,'file':'photo.png','url':'https://cdn.jliji.com/photo.png','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'width':size[0],'height':size[1]}]}
  (folder/'manifest.json').write_text(json.dumps(m));return folder
 primary=edition('small',(600,900));larger=edition('larger',(1200,1800));out=root/'selected'
 result=merge(primary,larger,out)
 assert len(result['higher_resolution_web_replacements'])==1
 assert (out/result['images'][0]['file']).read_bytes()==(larger/'photo.png').read_bytes()
 assert not result['publisher_original_verified']
 retained=merge(larger,primary,root/'retained')
 assert not retained['higher_resolution_web_replacements']
 ai=edition('artificial',(2400,3600),True)
 try:merge(primary,ai,root/'ai-rejected')
 except ValueError as error:assert 'AI' in str(error)
 else:raise AssertionError('Artificial enlargement replaced a non-AI file')
 assert not (root/'ai-rejected'/'manifest.json').exists()
print('MATCHED_LARGER_BYTES_PRESERVED_SMALLER_AND_AI_COPIES_REJECTED_PASS')
