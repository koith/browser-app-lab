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
    'collect': workflow.index('      - name: Acquire every registered work'),
}
assert stages['reverse'] < stages['checkpoint'] < stages['sources'] < stages['collect'], stages
assert 'ALL_OWNER_PHOTO_REVERSE_CURSOR_PERSISTED_AND_READBACK' in workflow
assert 'SOURCE_ALIAS_SEARCH_UNAVAILABLE' in workflow
assert 'timeout 540s python apps/gallery-archive/source_alias_search.py' in workflow
assert 'source_alias_status' in workflow
assert 'continue_until_exhausted:' in workflow
print('GALLERY_REVERSE_PROGRESS_DURABLE_BEFORE_OPTIONAL_ALIAS_AND_COLLECTION_PASS',stages)

# Execute the actual shell handoff block, using harmless fake git/gh/sleep.
# This checks that checkpoint-only writes never request deployment, a saved
# gallery requests it, and a rejected dispatch is retried and fails closed.
import os
import subprocess
import tempfile
import textwrap
start=workflow.index('            gallery_changed=0')
end=workflow.index('            sleep 3', start)
block=textwrap.dedent(workflow[start:end])
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    log=tmp/'gh-calls'
    (tmp/'git').write_text("""#!/bin/sh
case "$1" in
diff) exit "$DIFF_EXIT";;
push) exit 0;;
rev-parse) echo 0123456789012345678901234567890123456789;;
*) exit 99;;
esac
""")
    (tmp/'gh').write_text("""#!/bin/sh
echo "$*" >> "$CALL_LOG"
test "$(wc -l < "$CALL_LOG")" -gt "$FAIL_COUNT"
""")
    (tmp/'sleep').write_text('#!/bin/sh\nexit 0\n')
    for name in ('git','gh','sleep'):
        (tmp/name).chmod(0o755)
    env={**os.environ,'PATH':str(tmp)+':'+os.environ['PATH'],
         'MODEL':'yui','GITHUB_REPOSITORY':'example/repo',
         'GITHUB_STEP_SUMMARY':str(tmp/'summary'),'CALL_LOG':str(log)}
    for diff_exit,fail_count,expected_status,expected_calls in (
        (0,0,0,0), (1,0,0,1), (1,2,0,3), (1,3,1,3),
    ):
        log.write_text('')
        proc=subprocess.run(['bash','-euo','pipefail','-c',block],
            env={**env,'DIFF_EXIT':str(diff_exit),'FAIL_COUNT':str(fail_count)},
            capture_output=True,text=True)
        calls=log.read_text().splitlines()
        assert proc.returncode==expected_status,(proc.returncode,proc.stdout,proc.stderr)
        assert len(calls)==expected_calls,calls
        assert all(call=='workflow run static.yml --repo example/repo --ref main'
                   for call in calls),calls
print('GALLERY_SAVE_PAGES_HANDOFF_SHELL_REGRESSION_PASS 4 cases')
