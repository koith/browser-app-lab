#!/usr/bin/env python3
"""Read-only acceptance of 214 already-owned user-incident originals on live Cloudflare.

Uses the same exact SHA256 / byte-length / image dimension / pixel decode
verification as the proven full 7,724 owner readback. No Render dependency.
No uploads, credentials, billing changes, mutation, or source-site crawling.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time

from qa_cloudflare_full_remote import indexed, check, BASE

# These exact incident albums and expected counts are also checked against the
# owner-rescue metadata and gateway incident list by compile-contract CI.
TARGET = {
    "mimmi": (("v2ph-actor-a8n8n85a", 61),
              ("djawa-janus-scary-lantern-night", 15),
              ("mimmi-indie-sana-sopmod2-2019", 7)),
    "yui": (("teddy-bear97", 97),
            ("djawa-privaty-public-samples", 30),
            ("yui-chinokun-illustar-2026-public", 4)),
}


def main(model):
    rows = indexed()
    albums = {}
    for owner_model, album_id, photo in rows:
        if owner_model == model:
            albums.setdefault(album_id, []).append((owner_model, album_id, photo))
    targets = []
    for album_id, count in TARGET[model]:
        matches = albums.get(album_id)
        if matches is None or len(matches) != count:
            raise ValueError("WRONG_INCIDENT_ALBUM_COUNT " + model + "/" + album_id)
        actual_numbers = {item[2]['number'] for item in matches}
        if len(actual_numbers) != count:
            raise ValueError("DUPLICATE_INCIDENT_STORAGE_NUMBER " + model + "/" + album_id)
        targets.extend(matches)
    assert len(targets) == (83 if model == 'mimmi' else 131)
    failures = []
    successes = 0
    started = time.monotonic()
    # Four independent bounded remote reads, never re-uploading originals.
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(check, item): (item[1], item[2]['number']) for item in targets}
        for future in as_completed(jobs):
            album_id, number = jobs[future]
            try:
                returned_model = future.result()
                assert returned_model == model, 'MODEL_CROSSING'
                successes += 1
            except Exception as error:
                failures.append({'album': album_id, 'number': number,
                                 'reason': str(error)[:100]})
    output = {
        'model': model, 'source': 'real-cloudflare-signed-originals',
        'expected': len(targets), 'exact_sha_bytes_pixels_pass': successes,
        'failures_first_20': sorted(failures, key=lambda f: (f['album'], f['number']))[:20],
        'fail_count': len(failures),
        'elapsed_seconds': round(time.monotonic() - started, 1),
        'owner_uploads': 0, 'billing_changed': 0,
        'physical_iphone_verified': False,
    }
    print('LIVE_214_CLOUDFLARE_ORIGINAL_ACCEPTANCE', json.dumps(output, sort_keys=True),
          flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=('mimmi', 'yui'), required=True)
    main(parser.parse_args().model)
