"""Select already saved same-photo editions by *measured optical evidence*,
not by megapixels, file bytes or a watermarked site's marketing claim.

Conservative on incomplete evidence: an unmeasured 4K upscale cannot displace
a known original. An exact-SHA verified watermark review may break a proven
visual-quality tie. Never alter or delete original bytes.
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


def optical_pair(candidate,current):
    """Accept only a measured pair tied to both actual physical SHA values."""
    if not isinstance(candidate,dict) or not isinstance(current,dict):
        return None
    q=candidate.get('visual_quality')
    if not isinstance(q,dict):return None
    sha=candidate.get('sha256','')
    old=current.get('sha256','')
    if (not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{64}',sha)
            or not isinstance(old,str) or not re.fullmatch(r'[0-9a-f]{64}',old)):
        return None
    if (q.get('method')!='paired-decoded-pixel-v1'
            or q.get('candidate_sha256')!=sha or q.get('compared_to_sha256')!=old
            or q.get('same_photo_verified') is not True
            or q.get('confidence')!='measured'):
        return None
    relation=q.get('relation')
    return relation if relation in ('higher','lower','comparable') else None


def replacement_reason(candidate,current):
    """Only choose replacements when the *same image* has stronger pixels."""
    if not isinstance(candidate,dict) or not isinstance(current,dict):return None
    if candidate.get('ai_enhanced') and not current.get('ai_enhanced'):return None
    if candidate.get('sha256')==current.get('sha256'):return None
    forward=optical_pair(candidate,current)
    reverse=optical_pair(current,candidate)
    if forward=='lower' or reverse=='higher':return None
    if forward=='higher' or reverse=='lower':
        return 'measured_higher_optical_detail'
    if forward=='comparable' or reverse=='comparable':
        if watermark_status(candidate)=='absent' and watermark_status(current)!='absent':
            return 'comparable_verified_without_site_watermark'
    return None
