"""Actual decoded-pixel photo-pair ranking; never use megapixels/bytes alone."""
import hashlib
from io import BytesIO
import unittest
from PIL import Image, ImageDraw, ImageFilter
from photo_quality_evidence import inspect_pair, preferred_pair

def encoded(im, quality=92):
    result=BytesIO()
    im.save(result,format='JPEG',quality=quality)
    return result.getvalue()

def scene():
    im=Image.new('RGB',(900,1350),'#777777')
    d=ImageDraw.Draw(im)
    for i in range(130):
        x=(i*91)%900;y=(i*37)%1350;r=9+(i*3)%55
        d.ellipse((x-r,y-r,x+r,y+r),fill=((i*31)%256,(i*17)%256,(i*67)%256))
    return im

class OpticalEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        im=scene()
        cls.sharp=encoded(im,quality=93)
        cls.blurred=encoded(im.filter(ImageFilter.GaussianBlur(2)),quality=94)
        small=im.resize((250,375),Image.Resampling.LANCZOS)
        cls.small=encoded(small,quality=92)
        cls.fake4k=encoded(small.resize((1000,1500),Image.Resampling.BICUBIC),quality=95)
        cls.oldsha=hashlib.sha256(cls.sharp).hexdigest()

    def test_better_watermarked_image_wins_over_blurry_watermark_free(self):
        winner,evidence=preferred_pair(self.blurred,self.sharp,
            hashlib.sha256(self.blurred).hexdigest(),
            old_watermark_status='absent_verified',
            new_watermark_status='present_verified')
        self.assertTrue(winner,evidence)
        self.assertEqual(evidence['relation'],'higher')
        reverse,details=preferred_pair(self.sharp,self.blurred,self.oldsha,
            old_watermark_status='present_verified',
            new_watermark_status='absent_verified')
        self.assertFalse(reverse,details)
        self.assertEqual(details['relation'],'lower')

    def test_upsized_pixels_without_optical_detail_do_not_win(self):
        better,evidence=preferred_pair(self.small,self.fake4k,
            hashlib.sha256(self.small).hexdigest())
        self.assertFalse(better,evidence)
        self.assertNotEqual(evidence['relation'],'higher',evidence)

    def test_clean_only_wins_when_actual_visual_quality_is_comparable(self):
        sha=self.oldsha
        winner,evidence=preferred_pair(self.sharp,self.sharp,sha,
            old_watermark_status='present_verified',
            new_watermark_status='absent_verified')
        self.assertTrue(winner,evidence)
        self.assertEqual(evidence['relation'],'comparable')
        unknown,_=preferred_pair(self.sharp,self.sharp,sha,
            old_watermark_status='present_verified',
            new_watermark_status='unknown')
        self.assertFalse(unknown,'Unknown watermark state must not masquerade as clean')

    def test_byte_bound_evidence_rejects_stale_hash(self):
        evidence=inspect_pair(self.sharp,self.blurred,'0'*64)
        self.assertFalse(evidence['same_photo_verified'])
        self.assertEqual(evidence['reason'],'previous_bytes_sha256_mismatch')
        claimed=inspect_pair(self.sharp,self.sharp,self.oldsha)
        self.assertEqual(claimed['candidate_sha256'],
                         hashlib.sha256(self.sharp).hexdigest())
        winner,_=preferred_pair(self.sharp,self.blurred,'0'*64)
        self.assertFalse(winner)

    def test_unrelated_photo_rejected(self):
        replacement=encoded(Image.new('RGB',(900,1350),'#eecc00'),quality=95)
        result=inspect_pair(self.sharp,replacement,self.oldsha)
        self.assertFalse(result['same_photo_verified'])

if __name__=='__main__':
    unittest.main(verbosity=2)
