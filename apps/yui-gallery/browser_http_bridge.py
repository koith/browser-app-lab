"""Relay a real browser request while requests verifies the managed proxy CA.

Preserve the browser's actual method/headers/body. Never synthesize a different
User-Agent, inject authentication, change an origin or disable TLS verification.
CI uses direct browser TLS; this helper is for the managed local QA environment.
"""
import asyncio

import requests


async def fulfill_verified_request(route):
    request = route.request
    headers = {k: v for k, v in (await request.all_headers()).items()
               if k.lower() not in ('host', 'content-length', 'accept-encoding', 'connection')}
    response = await asyncio.to_thread(
        requests.request, request.method, request.url, headers=headers,
        data=request.post_data_buffer, timeout=(12, 45), allow_redirects=False)
    response_headers = {k: v for k, v in response.headers.items()
                        if k.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'connection')}
    await route.fulfill(status=response.status_code, headers=response_headers, body=response.content)
