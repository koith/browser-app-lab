#!/usr/bin/env python3
"""Generate two tiny real-byte test ZIPs from physically committed photos."""
import hashlib,json,zipfile
from pathlib import Path
out=Path('/tmp/photo-vault-qa');out.mkdir(exist_ok=True)
for model in ('yui','mimmi'):
 root=Path('apps')/(model+'-gallery')
 albums=json.loads((root/'stored-albums.json').read_text())['albums']
 item=next(p for a in albums for p in a['images'] if p.get('url','').startswith('stored-albums/'))
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
 print('FIXTURE_CREATED',model,len(data))
