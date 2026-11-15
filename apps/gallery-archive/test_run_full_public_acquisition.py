"""No-network safety gate for broad, two-model physical image collection."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from run_full_public_acquisition import work_batches, PRIORITY, replay

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
