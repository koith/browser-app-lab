import unittest
from g05_registered_batches import BASELINE, plan

class RegisteredBatchTests(unittest.TestCase):
    def registry(self):
        return ([{'id': i, 'source': 'https://showartx.net/work/'} for i in sorted(BASELINE)] +
                [{'id': 'new-yui-'+str(i), 'source': 'https://showartx.net/new/'} for i in range(7)] +
                [{'id': 'official-yui-'+str(i), 'source': 'https://djawaphoto.com/portfolio/yui/'} for i in range(11)])

    def test_expanded_twenty_work_registry_and_all_independent_sources_survive_once(self):
        rows = self.registry(); batches = plan(rows)
        self.assertEqual([len(b['ids']) for b in batches], [8, 8, 4, 8, 3])
        self.assertEqual(len({b['stage'] for b in batches}), 5)
        ids = [i for b in batches for i in b['ids']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {r['id'] for r in rows})
        self.assertNotEqual(batches[2]['stage'], batches[3]['stage'])

    def test_growth_does_not_allow_lost_or_duplicated_baseline_works(self):
        for rows in (self.registry()[1:], self.registry()+[self.registry()[0]]):
            with self.assertRaisesRegex(ValueError, 'BASELINE_WORK'):
                plan(rows)

    def test_independent_baseline_and_per_batch_limits_stay_enforced(self):
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_SOURCE'):
            plan(self.registry()[:23])
        with self.assertRaisesRegex(ValueError, 'BATCH_BOUND'):
            plan(self.registry(), 100)

if __name__ == '__main__': unittest.main()
