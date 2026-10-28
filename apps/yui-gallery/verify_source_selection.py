"""Re-download selected source files and verify unchanged bytes; not cloud storage."""
import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

import requests


def selection(manifest, decisions, album_ids):
    numbers = {a['id']: {p['number'] for p in a['replacements']}
               for a in decisions['albums']}
    return {p['sha256']: {**p, 'album_id': a['id']}
            for a in manifest['albums'] for p in a['images']
            if a['id'] in album_ids or p['number'] in numbers.get(a['id'], set())}


def check(photo, client=None):
    result = {k: photo[k] for k in ('album_id', 'number', 'sha256')}
    url = urlsplit(photo['url'])
    if url.scheme != 'https' or url.username or url.password:
        raise ValueError('Expected a public HTTPS source URL')
    for attempt in range(3):
        try:
            response = (client.get(photo['url']) if client else
                        requests.get(photo['url'], timeout=(15, 45), allow_redirects=False))
            response.raise_for_status()
            assert response.status_code == 200, response.status_code
            assert len(response.content) == photo['bytes'], 'Byte count changed'
            assert hashlib.sha256(response.content).hexdigest() == photo['sha256'], 'SHA-256 changed'
            return {**result, 'source_readback_match': True}
        except (requests.RequestException, AssertionError) as error:
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            if attempt == 2 or status in (401, 403, 429, 451):
                return {**result, 'source_readback_match': False, 'error': str(error)[:200]}
            time.sleep(attempt + 1)
        except PermissionError as error:
            return {**result, 'source_readback_match': False, 'error': str(error)[:200]}


if __name__ == '__main__':
    root = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=root/'additional-source-albums.json')
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--album', action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=range(1,5), default=4)
    parser.add_argument('--public-policy', action='store_true', help='Respect robots and stop denied origins using PublicSession')
    args = parser.parse_args()
    photos = selection(json.loads(args.manifest.read_text()), json.loads(args.selection.read_text()), set(args.album))
    assert photos, 'No selected source files'
    rows = []
    client = None
    if args.public_policy:
        from public_photo_archive import PublicSession
        client = PublicSession(delay=1)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for task in as_completed([pool.submit(check, p, client) for p in photos.values()]):
            rows.append(task.result())
            if len(rows) % 50 == 0:
                print('SOURCE_READBACK_PROGRESS', len(rows), '/', len(photos), flush=True)
    errors = [r for r in rows if not r['source_readback_match']]
    report = {'kind': 'source_hosted_readback_not_personal_cloud',
              'requested_unique_files': len(photos), 'source_sha256_readback_pass': len(rows)-len(errors),
              'personal_cloud_verified': 0, 'errors': errors, 'files': rows}
    report['public_policy_checked'] = args.public_policy
    args.out.write_text(json.dumps(report, indent=2)+'\n')
    print('SOURCE_READBACK_FINISHED', len(rows)-len(errors), '/', len(photos), 'ERRORS', len(errors), flush=True)
    if errors:
        raise SystemExit(1)
