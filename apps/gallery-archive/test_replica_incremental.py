"""Regression tests: no photo byte reads needed for unchanged deployed SHA inventory."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from replica_incremental import inventory_delta, local_owner_inventory
from cloudflare_assets_snapshot import KIND

PHOTO = {
    'number': 1, 'sha256': 'a' * 64, 'bytes': 1200,
    'width': 800, 'height': 600,
}
ALBUM = 'known-album'


def existing():
    return {model: {'schema_version': 1, 'model': model,
                    'archive_kind': KIND,
                    'albums': [{'id': ALBUM, 'images': [
                        {**PHOTO, 'key': f'originals/{ALBUM}/0001_{"a" * 64}.jpg'}]}]}
            for model in ('mimmi', 'yui')}


def owners():
    return {model: {(ALBUM, 1): dict(PHOTO)} for model in ('mimmi', 'yui')}


class IncrementalReplicaTests(unittest.TestCase):
    def test_same_sha_inventory_zero_reads_and_zero_deploy_needed(self):
        missing, retained = inventory_delta(existing(), owners())
        self.assertEqual(retained, {'mimmi': 1, 'yui': 1})
        self.assertEqual(missing, {'mimmi': {}, 'yui': {}})

    def test_only_new_photo_requires_work(self):
        own = owners()
        own['yui'][(ALBUM, 2)] = {**PHOTO, 'number': 2, 'sha256': 'b'*64}
        missing, retained = inventory_delta(existing(), own)
        self.assertEqual(retained, {'mimmi': 1, 'yui': 1})
        self.assertEqual(list(missing['yui']), [(ALBUM, 2)])
        self.assertFalse(missing['mimmi'])

    def test_existing_photo_sha_change_fails_closed(self):
        own = owners()
        own['mimmi'][(ALBUM, 1)]['sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'REFUSE_TO_REPLACE'):
            inventory_delta(existing(), own)

    def test_existing_photo_removal_fails_closed(self):
        own = owners()
        own['yui'].clear()
        with self.assertRaisesRegex(ValueError, 'REFUSE_TO_DROP'):
            inventory_delta(existing(), own)

    def test_duplicate_existing_photo_fails_closed(self):
        old = existing()
        old['mimmi']['albums'][0]['images'].append(
            copy.deepcopy(old['mimmi']['albums'][0]['images'][0]))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            inventory_delta(old, owners())

    def test_unsafe_original_key_fails_closed(self):
        old = existing()
        old['yui']['albums'][0]['images'][0]['key'] = 'originals/../bad.jpg'
        with self.assertRaisesRegex(ValueError, 'KEY_INVALID'):
            inventory_delta(old, owners())

    def test_local_owner_inventory_and_duplicate_check(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for model in ('mimmi', 'yui'):
                base = root / 'apps' / (model + '-gallery')
                base.mkdir(parents=True)
                (base / 'owner-index.json').write_text(
                    json.dumps({'model': model, 'albums': [
                        {'id': ALBUM, 'images': [PHOTO]}]}))
            self.assertEqual(local_owner_inventory(root), owners())
            (root / 'apps/yui-gallery/owner-index.json').write_text(
                json.dumps({'model': 'yui', 'albums': [
                    {'id': ALBUM, 'images': [PHOTO, PHOTO]}]}))
            with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
                local_owner_inventory(root)


if __name__ == '__main__':
    unittest.main()
