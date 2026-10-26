#!/usr/bin/env python3
"""Recover known source files individually; never replace a verified file silently.

The source manifest is a byte commitment, not proof of private cloud storage.
Output stays outside the public repository. Partial runs can be resumed.
"""
import argparse
import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image


def verified(blob, row):
    if len(blob) != row['bytes'] or hashlib.sha256(blob).hexdigest() != row['sha256']:
        raise ValueError('Source bytes differ from committed SHA-256')
    with Image.open(io.BytesIO(blob)) as image:
        image.verify()
    with Image.open(io.BytesIO(blob)) as image:
        image.load()
        if image.size != (row['width'], row['height']):
            raise ValueError('Source dimensions differ')


def retrieve(album, row, output):
    aid, number = album['id'], row['number']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}', aid) or type(number) is not int or number < 1:
        raise ValueError('Invalid album/sequence')
    url = row['url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not (parsed.hostname == 'cdn.jliji.com' or
            re.fullmatch(r'imgx\d{3}\.pixibb\.com', parsed.hostname or '')):
        raise ValueError('Unapproved public image host')
    ext = Path(parsed.path).suffix.lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.avif') or not 2000 < row['bytes'] < 140_000_000:
        raise ValueError('Invalid image type/size')
    folder = output / aid
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f'{number:04d}{ext}'
    resumed = file.exists()
    if resumed:
        verified(file.read_bytes(), row)
    else:
        for attempt in range(3):
            # Do not follow unknown-host redirects or work around access blocks.
            with requests.get(url, timeout=(15, 50), stream=True, allow_redirects=False) as response:
                if response.status_code in (429, 503) and attempt < 2:
                    time.sleep(min(30, max(2, int(response.headers.get('Retry-After', '3')))))
                    continue
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError('Expected direct image HTTP 200')
                blob = bytearray()
                for chunk in response.iter_content(65536):
                    blob.extend(chunk)
                    if len(blob) > row['bytes']:
                        raise ValueError('Source response larger than committed image')
                verified(blob, row)
                temp = file.with_suffix(file.suffix + '.part')
                temp.write_bytes(blob)
                temp.replace(file)
                break
    return {**row, 'file': file.name, 'resumed': resumed}


def run(manifest, output, workers=3):
    data = json.loads(manifest.read_text())
    output.mkdir(parents=True, exist_ok=True)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'method': 'HTTP 200 + unchanged SHA256 + complete image decode',
              'private_cloud_verified': 0, 'albums': [], 'failures': []}
    for album in data['albums']:
        images, failures = [], []
        if [r['number'] for r in album['images']] != list(range(1, album['expected'] + 1)):
            raise ValueError('Incomplete source sequence')
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(retrieve, album, row, output): row for row in album['images']}
            for future in as_completed(jobs):
                try:
                    images.append(future.result())
                except Exception as exc:
                    failures.append({'album': album['id'], 'number': jobs[future]['number'],
                                     'error': str(exc)[:250]})
        images.sort(key=lambda x: x['number'])
        record = {'id': album['id'], 'title': album['title'], 'expected': album['expected'],
                  'images': images, 'failures': failures, 'source_pages': album.get('source_pages', [])}
        (output / album['id'] / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
        report['albums'].append({'id': album['id'], 'expected': album['expected'],
                                 'verified_files': len(images), 'new_local_files': sum(not x['resumed'] for x in images),
                                 'bytes': sum(x['bytes'] for x in images)})
        report['failures'].extend(failures)
        print('SOURCE_FILE_RETRIEVAL', report['albums'][-1], 'failures', len(failures), flush=True)
    (output / 'retrieval-report.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['failures']:
        raise RuntimeError('Incomplete source recovery; see retrieval-report.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('source-viewer-albums.json'))
    parser.add_argument('--out', type=Path, required=True, help='Private directory outside public repository')
    parser.add_argument('--workers', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('Photo bytes must stay outside the public repository')
    run(args.manifest, args.out, args.workers)
