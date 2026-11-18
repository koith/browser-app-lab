#!/usr/bin/env python3
"""Do not drop existing owner editions from actual reviewed photo collection."""
import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from direct_photo_pipeline import collect, merge_owner_census_sources


PAGE='https://public-gallery.example.org/yui-summer-edition/'
ASSET='https://cdn.public-gallery.example.org/yui-summer-edition/001.jpg'
WORK='summer-edition-yui'


def jpg(rgb):
    out=BytesIO()
    # Real photo validation correctly rejects flat-color placeholder JPEGs.
    # The regression fixture must have actual pixel contrast and detail.
    textured=Image.effect_noise((1280,1920),60).convert('RGB')
    Image.blend(textured,Image.new('RGB',(1280,1920),rgb),0.25).save(
        out,'JPEG',quality=93)
    return out.getvalue()


class ActualOwnerSourceCoverage(unittest.TestCase):
    def test_existing_owner_work_in_registered_book_retains_source_proof(self):
        owner={'albums':[{'id':WORK,'title':'Yui Sim Summer Edition','images':[]}]}
        books={WORK:{'id':WORK,'title':'Yui Sim Summer Edition',
                     'source':PAGE,'source_pages':[],
                     'curated_images_only':False}}
        rows=[{'model':'yui','kind':'work','id':WORK,
               'urls':[PAGE],'manifest_sources':['owner-index.json']}]
        info=merge_owner_census_sources(books,owner,rows,'yui')
        self.assertEqual(info['census_eligible_work_count'],1)
        self.assertTrue(books[WORK]['census_existing_owner'])
        self.assertEqual(books[WORK]['source'],PAGE)

    def test_public_article_in_existing_owner_work_yields_real_image_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/'apps/gallery-archive'
            archive.mkdir(parents=True)
            (archive/'global_source_registry.json').write_text('{"sources":[]}')
            base=root/'apps/yui-gallery'
            base.mkdir()
            (base/'public-work-pages.json').write_text(json.dumps({
                'albums':[{'id':WORK,'title':'Yui Sim Summer Edition',
                           'source':PAGE}]}))
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            old=jpg((80,50,30))
            new=jpg((140,90,50))
            owner={'model':'yui','schema_version':1,'albums':[{
                'id':WORK,'title':'Yui Sim Summer Edition',
                'images':[{'number':1,'sha256':hashlib.sha256(old).hexdigest()}]}]}
            article=(f'<html><h1>Yui Sim Summer Edition</h1><article>'
                     f'<img src="{ASSET}"></article></html>').encode()
            class Client:
                blocked_origins=set()
                def get(self,url):
                    if url==PAGE:return type('R',(),{'content':article})()
                    if url==ASSET:return type('R',(),{'content':new})()
                    raise AssertionError('Unexpected public URL '+url)
            rows=[{'model':'yui','kind':'work','id':WORK,'urls':[PAGE],
                   'manifest_sources':['public-work-pages.json']}]
            with patch('collector_full_census.census',return_value={'targets':rows}),patch(
                    'direct_photo_pipeline.page_images',
                    return_value=([] ,[], 'no_public_photos')):
                report=collect(root,'yui',owner,root/'stage',
                               max_new=4,max_pages=8,client=Client(),
                               reviewed_source_only=True,alternative_engines=False)
            self.assertEqual(report['owner_census_source_coverage']['reviewed_storage_scope_works'],1)
            self.assertEqual(report['new_local_individual_files'],1,report)
            result=report['results'][0]
            self.assertEqual(result['id'],WORK)
            self.assertEqual(result['pages'],1)
            staged=json.loads((root/'stage/metadata/catalog.json').read_text())
            image=staged['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/image['key']).read_bytes(),new)


if __name__=='__main__':
    unittest.main()
