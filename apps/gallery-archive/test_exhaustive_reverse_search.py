"""Proof that every owned SHA is searched before any photo is repeated."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_exhaustive_reverse_search as m


def photo(model, album, number):
    return {
        'model': model, 'album_id': album, 'album_title': album,
        'photo_sha256': f'{number:064x}',
        'public_image_url': f'https://example.org/gallery/{album}/{number}.jpg',
        'seed_kind': 'static-public',
        'owner_saved_count': 3,
        'union_saved_count': 3,
    }


def fixtures():
    rows = []
    for album, count in (('album-a', 21), ('album-b', 3), ('album-c', 5),
                         ('album-only-static', 2)):
        rows.extend(photo('mimmi', album, i + 1) for i in range(count))
    rows.extend(photo('yui', 'yui-album', n + 1) for n in range(11))
    return rows


def search_fake(seed):
    return {**seed, 'search_status': {'yandex_sites': 'leads_0'},
            'candidate_pages': [], 'off_model_rejected': 0,
            'originals_stored': 0, 'visible_gallery_added': 0}


class FullReverseCoverageTests(unittest.TestCase):
    def test_union_covers_all_images_and_deduplicates_sha_only_within_album(self):
        rows = fixtures()
        queue = m.complete_queue(rows, 'mimmi')
        self.assertEqual(len(queue), 31)
        self.assertEqual(len({p['seed_id'] for p in queue}), len(queue))
        self.assertEqual({p['album_id'] for p in queue},
                         {'album-a','album-b','album-c','album-only-static'})
        self.assertEqual(len(m.complete_queue(rows, 'yui')), 11)
        self.assertEqual(len(m.complete_queue(rows + [rows[0]], 'mimmi')), 31)

    def test_no_repeated_images_until_all_31_are_searched(self):
        queue = m.complete_queue(fixtures(), 'mimmi')
        state = {'attempted_ids': [], 'cycle': 0}
        seen = set()
        for i in range(7):
            batch, cycle = m.plan_batch(queue, state, 5)
            self.assertEqual(cycle, 0)
            new = {p['seed_id'] for p in batch}
            self.assertFalse(seen & new, 'repeated before full coverage')
            seen.update(new)
            state['attempted_ids'] = list(seen)
        self.assertEqual(len(seen), 31)
        self.assertEqual(state['cycle'], 0)
        next_batch, next_cycle = m.plan_batch(queue, state, 5)
        self.assertEqual(next_cycle, 1)
        self.assertEqual(len(next_batch), 5)

    def test_runner_persists_every_attempt_and_auto_advances_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous, output, next_state = (root/p for p in ('prior.json', 'found.json', 'next.json'))
            with patch.object(m, 'seeds', return_value=fixtures()), patch.object(m, 'search_one', side_effect=search_fake):
                for _ in range(4):
                    result = m.run('mimmi', previous, output, next_state,
                                   budget=10, seconds=60, workers=2)
                    self.assertTrue(result['research_only'])
                    self.assertEqual(result['model_matched_photo_frames'], 0)
                    self.assertEqual(result['name_supported_source_frames_unverified_visual'], 0)
                    self.assertEqual(result['verified_same_photo_matches'], 0)
                    self.assertTrue(result['coverage']['attempted_is_not_verified_match'])
                    self.assertEqual(result['readable_html_without_name_supported_source'],
                                     len(result['results']))
                    self.assertEqual(result['photo_frames_with_zero_model_matches'], len(result['results']))
                    self.assertEqual(result['search_engine_outcomes']['yandex_sites']['leads_0'],len(result['results']))
                    self.assertEqual(result['total_seed_frames'], 31)
                    self.assertEqual(result['seed_queries'], len(result['results']))
                    previous.write_text(next_state.read_text())
                state = json.loads(previous.read_text())
                self.assertEqual(len(state['attempted_ids']), 31)
                self.assertEqual(state['cycle'], 0)
                # Fifth call begins a new cycle only after the 31st image.
                fifth=m.run('mimmi', previous, output, next_state,
                            budget=10, seconds=60, workers=2)
                self.assertEqual(fifth['coverage']['cycle'], 1)
                self.assertEqual(fifth['coverage']['attempted_this_cycle'], 10)

    def test_new_sha_is_added_to_pending_without_destroying_checkpoint(self):
        queue=m.complete_queue(fixtures(), 'mimmi')
        ids={p['seed_id'] for p in queue}
        state={'attempted_ids':[p['seed_id'] for p in queue], 'cycle': 4}
        new=photo('mimmi', 'album-b', 9999)
        extended=m.complete_queue(fixtures()+[new], 'mimmi')
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'state.json'
            path.write_text(json.dumps({'schema_version':1, 'model':'mimmi',
                                         'cycle':4,'attempted_ids':state['attempted_ids']}))
            restored=m.read_progress(path, 'mimmi', {p['seed_id'] for p in extended})
            chosen,cycle=m.plan_batch(extended,restored,10)
            self.assertEqual(cycle,4)
            self.assertEqual(len(chosen),1)
            self.assertEqual(chosen[0]['photo_sha256'], new['photo_sha256'])

    def test_new_search_revision_rechecks_old_done_shas_once_then_resumes(self):
        queue=m.complete_queue(fixtures(), 'mimmi')
        legacy={'schema_version':1,'model':'mimmi','cycle':0,
                'attempted_ids':[p['seed_id'] for p in queue],
                'last_cycle_size':len(queue),'last_run_attempts':0}
        with tempfile.TemporaryDirectory() as t:
            checkpoint=Path(t)/'prior.json'
            checkpoint.write_text(json.dumps(legacy))
            repaired=m.read_progress(checkpoint,'mimmi',
                                     {p['seed_id'] for p in queue},
                                     required_revision=2)
            self.assertEqual(repaired['search_revision'],2)
            self.assertEqual(repaired['attempted_ids'],[])
            batch,_=m.plan_batch(queue,repaired,10,stop_after_full=True)
            self.assertEqual(len(batch),10)
            # The second batch must continue rather than resetting again.
            repaired['attempted_ids']=[p['seed_id'] for p in batch]
            checkpoint.write_text(json.dumps(repaired))
            resumed=m.read_progress(checkpoint,'mimmi',
                                    {p['seed_id'] for p in queue},
                                    required_revision=2)
            self.assertEqual(resumed['attempted_ids'],repaired['attempted_ids'])
            next_batch,_=m.plan_batch(queue,resumed,10,stop_after_full=True)
            self.assertEqual(len(next_batch),10)
            self.assertFalse({x['seed_id'] for x in batch}&
                             {x['seed_id'] for x in next_batch})
            with self.assertRaisesRegex(ValueError,'SEARCH_REVISION_ROLLBACK'):
                m.read_progress(checkpoint,'mimmi',
                                {p['seed_id'] for p in queue},
                                required_revision=1)

    def test_first_full_pass_does_not_restart_in_multimodel_campaign(self):
        queue=m.complete_queue(fixtures(), 'yui')
        state={'attempted_ids':[p['seed_id'] for p in queue], 'cycle':0}
        pending, cycle=m.plan_batch(queue,state,256,stop_after_full=True)
        self.assertEqual(pending,[])
        self.assertEqual(cycle,0)
        repeat, cycle=m.plan_batch(queue,state,256,stop_after_full=False)
        self.assertEqual(len(repeat),len(queue))
        self.assertEqual(cycle,1)

    def test_wrong_model_and_corrupt_state_abort(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'progress.json'
            path.write_text(json.dumps({'schema_version':1, 'model':'yui',
                                        'cycle':0, 'attempted_ids':[]}))
            with self.assertRaisesRegex(ValueError,'CHECKPOINT_SCHEMA'):
                m.read_progress(path,'mimmi',set())
            with self.assertRaisesRegex(ValueError,'INVALID_MODEL'):
                m.complete_queue(fixtures(),'other')


if __name__=='__main__':
    unittest.main()
