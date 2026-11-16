#!/usr/bin/env python3
"""Regression: reverse SHA checkpoint commits before independent network work.

The previous workflow called source_alias_search before saving the reverse
cursor. A slow name/source lookup could discard hundreds of completed image
searches and trigger expensive duplicate calls on the next scheduled run.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
workflow=(ROOT/'.github/workflows/gallery-full-missing-public-collection.yml').read_text()

stages={
    'reverse': workflow.index('      - name: Search ALL owned photo SHAs'),
    'checkpoint': workflow.index('      - name: Persist reverse-search progress before ANY downstream network research'),
    'sources': workflow.index('      - name: Discover edition-specific public source pages'),
    'source_checkpoint': workflow.index('      - name: Persist source-page review cursor so unvisited image leads survive across runs'),
    'collect': workflow.index('      - name: Acquire every registered work'),
}
assert (stages['reverse'] < stages['checkpoint'] < stages['sources'] <
        stages['source_checkpoint'] < stages['collect']), stages
assert 'ALL_OWNER_PHOTO_REVERSE_CURSOR_PERSISTED_AND_READBACK' in workflow
# Every material change to visual backend must replay all previously scanned
# SHA records. A v3 exhausted cursor must NOT strand the new v4 engine.
assert '--search-revision 4' in workflow, 'new Bing PagesIncluding would never query old records'
assert '--search-revision 3' not in workflow
assert 'SOURCE_ALIAS_SEARCH_UNAVAILABLE' in workflow
assert '--reverse-progress "$STAGE/reverse-next.json"' in workflow
assert 'GALLERY_SOURCE_BACKLOG_DURABLY_SAVED' in workflow
assert 'GALLERY_SOURCE_BACKLOG_READBACK_MISMATCH' in workflow
assert "old.get('search_revision')==report['search_revision']" in workflow
assert 'timeout 420s python apps/gallery-archive/source_alias_search.py' in workflow
assert 'source_alias_status' in workflow
assert 'continue_until_exhausted:' in workflow
print('GALLERY_REVERSE_PROGRESS_DURABLE_BEFORE_OPTIONAL_ALIAS_AND_COLLECTION_PASS',stages)
