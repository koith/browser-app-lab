#!/usr/bin/env python3
from io import BytesIO
from pathlib import Path
import tempfile
from PIL import Image,ImageDraw
from perceptual_duplicate_audit import scan_stage,scan_image,candidate_relation


def blob(width=300,height=450,seed=0,quality=95):
    im=Image.new('RGB',(width,height),'white')
    d=ImageDraw.Draw(im)
    d.rectangle((65+seed,30,210+seed,360),fill=(45,95,170))
    d.ellipse((85+seed,65,180+seed,190),fill=(230,170,120))
    d.line((5,20,200,200),fill=(0,0,0),width=5)
    out=BytesIO();im.save(out,format='JPEG',quality=quality)
    return out.getvalue()


def test():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);(root/'originals/first').mkdir(parents=True)
        (root/'originals/second').mkdir(parents=True)
        raw=blob()
        (root/'originals/first/1.jpg').write_bytes(raw)
        (root/'originals/second/2.jpg').write_bytes(raw)
        resized=Image.open(BytesIO(raw)).resize((600,900),Image.Resampling.LANCZOS)
        out=BytesIO();resized.save(out,format='JPEG',quality=80)
        (root/'originals/first/3.jpg').write_bytes(out.getvalue())
        (root/'originals/second/4.jpg').write_bytes(blob(seed=100))
        result=scan_stage(root)
        kinds=[p['type'] for p in result['review_pairs']]
        assert result['files_scanned']==4,result
        assert 'same_sha256' in kinds,kinds
        assert 'perceptually_similar_review' in kinds,kinds
        assert any(p['cross_work_review'] for p in result['review_pairs'])
        assert result['mode']=='evidence_only_no_gallery_mutation'
        assert len(list((root/'originals').rglob('*.jpg')))==4
        assert candidate_relation(scan_image(raw),scan_image(out.getvalue()))[0]=='perceptually_similar_review'
        try:scan_stage(root,max_files=2)
        except ValueError:pass
        else:raise AssertionError('Unbounded scan must reject')
        assert scan_stage(root/'no-stage')['files_scanned']==0
    print('PHOTO_PERCEPTUAL_AUDIT_OFFLINE_PASS')


if __name__=='__main__':test()
