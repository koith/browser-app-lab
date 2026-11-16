"""No-network safety gate for broad, two-model physical image collection."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from run_full_public_acquisition import (work_batches, PRIORITY, replay, execute,
    MAX_REGISTERED_PAGES_PER_WORK, MAX_CHROMIUM_WEAK_PAGES_PER_BATCH)

ROOT=Path(__file__).resolve().parents[2]


class FullAcquisitionTests(unittest.TestCase):
    def test_every_registered_work_is_visited_once(self):
        for model in PRIORITY:
            original=json.loads((ROOT/f'apps/{model}-gallery/public-work-pages.json').read_text())
            known=[a['id'] for a in original['albums']]
            for number in (1,2,17,101):
                batches=work_batches(model,number,ROOT,7)
                seen=[aid for batch in batches for aid in batch]
                self.assertEqual(set(seen),set(known))
                self.assertEqual(len(seen),len(known))
                self.assertEqual(seen[:len(PRIORITY[model])],list(PRIORITY[model]))

    def test_rotation_changes_secondary_work_order_without_losing_any(self):
        for model in PRIORITY:
            first=work_batches(model,1,ROOT,7)
            second=work_batches(model,2,ROOT,7)
            self.assertEqual(first[0],second[0])
            self.assertNotEqual(first[1:],second[1:])

    def test_no_replay_without_immutable_on_disk_stage_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('run_full_public_acquisition.replay', wraps=replay):
                for model in PRIORITY:
                    self.assertEqual(replay(model,Path(temporary),1,1000000),0)

    def test_secondary_batch_visits_all_four_registered_pages_not_three(self):
        # A real Mimmi edition has four verified sources. The old secondary
        # batch page cap=3 silently skipped one source in each invocation.
        self.assertEqual(MAX_REGISTERED_PAGES_PER_WORK, 5)
        with tempfile.TemporaryDirectory() as temporary:
            args=SimpleNamespace(model='mimmi',run_number=1,
                stage=Path(temporary),source_evidence=None,batch_size=7,
                max_per_batch=48,bytes_per_batch=36000000,
                batch_timeout=60,alternate_priority=False,plan_only=False)
            with patch('run_full_public_acquisition.subprocess.run',
                       return_value=SimpleNamespace(returncode=1)) as command:
                self.assertEqual(execute(args),2)
            calls=[call.args[0] for call in command.call_args_list]
            self.assertGreater(len(calls),1)
            for index,invocation in enumerate(calls):
                with self.subTest(batch=index):
                    self.assertEqual(
                        invocation[invocation.index('--max-pages')+1],'5')

    def test_alternative_parsers_and_browser_apply_to_every_work_batch(self):
        # Previously every batch except the first one silently lost Scrapy
        # and Chromium image recovery despite having verified source pages.
        self.assertEqual(MAX_CHROMIUM_WEAK_PAGES_PER_BATCH,2)
        with tempfile.TemporaryDirectory() as temporary:
            for model in PRIORITY:
                args=SimpleNamespace(model=model,run_number=1,
                    stage=Path(temporary)/model,source_evidence=None,
                    batch_size=7,max_per_batch=48,bytes_per_batch=36000000,
                    batch_timeout=60,alternate_priority=True,plan_only=False)
                with patch('run_full_public_acquisition.subprocess.run',
                           return_value=SimpleNamespace(returncode=1)) as command:
                    self.assertEqual(execute(args),2)
                calls=[call.args[0] for call in command.call_args_list]
                self.assertGreater(len(calls),1)
                for index,invocation in enumerate(calls):
                    with self.subTest(model=model,batch=index):
                        self.assertIn('--alternative-engines',invocation)
                        self.assertIn('--reviewed-source-only',invocation)
                        self.assertEqual(
                            invocation[invocation.index('--render-budget')+1],'2')
                        self.assertEqual(
                            invocation[invocation.index('--max-pages')+1],'5')

    def test_one_timed_out_batch_does_not_abort_other_album_batches(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary)/'stage'
            args=SimpleNamespace(model='mimmi',run_number=1,
                stage=stage,source_evidence=None,batch_size=7,
                max_per_batch=48,bytes_per_batch=36000000,
                batch_timeout=60,alternate_priority=False,plan_only=False)
            attempts=[]
            collector_calls=[]
            def fake_run(command,**kwargs):
                attempts.append(command)
                if command[1].endswith('direct_photo_pipeline.py'):
                    collector_calls.append(command)
                    if len(collector_calls)==2:
                        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
                    root=Path(command[command.index('--out')+1])/'metadata'
                    root.mkdir(parents=True,exist_ok=True)
                    (root/'catalog.json').write_text('{"albums":[]}')
                else:
                    root=Path(command[command.index('--stage')+1])/'metadata'
                    (root/'pages-publication.json').write_text(json.dumps({
                        'new_sha_verified_originals':0,'total_bytes_added':0}))
                return SimpleNamespace(returncode=0)
            with patch('run_full_public_acquisition.subprocess.run',
                       side_effect=fake_run):
                self.assertEqual(execute(args),0)
            doc=json.loads((stage/'full-collection-summary.json').read_text())
            self.assertEqual(doc['timed_out_batches'],[1])
            self.assertFalse(doc['collection_complete_without_batch_timeouts'])
            self.assertEqual(doc['state'],'LOCAL_STAGED_PARTIAL_INCOMPLETE_BATCHES')
            self.assertFalse(doc['collection_all_batches_success'])
            self.assertEqual(doc['incomplete_batch_count'],1)
            self.assertEqual(doc['registered_works_scheduled'],43)
            self.assertEqual(doc['registered_works_visited'],
                             43-len(doc['batches'][1]['works']))
            self.assertEqual(doc['registered_work_ids_in_incomplete_batches'],
                             doc['batches'][1]['works'])
            self.assertGreater(len(attempts),2)
            self.assertEqual(doc['batches'][1]['collector_returncode'],124)
            self.assertEqual(doc['batches'][1]['collection_error'],'collector_timeout')

    def test_success_exit_without_finalized_catalog_is_not_photo_acquisition(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary)
            args=SimpleNamespace(model='yui',run_number=1,
                stage=stage,source_evidence=None,batch_size=7,
                max_per_batch=48,bytes_per_batch=36000000,
                batch_timeout=60,alternate_priority=False,plan_only=False)
            with patch('run_full_public_acquisition.subprocess.run',
                       return_value=SimpleNamespace(returncode=0)):
                self.assertEqual(execute(args),2)
            audit=json.loads((stage/'full-collection-summary.json').read_text())
            self.assertEqual(audit['registered_works_visited'],0)
            self.assertFalse(audit['collection_all_batches_success'])
            self.assertEqual(audit['incomplete_batch_count'],len(audit['batches']))
            self.assertTrue(all(x.get('collection_error')=='missing_finalized_stage_catalog'
                                for x in audit['batches']))

    def test_replay_skips_catalogs_from_timed_out_or_unpublished_batches(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary)
            for name in ('batch-00','batch-01','batch-02'):
                folder=stage/name/'metadata'
                folder.mkdir(parents=True)
                (folder/'catalog.json').write_text('{"albums":[]}')
            (stage/'full-collection-summary.json').write_text(json.dumps({
                'model':'mimmi','batches':[
                    {'batch':0,'collector_returncode':124,'collection_error':'collector_timeout'},
                    {'batch':1,'collector_returncode':0,'publisher_returncode':0},
                    {'batch':2,'collector_returncode':0,'publisher_returncode':1}]}))
            with patch('publish_new_public_photos_to_pages.publish',
                       return_value={'new_sha_verified_originals':3}) as publishing:
                self.assertEqual(replay('mimmi',stage,48,36000000),3)
                self.assertEqual(publishing.call_count,1)
                self.assertEqual(publishing.call_args.args[1].name,'batch-01')

    def test_replay_rejects_unverified_catalog_if_summary_was_lost(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage=Path(temporary)
            folder=stage/'batch-00/metadata'
            folder.mkdir(parents=True)
            (folder/'catalog.json').write_text('{"albums":[]}')
            with self.assertRaisesRegex(ValueError,'UNVERIFIED_COLLECTION_STAGE'):
                replay('mimmi',stage,48,36000000)

    def test_all_priority_ids_have_explicit_work_source_scope(self):
        for model,ids in PRIORITY.items():
            data=json.loads((ROOT/f'apps/{model}-gallery/public-work-pages.json').read_text())
            reg={a['id']:a for a in data['albums']}
            for aid in ids:
                with self.subTest(model=model,id=aid):
                    self.assertIn(aid,reg)
                    self.assertTrue(reg[aid].get('source','').startswith('https://'))


if __name__=='__main__':
    unittest.main()
