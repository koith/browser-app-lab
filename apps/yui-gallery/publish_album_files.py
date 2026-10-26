#!/usr/bin/env python3
"""Publish only actually downloaded PUBLIC album-page image bytes to the gallery.

Album URLs come from albums.json; gallery shows no invented media.
Does not log in or access paid content. This is a bounded GitHub Pages
bootstrap, NOT the promised large permanent storage backend.
"""
import asyncio, hashlib, io, json, os, re, time, urllib.parse
from pathlib import Path
import requests
from PIL import Image
from playwright.async_api import async_playwright

ROOT=Path('apps/yui-gallery')
OUT=ROOT/'stored-albums'
OUT.mkdir(exist_ok=True,parents=True)
MAX_ALBUMS=int(os.environ.get('MAX_ALBUMS','20'))
MAX_IMAGE=int(os.environ.get('MAX_IMAGE_PER_ALBUM','40'))
MAX_TOTAL_MB=int(os.environ.get('MAX_TOTAL_MB','150'))
BUDGET=MAX_TOTAL_MB*1024*1024
SCROLL=r"""async () => {
 let stable=0,last=0;
 for(let i=0;i<28;i++){
   window.scrollBy(0,Math.max(650,innerHeight*.85));
   await new Promise(r=>setTimeout(r,250));
   const m=document.documentElement.scrollHeight;
   if(scrollY+innerHeight>=m-3&&m===last)stable++;else stable=0;
   last=m;if(stable>=3)break;
 }
 return true;
}"""
SCRAPE=r"""() => {
 const root=document.querySelector('.photos,.photo-list,.album-content,.gallery,.entry-content,article,main')||document.body;
 let result=[];
 for(const img of root.querySelectorAll('img,picture source')){
   if(img.closest('footer,header,nav,.sidebar,.related,.recommend,.ad,.advertisement'))continue;
   for(const key of ['data-original','data-full','data-src','data-lazy-src','srcset','src']){
     let val=img.getAttribute(key);if(!val)continue;
     for(const x of val.split(',')){
       let u=x.trim().split(/\s+/)[0];
       try{u=new URL(u,location.href).href}catch{continue}
       if(/^https?:/.test(u))result.push(u);
     }
   }
 }
 let next=[];
 for(const a of document.querySelectorAll('a[href]')){
   const t=(a.innerText||'').trim(), rel=a.getAttribute('rel')||'';
   if(/^(?:\d{1,3}|下一页|下页|next|›|»)$/.test(t)||/next/.test(rel)){
     try{const u=new URL(a.href,location.href);if(u.host===location.host)next.push(u.href)}catch{}
   }
 }
 return {images:[...new Set(result)],next:[...new Set(next)]};
}"""
def image_url(u):
 p=urllib.parse.urlsplit(u)
 return p.scheme in ('http','https') and bool(re.search(r'\.(?:jpg|jpeg|png|webp)(?:$|\?)',u,re.I)) and not re.search(r'avatar|logo|icon|favicon|banner|ad-|advert|placeholder',p.path,re.I)

async def main():
 albums=json.loads((ROOT/'albums.json').read_text())['albums']
 chosen=[a for a in albums if a.get('kind')=='album' and a.get('source','').startswith('https://')][:MAX_ALBUMS]
 old_file=ROOT/'stored-albums.json'
 old=json.loads(old_file.read_text()) if old_file.exists() else {'albums':[]}
 byid={a['id']:a for a in old['albums']}
 session=requests.Session()
 budget_used=sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file())
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  ctx=await browser.new_context(viewport={'width':1100,'height':780'},service_workers='block')
  for album in chosen:
   aid=album['id']; url=album['source']; base=urllib.parse.urlsplit(url)
   page=await ctx.new_page()
   queue=[url];visited=set();seen=set();items=list(byid.get(aid,{}).get('images',[]))
   seen.update(x['source_url'] for x in items)
   errors=[]
   while queue and len(visited)<12 and len(items)<MAX_IMAGE and budget_used<BUDGET:
    target=queue.pop(0)
    if target in visited:continue
    visited.add(target)
    try:
     resp=await page.goto(target,wait_until='domcontentloaded',timeout=22000)
     if not resp or resp.status>=400:raise ValueError('HTTP '+str(resp.status if resp else 'no response'))
     await page.evaluate(SCROLL)
     data=await page.evaluate(SCRAPE)
     for link in data['next']:
      u=urllib.parse.urlsplit(link)
      if u.hostname==base.hostname and (u.path==base.path or u.path.startswith(base.path.rstrip('/')+'/page/')) and link not in visited and link not in queue:queue.append(link)
     for img_url in data['images']:
      if not image_url(img_url) or img_url in seen or len(items)>=MAX_IMAGE:continue
      seen.add(img_url)
      try:
       res=session.get(img_url,timeout=(8,14),headers={'User-Agent':'Mozilla/5.0','Referer':target},stream=True)
       res.raise_for_status()
       raw=b''
       for chunk in res.iter_content(65536):
        raw+=chunk
        if len(raw)>10_000_000:raise ValueError('file >10MB')
       im=Image.open(io.BytesIO(raw));im.verify()
       im=Image.open(io.BytesIO(raw))
       if min(im.size)<300:continue
       fmt={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(im.format)
       if not fmt:continue
       digest=hashlib.sha256(raw).hexdigest()
       dest=OUT/aid/(digest[:20]+'.'+fmt)
       dest.parent.mkdir(parents=True,exist_ok=True)
       if not dest.exists():
        if budget_used+len(raw)>BUDGET:break
        dest.write_bytes(raw);budget_used+=len(raw)
       items.append({'url':'stored-albums/'+aid+'/'+dest.name,'source_url':img_url,'sha256':digest,'width':im.width,'height':im.height,'bytes':len(raw),'origin_page':target})
      except Exception as e:errors.append(str(e)[:140])
    except Exception as e:errors.append(str(e)[:140])
   await page.close()
   byid[aid]={'id':aid,'site':album['site'],'title':album['title'],'source':url,'expected':album.get('photos'),
              'images':items,'pages_visited':len(visited),'errors':errors[:8],
              'status':'public_previews_only' if items else 'no_verified_local_images'}
   print('ALBUM',aid,'stored',len(items),'pages',len(visited),'errors',len(errors),flush=True)
  await browser.close()
 final={'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'storage':'GitHub Pages local files (temporary bounded bootstrap)','albums':list(byid.values())}
 old_file.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
 count=sum(len(a['images']) for a in final['albums'])
 print('STORED_ALBUMS_FINAL',json.dumps({'albums':len(final['albums']),'images':count,'bytes':budget_used}),flush=True)
 if not count:raise RuntimeError('No real photobook files acquired; cannot claim linked gallery success')
if __name__=='__main__':asyncio.run(main())
