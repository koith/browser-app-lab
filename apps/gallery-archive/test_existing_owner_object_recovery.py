"""A metadata courier grants no original-write or failed-byte admission."""
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from direct_photo_pipeline import inspect
from test_direct_photo_pipeline import photo
from verify_sealed_existing_work import restore_work


class ExistingObjectRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.raw=photo(140);self.meta,self.preview,_=inspect(self.raw)
        aid='saved-work';self.aid=aid
        self.owner={'schema_version':1,'model':'mimmi','albums':[{'id':aid,'images':[
            {'number':n,'sha256':str(n)*64} for n in (1,2,3)]}]}
        self.row={**self.meta,'extension':self.meta['extension'],'preview_sha256':'9'*64,
            'preview_bytes':1000,'preview_width':400,'preview_height':600,
            'source_photo_number':4,'work_identity_saved_cut_anchors':3}
        self.album={'id':aid,'images':[self.row],'source_coverage':{
            'source':'https://example.invalid/reviewed-work','known_web_edition_photos':4,
            'observed_filename_numbers':[1,2,3,4],'source_files_decoded':4,
            'source_edition_all_files_accounted_for':True,'unresolved_source_numbers':[],
            'uncertain_source_numbers':[],'saved_cut_correspondence':[
                {'owner_sha256':str(n)*64} for n in (1,2,3)]}}
        self.original='originals/'+aid+'/'+self.meta['sha256']+'.jpg'

    def test_existing_original_is_read_only_and_missing_preview_is_independently_verified(self):
        remote={self.original:self.raw};writes=[];queued=[]
        def read(args,**kwargs):return remote.get(args[1].split('archive:MimmiArchive/',1)[1])
        def put(args):
            self.assertEqual(args[0],'copyto');target=args[2].split('archive:MimmiArchive/',1)[1]
            self.assertTrue(target.startswith('previews/'+self.aid+'/'))
            remote[target]=Path(args[1]).read_bytes();writes.append(target);return 0
        def persist(stage,remote_name):queued.append(stage)
        with tempfile.TemporaryDirectory() as directory,patch('verify_sealed_existing_work.storage',side_effect=read),\
                patch('verify_sealed_existing_work.storage_write',side_effect=put),\
                patch('verify_sealed_existing_work.persist',side_effect=persist):
            self.assertEqual(restore_work(self.album,self.owner,Path(directory)),1)
        self.assertEqual(len(writes),1);self.assertEqual(len(queued),1)
        self.assertEqual(remote[self.original],self.raw)

    def test_bad_original_or_provider_verification_cannot_trigger_preview_writes_or_a_queue(self):
        for bad in [b'changed bytes',b'{"errno":400141,"errmsg":"private-provider-value"}']:
            with self.subTest(body=bad[:10]),tempfile.TemporaryDirectory() as directory,\
                    patch('verify_sealed_existing_work.storage',return_value=bad),\
                    patch('verify_sealed_existing_work.storage_write') as put,\
                    patch('verify_sealed_existing_work.persist') as persist:
                with self.assertRaises(ValueError):restore_work(self.album,self.owner,Path(directory))
                put.assert_not_called();persist.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
