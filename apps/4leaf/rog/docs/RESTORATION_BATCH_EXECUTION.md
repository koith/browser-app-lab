# 4LEAF restoration — batch execution protocol

This document governs how the assistant and Claude divide independent
development, avoid one-ticket-at-a-time conversations and close actual
restoration tasks. The sole authoritative completion source remains
RESTORATION_LEDGER.json; this policy does not mark any item done.

## User goal and immutable priority

4LEAF is first and foremost a **multi-user chat community**. The dice game
("주사위의 잔영") is a child application, not the hosting system.

Do not ask the user to approve individual safe/reversible code choices. One
user instruction to continue means: complete the next feasible dependency
chain and its tests, then proceed to the next task in the same working turn.

No agent should claim that work continues after the conversation stops
unless a real scheduled automation, GitHub Action or other asynchronous
runtime has been created and its execution verified.

## Responsibility split (avoid cross-edits)

* Claude: original ChatRoom screenshots, six backgrounds, seats, avatar
  source graphics, foreground occlusion, visual CSS and source-backed
  rendering evidence (CHT-02/04/05 visual acceptance).
* GPT: server-side persistent state, real session/owner/moderation security,
  message delivery, network recovery, cross-browser real-user tests, CI,
  production Pages/Render verification, and safe deploy gates.
* Integrate on **latest main** after each independently tested batch.
  Do not edit the other track's changed files without rebasing and
  announcing the coordination reason in the PR.

## Dependency-led development batches

1. **Core chat continuity:** authenticated server authority, cloud persistence
   adapter, encrypted restore, restart proof, free-host wake/reconnect.
2. **Chat trust and delivery:** abuse controls; session owner/moderation;
   idempotent message acknowledgement; ordered, room-scoped history.
3. **Original chat UI acceptance:** compare all six native rooms and actual
   controls/avatars against source evidence; verify multi-user WebKit/Chromium.
4. **Chat-first navigation:** WorldMap -> Region -> directory -> room ->
   connected real peer; return navigation without losing session.
5. **Child game unblock:** start Jujan from the chat platform, preserve
   saved games, original dice/board/actors, real two-turn and game completion.
6. **Final acceptance:** exact published SHA/asset version, live HTTPS chat,
   multi-user real browser testing, mobile WebKit + explicitly labeled
   physical-device status, original evidence reconciliation.

A batch is normally 3–8 dependent fixes and tests. It may contain one
large high-risk migration. Avoid a separate PR for every small mistake.
Do not bundle server schema changes with another service's production DB.

## Verification levels and finish rules

* VERIFIED: actual source/commit/test/log inspected. Keep exact SHA and
  commands or CI link; distinguish mocked DB tests from real project cutover.
* INFERRED: supported implementation behavior without direct live proof.
* UNVERIFIED: pending production or physical original comparison.

Do **not** mark a task done merely because code was merged:
1. Requirement traced to ledger id and exact original evidence.
2. Implementation and negative-path tests actually pass.
3. Safe peer/user acceptance passes (2 browsers and mobile WebKit if relevant).
4. PR merged to main; conflicting/failed paths disclosed and fixed where in scope.
5. Public deployed asset/sha verified when user-facing; do not conflate
   successful GitHub Actions with live site functionality.
6. Ledger status/evidence updated via the canonical ledger command, with
   REQUEST_REGISTERED event for every new intake. The ledger must pass its
   append-only CI gate.

## CI cost and queue discipline

Fast checks first: syntax, narrow Node tests, targeted Chromium smoke.
Full WebKit, 10 real peers, archived source audits and visual/battle suites
are release gates for relevant batches. The repository's existing full
checks must NOT be disabled merely to make a PR green.

Workflows for the key high-cost 4LEAF suites now cancel only **superseded
pull-request revisions**. Main push checks are keyed by immutable commit SHA
and are not cancelled. Pages has its own independent concurrency policy;
do not change Pages production deployment strategy in this protocol.

When a workflow fails: inspect the failing log and identify whether it is
regression, known unrelated failure or flaky infrastructure. Do not repeat
the same failed tool call indefinitely. Fix or clearly isolate the failing
gate. Never mark a failed live acceptance as success.

## User reporting

Report once per meaningful batch, not after each minor commit. Always show:
* Closed task IDs (only actually accepted ones)
* Newly merged PRs, commit SHA, live published version if verified
* PASS/FAIL breakdown for server, Chrome, WebKit and actual production
* Blockers requiring cost/security/credentials/irreversible approval
* Next batch automatically selected by dependency/priority

The initial 60 ledger tasks (13 done / 47 not done at time of writing)
contain overlapping umbrellas; count is backlog accounting, not a
scientific measure of actual restoration fidelity. Do not fabricate
completion percentages or a delivery date without measured throughput.
