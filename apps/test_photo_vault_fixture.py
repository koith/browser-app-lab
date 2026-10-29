#!/usr/bin/env python3
"""Generate two tiny real-byte test ZIPs from physically committed photos."""
import hashlib,json,zipfile
from pathlib import Path
out=Path('/tmp/photo-vault-qa');out.mkdir(exist_ok=True)
for model in ('yui','mimmi'):
 root=Path('apps')/(model+'-gallery')
 albums=json.loads((root/'stored-albums.json').read_text())['albums']
 source_album=next(a for a in albums if any(p.get('url','').startswith('stored-albums/') for p in a['images']))
 item=next(p for p in source_album['images'] if p.get('url','').startswith('stored-albums/'))
 data=(root/item['url']).read_bytes()
 assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
 ext=Path(item['url']).suffix
 rel='photos/'+item['sha256']+ext
 album={'id':'vault-fixture-'+model,'title':'ZIP 실파일 검증 화보','images':[{'url':rel,'number':1,'sha256':item['sha256'],'bytes':len(data),'width':item['width'],'height':item['height']}]}
 manifest={'version':1,'model':model,'physical_verified_image_count':1,'albums':[album]}
 for bad in (False,True):
  m=json.loads(json.dumps(manifest))
  if bad:
   m['albums'][0]['images'][0]['sha256']='0'*64
   m['albums'][0]['images'][0]['url']='photos/'+'0'*64+ext
  name=f'{model}-corrupt.zip' if bad else f'{model}-good.zip'
  with zipfile.ZipFile(out/name,'w',compression=zipfile.ZIP_STORED) as z:
   z.writestr('TEST/manifest.json',json.dumps(m,ensure_ascii=False))
   z.writestr('TEST/'+(m['albums'][0]['images'][0]['url'] if bad else rel),data)
 incremental=json.loads(json.dumps(manifest))
 incremental['albums'][0]['images'][0]['number']=2
 # A repeated SHA at a different numbered position is an independent album entry.
 with zipfile.ZipFile(out/(model+'-incremental.zip'),'w',compression=zipfile.ZIP_STORED) as z:
  z.writestr('TEST/manifest.json',json.dumps(incremental,ensure_ascii=False))
  z.writestr('TEST/'+rel,data)
 # GitHub Actions artifacts contain nested private-import ZIP files.
 # Deflate compression reproduces the wrapper format downloaded from Actions.
 with zipfile.ZipFile(out/(model+'-actions.zip'),'w',compression=zipfile.ZIP_DEFLATED) as outer:
  outer.write(out/(model+'-good.zip'),arcname='vault-part1-private-import.zip')
  outer.write(out/(model+'-incremental.zip'),arcname='vault-part2-private-import.zip')
  outer.writestr('audit.json',json.dumps({'artifact':'fixture','model':model}))
 # Import a verified byte-identical private copy of public photo number one.
 # The gallery must not double-count it, and should use its private Blob on ties.
 overlap=json.loads(json.dumps(manifest))
 overlap['albums'][0]['id']=source_album['id']
 overlap['albums'][0]['title']=source_album['title']
 with zipfile.ZipFile(out/(model+'-overlap.zip'),'w',compression=zipfile.ZIP_STORED) as z:
  z.writestr('TEST/manifest.json',json.dumps(overlap,ensure_ascii=False))
  z.writestr('TEST/'+rel,data)
 print('FIXTURE_CREATED',model,len(data))
