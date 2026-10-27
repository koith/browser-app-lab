"""Resolution remains primary; only reviewed clean copies win resolution ties."""
import hashlib,json,tempfile
from pathlib import Path
from PIL import Image,ImageDraw
from photo_quality_policy import replacement_reason,watermark_status
from merge_higher_resolution import merge
from build_additional_source_manifest import build

with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 def edition(name,size,mark=False,status=None):
  folder=root/name;folder.mkdir();im=Image.new('RGB',size,(30,80,140));d=ImageDraw.Draw(im)
  d.rectangle((size[0]//4,size[1]//4,size[0]*3//4,size[1]*3//4),fill=(180,150,90))
  if mark:d.text((size[0]-100,size[1]-20),'EXAMPLE SITE',fill='white')
  f=folder/'photo.png';im.save(f);raw=f.read_bytes();p={'number':1,'file':f.name,'url':'https://cdn.jliji.com/'+name+'.png','width':size[0],'height':size[1],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
  if status:p['site_watermark_review']={'status':status,'sha256':p['sha256'],'evidence':'Synthetic full-frame fixture with known site text presence.'}
  m={'id':'work','title':'work','expected':1,'images':[p]};(folder/'manifest.json').write_text(json.dumps(m));return folder,p
 marked,mp=edition('marked',(600,900),True,'present')
 clean,cp=edition('clean',(600,900),False,'absent')
 lower,lp=edition('small-clean',(400,600),False,'absent')
 larger,hp=edition('large-marked',(1200,1800),True,'present')
 assert replacement_reason(cp,mp)=='same_resolution_without_site_watermark'
 assert replacement_reason(hp,cp)=='higher_resolution'
 assert replacement_reason(lp,mp) is None
 assert replacement_reason(mp,cp) is None
 unknown={**mp,'site_watermark_review':{'status':'absent'}}
 assert watermark_status(unknown)=='unknown' and replacement_reason(unknown,mp) is None
 stale={**mp,'site_watermark_review':{**cp['site_watermark_review']}}
 assert watermark_status(stale)=='unknown'
 out=root/'selected';result=merge(marked,clean,out)
 assert len(result['watermark_free_web_replacements'])==1
 assert not result['higher_resolution_web_replacements']
 assert (out/result['images'][0]['file']).read_bytes()==(clean/'photo.png').read_bytes()
 gallery=root/'gallery.json';build([marked],gallery);build([clean],gallery)
 assert json.loads(gallery.read_text())['albums'][0]['images'][0]['sha256']==cp['sha256']
 # Registration cannot later overwrite the clean copy with a tied marked file.
 build([marked],gallery);selected=json.loads(gallery.read_text())['albums'][0]['images'][0]
 assert selected['sha256']==cp['sha256'] and watermark_status(selected)=='absent'
 build([lower],gallery);assert json.loads(gallery.read_text())['albums'][0]['images'][0]['sha256']==cp['sha256']
 build([larger],gallery);assert json.loads(gallery.read_text())['albums'][0]['images'][0]['sha256']==hp['sha256']
print('RESOLUTION_FIRST_VERIFIED_WATERMARK_TIEBREAK_AND_NO_DOWNGRADE_PASS')
