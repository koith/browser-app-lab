"""Read the owner's normal web upload token; never export it or execute scripts.

The pinned rclone backend only recognizes an old token wrapper on the homepage.
Use the authenticated /main document, then pass its token to that same backend
in the child environment. Access denials and login pages remain failures.
"""
import asyncio
import hashlib
import re
import time
from urllib.parse import unquote, urljoin, urlsplit

import httpx


class WebStateUnavailable(ValueError):
    pass


def official_url(value):
    u=urlsplit(value)
    return (u.scheme=='https' and u.port in (None,443) and not u.username and not u.password
            and bool(re.fullmatch(r'(?:[a-z0-9-]+\.)?terabox\.com',u.hostname or '')))


def extract_token(document):
    # Decode the static escaped assignment; never eval provider JavaScript.
    text=unquote(document)
    patterns=(r'''window\.jsToken\s*=\s*(["'])([^"'\r\n]+)\1''',
              r'''function\s+fn\(a\)\s*\{\s*window\.jsToken\s*=\s*a\s*\}\s*;?\s*fn\((["'])([^"'\r\n]+)\1\)''')
    for pattern in patterns:
        match=re.search(pattern,text)
        if match:
            value=match[2]
            if 16<=len(value)<=4096 and all(32<ord(c)<127 for c in value) and value not in ('undefined','null'):
                return value
    raise WebStateUnavailable('Owner web document has no recognized upload token')


class OwnerUploadState:
    def __init__(self,transport=None):
        self.transport=transport;self.lock=asyncio.Lock();self.key=None;self.token=None;self.until=0

    async def get(self,cookie,origin='https://www.terabox.com'):
        if not official_url(origin) or urlsplit(origin).path not in ('','/'):
            raise WebStateUnavailable('Unsupported owner storage origin')
        key=hashlib.sha256((origin+'\n'+cookie).encode()).digest()
        async with self.lock:
            if self.key==key and time.monotonic()<self.until:return self.token
            url=origin.rstrip('/')+'/main'
            headers={'Cookie':cookie,'Accept':'text/html,application/xhtml+xml',
                     'Referer':origin,'User-Agent':'terabox;1.42.2.150;PC;PC-Windows;10.0.22631;WindowsTeraBox'}
            async with httpx.AsyncClient(transport=self.transport,timeout=30,follow_redirects=False) as client:
                for _ in range(4):
                    async with client.stream('GET',url,headers=headers) as response:
                        status=response.status_code
                        print('OWNER_UPLOAD_WEB_DOCUMENT',status,urlsplit(url).path,flush=True)
                        if status in (301,302,303,307,308):
                            target=urljoin(url,response.headers.get('location',''))
                            if not official_url(target) or re.search(r'login|passport|challenge',urlsplit(target).path,re.I):
                                raise WebStateUnavailable('Owner web session needs normal login')
                            url=target;continue
                        if status!=200:raise WebStateUnavailable('Owner web upload document HTTP '+str(status))
                        raw=bytearray()
                        async for part in response.aiter_bytes():
                            raw.extend(part)
                            if len(raw)>2_000_000:raise WebStateUnavailable('Owner web document exceeds bound')
                        token=extract_token(raw.decode('utf-8','replace'))
                        self.key,self.token,self.until=key,token,time.monotonic()+900
                        print('OWNER_UPLOAD_WEB_TOKEN_READY',flush=True)
                        return token
            raise WebStateUnavailable('Owner web document redirect bound exceeded')
