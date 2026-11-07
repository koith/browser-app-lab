"""Build an exact-byte personal replica; never create photo bundles or publish to Git."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from PIL import Image

MODELS = ('mimmi', 'yui')
KIND = 'gallery-archive-free:replica-catalog'
MAX_FILES = 19_500
MAX_BYTES = 4_000_000_000
ID = re.compile(r'[a-z0-9][a-z0-9-]{1,99}')


def signature(p):
    return tuple(p.get(k) for k in ('sha256', 'bytes', 'width', 'height'))


def checked(photo, raw):
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= 8_000_000
            or len(raw) != photo.get('bytes')
            or hashlib.sha256(raw).hexdigest() != photo.get('sha256')):
        raise ValueError('PHOTO_EXACT_INTEGRITY_FAILED')
    with Image.open(io.BytesIO(raw)) as image:
        if image.size != (photo.get('width'), photo.get('height')) or image.width * image.height > 40_000_000:
            raise ValueError('PHOTO_DIMENSIONS_FAILED')
        extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}.get(image.format)
        if extension is None:
            raise ValueError('PHOTO_FORMAT_NOT_SUPPORTED')
        image.verify()
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
    return extension


class Snapshot:
    def __init__(self, root, directory):
        self.root, self.directory = Path(root), Path(directory)
        self.catalogs = {m: {'schema_version': 1, 'model': m, 'archive_kind': KIND, 'albums': []} for m in MODELS}
        self.rows = {m: {} for m in MODELS}
        self.expected = {}
        for m in MODELS:
            index = json.loads((self.root / f'apps/{m}-gallery/owner-index.json').read_text())
            if index.get('model') != m:
                raise ValueError('OWNER_INDEX_MODEL_FAILED')
            self.expected[m] = {(a['id'], p['number']): p for a in index['albums'] for p in a['images']}
        self.directory.mkdir(parents=True, exist_ok=True)

    def add(self, model, album, photo, raw, source):
        aid, number = album['id'], photo['number']
        if not ID.fullmatch(aid) or type(number) is not int or not 0 < number < 10000:
            raise ValueError('INVALID_OWNER_PHOTO')
        expected = self.expected[model].get((aid, number))
        if not expected or signature(expected) != signature(photo):
            raise ValueError('OWNER_INDEX_PHOTO_MISMATCH')
        extension = checked(photo, raw)
        old = self.rows[model].get((aid, number))
        if old and signature(old) != signature(photo):
            raise ValueError('EXISTING_ORIGINAL_REPLACEMENT_REFUSED')
        if old:
            return False
        key = f'originals/{aid}/{number:04d}_{photo["sha256"]}.{extension}'
        target = self.directory / model / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        self.rows[model][aid, number] = {k: photo[k] for k in ('number', 'sha256', 'bytes', 'width', 'height')}
        self.rows[model][aid, number].update(key=key, replica_source=source)
        self.check_budget()
        return True

    def check_budget(self):
        rows = [p for model in MODELS for p in self.rows[model].values()]
        if len(rows) + 4 > MAX_FILES or sum(p['bytes'] for p in rows) > MAX_BYTES:
            raise ValueError('FREE_ASSET_PROJECT_BUDGET_EXCEEDED')

    def public_originals(self):
        counts = {}
        for model in MODELS:
            base = self.root / f'apps/{model}-gallery'
            stored = json.loads((base / 'stored-albums.json').read_text())
            by_sha = {}
            for a in stored['albums']:
                for p in a['images']:
                    if not re.fullmatch(r'stored-albums/[a-z0-9-]+/[A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp)', p['url']):
                        raise ValueError('PUBLIC_ORIGINAL_PATH_FAILED')
                    by_sha[signature(p)] = p['url']
            count = 0
            for (aid, number), p in self.expected[model].items():
                path = by_sha.get(signature(p))
                if path:
                    count += self.add(model, {'id': aid}, p, (base / path).read_bytes(), 'existing-exact-public-copy')
            counts[model] = count
        return counts

    def existing_owner(self, model, maximum=32):
        # Read only the explicitly authenticated owner's original files.
        # Four bounded parallel independent reads keep the exhaustive Free
        # restoration within a single Actions job without parallel mutations
        # to the SHA-checked snapshot or any upstream account settings.
        from restore_known_owner_cache import COOKIE, REMOTE, verified_owner_catalog, cookie_header
        from qa_existing_owner_exact_file import read_existing
        env = os.environ.copy()
        cookie = env.get(COOKIE[model], '')
        if not cookie:
            return {'added': 0, 'state': 'OWNER_SESSION_MISSING'}
        env.update(RCLONE_CONFIG_ARCHIVE_TYPE='terabox', RCLONE_CONFIG_ARCHIVE_COOKIE=cookie_header(cookie))
        env.pop('RCLONE_CONFIG_ARCHIVE_DOMAIN', None)
        try:
            _, catalog = verified_owner_catalog(model, env, attempts=1)
        except Exception:
            return {'added': 0, 'state': 'EXISTING_OWNER_CATALOG_UNAVAILABLE'}
        source = {(a['id'], p['number']): (a, p) for a in catalog['albums'] for p in a['images']}
        if set(source) != set(self.expected[model]) or any(
                signature(pair[1]) != signature(self.expected[model][key])
                for key, pair in source.items()):
            return {'added': 0, 'state': 'EXISTING_OWNER_CATALOG_DIFFERS_FROM_SHA_INDEX'}
        priorities = {'mimmi': ['mimmi-indie-sana-sopmod2-2019', 'djawa-pop-kitty-party'],
                      'yui': ['yuis-present33', 'teddy-bear97', 'athletic-club104']}[model]
        pending = [(a, p) for key, (a, p) in source.items() if key not in self.rows[model]]
        pending.sort(key=lambda pair: (
            priorities.index(pair[0]['id']) if pair[0]['id'] in priorities else len(priorities),
            pair[0]['id'], pair[1]['number']))

        def read_one(pair):
            album, photo = pair
            key = photo.get('key')
            prefix = 'originals/' + album['id'] + '/'
            if (not isinstance(key, str) or not key.startswith(prefix)
                    or not re.fullmatch(r'[A-Za-z0-9/_ .-]+', key)
                    or any(s in ('', '.', '..') for s in key.split('/'))):
                return album, photo, None, 'invalid_owner_key'
            try:
                with tempfile.TemporaryDirectory(prefix='exact-owner-read-') as temporary:
                    target = Path(temporary) / 'photo'
                    ok, reason = read_existing(REMOTE[model], key, target, env)
                    if not ok:
                        # Never copy provider messages or private source paths
                        # into the public workflow log.
                        sanitized = str(reason)
                        if not re.fullmatch(r'[a-z_]{1,55}', sanitized):
                            sanitized = 'remote_read_failed'
                        return album, photo, None, sanitized
                    return album, photo, target.read_bytes(), None
            except (OSError, ValueError, RuntimeError):
                return album, photo, None, 'owner_read_exception'

        added, failures = 0, Counter()
        blocked = False
        with ThreadPoolExecutor(max_workers=4) as pool:
            # A bounded batch limits concurrently downloaded photos to eight.
            # Snapshot.add() is always serialized and independently verifies
            # the raw bytes, SHA-256, image dimensions and free-budget cap.
            for offset in range(0, len(pending), 8):
                if maximum and added >= maximum:
                    break
                for album, photo, raw, reason in pool.map(read_one, pending[offset:offset + 8]):
                    if maximum and added >= maximum:
                        break
                    if reason is not None:
                        failures[reason] += 1
                        if reason in ('provider_access_denied', 'provider_access_rejected',
                                      'remote_read_rejected') or sum(failures.values()) >= 5:
                            blocked = True
                            break
                        continue
                    try:
                        added += self.add(model, album, photo, raw, 'existing-authenticated-owner-original')
                    except (ValueError, OSError):
                        failures['exact_image_verification_failed'] += 1
                        blocked = True
                        break
                    if added == 1 or added % 20 == 0:
                        print('BOUND_ASSET_OWNER_READ_PROGRESS', model, added, flush=True)
                if blocked:
                    break
        print('BOUND_ASSET_OWNER_READ_TOTAL', model, 'added', added,
              'remaining', len(pending) - added, 'failure_count',
              sum(failures.values()), flush=True)
        return {'added': added, 'failures': dict(failures),
                'remaining_metadata_rows': len(pending) - added,
                'state': ('EXISTING_OWNER_READ_STOPPED_AFTER_FAILURES' if blocked else
                          'EXISTING_OWNER_READ_FINISHED_NOT_FULL_GALLERY_PROOF')}

    def finish(self):
        self.check_budget()
        for model in MODELS:
            albums = {}
            for (aid, _), photo in sorted(self.rows[model].items()):
                albums.setdefault(aid, []).append(photo)
            self.catalogs[model]['albums'] = [{'id': aid, 'images': images} for aid, images in albums.items()]
        return self.catalogs
