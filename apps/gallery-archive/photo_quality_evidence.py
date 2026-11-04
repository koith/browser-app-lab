"""Conservative actual-pixel comparison of two VERIFIED images of one photo.

A sharpness proxy is not a universal blind IQA model. Inspect decoded pixels at
the same displayed scale; suppress single-pixel noise, compare fine detail per
contrast and never declare improvement on pixel dimensions or JPEG bytes alone.
A photo with different content/crop must NOT be compared or overwritten.
"""
import hashlib
from io import BytesIO
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat


def _decoded(raw):
    with Image.open(BytesIO(raw)) as im:
        im.load()
        return ImageOps.exif_transpose(im).convert('RGB')


def _detail(image):
    gray=ImageOps.grayscale(image)
    # Common display scale preserves meaningful differences between a blurry
    # upscale and a natively sharp image. Crop edges to avoid corner stamps.
    width,height=gray.size
    gray=gray.resize((max(32,round(960*width/max(width,height))),
                      max(32,round(960*height/max(width,height)))),Image.Resampling.LANCZOS)
    w,h=gray.size
    gray=gray.crop((int(.08*w),int(.08*h),int(.92*w),int(.92*h)))
    contrast=ImageStat.Stat(gray).stddev[0]
    denoised=gray.filter(ImageFilter.MedianFilter(3))
    fine=ImageStat.Stat(ImageChops.difference(
        denoised,denoised.filter(ImageFilter.GaussianBlur(1.1)))).mean[0]
    spurious=ImageStat.Stat(ImageChops.difference(gray,denoised)).mean[0]
    return round(max(0.0,(fine-0.25*spurious)/(contrast+4.0)),7)


def inspect_pair(previous_raw,candidate_raw,previous_sha):
    """Return visual evidence; only for same source photo proven by caller."""
    real_previous_sha=hashlib.sha256(previous_raw).hexdigest()
    real_candidate_sha=hashlib.sha256(candidate_raw).hexdigest()
    if real_previous_sha!=previous_sha:
        return {'method':'paired-decoded-pixel-v1',
                'confidence':'unverified','relation':'uncertain',
                'same_photo_verified':False,
                'reason':'previous_bytes_sha256_mismatch'}
    a,b=_decoded(previous_raw),_decoded(candidate_raw)
    if abs(a.width/a.height-b.width/b.height)>0.012:
        return {'method':'paired-decoded-pixel-v1','confidence':'unverified',
                'relation':'uncertain','same_photo_verified':False}
    small_a=a.resize((64,64),Image.Resampling.LANCZOS)
    small_b=b.resize((64,64),Image.Resampling.LANCZOS)
    drift=max(ImageStat.Stat(ImageChops.difference(small_a,small_b)).mean)
    if drift>5.0:
        return {'method':'paired-decoded-pixel-v1','confidence':'unverified',
                'relation':'uncertain','same_photo_verified':False}
    before,after=_detail(a),_detail(b)
    if max(before,after)<0.001:
        relation='uncertain'
    elif after>before*1.18 and after-before>0.0008:
        relation='higher'
    elif before>after*1.18 and before-after>0.0008:
        relation='lower'
    elif min(before,after)>0.001 and max(before,after)/min(before,after)<1.08:
        relation='comparable'
    else:
        relation='uncertain'
    return {'method':'paired-decoded-pixel-v1','confidence':'measured',
            'candidate_sha256':real_candidate_sha,
            'same_photo_verified':True,'compared_to_sha256':previous_sha,
            'relation':relation,'previous_detail':before,'candidate_detail':after,
            'comparison':'same_display_scale_center_detail_noise_suppressed_v1',
            'limitations':'heuristic sharpness only; inspect fine textures, compression, oversharpening and watermarks before trusting replacement'}


def preferred_pair(previous_raw,candidate_raw,previous_sha,
                   old_watermark_status='unknown',new_watermark_status='unknown'):
    evidence=inspect_pair(previous_raw,candidate_raw,previous_sha)
    if not evidence.get('same_photo_verified'):return False,evidence
    if evidence['relation']=='higher':return True,evidence
    if evidence['relation']=='comparable':
        return old_watermark_status=='present_verified' and new_watermark_status=='absent_verified',evidence
    return False,evidence
