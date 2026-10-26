#!/usr/bin/env python3
"""Update references to publicly published creator posts; never fetch or store the image bytes."""
import json,re,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
RSS='https://teapawt.net/super_yuisan/media/rss'
req=urllib.request.Request(RSS,headers={'User-Agent':'Mozilla/5.0 (compatible; PersonalGalleryIndex/1.0)'})
with urllib.request.urlopen(req,timeout=25) as res: xml=res.read(2000000)
root=ET.fromstring(xml)
images=[]
for item in root.findall('.//item'):
    link=item.findtext('link','').replace('xitter.cf','x.com')
    desc=item.findtext('description','').split('<blockquote')[0]
    pub=item.findtext('pubDate','')
    for url in re.findall(r'https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)',desc):
        url=url+'?name=orig'
        if not any(x['url']==url for x in images):
            images.append({'url':url,'post':link,'date':pub,'caption':'심유이 공개 SNS'})
p=Path(__file__).with_name('feed.json')
if not images: raise RuntimeError('RSS returned no images; preserving old index')
old=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
seen={x['url'] for x in images}
merged=images+[x for x in old.get('images',[]) if x['url'] not in seen]
out={'updated':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source':RSS,'images':merged[:500]}
if old.get('images')!=out['images']:p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Indexed',len(images),'image links')
