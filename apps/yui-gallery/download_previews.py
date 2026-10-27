#!/usr/bin/env python3
"""Archive openly displayed preview images from Yui's Chinese catalogue pages.
Only preview URLs observed on the public pages. Never enter paywalls or archives.
The downloaded images are for the user's personal off-repository archive.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from PIL import Image
from hashlib import sha256
import json,zipfile,time

IMAGES=[
 ("huantuji","https://www.huantuji.com/yui/","https://image.huantuji.com/2026/07/2026070806385046-2048x1366.webp"),
 ("huantuji","https://www.huantuji.com/yui/","https://image.huantuji.com/2026/07/2026070806385978.webp"),
 ("huantuji","https://www.huantuji.com/yui/","https://image.huantuji.com/2026/07/2026070806390473.webp"),
 ("chaotuji","https://www.chaotuji.com/yui/","https://image.chaotuji.com/2026/04/2026042913290312.webp?fit=scale&fm=pjpg&h=1536&ixlib=php-3.3.1&w=1024&wpsize=1536x1536&s=3447f2be9e42a28d166a6a8f65e359de"),
 ("chaotuji","https://www.chaotuji.com/yui/","https://image.chaotuji.com/2026/04/2026042913291272.webp?fit=scale&fm=pjpg&h=1536&ixlib=php-3.3.1&w=1105&wpsize=1536x1536&s=18cce12f0a8bf5cd796dba730a842bf6"),
 ("yuntu8","https://yuntu8.com/1748.html","https://pic1.imgdb.cn/item/67a389fad0e0a243d4fc02d1.jpg"),
 ("yuntu8","https://yuntu8.com/1748.html","https://pic1.imgdb.cn/item/67a3897ed0e0a243d4fc02ca.jpg"),
 ("yuntu8","https://yuntu8.com/1748.html","https://pic1.imgdb.cn/item/67a389e5d0e0a243d4fc02d0.jpg"),
 ("yuntu8","https://yuntu8.com/1748.html","https://pic1.imgdb.cn/item/67a389e5d0e0a243d4fc02cf.jpg")
]
root=Path("yui-chinese-free-previews");root.mkdir(exist_ok=True)
results=[]
for n,(site,source,url) in enumerate(IMAGES,1):
  obj={"site":site,"source_page":source,"image_url":url,"index":n}
  for attempt in range(2):
    try:
      req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ArchiveQA/1.0)","Accept":"image/avif,image/webp,image/png,image/jpeg,*/*"})
      with urlopen(req,timeout=18) as response:
        typ=response.headers.get("Content-Type","").split(";")[0].lower()
        raw=response.read(20000001)
      if len(raw)>20000000: raise ValueError("image exceeds safety size")
      im=Image.open(BytesIO(raw));im.load()
      if im.width<200 or im.height<200:raise ValueError("image below minimum size")
      ext={"JPEG":".jpg","WEBP":".webp","PNG":".png"}.get(im.format)
      if not ext: raise ValueError("unsupported image format: "+str(im.format))
      path=root/site/f"{n:02d}{ext}";path.parent.mkdir(exist_ok=True)
      path.write_bytes(raw)
      obj.update({"status":"downloaded","file":str(path.relative_to(root)),"bytes":len(raw),"width":im.width,"height":im.height,"sha256":sha256(raw).hexdigest(),"mime":typ})
      break
    except Exception as e:
      obj.update({"status":"failed","error":type(e).__name__+": "+str(e)[:180]})
      if attempt==0:time.sleep(.8)
  results.append(obj)
  print(site,n,obj["status"],obj.get("width"),obj.get("bytes"),obj.get("error",""),flush=True)
(root/"manifest.json").write_text(json.dumps({"purpose":"Public Chinese gallery preview images only; not subscriber-only photo book originals","images":results},ensure_ascii=False,indent=2),encoding="utf-8")
success=[x for x in results if x["status"]=="downloaded"]
with zipfile.ZipFile("yui-chinese-free-previews.zip","w",zipfile.ZIP_DEFLATED,compresslevel=4) as z:
  for file in root.rglob("*"):
    if file.is_file():z.write(file,str(file.relative_to(root)))
with zipfile.ZipFile("yui-chinese-free-previews.zip") as z:
  assert z.testzip() is None
assert len(success)>=2,f"Only {len(success)} images downloaded"
