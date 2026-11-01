#!/usr/bin/env python3
"""Normal public-origin transport diagnosis; no credentials or image saves."""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'yui-gallery'))
from public_photo_archive import PublicSession, public_failure

SAMPLES=[
    'https://showartx.net/artgravia-vol-693-yui/',
    'https://showartx.net/wp-content/uploads/2025/10/ART_693_3.jpg',
]

def inspect(url):
    s=PublicSession(delay=0)
    host=urlsplit(url).hostname
    row={'host':host,'path':urlsplit(url).path}
    try:
        r=s.get(url)
        row.update(public_session_status=r.status_code,
                   public_session_type=r.headers.get('Content-Type','').split(';')[0],
                   public_session_bytes=len(r.content))
    except Exception as e:
        row.update(public_session_error=type(e).__name__, public_session_details=public_failure(e))
    row['robots_status']=s.robot_status
    # Independent plain HTTP layer to distinguish origin denial, broken
    # robot policy and PublicSession implementation errors. No retries, no
    # auth, no login, redirects disabled, no bytes saved.
    try:
        r=requests.get(url,timeout=(8,18),allow_redirects=False,
                       headers={'User-Agent':'PersonalPublicPhotoSourceResearch/1.0'},
                       stream=True)
        row.update(plain_status=r.status_code,
                   plain_type=r.headers.get('Content-Type','').split(';')[0],
                   redirect_host=urlsplit(r.headers.get('Location','')).hostname)
        r.close()
    except requests.RequestException as e:
        row['plain_error']=type(e).__name__
    print('PUBLIC_SOURCE_TRANSPORT_DIAGNOSTIC',row,flush=True)

if __name__=='__main__':
    for url in SAMPLES:inspect(url)
