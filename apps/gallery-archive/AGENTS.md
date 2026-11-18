# Shared Yui/Mimmi gallery collection and QA

This directory hosts shared photo acquisition, resume checkpoints, deployment and browser QA for G-03 (Mimmi) and G-12 (Yui).
- Read `../../docs/gallery-archive/DEVELOPMENT-RUNBOOK.md` and only current issue https://github.com/koith/browser-app-lab/issues/605.
- Read `../yui-gallery/AGENTS.md` or `../mimmi-gallery/AGENTS.md` for the model being changed.
- Pick a missing real album; compare existing physically stored SHA and official album requirements before collecting.
- Validate newly acquired bytes, image decoding, SHA, quality, non-destructive manifest update, deployment and actual browser display. Count 0 new saved photos as 0 progress.
- If one source fails repeatedly (403/502), test a materially different lawful source; do not requeue identical attempts blindly.
- Limit tool output to changed files, evidence and counts; no full history, large JSON or all CI logs in chat. Never restart unwanted scheduled autonomous development.
