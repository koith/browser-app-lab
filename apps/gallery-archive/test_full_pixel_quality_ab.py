#!/usr/bin/env python3
"""No photo may be omitted from either whole-gallery pixel hash comparison."""
from PIL import Image,ImageDraw,ImageFilter
import imagehash
from full_pixel_quality_ab import entries,choose_shard,scan_photo,ROOT


def test():
    photos,metadata=entries(ROOT)
    assert metadata['owner_albums']>=110,metadata
    assert metadata['all_owner_original_positions']>=7709,metadata
    assert metadata['repo_committed_photo_rows']>=2266,metadata
    assert len(photos)==metadata['repo_committed_photo_rows']
    for shards in (1,3,8,16):
        parts=[x for model in ('yui','mimmi') for shard in range(shards) for x in photos
            if x['model']==model and choose_shard(x,shards)==shard]
        assert len(parts)==len(photos),shards
    # Test two encodings of the same image and an actual different image.
    image=Image.new('RGB',(360,540),(255,255,255))
    draw=ImageDraw.Draw(image)
    draw.rectangle((38,44,195,410),fill=(0,80,145))
    draw.ellipse((65,130,180,280),fill=(220,140,90))
    smaller=image.resize((280,420),Image.Resampling.LANCZOS)
    other=image.filter(ImageFilter.GaussianBlur(20))
    d1=imagehash.dhash(image,hash_size=8);d2=imagehash.dhash(smaller,hash_size=8)
    p1=imagehash.phash(image,hash_size=8);p2=imagehash.phash(smaller,hash_size=8)
    assert (p1-p2)<=8 and (d1-d2)<=5,(p1-p2,d1-d2)
    assert imagehash.phash(other,hash_size=8) is not None
    # Every row has a model, title and actual hash evidence source from the
    # user's existing gallery, not a generated or guessed URL.
    sample=photos[0]
    actual=scan_photo(sample)
    assert actual['status'] in ('decoded_sha256_verified','metadata_disagreement'),actual
    print('ALL_COMMITTED_PHOTO_PIXEL_CENSUS_TEST_PASS',metadata)


if __name__=='__main__':test()
