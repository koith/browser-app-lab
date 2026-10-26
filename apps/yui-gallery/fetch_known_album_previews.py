#!/usr/bin/env python3
"""Archive only observed publicly displayed photos from individual album pages.

Never invent URLs or enumerate gated pages. Album expected count is separate from
the real downloadable first-page subset.
"""
import hashlib,io,json,os,time
from pathlib import Path
import requests
from PIL import Image
ROOT=Path('apps/yui-gallery')
source=json.loads((ROOT/'known-album-preview-urls.json').read_text(encoding='utf-8'))
existing=ROOT/'stored-albums.json'
stored=json.loads(existing.read_text(encoding='utf-8')) if existing.exists() else {'albums':[]}
byid={a['id']:a for a in stored.get('albums',[])}
session=requests.Session()
session.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'})
overall=0
for a in source['albums']:
  aid=a['id'];old=byid.get(aid,{});images=list(old.get('images',[]))
  known={x['sha256'] for x in images}
  errors=[]
  for i,u in enumerate(a['urls'],1):
    try:
      response=session.get(u,timeout=16,headers={'Referer':a['source']})
      response.raise_for_status()
      raw=response.content
      if len(raw)>25_000_000:raise ValueError('Image file too large')
      with Image.open(io.BytesIO(raw)) as im:
        im.verify()
      with Image.open(io.BytesIO(raw)) as im:
        fmt=im.format;w,h=im.size
      if min(w,h)<320:raise ValueError('Below 320px')
      ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(fmt)
      if not ext:raise ValueError('Invalid image format '+str(fmt))
      digest=hashlib.sha256(raw).hexdigest()
      if digest in known:continue
      f=ROOT/'stored-albums'/aid/(str(i).zfill(3)+'_'+digest[:12]+'.'+ext)
      f.parent.mkdir(parents=True,exist_ok=True)
      f.write_bytes(raw)
      images.append({'url':str(f.relative_to(ROOT)).replace('\\','/'),'source_url':u,'origin_page':a['source'],
        'sha256':digest,'width':w,'height':h,'bytes':len(raw)})
      known.add(digest);overall+=1
      print('PUBLIC_ALBUM_IMAGE',aid,i,w,h,len(raw),flush=True)
    except Exception as ex:
      errors.append({'image':i,'url':u,'error':str(ex)[:180]})
      print('PUBLIC_ALBUM_IMAGE_FAILED',aid,i,str(ex)[:140],flush=True)
    time.sleep(.15)
  byid[aid]={'id':aid,'site':'V2PH','title':a['title'],'source':a['source'],'expected':a['expected'],
      'images':images,'status':'partial_public_page_only','pages_visited':1,'errors':errors}
  print('PUBLIC_ALBUM_RESULT',aid,'stored',len(images),'expected',a['expected'],'errors',len(errors),flush=True)
if overall==0:raise RuntimeError('None of the public first-page images could be downloaded; archive is unchanged')
stored['updated']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
stored['albums']=list(byid.values())
existing.write_text(json.dumps(stored,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PHYSICAL_ALBUM_FILES_ADDED',overall,flush=True)
