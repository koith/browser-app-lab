#!/usr/bin/env python3
"""Archive accessible original-image URLs from Yui's publicly published media timeline.

Maintains real media files, image decoding checks, dates and source status URLs;
no paid/private content, no site-authentication circumvention.
"""
import json,hashlib,datetime,zipfile
from pathlib import Path
from archive_engine import download,utcnow

source=Path("apps/yui-gallery/paginated-sns-index.json")
index=json.loads(source.read_text(encoding="utf-8"))
records=[];seen=set()
for item in index["images"]:
    img=item["url"];post=item.get("post","")
    if not post.startswith("https://x.com/super_yuisan/status/"):continue
    if img in seen:continue
    seen.add(img)
    try:
        tweet_id=int(post.split("/status/")[1].split("/")[0])
        created=datetime.datetime.fromtimestamp(((tweet_id>>22)+1288834974657)/1000,datetime.timezone.utc).isoformat()
    except (ValueError,IndexError,OverflowError):
        created=None
    records.append({"url":img,"origin_page":post,"source_attribute":"public_post_media","alt":item.get("name",""),"date":created})
manifest={"generated_at":utcnow(),"sources":[{"id":"Yui-public-SNS","source_url":index["source"],
    "declared_photos":None,"pages_visited":[{"url":x["source"],"page":x["page"]} for x in index["pages"]],
    "urls_discovered":records,"images_discovered":len(records),
    "errors":[],"truncated":False,"collected_at":utcnow()}]}
Path("yui-sns-cursor-discovery.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
total=download(Path("yui-sns-cursor-discovery.json"),Path("yui-sns-originals"),max_images=600)
Path("yui-public-archive-dynamic.zip").rename("yui-sns-originals-verified.zip")
with zipfile.ZipFile("yui-sns-originals-verified.zip") as z:assert z.testzip() is None
print("SNS_DOWNLOAD_FINAL",json.dumps({"discovered":len(records),"status":total},ensure_ascii=False),flush=True)
