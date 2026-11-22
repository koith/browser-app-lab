"""Owner-only, fail-closed Cloudflare Workers Assets manifest update.

Preserves the complete remote immutable asset set in every upload manifest,
without reading previously verified media through the public Worker.

Docs: https://developers.cloudflare.com/workers/static-assets/direct-upload/
"""
import base64
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import secrets
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from check_cloudflare_connection import NoRedirect
from cloudflare_assets_snapshot import MODELS, KIND, signature, checked

NAME = 'gallery-archive-free'
API = 'https://api.cloudflare.com/client/v4'
HEX32 = re.compile(r'[a-f0-9]{32}')
PATH = re.compile(r'/(?:mimmi|yui)/originals/[a-z0-9-]+/[A-Za-z0-9._ -]+\.(?:jpg|jpeg|png|webp)')
SAFE_SOURCE_PARTS = ('entry.mjs', 'worker.mjs', 'private-s3.mjs', 'bound-assets.mjs',
                     'private-mimmi-catalog.txt', 'private-yui-catalog.txt')


def asset_hash(raw, suffix):
    """Provider document's base64+extension SHA256/128 asset upload key."""
    if suffix not in ('jpg', 'jpeg', 'png', 'webp'):
        raise ValueError('ASSET_EXTENSION_NOT_ALLOWED')
    return hashlib.sha256(base64.b64encode(raw) + suffix.encode('ascii')).hexdigest()[:32]


def build_manifest(catalogs, directory):
    """Asset manifest includes ALL already deployed entries, bytes only NEW ones.

    Any absent or incorrect retained asset hash is a hard failure, not a reason
    to omit, redownload or overwrite an old photo.
    """
    if set(catalogs) != set(MODELS):
        raise ValueError('MANIFEST_MODEL_SET_INVALID')
    entries, hashes, paths = {}, {}, set()
    for model in MODELS:
        cat = catalogs[model]
        if cat.get('archive_kind') != KIND or cat.get('model') != model or cat.get('schema_version') != 1:
            raise ValueError('MANIFEST_CATALOG_INVALID')
        for album in cat['albums']:
            for photo in album['images']:
                path = '/' + model + '/' + photo['key']
                h = photo.get('asset_hash')
                if (not PATH.fullmatch(path) or not HEX32.fullmatch(h or '') or
                        not isinstance(photo.get('bytes'), int) or photo['bytes'] < 1 or
                        photo['bytes'] > 8_000_000 or path in paths):
                    raise ValueError('MANIFEST_ENTRY_INVALID')
                paths.add(path)
                entries[path] = {'hash': h, 'size': photo['bytes']}
                hashes.setdefault(h, set()).add(path)
    if not entries:
        raise ValueError('MANIFEST_EMPTY_REFUSED')
    directory = Path(directory)
    files = {}
    for model in MODELS:
        root = directory / model
        if not root.exists():
            continue
        for filename in root.rglob('*'):
            if not filename.is_file():
                continue
            path = '/' + filename.relative_to(directory).as_posix()
            record = entries.get(path)
            if record is None:
                raise ValueError('LOCAL_FILE_OUTSIDE_REPLICA_MANIFEST')
            raw = filename.read_bytes()
            if (len(raw) != record['size'] or
                    asset_hash(raw, filename.suffix.removeprefix('.').lower()) != record['hash']):
                raise ValueError('LOCAL_ASSET_HASH_OR_LENGTH_INVALID')
            files[record['hash']] = (filename.suffix.lower(), raw)
    return entries, files


def multipart(parts):
    """Fixed trusted form-data part names; never log private byte contents."""
    boundary = 'gallery-asset-' + secrets.token_hex(20)
    chunks = []
    for name, mime, raw in parts:
        if not re.fullmatch('[A-Za-z0-9_.-]{1,100}', name):
            raise ValueError('MULTIPART_NAME_INVALID')
        chunks.append((f'--{boundary}\r\n'
                       f'Content-Disposition: form-data; name="{name}"; filename="{name}"\r\n'
                       f'Content-Type: {mime}\r\n\r\n').encode() + raw + b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    return 'multipart/form-data; boundary=' + boundary, b''.join(chunks)


def _upload_bucket(account, jwt, names, files):
    """Use short-lived upload JWT only for the Cloudflare asset upload URL."""
    if not isinstance(jwt, str) or not jwt or len(jwt) > 8192:
        raise ValueError('ASSET_UPLOAD_SESSION_JWT_INVALID')
    parts = []
    for h in names:
        if h not in files or not HEX32.fullmatch(h):
            raise ValueError('EXISTING_ASSET_REUPLOAD_REQUIRED_REFUSED')
        extension, raw = files[h]
        content_type = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                        'png': 'image/png', 'webp': 'image/webp'}[extension.removeprefix('.')]
        parts.append((h, content_type, base64.b64encode(raw)))
    content_type, body = multipart(parts)
    request = Request(API + '/accounts/' + account + '/workers/assets/upload?base64=true',
                      data=body, method='POST',
                      headers={'Authorization': 'Bearer ' + jwt,
                               'Content-Type': content_type, 'Accept': 'application/json'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=120) as response:
            if response.status not in (200, 201):
                raise ValueError('ASSET_UPLOAD_STATUS_INVALID')
            result = json.loads(response.read(32768))
    except HTTPError as error:
        print('CF_INCREMENTAL_ASSET_UPLOAD_HTTP', error.code, flush=True)
        raise ValueError('ASSET_UPLOAD_REJECTED') from None
    except (OSError, URLError, TimeoutError):
        raise ValueError('ASSET_UPLOAD_NETWORK_FAILED') from None
    if not isinstance(result, dict) or result.get('success') is not True:
        raise ValueError('ASSET_UPLOAD_NOT_CONFIRMED')
    data = result.get('result')
    return data.get('jwt') if isinstance(data, dict) else None


def deployed_version(cf):
    """Remember exact active version before modifying live traffic."""
    result = cf.call('workers/scripts/' + NAME + '/deployments')['result']
    rows = result.get('deployments', []) if isinstance(result, dict) else result
    if not isinstance(rows, list) or not rows:
        raise ValueError('ACTIVE_DEPLOYMENT_NOT_FOUND')
    versions = rows[0].get('versions', [])
    if (len(versions) != 1 or versions[0].get('percentage') != 100 or
            not re.fullmatch('[0-9a-f-]{36}', versions[0].get('version_id', ''))):
        raise ValueError('ACTIVE_DEPLOYMENT_NOT_SINGLE_VERSION')
    return versions[0]['version_id']


def rollback_to(cf, version):
    """Restore the exact known-good release if live post-deploy QA fails."""
    if not isinstance(version, str) or not re.fullmatch('[0-9a-f-]{36}', version):
        raise ValueError('ROLLBACK_VERSION_UNVERIFIED')
    body = {'strategy': 'percentage', 'versions': [{'version_id': version, 'percentage': 100}]}
    response = cf.call('workers/scripts/' + NAME + '/deployments', 'POST', body)
    if not isinstance(response.get('result'), dict):
        raise ValueError('ROLLBACK_DEPLOYMENT_UNVERIFIED')
    print('CF_INCREMENTAL_ROLLBACK_SUBMITTED', flush=True)


def upload_incremental(cf, source, directory, catalogs, retained_reader=None):
    """One new full-path manifest; only truly missing new file bytes are uploaded.

    Returns prior active version ID for automatic rollback if postdeploy tests fail.
    """
    manifest, local = build_manifest(catalogs, directory)
    old_version = deployed_version(cf)
    print('CF_INCREMENTAL_PREPARED', 'catalog_photos', len(manifest),
          'new_local_files', len(local), flush=True)
    if not local:
        raise ValueError('INCREMENTAL_NO_NEW_LOCAL_BYTES')
    start = cf.call('workers/scripts/' + NAME + '/assets-upload-session', 'POST',
                    {'manifest': manifest})['result']
    if not isinstance(start, dict) or not isinstance(start.get('jwt'), str):
        raise ValueError('ASSET_UPLOAD_SESSION_NOT_CONFIRMED')
    groups = start.get('buckets') or []
    if not isinstance(groups, list) or any(not isinstance(group, list) for group in groups):
        raise ValueError('ASSET_UPLOAD_SESSION_BUCKETS_INVALID')
    requested = [h for group in groups for h in group]
    if len(requested) != len(set(requested)):
        raise ValueError('DUPLICATE_ASSET_UPLOAD_BUCKET_HASH')
    # Reuse is guaranteed only for recently uploaded versions. The provider
    # can request an older immutable file again. Recover exactly those hashes
    # from the still-active verified replica, never omit their manifest rows.
    known = {}
    for model in MODELS:
        for album in catalogs[model]['albums']:
            for photo in album['images']:
                known.setdefault(photo['asset_hash'], (model, album['id'], photo))
    if any(not isinstance(h, str) or not HEX32.fullmatch(h) or h not in known for h in requested):
        raise ValueError('UNRECOGNIZED_REQUESTED_ASSET_HASH')
    missing = set(requested) - set(local)
    print('CF_INCREMENTAL_UPLOAD_REQUEST', 'requested', len(requested),
          'new_local', len(set(requested) & set(local)), 'retained_reupload', len(missing), flush=True)
    if missing and retained_reader is None:
        raise ValueError('REFUSE_MISSING_EXISTING_CLOUDFLARE_ASSET_HASH')
    completion = start['jwt'] if not groups else None
    for group in groups:
        files = {h: local[h] for h in group if h in local}
        for h in group:
            if h in files:
                continue
            model, album, photo = known[h]
            raw = retained_reader(model, album, photo)
            checked(photo, raw)
            extension = Path(photo['key']).suffix.lower()
            if asset_hash(raw, extension.removeprefix('.')) != h:
                raise ValueError('RETAINED_ASSET_UPLOAD_HASH_MISMATCH')
            files[h] = (extension, raw)
        # Readback failure above stops before this group or any script deploy.
        # At most one provider-assigned bucket is retained in memory.
        token = _upload_bucket(cf.account, start['jwt'], group, files)
        if token:
            completion = token
    if not completion:
        raise ValueError('ASSET_UPLOAD_COMPLETION_NOT_CONFIRMED')
    source = Path(source)
    metadata = {
        'main_module': 'entry.mjs',
        'compatibility_date': '2026-11-01',
        'keep_bindings': ['secret_text'],
        'assets': {
            'jwt': completion,
            'config': {'run_worker_first': True,
                       'html_handling': 'none', 'not_found_handling': 'none'}
        },
        'bindings': [
            {'type': 'plain_text', 'name': 'PAGE_ORIGIN', 'text': 'https://koith.github.io'},
            {'type': 'plain_text', 'name': 'PAGES_READ_POLICY', 'text': 'existing-sha-pinned-gallery'},
            {'type': 'plain_text', 'name': 'ARCHIVE_RELEASE',
             'text': json.loads((source / 'wrangler.json').read_text())['vars']['ARCHIVE_RELEASE']},
            {'type': 'plain_text', 'name': 'ARCHIVE_REPOSITORY', 'text': 'koith/browser-app-lab'},
            {'type': 'assets', 'name': 'ARCHIVE_ASSETS'},
        ],
    }
    parts = [('metadata', 'application/json', json.dumps(metadata).encode())]
    for name in SAFE_SOURCE_PARTS:
        parts.append((name, 'text/plain' if name.endswith('.txt')
                      else 'application/javascript+module', (source / name).read_bytes()))
    cf.call('workers/scripts/' + NAME, 'PUT', multipart=multipart(parts))
    print('CF_INCREMENTAL_MANIFEST_DEPLOYED',
          'retained_photo_readbacks', len(missing), 'uploaded_new_files', len(set(requested) & set(local)),
          'retained_photos', len(manifest)-len(local), flush=True)
    return old_version
