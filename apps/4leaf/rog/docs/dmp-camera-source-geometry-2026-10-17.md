# Original Genesis World DMP camera navigation restoration — 2026-10-17

## Source evidence vs unknown 3D height

- Original game routes: `original/maps.js` contains 25 known historical DMP route datasets. The first two integers are **source tile-grid positions** (VERIFIED-ARCHIVE); the third integer is a **source cell code**, not decoded as geometric elevation. No original `.mve`, full 3D mesh or terrain height-field exists in the extracted repository.
- The client still renders actual transparent **145×97** TIS source PNGs as independent clickable platforms, retains each DMP coordinate and raw third cell code, draws genuine Registry avatars sorted with DMP planar painter order and uses original **725×485** Dice `IMG/bgtile.png` forest underneath. These source pixels are not replaced.
- The live DMP-derived camera world is **1450×1120** pixels; the original game window shows only a portion of this world at a time. The previous `game.js` panning bound of `clientWidth*(zoom-1)/2` used the small display viewport, **not** actual 1450×1120 content. At 100% zoom or lower, all pointer pan was blocked even though most tiles were offscreen.
- Native 2003 mouse/keyboard bindings and 3D model matrices are **UNVERIFIED**. Pointer/wheel/keyboard/pinch UX below is a deliberate WEB RECONSTRUCTION for exploring the source geometry, not an assertion that the 2003 EXE used these exact controls.

## Implemented camera correction

- `board-camera.js` computes real camera travel boundaries from world width/height × zoom and the visible DOM viewport. `panBy(dx,dy)` clamps to the **actual source world bounds** and returns camera state. At any scale **0.65–2.4**, a player can visit the entire recoverable planar DMP route (no off-map black emptiness, no fake territory).
- The independent original **145×97** TIS platform click sprites are now visibility-culled by their **real scaled half-extents**, so the 145×97 image does not disappear while still partly visible at zoom 2.4. Pawn positions and game tile data remain unchanged.
- `game.js` now supports mouse/touch dragging, a two-pointer pinch, ordinary wheel magnification, the existing +/-/reset UI, and keyboard arrows/+/-/0 when the board has focus. Dragging does not start until a **5px threshold** so a simple platform click still works. Buttons, inputs, real mini-map and battle-player panels are excluded from grabbing the camera.
- Zoom buttons previously invoked `trackActivePawn()` without applying `mapViewport.zoom` to the camera during autotracking; this caused visible zoom controls to appear inert. They now update the camera's actual scale and then resume real pawn following.
- **Manual camera** persists across UI redraws within the same participant's turn; a genuine participant turn change/new match returns to pawn follow. A user may always choose the original reset control or press **0**. This uses the real `match.active` and match start identifier, never synthetic player position or server state.
- `dice-dmp-camera-controls.css` confines touch gestures to the real board and gives keyboard focus indication. It changes **no** historical TIS materials, source sprites, tile shape, game rules, or WorldMap/ChatTown scenes.
- PWA **v53** caches both camera code and touch stylesheet for real offline navigation.

## Browser verification

`tests/dice-dmp-full-camera.cjs` starts a genuine hotseat Genesis match, reads live camera and TIS sources, pans to both extreme DMP world edges, uses a physical mouse drag, arrow keys, normal mouse wheel, two-touch PointerEvents, original reset and zoom controls, 65–100% exploration and 390px mobile. The test also verifies real 145×97 source art, preserved DMP cell codes, unchanged participant turn and original playable tile count. The full source archive/ChatTown, central server and post-Pages Chromium regressions must remain green.

## Remaining work

The full original **3D tile height/mesh layout**, polygon winding, lighting, animations and camera projection matrices have not been extracted. Avoid deriving arbitrary fake elevation from the source third cell-code value, distorting the TIS original geometry, or claiming 3D completion before this data is recovered and checked against period screenshots/videos.
