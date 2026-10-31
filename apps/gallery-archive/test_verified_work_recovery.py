"""A failed photo cannot admit its work or discard another work's exact proof."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_deferred_verified_batch as fixtures
from defer_verified_batch import verified_queue
import recover_verified_work_batches as recovery
import verify_terabox


class VerifiedWorkRecoveryTests(unittest.TestCase):
    setUp=fixtures.DeferredBatchTests.setUp
    write=fixtures.DeferredBatchTests.write

    def failed_batch(self):
        good=copy.deepcopy(self.photo)
        for field,digest,extension,prefix in [('key','sha256','jpg','originals'),
                ('preview','preview_sha256','webp','previews')]:
            target=f'{prefix}/saved-work/{good[digest]}.{extension}'
            source=self.stage/good[field];dest=self.stage/target;source.rename(dest);good[field]=target
        bad={**good,'key':good['key'].replace('/saved-work/','/failed-work/'),
             'preview':good['preview'].replace('/saved-work/','/failed-work/')}
        for field in ('key','preview'):
            path=self.stage/bad[field];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((self.stage/good[field]).read_bytes())
        self.owner['albums'].append({'id':'failed-work','title':'Failed','images':[{'number':10,'sha256':'b'*64}]})
        self.write('catalog.json',{'schema_version':1,'model':'mimmi','albums':[
            {'id':'saved-work','images':[good]},{'id':'failed-work','images':[bad]}]})
        self.write('collection-audit.json',{'model':'mimmi','results':[{'id':aid,
            'source_edition_all_files_accounted_for':True,'known_web_edition_photos':27,
            'source_files_decoded':27,'unresolved_source_numbers':[],'saved_reference_anchors':10}
            for aid in ('saved-work','failed-work')]})
        def read(row,remote):
            if row[0]==bad['key']:raise ValueError('Owner provider response instead of image: errno=400141')
            return row[0]
        with patch.object(verify_terabox,'read_remote_with_recovery',side_effect=read):
            with self.assertRaisesRegex(ValueError,'failed full byte verification'):
                verify_terabox.verify(self.stage,'archive:MimmiArchive',2,only_staged=True)
        return good,bad

    def test_whole_successful_work_survives_other_failure_without_publishing_or_masking_it(self):
        good,bad=self.failed_batch()
        original_catalog=(self.stage/'metadata/catalog.json').read_bytes();proof=json.loads((self.stage/'metadata/remote-verification.json').read_text())
        self.assertEqual((proof['media_checked'],proof['full_SHA256_verified'],proof['failed']),(4,3,1))
        self.assertNotIn('verified_specs_sha256',proof)
        self.assertNotIn('verified_specs_sha256',proof['work_verification']['failed-work'])
        accepted=[]
        def persist(stage,remote):
            _,raw=verified_queue(stage);accepted.append(json.loads(raw))
        with patch.object(recovery,'persist',side_effect=persist):
            self.assertEqual(recovery.recover(self.stage,self.owner,'archive:MimmiArchive'),1)
        self.assertEqual([a['id'] for d in accepted for a in d['albums']],['saved-work'])
        self.assertEqual(accepted[0]['albums'][0]['images'][0]['sha256'],good['sha256'])
        self.assertEqual((self.stage/good['key']).read_bytes(),self.original_bytes)
        self.assertEqual((self.stage/'metadata/catalog.json').read_bytes(),original_catalog)
        self.assertEqual(json.loads((self.stage/'metadata/remote-verification.json').read_text())['failed'],1)

    def test_changed_proof_and_one_missing_local_pair_do_not_enter_any_queue(self):
        good,_=self.failed_batch();path=self.stage/'metadata/remote-verification.json';proof=json.loads(path.read_text())
        altered=copy.deepcopy(proof);altered['work_verification']['saved-work']['verified_specs_sha256']='0'*64
        path.write_text(json.dumps(altered))
        with patch.object(recovery,'persist') as persist:
            with self.assertRaisesRegex(ValueError,'differs from staged'):recovery.recover(self.stage,self.owner,'archive:MimmiArchive')
            persist.assert_not_called()
        path.write_text(json.dumps(proof));(self.stage/good['preview']).unlink()
        with patch.object(recovery,'persist') as persist:
            with self.assertRaisesRegex(ValueError,'every exact local'):recovery.recover(self.stage,self.owner,'archive:MimmiArchive')
            persist.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
