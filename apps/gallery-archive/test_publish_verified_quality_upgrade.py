#!/usr/bin/env python3
"""Real original bytes, immutable history and an unchanged gallery slot are
required when a proven sharper same-frame rendition replaces a low-quality one.
Separate optical and perceptual tests exercise the actual comparators.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
from publish_new_public_photos_to_pages import publish


def photo(path, quality):
    im=Image.new('RGB',(540,810),(80,100,120))
    draw=ImageDraw.Draw(im)
    for x in range(0,540,65):
        draw.rectangle((x,0,x+18,810),fill=(140,170,60))
    for y in range(0,810,90):
        draw.ellipse((65,y,340,y+76),fill=(210,50,75))
    im.save(path,format='JPEG',quality=quality)
    return path.read_bytes()


def fixture(tmp, model):
    root=Path(tmp)
    base=root/'apps'/f'{model}-gallery'
    aid='public-edition'
    old_path=base/'stored-albums'/aid/'original-low.jpg'
    old_path.parent.mkdir(parents=True)
    old=photo(old_path,quality=25)
    old_sha=hashlib.sha256(old).hexdigest()
    record={'number':5,'url':f'stored-albums/{aid}/original-low.jpg',
            'sha256':old_sha,'bytes':len(old),'width':540,'height':810,
            'quality':'legacy_low_quality','watermark_status':'unknown'}
    (base/'owner-index.json').write_text(json.dumps({
        'schema_version':1,'model':model,'albums':[]}))
    (base/'stored-albums.json').write_text(json.dumps({
        'albums':[{'id':aid,'title':'Public edition','images':[record]}]}))
    (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
        'id':aid,'title':'Public edition',
        'source':f'https://public-images.example.org/{model}/work'}]}))
    stage=root/'stage'
    staged=stage/'originals'/aid/'new.jpg'
    staged.parent.mkdir(parents=True)
    new=photo(staged,quality=97)
    new_sha=hashlib.sha256(new).hexdigest()
    (stage/'metadata').mkdir()
    (stage/'metadata/catalog.json').write_text(json.dumps({
        'model':model,'albums':[{'id':aid,'images':[{
            'number':5,'key':str(staged.relative_to(stage)),
            'sha256':new_sha,'bytes':len(new),
            'width':540,'height':810,
            'source_url':f'https://public-images.example.org/{model}/new.jpg'
        }]}]}))
    classification={
        'existing_number':5,'existing_sha256':old_sha,
        'new_sha256':new_sha,'needs_replacement_transaction':True,
        'quality_relation':'higher','visual_comparison':'strict_same_cut_reencode'}
    return root,base,stage,old,new,record,classification


class VerifiedUpgradeTransaction(unittest.TestCase):
    def test_both_models_preserve_originals_and_gallery_number(self):
        for model in ('mimmi','yui'):
            with self.subTest(model=model),tempfile.TemporaryDirectory() as tmp:
                root,base,stage,old,new,old_record,match=fixture(tmp,model)
                verified={'same_photo_verified':True,'relation':'higher',
                          'compared_to_sha256':old_record['sha256'],
                          'candidate_sha256':hashlib.sha256(new).hexdigest(),
                          'method':'paired-decoded-pixel-v1'}
                with patch('publish_new_public_photos_to_pages.WorkVisualIndex.classify',
                           return_value=match),patch(
                           'photo_quality_evidence.preferred_pair',
                           return_value=(True,verified)):
                    first=publish(model,stage,root=root)
                    self.assertEqual(first['new_sha_verified_originals'],0,first)
                    self.assertEqual(first['higher_visual_quality_replacements'],1,first)
                    second=publish(model,stage,root=root)
                    self.assertEqual(second['higher_visual_quality_replacements'],0)
                albums=json.loads((base/'stored-albums.json').read_text())['albums']
                self.assertEqual(len(albums),1)
                self.assertEqual(len(albums[0]['images']),1)
                row=albums[0]['images'][0]
                self.assertEqual(row['number'],5)
                self.assertEqual(row['sha256'],hashlib.sha256(new).hexdigest())
                self.assertEqual((base/row['url']).read_bytes(),new)
                self.assertEqual((base/old_record['url']).read_bytes(),old)
                self.assertEqual(row['previous_versions'][0]['sha256'],
                                 old_record['sha256'])
                self.assertEqual(row['previous_versions'][0]['url'],
                                 old_record['url'])
                self.assertEqual(row['quality_upgrade_evidence']['relation'],'higher')

    def test_uncertain_improvement_cannot_overwrite_existing_photo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,stage,old,new,old_record,match=fixture(tmp,'yui')
            with patch('publish_new_public_photos_to_pages.WorkVisualIndex.classify',
                       return_value=match),patch(
                       'photo_quality_evidence.preferred_pair',
                       return_value=(False,{'same_photo_verified':False,'relation':'uncertain'})):
                doc=publish('yui',stage,root=root)
            self.assertEqual(doc['new_sha_verified_originals'],0)
            self.assertEqual(doc['higher_visual_quality_replacements'],0)
            self.assertEqual(doc['quality_upgrades_held_for_verified_replacement'],1)
            row=json.loads((base/'stored-albums.json').read_text())['albums'][0]['images'][0]
            self.assertEqual(row['sha256'],old_record['sha256'])
            self.assertEqual((base/old_record['url']).read_bytes(),old)

    def test_corrupted_original_stops_upgrade_without_destroying_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base,stage,old,new,old_record,match=fixture(tmp,'mimmi')
            (base/old_record['url']).write_bytes(b'corrupted-local-history')
            with patch('publish_new_public_photos_to_pages.WorkVisualIndex.classify',
                       return_value=match):
                with self.assertRaisesRegex(ValueError,
                        'quality_upgrade_original_sha_readback_failed'):
                    publish('mimmi',stage,root=root)
            row=json.loads((base/'stored-albums.json').read_text())['albums'][0]['images'][0]
            self.assertEqual(row['sha256'],old_record['sha256'])


if __name__=='__main__':
    unittest.main()
