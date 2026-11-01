#!/usr/bin/env python3
"""Compare resume/dedup queue technologies on the *complete* registered URL set.

No network fetch, no photo downloads, no paid endpoints. Crawlee's real
RequestQueue and Scrapy's actual URL fingerprints are exercised on identical
inputs. Queue success is NOT evidence that a photo was acquired.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

from collector_full_census import census
from scrapy import Request as ScrapyRequest
from scrapy.utils.request import fingerprint
from crawlee.storages import RequestQueue


async def measure(links,queue_name='gallery-full-census-queue'):
    queue=await RequestQueue.open(name=queue_name)
    try:
        # Run exact registered URLs through a persistent Crawlee RequestQueue.
        # No arbitrary URLs are invented and no HTTP requests are made.
        for i in range(0,len(links),400):
            for url in links[i:i+400]:
                await queue.add_request(url)
        total=await queue.get_total_count()
        first=await queue.fetch_next_request()
        reclaimed=False
        if first:
            await queue.reclaim_request(first,forefront=True)
            again=await queue.fetch_next_request()
            reclaimed=again is not None and again.unique_key==first.unique_key
            if again:await queue.mark_request_as_handled(again)
        still=await queue.get_total_count()
        return {'total_queued_unique':total,'total_after_reclaim':still,
                'actual_reclaim_replays_same_item':reclaimed}
    finally:await queue.drop()


def run(root,out,queue_name='gallery-full-census-queue'):
    snapshot=census(root)
    targets=snapshot['targets']
    links=[u for t in targets for u in t.get('urls',[]) + t.get('direct_image_urls',[])]
    unique_links=list(dict.fromkeys(links))
    scrapy_keys={fingerprint(ScrapyRequest(url)).hex() for url in links}
    crawlee=asyncio.run(measure(links,queue_name))
    report={
        'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'ALL registered works, catalogues, social and direct-image metadata',
        'targets':len(targets),'url_entries_including_repeated_sources':len(links),
        'exact_unique_url_count':len(unique_links),
        'scrapy_request_fingerprint_unique':len(scrapy_keys),
        'crawlee_request_queue':crawlee,
        'function_compared':'duplicate request elimination and reclaim-resume',
        'direct_photo_downloads':0,'new_owner_files_stored':0,
        'urls_not_included_due_to_target_sampling':0,
    }
    output=Path(out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if crawlee['total_queued_unique']>len(unique_links):
        raise ValueError('queue_was_larger_than_original_unique_url_set')
    if not crawlee['actual_reclaim_replays_same_item'] and links:
        raise ValueError('crawlee_queue_resume_not_verified')
    print('FULL_URL_QUEUE_COMPARE',json.dumps(report,ensure_ascii=False),flush=True)
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    run(a.root,a.out,queue_name='gallery-census-20261101-'+sha256(str(a.out).encode()).hexdigest()[:10])


if __name__=='__main__':main()
