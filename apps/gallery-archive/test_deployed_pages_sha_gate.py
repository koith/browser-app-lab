#!/usr/bin/env python3
"""Reject post-Pages QA that confuses newest main with deployed source SHA."""
from pathlib import Path

wf = Path(__file__).resolve().parents[2] / ".github/workflows/gallery-first-image-metrics.yml"
text = wf.read_text(encoding="utf-8")
assert "workflow_run.head_sha == github.sha" not in text
assert "workflow_run.conclusion == 'success'" in text
assert "workflow_run.head_repository.full_name == github.repository" in text
assert "workflow_run.head_branch == 'main'" in text
assert "git rev-parse HEAD" in text
assert "workflow_run.head_sha" in text
assert "--verify-progressive" in text
print("GALLERY_POSTDEPLOY_TRUSTED_EXACT_SHA_NO_MONOREPO_RACE_PASS")
