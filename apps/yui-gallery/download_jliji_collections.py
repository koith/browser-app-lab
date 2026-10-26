#!/usr/bin/env python3
"""Archive four fully visible Yui photobooks from a freely readable set gallery.

Collect exact rendered data-full image URLs for each specified album; reject
related-model tiles, thumbnails and partial groups. No auth/purchase bypass.
Files are emitted as individual image files with a manifest for personal use,
never added to the public GitHub Pages repository.
"""
import asyncio,concurrent.futures,hashlib,io,json,re,requests
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
from playwright.async_api import async_playwright

CONFIG=[
 {"id":"yuis-present33","set_id":12343,"gallery_id":54756,"count":33,"title":"SWEETBOX Yui — Yui’s Present"},
 {"id":"athletic-club104","set_id":14973,"gallery_id":56008,"count":104,"title":"Yui — Athletic Club"},
 {"id":"wet-yui80","set_id":14346,"gallery_id":42862,"count":80,"title":"Yui — Wet ゆい"},
 {"id":"teddy-bear97","set_id":19356,"gallery_id":49348,"count":97,"title":"SWEETBOX Yui — Teddy Bear"}
]
ROOT=Path('yui-jliji-full-private')
ROOT.mkdir(exist_ok=True)

async def discover(page,cfg):
 url=f"https://www.jliji.com/set/{cfg['set_id']}"
 await page.goto(url,wait_until='domcontentloaded',timeout=36000)
 await page.wait_for_timeout(650)
 for _ in range(25):
  await page.evaluate("window.scrollBy(0, Math.max(650, innerHeight*.9))")
  await page.wait_for_timeout(120)
 imgs=await page.evaluate("""() => [...document.querySelectorAll('img[data-full]')].map(i=>({full:i.getAttribute('data-full'),alt:i.alt,src:i.src}))""")
 path=f'/galleries/buondua/{cfg["gallery_id"]}/'
 selected={}
 for x in imgs:
  u=x.get('full') or ''
  if u.startswith("https://cdn.jliji.com"+path) and re.search(r'/\d+\.(?:jpg|jpeg|png|webp)$',u):
   n=int(re.search(r'/(\d+)\.(?:jpg|jpeg|png|webp)$',u).group(1))
   selected[n]=u
 print("GALLERY_DISCOVERY",cfg['id'],len(selected),"EXPECTED",cfg['count'],flush=True)
 if set(selected)!=set(range(1,cfg["count"]+1)):
  missing=sorted(set(range(1,cfg["count"]+1))-set(selected))
  raise RuntimeError(f"Album {cfg['id']} incomplete visible page: {len(selected)}/{cfg['count']}; missing {missing[:20]}")
 return selected,url

def getphoto(task):
 idx,url,source=task
 res=requests.get(url,timeout=(12,30),headers={'User-Agent':'Mozilla/5.0','Referer':source})
 res.raise_for_status()
 b=res.content
 if len(b)<3000 or len(b)>22000000:raise ValueError("Unreasonable file size "+str(len(b)))
 with Image.open(io.BytesIO(b)) as im:im.verify()
 with Image.open(io.BytesIO(b)) as im:im.load();fmt=im.format;w,h=im.size
 if min(w,h)<400:raise ValueError("Image is too small "+str((w,h)))
 ext={"JPEG":"jpg","PNG":"png","WEBP":"webp"}.get(fmt)
 if not ext:raise ValueError("Unsupported format "+str(fmt))
 return {"n":idx,"file":f"{idx:03d}.{ext}","url":url,"bytes":len(b),"width":w,"height":h,
         "sha256":hashlib.sha256(b).hexdigest()},b

async def main():
 report=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  page=await browser.new_page(viewport={"width":1200,"height":900})
  for cfg in CONFIG:
   selected,source=await discover(page,cfg)
   successful={};failures={}
   with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
    fut={pool.submit(getphoto,(n,url,source)):n for n,url in selected.items()}
    for f in concurrent.futures.as_completed(fut):
     n=fut[f]
     try:successful[n]=f.result()
     except Exception as e:failures[n]=str(e)
   if len(successful)!=cfg['count'] or failures:
    raise RuntimeError(f"Downloaded {len(successful)}/{cfg['count']} of {cfg['id']}; errors={list(failures.items())[:5]}")
   hashes=[row["sha256"] for row,b in successful.values()]
   if len(set(hashes))!=cfg['count']:raise RuntimeError("Hash duplicate within album "+cfg['id'])
   manifest={"id":cfg["id"],"title":cfg["title"],"source_page":source,"advertised_count":cfg["count"],
             "acquired_count":len(successful),"images":[v[0] for _,v in sorted(successful.items())],
             "complete_public_visible_page":True,"publisher_original_quality_unverified":True}
   folder=ROOT/cfg['id']
   folder.mkdir(parents=True,exist_ok=True)
   for n,(row,blob) in sorted(successful.items()):
    path=folder/row['file']
    path.write_bytes(blob)
    assert path.stat().st_size==row['bytes']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
   (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
   assert len(list(folder.glob('*.jpg')))+len(list(folder.glob('*.jpeg')))+len(list(folder.glob('*.png')))+len(list(folder.glob('*.webp')))==cfg['count']
   summary={"id":cfg["id"],"advertised":cfg["count"],"downloaded":len(successful),
            "bytes":sum(row['bytes'] for row,blob in successful.values()),
            "sizes":Counter((v[0]["width"],v[0]["height"]) for v in successful.values()).most_common(3)}
   report.append(summary)
   print('VERIFIED_PUBLIC_ALBUM',json.dumps(summary,ensure_ascii=False),flush=True)
  await browser.close()
 (ROOT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print('ALL_ALBUMS_FILES_OK',sum(x['downloaded'] for x in report),flush=True)
if __name__=='__main__':asyncio.run(main())
