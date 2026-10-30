#!/usr/bin/env python3
"""Bounded, polite public-web retry transport shared by both photo crawlers.

No proxy rotation, captcha bypass, spoofed IP headers, authentication or
permission circumvention. A 403/451 is final. A 429 respects Retry-After and
transient 5xx/timeouts receive only a small number of retry attempts.
"""
from __future__ import annotations
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TRANSIENT = frozenset((429, 500, 502, 503, 504))
DENIED = frozenset((401, 403, 404, 451))


def build_session(headers: dict[str, str], retries: int = 2) -> requests.Session:
    if not 0 <= retries <= 3:
        raise ValueError("Crawl retry limit must remain bounded")
    policy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.8,
        status_forcelist=TRANSIENT,
        allowed_methods=frozenset(("GET",)),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update(headers)
    adapter = HTTPAdapter(max_retries=policy, pool_connections=2, pool_maxsize=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
