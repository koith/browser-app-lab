#!/usr/bin/env python3
"""Build public photo gallery index by traversing normal media pagination.

Never download or mirror image bytes to the public GitHub repository.
Preserve previously indexed media if a transient network result is shorter.
"""
import json, requests
from datetime import datetime, timezone
from pathlib import Path
from sns_archive import crawl_pages

feed_file=Path(__file__).with_name('feed.json')
old=json.loads(feed_file.read_text(encoding='utf-8')) if feed_file.exists() else {'images':[]}
session=requests.Session()
photos,pages=crawl_pages(session,max_pages=85,delay=.35)
if len(photos)<50:
    raise RuntimeError('Media index response too small; leave previously published feed unchanged')

def record(p):
    post_id=p.get('post','').split('/status/')[-1].split('/')[0]
    iso=''
    if post_id.isdigit():
        try: iso=datetime.fromtimestamp((((int(post_id)>>22)+1288834974657)/1000),timezone.utc).isoformat()
        except (ValueError,OverflowError): pass
    return {'url':p['url'],'post':p.get('post',''),'date':iso,
            'name':'SNS '+iso[:10]+' · '+p['id']+'.jpg' if iso else p['id']+'.jpg',
            'caption':'심유이 공개 SNS 미디어','source':'official-sns'}
results=[record(p) for p in photos]
keys={x['url'] for x in results}
for item in old.get('images',[]):
    if item.get('url') not in keys:
        results.append(item);keys.add(item['url'])
new={'updated':datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'source':'https://teapawt.net/super_yuisan/media',
    'complete_pagination':bool(pages) and not pages[-1].get('next'),
    'pages_visited':len(pages),'images':results}
if not old.get('images') or len(results)>=len(old['images']):
    feed_file.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('SNS_INDEX_UPDATED',json.dumps({'pages':len(pages),'photos':len(results),
        'complete_pagination':new['complete_pagination']}),flush=True)
else:
    raise RuntimeError('New feed would delete media links; refusing index regression')
