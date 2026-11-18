#!/usr/bin/env python3
"""Both gallery models resume actual incomplete editions, without skipping the rest."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run_full_public_acquisition import (
    unresolved_first, work_batches, record_failure_checkpoint,
    MAX_URGENT_INCOMPLETE_PER_RUN
)


class DurableIncompleteRecovery(unittest.TestCase):
    def test_checkpoint_written_from_real_collection_summary_and_idempotent(self):
        for model in ('mimmi','yui'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp)
                stage=base/'stage'
                stage.mkdir()
                report={
                    'model':model,'registered_works_scheduled':4,
                    'registered_work_ids_in_incomplete_batches':[
                        'work-b','work-a','work-b'
                    ]
                }
                (stage/'full-collection-summary.json').write_text(json.dumps(report))
                self.assertEqual(record_failure_checkpoint(model,stage,base),2)
                check=base/'apps/gallery-archive/verification'/f'incomplete-{model}.json'
                raw=check.read_bytes()
                self.assertEqual(json.loads(raw)['unresolved_work_ids'],['work-a','work-b'])
                self.assertEqual(record_failure_checkpoint(model,stage,base),2)
                self.assertEqual(check.read_bytes(),raw)
                with self.assertRaisesRegex(ValueError,'UNSUPPORTED_CHECKPOINT'):
                    record_failure_checkpoint('other',stage,base)

    def test_work_batches_resume_unfinished_individually_but_visit_every_work(self):
        for model in ('mimmi','yui'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                gallery=root/'apps'/f'{model}-gallery'
                gallery.mkdir(parents=True)
                labels=[f'work-{i:02d}' for i in range(12)]
                (gallery/'public-work-pages.json').write_text(json.dumps({
                    'albums':[{'id':name,'source':'https://example.org/'+name}
                              for name in labels]}))
                verification=root/'apps/gallery-archive/verification'
                verification.mkdir(parents=True)
                (verification/f'incomplete-{model}.json').write_text(json.dumps({
                    'schema_version':1,'model':model,
                    'unresolved_work_ids':labels[2:10]}))
                with patch('official_sample_supply.exhausted_official_samples',
                           return_value=set()):
                    first=work_batches(model,1,root,7)
                    second=work_batches(model,2,root,7)
                self.assertEqual(first[:6],[[w] for w in labels[2:8]])
                self.assertEqual(second[:6],[[labels[8]],[labels[9]],
                                                   [labels[2]],[labels[3]],
                                                   [labels[4]],[labels[5]]])
                self.assertEqual({aid for group in first for aid in group},set(labels))
                self.assertEqual({aid for group in second for aid in group},set(labels))
                self.assertEqual(sum(map(len,first)),len(labels))
                self.assertLessEqual(len(first),len(labels))
                self.assertEqual(MAX_URGENT_INCOMPLETE_PER_RUN,6)

    def test_corrupt_checkpoint_does_not_skip_healthy_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dest=root/'apps/gallery-archive/verification'
            dest.mkdir(parents=True)
            (dest/'incomplete-mimmi.json').write_text('bad JSON')
            self.assertEqual(unresolved_first('mimmi',1,root,['work-a','work-b']),
                             ([],['work-a','work-b']))
            (dest/'incomplete-mimmi.json').write_text(json.dumps({
                'schema_version':1,'model':'yui',
                'unresolved_work_ids':['work-b']}))
            self.assertEqual(unresolved_first('mimmi',1,root,['work-a','work-b']),
                             ([],['work-a','work-b']))

    def test_reject_malicious_or_cross_model_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=root/'stage'
            stage.mkdir()
            file=stage/'full-collection-summary.json'
            for pending in [['../escape'],['work', 'a%20b'],[None]]:
                file.write_text(json.dumps({
                    'model':'yui','registered_works_scheduled':2,
                    'registered_work_ids_in_incomplete_batches':pending}))
                with self.assertRaisesRegex(ValueError,
                        'INVALID_WORK_IDS'):
                    record_failure_checkpoint('yui',stage,root)
            file.write_text(json.dumps({
                'model':'mimmi','registered_works_scheduled':2,
                'registered_work_ids_in_incomplete_batches':[]}))
            with self.assertRaisesRegex(ValueError,'CHECKPOINT_INVALID'):
                record_failure_checkpoint('yui',stage,root)


if __name__=='__main__':
    unittest.main()
