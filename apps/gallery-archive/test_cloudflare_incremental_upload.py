"""Fail-closed Cloudflare delta manifest tests: no old photo read or reupload."""
import base64
import hashlib
import io
from PIL import Image
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cloudflare_assets_snapshot import KIND, Snapshot
from cloudflare_incremental_upload import (
    asset_hash, build_manifest, deployed_version, multipart, rollback_to, upload_incremental
)

VERSION = '11111111-2222-3333-4444-555555555555'
def jpeg(color):
    buf = io.BytesIO()
    Image.new('RGB', (12, 10), color).save(buf, format='JPEG')
    return buf.getvalue()

SRC = jpeg('blue')
OLD = jpeg('red')


def photo(n, raw, model):
    suffix = 'jpg'
    sha = hashlib.sha256(raw).hexdigest()
    return {'number': n, 'sha256': sha, 'bytes': len(raw),
            'width': 12, 'height': 10,
            'key': f'originals/known-album/{n:04d}_{sha}.{suffix}',
            'asset_hash': asset_hash(raw, suffix)}


def catalog(m, include_new=False):
    rows = [photo(1, OLD, m)]
    if include_new and m == 'yui':
        rows.append(photo(2, SRC, m))
    return {'archive_kind': KIND, 'schema_version': 1,
            'model': m, 'albums': [{'id': 'known-album', 'images': rows}]}


class FakeCF:
    def __init__(self, requested=None):
        self.account = 'a'*32
        self.calls = []
        self.requested = requested
    def call(self, tail, method='GET', body=None, multipart=None):
        self.calls.append((tail, method))
        if tail.endswith('/deployments') and method == 'GET':
            return {'result': {'deployments': [{'versions': [
                {'version_id': VERSION, 'percentage': 100}]}]}}
        if tail.endswith('/assets-upload-session'):
            manifest = body['manifest']
            assert len(manifest) == 3  # old mimmi, old yui, new yui
            hashes = self.requested if self.requested is not None else [asset_hash(SRC, 'jpg')]
            return {'result': {'jwt': 'fake-session-jwt', 'buckets': [hashes]}}
        if tail == 'workers/scripts/gallery-archive-free' and method == 'PUT':
            mime, raw = multipart
            assert 'multipart/form-data' in mime
            assert b'\\r\\n' not in raw
            assert b'\r\n' in raw
            assert b'keep_bindings' in raw
            assert b'ARCHIVE_ASSETS' in raw
            assert b'fake-completion-jwt' in raw
            return {'result': {}}
        if tail.endswith('/deployments') and method == 'POST':
            assert body['versions'][0]['version_id'] == VERSION
            return {'result': {'id': 'ok'}}
        raise AssertionError('unexpected Cloudflare operation ' + tail)


class IncrementalAssetUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / 'assets'
        self.src = self.root / 'source'
        self.src.mkdir()
        self.catalogs = {m: catalog(m, True) for m in ('mimmi', 'yui')}
        new = self.catalogs['yui']['albums'][0]['images'][1]
        f = self.assets / 'yui' / new['key']
        f.parent.mkdir(parents=True)
        f.write_bytes(SRC)
        (self.src / 'wrangler.json').write_text(
            json.dumps({'vars': {'ARCHIVE_RELEASE': 'f'*40}}))
        for name in ('entry.mjs','worker.mjs','private-s3.mjs','bound-assets.mjs',
                     'private-mimmi-catalog.txt','private-yui-catalog.txt'):
            (self.src / name).write_text('export default {};')

    def tearDown(self):
        self.temp.cleanup()

    def test_provider_hash_matches_documented_base64_plus_extension(self):
        expected = hashlib.sha256(base64.b64encode(SRC) + b'jpg').hexdigest()[:32]
        self.assertEqual(asset_hash(SRC, 'jpg'), expected)

    def test_manifest_retains_old_paths_without_local_old_files(self):
        manifest, new_only = build_manifest(self.catalogs, self.assets)
        self.assertEqual(len(manifest), 3)
        self.assertEqual(set(new_only), {asset_hash(SRC,'jpg')})
        self.assertIn('/mimmi/' + photo(1, OLD, 'mimmi')['key'], manifest)
        self.assertFalse((self.assets / 'mimmi').exists())

    def test_only_new_file_is_uploaded_and_all_old_paths_remain(self):
        cf = FakeCF()
        with patch('cloudflare_incremental_upload._upload_bucket', return_value='fake-completion-jwt') as upload:
            previous = upload_incremental(cf, self.src, self.assets, self.catalogs)
        self.assertEqual(previous, VERSION)
        upload.assert_called_once()
        self.assertEqual(upload.call_args.args[2], [asset_hash(SRC,'jpg')])
        self.assertIn(('workers/scripts/gallery-archive-free', 'PUT'), cf.calls)

    def test_remote_requests_old_bytes_fails_before_any_script_deployment(self):
        cf = FakeCF([asset_hash(OLD, 'jpg')])
        with self.assertRaisesRegex(ValueError, 'REFUSE_MISSING_EXISTING'):
            upload_incremental(cf, self.src, self.assets, self.catalogs)
        self.assertNotIn(('workers/scripts/gallery-archive-free', 'PUT'), cf.calls)

    def test_provider_requested_retained_original_is_readback_verified_and_reuploaded(self):
        old_hash, new_hash = asset_hash(OLD, 'jpg'), asset_hash(SRC, 'jpg')
        cf = FakeCF([old_hash, new_hash])
        with patch('cloudflare_incremental_upload._upload_bucket', return_value='fake-completion-jwt') as upload:
            reads = []
            def reader(model, album, p):
                reads.append((model, album, p['sha256']))
                return OLD
            previous = upload_incremental(cf, self.src, self.assets, self.catalogs, reader)
        self.assertEqual(previous, VERSION)
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0][:2], ('mimmi', 'known-album'))
        self.assertEqual(upload.call_args.args[3][old_hash][1], OLD)
        self.assertIn(('workers/scripts/gallery-archive-free', 'PUT'), cf.calls)

    def test_corrupted_retained_bytes_prevent_upload_and_deployment(self):
        cf = FakeCF([asset_hash(OLD, 'jpg')])
        with patch('cloudflare_incremental_upload._upload_bucket') as upload:
            with self.assertRaisesRegex(ValueError, 'PHOTO_EXACT_INTEGRITY_FAILED'):
                upload_incremental(cf, self.src, self.assets, self.catalogs, lambda *args: SRC)
        upload.assert_not_called()
        self.assertNotIn(('workers/scripts/gallery-archive-free', 'PUT'), cf.calls)

    def test_unknown_provider_hash_cannot_trigger_any_original_read(self):
        cf = FakeCF(['c'*32])
        with patch('cloudflare_incremental_upload._upload_bucket') as upload:
            reader = unittest.mock.Mock()
            with self.assertRaisesRegex(ValueError, 'UNRECOGNIZED_REQUESTED_ASSET_HASH'):
                upload_incremental(cf, self.src, self.assets, self.catalogs, reader)
        reader.assert_not_called()
        upload.assert_not_called()
        self.assertNotIn(('workers/scripts/gallery-archive-free', 'PUT'), cf.calls)

    def test_missing_or_corrupted_existing_hash_fails_closed(self):
        self.catalogs['mimmi']['albums'][0]['images'][0]['asset_hash'] = None
        with self.assertRaisesRegex(ValueError, 'MANIFEST_ENTRY_INVALID'):
            build_manifest(self.catalogs, self.assets)

    def test_asset_upload_mime_has_real_crlf(self):
        content_type, encoded = multipart([('a'*32, 'image/jpeg', base64.b64encode(SRC))])
        self.assertIn('multipart/form-data', content_type)
        self.assertIn(b'\r\n', encoded)
        self.assertNotIn(b'\\r\\n', encoded)

    def test_pin_rollback_to_original_active_version(self):
        cf = FakeCF()
        rollback_to(cf, VERSION)
        self.assertEqual(cf.calls, [('workers/scripts/gallery-archive-free/deployments', 'POST')])


if __name__ == '__main__':
    unittest.main()
