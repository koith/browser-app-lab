"""Keep user-confirmed wrong-model sources out of future imports."""
import json
from pathlib import Path
POLICY=Path(__file__).with_name('identity-exclusions.json')
def is_excluded(album_id,source_urls,images):
    policy=json.loads(POLICY.read_text())
    return (album_id in policy['excluded_album_ids'] or album_id in policy['excluded_source_ids']
            or bool(set(source_urls)&set(policy['excluded_source_urls']))
            or any(p.get('sha256') in policy['excluded_image_sha256'] for p in images))
def ensure_allowed(album_id,source_urls,images):
    if is_excluded(album_id,source_urls,images):raise ValueError('Wrong-model source or image rejected by identity policy')
