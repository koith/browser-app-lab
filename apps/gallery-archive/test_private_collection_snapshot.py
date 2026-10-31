"""Failed storage must retain private provenance without admitting any image."""
import json
import unittest
from unittest.mock import patch

import test_deferred_verified_batch as fixtures
import private_collection_snapshot as recovery
from load_pending_individual import load


class PrivateSnapshotTests(unittest.TestCase):
    setUp=fixtures.DeferredBatchTests.setUp
    write=fixtures.DeferredBatchTests.write
    def test_private_journal_exact_readback_is_not_a_verified_queue(self):
        audit=json.loads((self.stage/'metadata/collection-audit.json').read_text());audit['model']='mimmi'
        self.write('collection-audit.json',audit)
        raw,count=recovery.snapshot(self.stage,'mimmi')
        data=json.loads(raw)
        self.assertEqual(count,1);self.assertEqual(data['state'],recovery.STATE)
        self.assertFalse(data['remote_media_verified']);self.assertFalse(data['pending_admission_queue'])
        self.assertEqual(data['catalog']['albums'][0]['images'][0]['source_photo_number'],27)
        with patch.object(recovery,'run',return_value=0) as upload,patch.object(recovery,'storage',return_value=raw):
            self.assertEqual(recovery.persist(self.stage,'mimmi','archive:MimmiArchive','41184365364-1'),1)
        target=upload.call_args.args[0][2]
        self.assertIn('/metadata/unverified-collection-staging/',target)
        self.assertNotIn('pending-individual',target);self.assertNotIn('/metadata/catalog.json',target)
        with self.assertRaises(ValueError):load(self.owner,[('a'*64+'.json',data)],'mimmi')

    def test_wrong_remote_corrupt_file_and_failed_journal_readback_cannot_start_transfer(self):
        audit=json.loads((self.stage/'metadata/collection-audit.json').read_text());audit['model']='mimmi'
        self.write('collection-audit.json',audit)
        with patch.object(recovery,'run') as upload:
            with self.assertRaises(ValueError):recovery.persist(self.stage,'mimmi','https://other.example','1-1')
            upload.assert_not_called()
        with patch.object(recovery,'run',return_value=0),patch.object(recovery,'storage',return_value=b'{"errno":400141}'):
            with self.assertRaisesRegex(ValueError,'exact readback'):recovery.persist(self.stage,'mimmi','archive:MimmiArchive','1-1')
        (self.stage/self.photo['key']).write_bytes(b'corrupt')
        with patch.object(recovery,'run') as upload:
            with self.assertRaises(ValueError):recovery.persist(self.stage,'mimmi','archive:MimmiArchive','1-1')
            upload.assert_not_called()


if __name__=='__main__':
    import unittest
    unittest.main(verbosity=2)
