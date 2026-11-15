#!/usr/bin/env python3
"""Exhaustive, resumable reverse-image search over every archived photo SHA.

Unlike the old --seeds 8 rolling window, every verified owner and public
static image is indexed. Checkpoint IDs refer only to model+album+SHA, not to
volatile URL positions or GitHub run numbers. The checkpoint lives on a
dedicated per-model Git branch, separate from Pages and original assets.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from reverse_seed_priority import seeds
from reverse_image_sweep import search_one

APP_ROOT = Path(__file__).resolve().parents[1]


def inventory_accounting(root, model):
    """Explain raw owner slots vs usable distinct visual search references."""
    owner = json.loads((Path(root)/f'{model}-gallery/owner-index.json').read_text(encoding='utf-8'))
    public = json.loads((Path(root)/f'{model}-gallery/stored-albums.json').read_text(encoding='utf-8'))
    totals = {'owner_photo_records': 0, 'owner_valid_records': 0,
              'owner_unique_album_sha': 0, 'owner_duplicate_album_sha': 0,
              'owner_invalid_sha_or_bytes': 0, 'owner_ai_album_records': 0,
              'public_photo_records': 0, 'public_valid_records': 0}
    owner_seen = set()
    for album in owner.get('albums', []):
        for p in album.get('images', []):
            totals['owner_photo_records'] += 1
            if 'ai enhanced' in album.get('title', '').casefold() or 'ai 보정' in album.get('title', '').casefold():
                totals['owner_ai_album_records'] += 1
            sha = p.get('sha256')
            if (not isinstance(sha, str) or len(sha) != 64
                    or any(c not in '0123456789abcdef' for c in sha)
                    or type(p.get('bytes')) is not int or p['bytes'] <= 1024):
                totals['owner_invalid_sha_or_bytes'] += 1
                continue
            totals['owner_valid_records'] += 1
            key = (album['id'], sha)
            if key in owner_seen:
                totals['owner_duplicate_album_sha'] += 1
            else:
                owner_seen.add(key)
    totals['owner_unique_album_sha'] = len(owner_seen)
    for album in public.get('albums', []):
        for p in album.get('images', []):
            totals['public_photo_records'] += 1
            sha = p.get('sha256')
            if (isinstance(sha, str) and len(sha) == 64 and
                    all(c in '0123456789abcdef' for c in sha) and
                    isinstance(p.get('url'), str) and p['url'].startswith('stored-albums/')):
                totals['public_valid_records'] += 1
    return totals


def identity(photo):
    return hashlib.blake2s(
        ('\x00'.join((photo['model'], photo['album_id'], photo['photo_sha256']))).encode('utf-8'),
        digest_size=16).hexdigest()


def complete_queue(inventory, model):
    """One search per distinct photo SHA *per album*, not 3 cover samples."""
    if model not in ('mimmi', 'yui'):
        raise ValueError('INVALID_MODEL')
    groups = defaultdict(list)
    included = set()
    for photo in inventory:
        if photo.get('model') != model:
            continue
        sha = photo.get('photo_sha256')
        aid = photo.get('album_id')
        url = photo.get('public_image_url')
        if not isinstance(sha, str) or len(sha) != 64 or not all(x in '0123456789abcdef' for x in sha):
            raise ValueError('INVALID_SOURCE_SHA')
        if not isinstance(aid, str) or not aid or not isinstance(url, str) or not url.startswith('https://'):
            raise ValueError('INVALID_SOURCE_PHOTO')
        key = identity(photo)
        if key in included:
            continue
        included.add(key)
        groups[(model, aid)].append({**photo, 'seed_id': key})
    if not groups:
        raise ValueError('EMPTY_MODEL_SEED_QUEUE')
    # Images from each underfilled album get a turn before repeating its
    # second, third, ... frame. No photo disappears after the first pass.
    album_rows = list(groups.values())
    queue = []
    for rank in range(max(len(g) for g in album_rows)):
        for group in album_rows:
            if rank < len(group):
                queue.append(group[rank])
    if len(queue) != len(included):
        raise ValueError('INCOMPLETE_REVERSE_SEED_QUEUE')
    return queue


def read_progress(path, model, ids):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not data:
        data = {'schema_version': 1, 'model': model, 'cycle': 0,
                'attempted_ids': [], 'last_cycle_size': 0}
    if data.get('schema_version') != 1 or data.get('model') != model:
        raise ValueError('CHECKPOINT_SCHEMA_OR_MODEL_MISMATCH')
    attempted = data.get('attempted_ids')
    if not isinstance(attempted, list) or any(
        not isinstance(x, str) or len(x) != 32 or not all(c in '0123456789abcdef' for c in x)
        for x in attempted):
        raise ValueError('CORRUPT_CHECKPOINT_IDS')
    if len(attempted) != len(set(attempted)):
        raise ValueError('CORRUPT_CHECKPOINT_DUPLICATES')
    if type(data.get('cycle')) is not int or data['cycle'] < 0:
        raise ValueError('CORRUPT_CHECKPOINT_CYCLE')
    # Retain only SHA IDs still represented in the current gallery catalog.
    data['attempted_ids'] = [x for x in attempted if x in ids]
    return data


def plan_batch(queue, state, budget):
    if type(budget) is not int or not 1 <= budget <= 512:
        raise ValueError('SEARCH_BUDGET_OUT_OF_BOUNDS')
    covered = set(state['attempted_ids'])
    remaining = [p for p in queue if p['seed_id'] not in covered]
    cycle = state['cycle']
    if not remaining:
        # Start a full repeat only AFTER all currently stored images had a
        # search attempt; new photos from the owner catalog join automatically.
        covered.clear()
        remaining = queue[:]
        cycle += 1
    return remaining[:budget], cycle


def run(model, progress_path, out_path, next_path, budget, seconds, workers):
    if not 1 <= workers <= 3 or not 60 <= seconds <= 4800:
        raise ValueError('PUBLIC_SEARCH_CONCURRENCY_OR_TIME_OUT_OF_BOUNDS')
    queue = complete_queue(seeds(APP_ROOT, all_cuts=True), model)
    state = read_progress(progress_path, model, {p['seed_id'] for p in queue})
    selected, cycle = plan_batch(queue, state, budget)
    started = time.monotonic()
    scanned = []
    # Finish each bounded group before saving results. If the runner ends
    # early, the state update is never pushed and photos are retried next run.
    for k in range(0, len(selected), 12):
        if scanned and time.monotonic() - started >= seconds:
            break
        batch = selected[k:k+12]
        outputs = [None] * len(batch)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            tasks = {pool.submit(search_one, p): i for i, p in enumerate(batch)}
            for future in as_completed(tasks):
                i = tasks[future]
                try:
                    outputs[i] = future.result()
                except Exception as ex:
                    outputs[i] = {**batch[i], 'search_status': {
                        'worker_error': type(ex).__name__},
                        'candidate_pages': [], 'off_model_rejected': 0,
                        'originals_stored': 0, 'visible_gallery_added': 0}
        if any(r is None for r in outputs):
            raise ValueError('MISSING_SEARCH_RESULT_ROW')
        scanned.extend(outputs)
        print('ALL_PHOTOS_REVERSE_PROGRESS', model,
              'searched_this_run', len(scanned),
              'of_selected', len(selected),
              'all_unique_photo_sha', len(queue),
              'elapsed_seconds', int(time.monotonic()-started), flush=True)

    already = set(state['attempted_ids']) if cycle == state['cycle'] else set()
    new_ids = [r['seed_id'] for r in scanned]
    if len(new_ids) != len(set(new_ids)) or any(p not in {x['seed_id'] for x in selected} for p in new_ids):
        raise ValueError('REVERSE_SEARCH_UNEXPECTED_SEED_ID')
    state.update({'cycle': cycle,
                  'attempted_ids': [p['seed_id'] for p in queue
                                    if p['seed_id'] in already or p['seed_id'] in set(new_ids)],
                  'last_cycle_size': len(queue),
                  'last_run_attempts': len(scanned),
                  'updated_at': datetime.now(timezone.utc).isoformat()})
    # A public search returned readable HTML if at least one engine found a
    # valid response, even when there are no matching source pages.
    readable = sum(any(str(x).startswith('leads_') for x in r['search_status'].values())
                   for r in scanned)
    sources = len({c['url'] for r in scanned for c in r.get('candidate_pages', [])})
    report = {'schema_version': 1, 'model': model,
              'method': 'all-owner-plus-static-photo-sha-round-robin',
              'generated_at': datetime.now(timezone.utc).isoformat(),
              'total_seed_frames': len(queue),
              'seed_queries': len(scanned),
              'readable_search_results': readable,
              'unique_albums_queried': len({r['album_id'] for r in scanned}),
              'source_pages_accepted': sources,
              'off_model_rejected': sum(r['off_model_rejected'] for r in scanned),
              'physical_photos_new': 0, 'gallery_photos_new': 0,
              'research_only': True,
              'coverage': {'cycle': cycle,
                           'unique_photo_sha_queued': len(queue),
                           'attempted_this_cycle': len(state['attempted_ids']),
                           'remaining_this_cycle': len(queue)-len(state['attempted_ids']),
                           'blocked_or_unreadable_this_run': len(scanned)-readable,
                           'scan_budget': budget},
              'results': scanned}
    out_path = Path(out_path); next_path = Path(next_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    next_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    next_path.write_text(json.dumps(state, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print('ALL_OWNER_PHOTOS_REVERSE_SEARCH', json.dumps(
        {**report['coverage'], 'model': model,
         'searched_this_run': len(scanned),
         'search_pages_accepted': sources, 'readable': readable,
         'photo_files_downloaded': 0}, ensure_ascii=False), flush=True)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=['mimmi', 'yui'], required=True)
    p.add_argument('--progress', type=Path, required=True)
    p.add_argument('--progress-out', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--budget', type=int, default=256)
    p.add_argument('--max-seconds', type=int, default=3300)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--plan-only', action='store_true')
    a = p.parse_args()
    if a.plan_only:
        queue = complete_queue(seeds(APP_ROOT, all_cuts=True), a.model)
        print('ALL_PHOTO_SHA_QUEUE_CENSUS', json.dumps({'model': a.model,
              'unique_photo_sha_per_album': len(queue),
              'distinct_albums': len({x['album_id'] for x in queue}),
              'accounting': inventory_accounting(APP_ROOT,a.model),
              'source_kind_counts': {kind: sum(1 for x in queue if x.get('seed_kind') == kind)
                 for kind in ('static-public', 'public-gateway-cover')}}, sort_keys=True), flush=True)
        return
    run(a.model, a.progress, a.out, a.progress_out, a.budget, a.max_seconds, a.workers)


if __name__ == '__main__':
    main()
