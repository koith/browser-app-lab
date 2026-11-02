#!/usr/bin/env python3
"""Read-only network probe for EXACT previously SHA-verified publisher samples.

No TeraBox, paid media, account/login or photo artifact is accessed or written.
This reports real current HTTP byte reachability separately from archive state.
"""
import json
import hashlib
from io import BytesIO
from pathlib import Path
import sys

import requests
from PIL import Image
from official_sample_recovery import (
    missing_verified_publisher_samples, matching_recorded_variant)

ROOT=Path(__file__).resolve().parents[2]


def probe(root=ROOT, model='mimmi', limit=32, get=None):
    root=Path(root)
    owner=json.loads((root/'apps'/f'{model}-gallery'/'owner-index.json').read_text())
    gaps=missing_verified_publisher_samples(
        root/'apps'/f'{model}-gallery',owner,model)
    session=requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; PublicPublisherSampleVerification/1.0)',
                            'Accept':'image/jpeg,image/png,image/webp'})
    get=get or session.get
    results=[]
    for aid,grouprows in gaps.items():
        for gap in grouprows:
            if len(results)>=limit:
                break
            url=gap['url']
            try:
                with get(url,timeout=(8,28),stream=True,allow_redirects=False,
                         headers={'Referer':gap['publisher_page']}) as r:
                    if r.status_code!=200:
                        results.append({'work':aid,'status':'http_'+str(r.status_code)})
                        continue
                    if r.url!=url:
                        results.append({'work':aid,'status':'unapproved_redirect'})
                        continue
                    chunks=bytearray()
                    for part in r.iter_content(65536):
                        chunks.extend(part)
                        if len(chunks)>35_000_000:
                            raise ValueError('oversize_public_sample')
                raw=bytes(chunks)
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
                with Image.open(BytesIO(raw)) as image:
                    meta={'width':image.width,'height':image.height}
                ok=matching_recorded_variant(raw,meta,gap['recorded_variants'])
                results.append({'work':aid,
                                'status':'EXACT_SHA_MATCH' if ok else 'different_bytes_unverified',
                                'bytes':len(raw),'sha_prefix':hashlib.sha256(raw).hexdigest()[:12]})
            except (requests.RequestException,ValueError,OSError) as exc:
                results.append({'work':aid,'status':type(exc).__name__})
    summary={'model':model,'publisher_urls_without_saved_variant':sum(map(len,gaps.values())),
             'urls_probed':len(results),'exact_sha_matched':sum(
                 x['status']=='EXACT_SHA_MATCH' for x in results),
             'other_outcomes':{status:sum(x['status']==status for x in results)
                               for status in sorted({x['status'] for x in results})
                               if status!='EXACT_SHA_MATCH'},
             'records':results}
    print('OFFICIAL_MISSING_BYTES_PROBE',json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


if __name__=='__main__':
    out=probe()
    if out['urls_probed']!=out['publisher_urls_without_saved_variant']:
        raise SystemExit('The bounded probe did not cover every currently missing official URL')
