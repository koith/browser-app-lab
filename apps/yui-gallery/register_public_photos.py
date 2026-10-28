#!/usr/bin/env python3
"""Connect reviewed public photographs without treating collections as full books."""
import argparse
import json
import shutil
from pathlib import Path

from build_additional_source_manifest import build
from public_photo_archive import atomic_json, verified_record


def register(sns_root, public_root, review_path, output, manifest_out, additional_input_roots=()):
    review = json.loads(review_path.read_text())
    accepted = set(review['photo_sha256'])
    originals, locations = {}, {}
    sns = json.loads((sns_root/'manifest.json').read_text())['images']
    public = json.loads((public_root/'manifest.json').read_text())['images']
    inputs = [(sns_root, sns), (public_root, public)] + [(p, json.loads((p/'manifest.json').read_text())['images']) for p in additional_input_roots]
    for root, rows in inputs:
        for row in rows:
            if root == sns_root and row['sha256'] not in accepted:
                continue
            verified_record(root, row)
            originals.setdefault(row['sha256'], row)
            locations.setdefault(row['sha256'], root/row['file'])
    preferred = {}
    for selection in review.get('reviewed_same_frame_variants', []):
        better = originals[selection['selected_sha256']]
        alternate = originals[selection['alternative_sha256']]
        if better['width']*better['height'] < alternate['width']*alternate['height']:
            raise ValueError('Reviewed variant would reduce actual resolution')
        preferred[alternate['sha256']] = better['sha256']
    groups = [
        ('public-yui-sns', '심유이 — 코스프레·공개 사진', '공개 SNS',
         'creator_public_photographs', [r for r in sns if r['sha256'] in accepted]
         + [r for r in public if r.get('collection_kind') == 'public_photographer_portfolio']),
        ('djawa-privaty-public-samples', 'DJAWA — Privaty Sharp Lesson · 공개 샘플', 'DJAWA',
         'official_public_samples', [r for r in public if r.get('collection_kind') == 'official_public_samples']),
        ('acosta-japan-public-report', '일본 공식 행사 후기', 'Hacosta / acosta!',
         'official_event_report', [r for r in public if r.get('source_country') == 'JP']),
        ('gamersky-public-editorial', 'GamerSky — 공개 기사 사진', 'GamerSky',
         'public_editorial_photos', [r for r in public if r.get('collection_kind') == 'public_editorial_photos']),
        ('inven-public-photos', '인벤 — 공개 게시 사진', '인벤',
         'public_board_photographs', [r for r in public if r.get('collection_kind') == 'public_board_post']),
    ]
    folders = []
    for aid, title, publisher, kind, rows in groups:
        folder = output/aid
        (folder/'images').mkdir(parents=True, exist_ok=True)
        by_hash = {}
        for original in rows:
            sha = preferred.get(original['sha256'], original['sha256'])
            photo = originals[sha]
            if sha not in by_hash:
                filename = 'images/'+Path(photo['file']).name
                destination = folder/filename
                shutil.copyfile(locations[sha], destination)
                by_hash[sha] = {**photo, 'file': filename, 'number': len(by_hash)+1,
                                'source_country': photo.get('source_country', 'KR'),
                                'alternative_sources': []}
            if original['sha256'] != sha:
                by_hash[sha]['alternative_sources'].append({k: original[k] for k in
                    ['url', 'sha256', 'bytes', 'width', 'height', 'origin_page'] if k in original})
        if not by_hash:
            continue
        manifest = {'id': aid, 'title': title, 'publisher': publisher,
                    'collection_kind': kind, 'expected': len(by_hash),
                    'not_complete_photobook': True, 'expected_total_unknown': True,
                    'numbering_kind': 'display_order_not_publisher_book_sequence',
                    'source_countries': sorted({r.get('source_country', 'KR') for r in rows}),
                    'source_pages': list(dict.fromkeys(r['origin_page'] for r in rows)),
                    'images': list(by_hash.values())}
        if aid == 'djawa-privaty-public-samples':
            manifest['advertised_publisher_photos'] = 190
        atomic_json(folder/'manifest.json', manifest)
        folders.append(folder)
    build(folders, manifest_out)
    return [{'id': json.loads((f/'manifest.json').read_text())['id'],
             'images': len(json.loads((f/'manifest.json').read_text())['images'])} for f in folders]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['sns-root', 'public-root', 'review', 'output']:
        parser.add_argument('--'+flag, type=Path, required=True)
    parser.add_argument('--manifest-out', type=Path,
                        default=Path(__file__).with_name('additional-source-albums.json'))
    parser.add_argument('--additional-input-root', type=Path, action='append', default=[],
                        help='Existing verified individual files selected by explicit same-frame review')
    args = parser.parse_args()
    print('REVIEWED_PUBLIC_PHOTOGRAPHS_REGISTERED', json.dumps(register(
        args.sns_root, args.public_root, args.review, args.output, args.manifest_out,
        args.additional_input_root)))
