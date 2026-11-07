from email.message import EmailMessage
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
from PIL import Image
from cloudflare_assets_snapshot import Snapshot, KIND, checked
from deploy_cloudflare_assets import existing_catalogs, free_account_and_existing, write_deploy_sources, CF
from check_cloudflare_connection import ProbeError

ROOT = Path(__file__).resolve().parents[2]
RAW = (ROOT / 'apps/yui-gallery/stored-albums/v04/001_bd8318cfe6e0.jpg').read_bytes()
with Image.open(io.BytesIO(RAW)) as im:
    WIDTH, HEIGHT = im.size
PHOTO = {'number': 1, 'sha256': hashlib.sha256(RAW).hexdigest(), 'bytes': len(RAW), 'width': WIDTH, 'height': HEIGHT}


class SnapshotChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for model in ('mimmi', 'yui'):
            base = self.root / f'apps/{model}-gallery'
            (base / 'stored-albums/known-album').mkdir(parents=True)
            (base / 'stored-albums/known-album/one.jpg').write_bytes(RAW)
            (base / 'owner-index.json').write_text(json.dumps({'model': model, 'albums': [{'id': 'known-album', 'images': [PHOTO]}]}))
            (base / 'stored-albums.json').write_text(json.dumps({'albums': [{'id': 'known-album', 'images': [{**PHOTO, 'url': 'stored-albums/known-album/one.jpg'}]}]}))
        self.snapshot = Snapshot(self.root, self.root / 'replica')

    def tearDown(self): self.temp.cleanup()

    def test_actual_original_is_copied_without_recompression_or_metadata_count_substitution(self):
        self.assertEqual(self.snapshot.public_originals(), {'mimmi': 1, 'yui': 1})
        catalogs = self.snapshot.finish()
        for model in ('mimmi', 'yui'):
            p = catalogs[model]['albums'][0]['images'][0]
            self.assertEqual((self.root / 'replica' / model / p['key']).read_bytes(), RAW)
            self.assertEqual(catalogs[model]['archive_kind'], KIND)
        self.assertEqual(self.snapshot.public_originals(), {'mimmi': 0, 'yui': 0})

    def test_wrong_sha_dimensions_and_foreign_owner_rows_fail_closed(self):
        for photo in ({**PHOTO, 'sha256': 'f' * 64}, {**PHOTO, 'width': WIDTH + 1}):
            with self.assertRaises(ValueError): checked(photo, RAW)
        with self.assertRaises(ValueError): self.snapshot.add('yui', {'id': 'foreign-album'}, PHOTO, RAW, 'test')
        self.assertFalse(any((self.root / 'replica').rglob('*.jpg')))

    def test_free_file_budget_cannot_be_silently_exceeded(self):
        with patch('cloudflare_assets_snapshot.MAX_FILES', 4):
            with self.assertRaises(ValueError): self.snapshot.public_originals()

    def test_control_plane_restores_both_private_text_catalogs_and_refuses_unknown_worker(self):
        self.snapshot.public_originals(); catalogs = self.snapshot.finish()
        message = EmailMessage(); message.make_mixed()
        for model in ('mimmi', 'yui'):
            part = EmailMessage(); part.set_content(json.dumps(catalogs[model]), subtype='plain')
            part['Content-Disposition'] = 'form-data; name="hashed-private-' + model + '-catalog.txt"'
            message.attach(part)
        raw = message.as_bytes(); _, body = raw.split(b'\n\n', 1)
        restored = existing_catalogs(message['Content-Type'], body)
        self.assertEqual(restored, catalogs)
        with self.assertRaises(ValueError): existing_catalogs('application/javascript', b'unknown owner code')

    def test_paid_or_incomplete_billing_probe_cannot_create_resources(self):
        class Existing:
            def call(self, name):
                assert name == 'subscriptions'
                return {'result': [{'price': 5}], 'result_info': {'total_count': 1}}
        with self.assertRaises(ValueError): free_account_and_existing(Existing())
        class Incomplete:
            def call(self, name): return {'result': [], 'result_info': {'total_count': 1}}
        with self.assertRaises(ValueError): free_account_and_existing(Incomplete())

    def test_generated_runtime_keeps_all_raw_assets_behind_worker_and_has_no_billed_binding(self):
        self.snapshot.public_originals()
        source = self.root / 'source'
        write_deploy_sources(source, self.root / 'replica', self.snapshot.finish(), 'a' * 32, 'b' * 40)
        config = json.loads((source / 'wrangler.json').read_text())
        self.assertTrue(config['assets']['run_worker_first'])
        self.assertEqual(config['assets']['not_found_handling'], 'none')
        for banned in ('r2_buckets', 'kv_namespaces', 'durable_objects', 'SIGNING_KEY', 'CLOUDFLARE_API_TOKEN'):
            self.assertNotIn(banned, json.dumps(config))
        self.assertTrue((source / 'private-yui-catalog.txt').exists())

    def test_control_api_rejects_billing_mutation_and_arbitrary_paths_before_network(self):
        cf = CF('dummy-token', 'a' * 32)
        for path in ('subscriptions', '../outside', 'r2/buckets'):
            with self.assertRaises(ValueError): cf.call(path, 'PUT', {})

    def test_denial_reports_exact_operation_without_upstream_secret_or_account_details(self):
        secret = 'PRIVATE_DO_NOT_PRINT_TOKEN'
        cf = CF(secret, 'a' * 32)
        raw = json.dumps({'errors': [{'code': 10000, 'message': 'Authentication error ' + secret}]}).encode()
        error = HTTPError('https://private.example/' + secret, 403, secret, {}, io.BytesIO(raw))
        output = io.StringIO()
        with patch.object(cf.opener, 'open', side_effect=error), redirect_stdout(output):
            with self.assertRaises(ProbeError) as caught:
                cf.call('workers/subdomain', 'PUT', {'subdomain': 'private-account-subdomain'})
        text = output.getvalue()
        self.assertEqual(caught.exception.phase, 'CF_PUT_WORKERS_SUBDOMAIN')
        self.assertIn('10000', text)
        self.assertIn('TOKEN_PERMISSION_OR_AUTH_REQUIRED', text)
        for private in (secret, 'a' * 32, 'private-account-subdomain'):
            self.assertNotIn(private, text)


if __name__ == '__main__': unittest.main()
