"""Offline regression: SHA-distinct encodings of one image are NOT new cuts."""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tempfile
from unittest.mock import patch
from PIL import Image, ImageDraw
from photo_visual_dedupe import WorkVisualIndex


def encoded(image, format, **options):
    b=BytesIO()
    image.save(b,format=format,**options)
    return b.getvalue()


def main():
    with tempfile.TemporaryDirectory() as temp:
        base=Path(temp)
        aid='photo-work'
        p=base/'stored-albums'/aid/'existing.png'
        p.parent.mkdir(parents=True)
        frame=Image.new('RGB',(320,480),(120,165,188))
        d=ImageDraw.Draw(frame)
        d.ellipse((30,30,290,300),fill=(201,60,131))
        d.rectangle((100,250,170,445),fill=(30,42,80))
        old=encoded(frame,'PNG')
        p.write_bytes(old)
        record={'id':aid,'images':[{'number':1,'url':f'stored-albums/{aid}/existing.png',
                                    'sha256':sha256(old).hexdigest()}]}
        index=WorkVisualIndex(base,record)
        assert index.reference_missing==index.reference_corrupt==0
        assert len(index.entries)==1
        recompressed=encoded(frame,'JPEG',quality=96,subsampling=0)
        assert sha256(recompressed).hexdigest()!=sha256(old).hexdigest()
        duplicate=index.classify(recompressed)
        assert duplicate and duplicate['existing_number']==1, duplicate
        assert not duplicate['needs_replacement_transaction'], duplicate
        unrelated=Image.new('RGB',(320,480),(20,35,65))
        d=ImageDraw.Draw(unrelated)
        d.rectangle((20,50,300,380),fill=(238,200,60))
        candidate=encoded(unrelated,'PNG')
        assert index.classify(candidate) is None
        new={'number':2,'url':f'stored-albums/{aid}/new.png',
             'sha256':sha256(candidate).hexdigest()}
        (base/new['url']).write_bytes(candidate)
        index.remember(new,candidate)
        assert index.classify(encoded(unrelated,'JPEG',quality=96,subsampling=0))
        with patch('photo_visual_dedupe.scan_image',
                   side_effect=ValueError('oversize_image')):
            assert index.classify(b'oversize') is None
            index.remember(new,b'oversize')
    print('GALLERY_VISUAL_DUPLICATE_PROTECTION_SHA_CHANGED_SAME_CUT_REJECTED_PASS')


if __name__=='__main__':
    main()
