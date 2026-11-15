"""No-network safety gate for broad, two-model physical image collection."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from run_full_public_acquisition import work_batches, PRIORITY, replay, execute, MAX_REGISTERED_PAGES_PER_WORK

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
