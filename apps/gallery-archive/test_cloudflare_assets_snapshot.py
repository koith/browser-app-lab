from email.message import EmailMessage
from contextlib import redirect_stdout
import hashlib
import os
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
from PIL import Image
from cloudflare_assets_snapshot import Snapshot, KIND, checked
from deploy_cloudflare_assets import existing_catalogs, free_account_and_existing, write_deploy_sources, CF, subdomain, bootstrap_missing_worker
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

    def test_exhaustive_owner_reads_preserve_exact_bytes_with_bounded_batch_and_limit(self):
        # Simulate twelve distinct slots from an exact owner manifest. The
        # authenticated download stub never changes the target's SHA.
        base = self.root / 'apps/mimmi-gallery'
        original = {**PHOTO, 'key': 'originals/known-album/0001.jpg'}
        photos = [{**original, 'number': i,
                   'key': f'originals/known-album/{i:04d}.jpg'}
                  for i in range(1, 13)]
        catalog = {'model': 'mimmi', 'schema_version': 1,
                   'albums': [{'id': 'known-album', 'images': photos}]}
        (base / 'owner-index.json').write_text(json.dumps(catalog))

        def authenticated_original(remote, key, target, env):
            assert key.startswith('originals/known-album/')
            assert env.get('RCLONE_CONFIG_ARCHIVE_TYPE') == 'terabox'
            target.write_bytes(RAW)
            return True, None

        with (
            patch.dict(os.environ, {'MIMMI_TERABOX_NDUS': 'fixture-owner-cookie'}),
            patch('restore_known_owner_cache.verified_owner_catalog', return_value=(None, catalog)),
            patch('restore_known_owner_cache.cookie_header', return_value='fixture'),
            patch('qa_existing_owner_exact_file.read_existing', side_effect=authenticated_original),
        ):
            snapshot = Snapshot(self.root, self.root / 'exhaustive-replica')
            complete = snapshot.existing_owner('mimmi', maximum=0)
            self.assertEqual(complete['added'], 12)
            self.assertEqual(complete['remaining_metadata_rows'], 0)
            self.assertFalse(complete['failures'])
            self.assertEqual(len(snapshot.finish()['mimmi']['albums'][0]['images']), 12)
            for row in snapshot.finish()['mimmi']['albums'][0]['images']:
                self.assertEqual((self.root / 'exhaustive-replica' / 'mimmi' / row['key']).read_bytes(), RAW)
            limited = Snapshot(self.root, self.root / 'limited-replica')
            count = limited.existing_owner('mimmi', maximum=3)
            self.assertEqual(count['added'], 3)
            self.assertEqual(count['remaining_metadata_rows'], 9)

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
        self.assertFalse(config['workers_dev'])
        self.assertFalse(config['preview_urls'])
        self.assertEqual(config['assets']['not_found_handling'], 'none')
        for banned in ('r2_buckets', 'kv_namespaces', 'durable_objects', 'SIGNING_KEY', 'CLOUDFLARE_API_TOKEN'):
            self.assertNotIn(banned, json.dumps(config))
        self.assertTrue((source / 'private-yui-catalog.txt').exists())

    def test_control_api_rejects_billing_mutation_and_arbitrary_paths_before_network(self):
        cf = CF('dummy-token', 'a' * 32)
        for path in ('subscriptions', '../outside', 'r2/buckets'):
            with self.assertRaises(ValueError): cf.call(path, 'PUT', {})

    def test_content_readback_uses_official_get_v2_and_rejects_write_only_content_route(self):
        cf = CF('dummy-token', 'a' * 32)
        with self.assertRaisesRegex(ValueError, 'UNAPPROVED_CF_CONTROL_CALL'):
            cf.call('workers/scripts/gallery-archive-free/content', raw=True)
        class Response:
            headers = {'Content-Type': 'multipart/form-data; boundary=one'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return b'private multipart source'
        with patch.object(cf.opener, 'open', return_value=Response()) as request:
            mime, raw = cf.call('workers/scripts/gallery-archive-free/content/v2', raw=True)
        self.assertTrue(request.call_args.args[0].full_url.endswith('/content/v2'))
        self.assertEqual(request.call_args.args[0].get_method(), 'GET')
        self.assertEqual(raw, b'private multipart source')

    def test_missing_subdomain_does_not_register_or_prevent_unrouted_upload(self):
        class Missing:
            def call(self, path):
                self.asserted_path = path
                raise ProbeError('CF_GET_WORKERS_SUBDOMAIN', 404)
        cf = Missing()
        self.assertIsNone(subdomain(cf))
        self.assertEqual(cf.asserted_path, 'workers/subdomain')

    def test_direct_upload_bootstrap_is_independent_of_assets_and_routing_and_read_back(self):
        class Direct:
            calls = []
            def call(self, tail, method='GET', body=None, multipart=None, raw=False):
                self.calls.append((tail, method))
                if tail == 'workers/workers' and method == 'POST':
                    assert body['name'] == 'gallery-archive-free'
                    return {'result': {'name': body['name'], 'id': 'b' * 32}}
                if tail == 'workers/scripts/gallery-archive-free' and method == 'PUT':
                    self.multipart = multipart
                    return {'success': True}
                assert tail == 'workers/scripts/gallery-archive-free/content/v2' and raw
                return self.multipart
        cf = Direct()
        with patch('deploy_cloudflare_assets.free_account_and_existing', return_value=None):
            catalog = bootstrap_missing_worker(cf, 'a' * 40)
        self.assertTrue(all(not c['albums'] for c in catalog.values()))
        self.assertEqual(cf.calls, [('workers/workers', 'POST'),
                                   ('workers/scripts/gallery-archive-free', 'PUT'),
                                   ('workers/scripts/gallery-archive-free/content/v2', 'GET')])
        for forbidden in (b'ARCHIVE_ASSETS', b'SIGNING_KEY', b'workers_dev', b'r2_buckets'):
            self.assertNotIn(forbidden, cf.multipart[1])

    def test_bootstrap_never_overwrites_an_existing_replica_and_rejects_unverified_readback(self):
        cf = CF('dummy-token', 'a' * 32)
        with patch('deploy_cloudflare_assets.free_account_and_existing', return_value={'mimmi': {}, 'yui': {}}):
            with self.assertRaisesRegex(ValueError, 'REFUSES_EXISTING'):
                bootstrap_missing_worker(cf, 'b' * 40)
        with self.assertRaises(ValueError):
            cf.call('workers/scripts/gallery-archive-free', 'PUT', {})
        with self.assertRaises(ValueError):
            cf.call('workers/subdomain', 'PUT', multipart=('text/plain', b'bad'))

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

    def test_null_provider_code_access_denial_and_html_challenge_are_not_conflated(self):
        for raw, headers, category, shape in (
            (json.dumps({'errors': [{'code': None, 'message': 'No access to the specified resource.'}]}).encode(),
             {}, 'RESOURCE_ACCESS_DENIED', 'json'),
            (b'<html>Blocked PRIVATE_ACCOUNT_AND_TOKEN</html>', {'cf-mitigated': 'challenge'},
             'EDGE_OR_CHALLENGE_REJECTED_NOT_PERMISSION_PROOF', 'html')):
            cf = CF('PRIVATE_ACCOUNT_AND_TOKEN', 'a' * 32)
            error = HTTPError('https://private.invalid', 403, 'private', headers, io.BytesIO(raw))
            output = io.StringIO()
            with patch.object(cf.opener, 'open', side_effect=error), redirect_stdout(output):
                with self.assertRaises(ProbeError):
                    cf.call('workers/workers', 'POST', {'name': 'gallery-archive-free'})
            self.assertIn(category, output.getvalue())
            self.assertIn('"body_format": "' + shape + '"', output.getvalue())
            self.assertNotIn('PRIVATE_ACCOUNT_AND_TOKEN', output.getvalue())


if __name__ == '__main__': unittest.main()
