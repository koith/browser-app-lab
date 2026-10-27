"""Rank unchanged copies: resolution first, verified site-watermark absence second.

Reviews describe the exact file SHA-256, not a site's reputation. Publisher or
artist signatures are distinct from a gallery site's added watermark. Nothing
here crops, erases, reencodes or upscales a photograph.
"""
import re

def watermark_status(photo):
    review=photo.get('site_watermark_review',{})
    digest=photo.get('sha256','')
    if (isinstance(digest,str) and re.fullmatch(r'[a-f0-9]{64}',digest)
            and isinstance(review,dict) and review.get('sha256')==digest
            and isinstance(review.get('evidence'),str) and review['evidence'].strip()
            and review.get('status') in ('absent','present')):
        return review['status']
    return 'unknown'

def watermark_review(photo):
    return dict(photo['site_watermark_review']) if watermark_status(photo)!='unknown' else {'status':'unknown'}

def replacement_reason(candidate,current):
    incoming=candidate['width']*candidate['height'];existing=current['width']*current['height']
    if incoming>existing:return 'higher_resolution'
    if (incoming==existing and (candidate['width'],candidate['height'])==(current['width'],current['height'])
            and watermark_status(candidate)=='absent' and watermark_status(current)!='absent'):
        return 'same_resolution_without_site_watermark'
    return None
