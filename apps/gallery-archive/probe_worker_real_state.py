#!/usr/bin/env python3
"""G-09 read-only production Worker transport diagnosis. No auth or retries.
Classify actual route 1042 (Worker missing/disabled or same-zone fetch),
503 (origin availability), 429 (rate limit), and browser preflight CORS
without mistaking a synthetic local Worker PASS for a deployed service.
"""
import json
import re
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener
BASE='https://gallery-archive-free.gallery-9f7d03138f3f.workers.dev'
ORIGIN='https://koith.github.io'
UA='GalleryTransportDiagnosis/1.0'
def inspect_once(path,method='GET',body=None,origin=ORIGIN):
    headers={'User-Agent':UA,'Origin':origin}
    if method=='OPTIONS':
        headers.update({'Access-Control-Request-Method':'POST',
                        'Access-Control-Request-Headers':'content-type'})
    if method=='POST':
        headers['Content-Type']='application/json'
    req=Request(BASE+path,method=method,headers=headers,data=body)
    try:
        with build_opener().open(req,timeout=18) as response:
            status=response.status
            hdr=response.headers
            content=response.read(8192)
    except HTTPError as response:
        status=response.code
        hdr=response.headers
        content=response.read(8192)
    except (URLError,TimeoutError,OSError) as error:
        return {'method':method,'path':path,'status':'transport_'+type(error).__name__,
                'failure_kind':'transport_failure'}
    body_text=content.decode('utf8','replace')
    hit=re.search(r'(?:Error\s*|error[^0-9]{0,12})(1042|1027|1101|1102)',body_text,re.I)
    code=hit.group(1) if hit else None
    kind='http_'+str(status)
    if code=='1042':kind='worker_route_disabled_or_same_zone_fetch_1042'
    elif code=='1027':kind='free_daily_request_limit_1027'
    elif status==429:kind='rate_limited_429'
    elif status==503:kind='service_unavailable_503'
    elif status==404:kind='worker_or_photo_missing_404'
    elif status==204 and method=='OPTIONS':kind='preflight_ok'
    return {'method':method,'path':path,'status':status,'cloudflare_code':code,
            'failure_kind':kind,
            'cors_origin_correct':hdr.get('Access-Control-Allow-Origin')==origin,
            'cors_allow_methods':hdr.get('Access-Control-Allow-Methods',''),
            'content_type':hdr.get('Content-Type','').split(';')[0]}
def probe():
    body=json.dumps({'model':'mimmi','album':'no-such-album',
                     'number':1,'variant':'original','sha256':'0'*64}).encode()
    observations=[
        inspect_once('/api/v1/health'),
        inspect_once('/api/v1/sign',method='OPTIONS'),
        inspect_once('/api/v1/sign',method='POST',body=body),
    ]
    online=observations[0]['status']==200 and observations[1]['status']==204
    has_cors=observations[1]['cors_origin_correct'] is True
    correct_sign=observations[2]['status']==404 and observations[2]['cors_origin_correct']
    result={'observations':observations,'production_worker_healthy':bool(online and has_cors and correct_sign),
            'local_worker_unit_test_is_not_live_deployment_proof':True}
    print('G09_LIVE_WORKER_ROUTE_AND_CORS_DIAGNOSTIC',json.dumps(result,ensure_ascii=False),flush=True)
    return result
if __name__=='__main__':
    observation=probe()
    if not observation['production_worker_healthy']:
        raise SystemExit('G09_PRODUCTION_WORKER_NOT_ACCEPTED')
