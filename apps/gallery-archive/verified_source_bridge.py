"""Admit only independently named, exact-work public discovery sources.

Existing reviewed storage host guards stay unchanged. A newly found site
may be used for real image bytes only after a second direct page-heading
identity check and a photo URL explicitly embedded in its article.
"""
from __future__ import annotations

from collections import defaultdict


def eligible_source_pages(evidence, model, safe_page):
    if not isinstance(evidence, dict) or evidence.get('schema_version') != 1 or evidence.get('model') != model:
        return {}
    result = defaultdict(set)
    for work in evidence.get('search_results', []):
        if not isinstance(work, dict):
            continue
        aid = work.get('id')
        known = work.get('urls', [])
        if not isinstance(aid, str) or not isinstance(known, list) or len(known) > 512:
            continue
        for item in work.get('observations', []):
            if not isinstance(item, dict):
                continue
            if (item.get('proof') != 'unique_named_work_page_model_and_edition'
                    or item.get('model') != model or item.get('album_id') != aid):
                continue
            url = item.get('source')
            if isinstance(url,str) and url in known and safe_page(url, model):
                result[aid].add(url)
    return dict(result)


def article_scoped_images(raw, page, model, album_id, work_title,
                          identity_check, public_image_scope):
    """Raw page content must prove the exact model and work before extraction."""
    if not identity_check(raw, work_title, album_id, model):
        return set()
    from public_work_photo_extractor import recover_public_work_photo_urls
    candidates, status = recover_public_work_photo_urls(raw, page, model, trusted_work=True)
    if status != 'article_image_attributes':
        return set()
    # Only observed article <img>/<picture>/<a> URLs, never sidebars,
    # neighboring sets, constructed URL sequences or unknown remote redirects.
    return {url for url in candidates if public_image_scope(url, page)}


