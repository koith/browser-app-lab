# 4LEAF Genesis World native dialog and event-message sources — 2026-10-16

## Extracted original graphics (VERIFIED-ARCHIVE)

- `original/IMG/dialog.png` is **292×110**. The recovered bitmap is a pale original game dialogue frame with a blue top border and small centered title marker; it contains no static option text or users.
- `original/IMG/eventmsgbox.png` is **244×52**. The recovered bitmap is a separate softly shaded violet/blue original event-message field, with no prerecorded event text.
- Both are independently recovered sources; do not paste `board.jpg` or `battle.jpg` into the playable UI.

## Implemented real gameplay connection

- `game.js::modal()` now marks only **simple, genuine Genesis-game text prompts with one to three actual buttons** as native-source dialogues. Game exit confirmation and charged ability activation use the real bitmap. Complex participant lists, multi-card ability menus, battle-result images and other structured content **keep their own full-size UI and never get clipped to 110px**.
- `dice-native-dialog-event.css` uses CSS **nine-slice** borders from the recovered 292×110 picture: top source band, corners and pale interior remain from the image while live text and HTML action buttons vary. No fake screenshots or dummy button proxies.
- `#move-log` still stores the existing real game event line, but the old modern `.item-bar` footer is **hidden** in the 2003 source-native game view, so decorating that element did not produce a visible panel. Instead `game.js::syncNativeDiceEvent()` mounts exactly one live `#dice-native-event` `<output>` directly inside the **visible `#board-area`**, on its own pointer-transparent layer. Its current text is supplied only by real match events in `toast()` and real `match.message` from `drawGame()`; the actual original **244×52 `IMG/eventmsgbox.png`** source is the backing. Full message is retained in `title` and real `match.history` while source-size rectangle clips only visual paint, not game data.
- All logic remains in existing action/turn/rollback and multiplayer code paths; `IMG/dialog.png` has **no source binary metadata proving a specific modal action**, so the association and nine-slice widths are **INFERRED WEB RESTORATION**, not a claim about exact old window bitmaps.
- Other WorldMap, KnightTown, ChatRoom, Magic Carden and Dice menu sprites remain unchanged; service-worker v45 caches both original bitmaps and this CSS.

## Automated QA

- `tests/dice-native-dialog-event.cjs` starts an actual two-participant AI game, verifies original natural image dimensions, real EXIT confirmation and Cancel without losing the match, exclusion of complex player-info modals, real dice roll / persisted match-history-backed event text inside recovered event artwork, actual ability confirmation, mobile viewport and no page errors.
- Existing map, battle, turns, save/resume, live WebRTC, ChatTown and restored KnightTown regression suites run independently. GitHub Pages post-deployment Chromium tests check the same real original-source elements.

## Remaining original differences

Native MVE 3D character meshes, actual combat camera/particles, original server-side match catalogue and full source protocol are **not** restored. This work corrects a real visible game overlay but does not imply 3D-engine parity.
