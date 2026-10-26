#!/usr/bin/env python3
"""Offline source audit and personal-use archive of photos visibly in public Yui's Present set.
Only actual img URLs discovered from the album's rendered page; no guessing or hidden assets.
"""
import asyncio,json,io,zipfile,hashlib,requests,re,time
from collections import Counter
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright
SOURCE="https://www.jliji.com/set/12343"
FOLDER=Path("YuiPresent33Private")
FOLDER.mkdir(exist_ok=True)
async def collect():
  async with async_playwright() as p:
    browser=await p.chromium.launch(headless=True)
    page=await browser.new_page(viewport={"width":1200,"height":900})
    await page.goto(SOURCE,wait_until="domcontentloaded",timeout=35000)
    for _ in range(12):
      await page.evaluate("window.scrollBy(0,Math.floor(innerHeight*.85))")
      await page.wait_for_timeout(200)
    extracted=await page.evaluate("""() => [...document.querySelectorAll('img')].filter(i=>/cdn\\.jliji\\.com\\/galleries\\/buondua\\/54756/.test(i.currentSrc||i.src||'')).map(i=>({
      current:i.currentSrc||i.src,
      attrs:Object.fromEntries(['src','data-src','data-full','data-original','srcset','data-zoom','data-href'].map(k=>[k,i.getAttribute(k)])),
      anchor:i.closest('a')?.href||null,
      parent:i.parentElement?.outerHTML?.slice(0,550)
    }))""")
    print("VISIBLE_CARD_COUNT",len(extracted),flush=True)
    print("SAMPLE_IMAGE_DOM",json.dumps(extracted[:2],ensure_ascii=False)[:3000],flush=True)
    if extracted:
      selector='img[src*="buondua/54756"]'
      try:
        await page.locator(selector).first().click(timeout=10000)
        await page.wait_for_timeout(900)
        more=await page.evaluate("""() => [...document.querySelectorAll('img')].filter(i=>i.naturalWidth>300&&i.getBoundingClientRect().width>300).map(i=>({src:i.currentSrc||i.src,w:i.naturalWidth,h:i.naturalHeight})).slice(-10)""")
        print("AFTER_IMAGE_CLICK",json.dumps(more,ensure_ascii=False)[:1800],flush=True)
      except Exception as e:print("CLICK_PROBE_FAILURE",str(e)[:180],flush=True)
    await browser.close()
    return extracted
def main():
  found=asyncio.run(collect())
  links=[]
  for record in found:
    u=record.get('current','')
    matched=re.search(r'/thumbs/(\d+)\.webp',u)
    if not matched:continue
    idx=int(matched.group(1))
    full=record.get('anchor') or record.get('attrs',{}).get('data-full') or ""
    if full.startswith("https://cdn.jliji.com/galleries/buondua/54756/") and full.endswith((".jpg",".jpeg",".png",".webp")):
      candidate=full
    else:candidate=u
    links.append((idx,candidate,u))
  by={i:(full,thumb) for i,full,thumb in links}
  if len(by)!=33 or set(by)!=set(range(1,34)):
    raise RuntimeError(f"Album is not fully visible: found {len(by)}/33 {sorted(by)}")
  session=requests.Session();manifest=[]
  for i in range(1,34):
    u,thumb=by[i]
    r=session.get(u,headers={'User-Agent':'Mozilla/5.0','Referer':SOURCE},timeout=22)
    r.raise_for_status()
    data=r.content
    if len(data)<2500:raise ValueError(f"Image {i} response too small: {len(data)}")
    with Image.open(io.BytesIO(data)) as im:im.verify()
    with Image.open(io.BytesIO(data)) as im:im.load();w,h=im.size;fmt=im.format
    ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(fmt)
    if not ext:raise ValueError(f"Image {i} unknown type")
    name=f"{i:03d}.{ext}"
    (FOLDER/name).write_bytes(data)
    manifest.append({'number':i,'url':u,'is_thumbnail_path':'/thumbs/' in u,'file':name,'bytes':len(data),'width':w,'height':h,'sha256':hashlib.sha256(data).hexdigest()})
  if len(set(x['sha256'] for x in manifest))!=33:raise ValueError("Duplicate image content")
  doc={'title':"SWEETBOX Yui's Present",'source':SOURCE,'declared':33,'files':manifest,'complete_visible_sequence':True,'original_publisher_quality_unverified':True}
  (FOLDER/'manifest.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2))
  with zipfile.ZipFile("YuiPresent33PublicGallery.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=2) as z:
    for a in manifest:z.write(FOLDER/a['file'],arcname='images/'+a['file'])
    z.write(FOLDER/'manifest.json',arcname='manifest.json')
  with zipfile.ZipFile('YuiPresent33PublicGallery.zip') as z:
    assert z.testzip() is None
    assert len(z.namelist())==34
  print("VERIFIED_33_PHOTOS",json.dumps({'count':len(manifest),'size':Path('YuiPresent33PublicGallery.zip').stat().st_size,'dims':Counter((x['width'],x['height']) for x in manifest).most_common(3),'thumbnails':sum(x['is_thumbnail_path'] for x in manifest)}),flush=True)
if __name__=='__main__':main()
