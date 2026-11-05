#!/usr/bin/env python3
"""Static fail-closed workflow policy: session refresh ≠ 214 originals present.

Keep GH Actions workflow semantic checks independent of live TeraBox service.
"""
from pathlib import Path

workflow=Path(__file__).resolve().parents[2]/".github/workflows/gallery-terabox-render-session-sync.yml"
source=workflow.read_text()

def action(name):
    anchor="      - name: "+name+"\n"
    assert source.count(anchor)==1,(name,"step missing or duplicated")
    piece=source.split(anchor,1)[1].split("      - name:",1)[0]
    return piece

ready=action("Lightweight complete-owner readiness check (214 originals, no downloads)")
assert "if:" not in ready.split("shell:",1)[0], "Non-schedule events skip 214-photo readiness"
assert "probe_private_owner_runtime.py" in ready and "healthy=false" in ready

session=action("Securely refresh Render storage session without exposing cookies or viewer passwords")
assert "continue-on-error: true" in session
assert "steps.ready.outputs.healthy != 'true'" in session
assert "verify_render_gallery_read.py" in session

for name in (
 "Install the existing checksum-pinned owner storage client for read-only rescue",
 "Recover existing same-owner SHA images without any new collection or storage writes",
 "Reject partial 214-photo rehydration after any successful session refresh",
):
    step=action(name)
    assert "if: steps.ready.outputs.healthy != 'true'" in step,(name,"rescue gated incorrectly")
    assert "steps.direct_owner_session.outcome" not in step,(name,"refresh success must not skip 214 originals")
    assert "github.event_name == 'schedule'" not in step,(name,"all event types must restore")

recover=action("Recover existing same-owner SHA images without any new collection or storage writes")
assert "restore_known_owner_cache.py" in recover
last=action("Reject partial 214-photo rehydration after any successful session refresh")
assert "probe_private_owner_runtime.py" in last
assert "LIVE_EXACT_214_RAM_READINESS_CONFIRMED_AFTER_SIGNED_RESCUE" in last

assert "cancel-in-progress: false" in source,"No interruption of in-progress owner photo writes"
print("SIGNED_SYNC_ALL_EVENT_TYPES_REQUIRE_214_EXACT_ORIGINALS_PASS")
