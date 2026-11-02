#!/usr/bin/env python3
"""Identify independently SHA-recorded ORIGINAL publisher sample URLs not yet stored.

The official metadata is a discovery ledger, never a count of newly archived
photos: a URL may occur multiple times with different historical JPEG bytes.
Only images hosted directly by the official publisher, with an already recorded
exact SHA-256/length/dimensions, can become staged originals. Never invent or
guess an original URL, bypass a payment, or treat re-encodes as new cuts.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

_SHA=re.compile(r'^[0-9a-f]{64}$')
_WORK=re.compile(r'^[a-z0-9][a-z0-9-]{1,100}$')
_PORTFOLIO=re.compile(r'^/portfolio/[a-zA-Z0-9%_-]{2,150}/?$')
_UPLOAD=re.compile(r'^/wp-content/uploads/[0-9]{4}/[0-9]{2}/[a-zA-Z0-9._-]{2,170}\.(?:jpe?g|png|webp)$',re.I)
_HOSTS={'djawaphoto.com','www.djawaphoto.com'}


def _publisher_page(raw: str) -> bool:
    try:
        p=urlsplit(raw)
        return (p.scheme=='https' and p.hostname in _HOSTS
                and not p.username and not p.password and p.port in (None,443)
                and not p.query and not p.fragment
                and bool(_PORTFOLIO.fullmatch(p.path)))
    except (ValueError,TypeError):
        return False


def _publisher_photo(raw: str) -> bool:
    try:
        p=urlsplit(raw)
        return (p.scheme=='https' and p.hostname in _HOSTS
                and not p.username and not p.password and p.port in (None,443)
                and not p.query and not p.fragment
                and bool(_UPLOAD.fullmatch(p.path)))
    except (ValueError,TypeError):
        return False


def missing_verified_publisher_samples(base: Path, owner: dict, model: str) -> dict:
    """Group by original URL, never by old row-number or historical SHA alone."""
    if model != 'mimmi':
        return {}
    base=Path(base)
    file=base/'official-previews.json'
    if not file.is_file():
        return {}
    source=json.loads(file.read_text(encoding='utf-8'))
    if source.get('model',{}).get('id') not in ('mimmi',None):
        raise ValueError('Wrong-model official sample index')
    if owner.get('model') != model:
        raise ValueError('Wrong-model saved owner index')
    saved={p['sha256'] for a in owner.get('albums',[]) for p in a.get('images',[])
           if isinstance(p.get('sha256'),str) and _SHA.fullmatch(p['sha256'])}
    result=defaultdict(list)
    for album in source.get('albums',[]):
        if not isinstance(album,dict):
            continue
        aid=album.get('id')
        if (not isinstance(aid,str) or not _WORK.fullmatch(aid)
                or not _publisher_page(album.get('source'))
                or album.get('publisher')!='DJAWA'):
            continue
        grouped={}
        for sample in album.get('samples',[]):
            if not isinstance(sample,dict):
                continue
            url=sample.get('url')
            sha=sample.get('sha256')
            if (not isinstance(url,str) or not _publisher_photo(url)
                    or not isinstance(sha,str) or not _SHA.fullmatch(sha)
                    or type(sample.get('bytes')) is not int
                    or not 4500<=sample['bytes']<=35_000_000
                    or type(sample.get('width')) is not int
                    or type(sample.get('height')) is not int
                    or min(sample['width'],sample['height'])<280):
                continue
            grouped.setdefault(url,[]).append({
                'sha256':sha,'bytes':sample['bytes'],
                'width':sample['width'],'height':sample['height']})
        for url,variants in grouped.items():
            # One identical source URL with 2 JPEG hashes is not 2 new images.
            if any(v['sha256'] in saved for v in variants):
                continue
            unique=list({v['sha256']:v for v in variants}.values())
            result[aid].append({'url':url,'recorded_variants':unique,
                                'publisher_page':album['source']})
    return dict(result)


def matching_recorded_variant(raw: bytes, decoded: dict, variants: list) -> bool:
    """Accept bytes only if exact historic SHA, length and decoded size agree."""
    import hashlib
    sha=hashlib.sha256(raw).hexdigest()
    return any(sha==v.get('sha256') and len(raw)==v.get('bytes')
               and decoded.get('width')==v.get('width')
               and decoded.get('height')==v.get('height')
               for v in variants)
