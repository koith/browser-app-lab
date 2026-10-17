# 4LEAF Genesis World — original source minimap and live DMP camera (2026-10-17)

## Evidence levels and original comparison

**VERIFIED-ARCHIVE:** `original/IMG/minimap.png` is the actual separately extracted **172×152** Genesis mini-map client frame. Its inner playing surface contains NO burned-in game screenshot, dots or route; the genuine game minimap is dynamically painted. The current web app already uses a single live `<canvas id="mini-map-canvas" width="152" height="112">`, reparented by `dice-native-client-frame.js` without duplication, and underlying `original/maps.js` has extracted DMP route positions.

**VERIFIED-SCREENSHOT:** `apps/4leaf/assets/board.jpg` and `battle.jpg` show the source blue mini frame at the lower-left, with bright route cells and colored player indicators. The old web app restored the frame but disabled its pointer events and drew only a static wireframe route plus player dots. Exact 2003 click/drag gestures and minimap camera viewport rectangle are **UNVERIFIED** because no original executable input capture is supplied.

## Genuine data-driven functionality now restored

- `board-camera.js` maintains ONE real camera into the source-supported **1450×1120** DMP world. After the actual camera translation, clamp and scaling are computed, its real visible rectangle is derived as `(x,y,width,height)` normalized to world extent. New `focusRatio()` pans that same camera to user-selected source map coordinates and keeps real movement/turn data untouched. It does **not** make a fake second map.
- `game.js::drawMinimap()` paints a pale outlined actual-camera viewport into the existing original-backed Canvas, beneath true user dots and above actual DMP route lines. When any real zoom, pan, pawn-follow or viewport resize changes the world transform, the same renderer invalidates and redraws the original Canvas. Its viewport rectangle is **INFERRED WEB UX**; its world coordinates come from the real DMP camera, NOT random heights or fabricated 3D data.
- Clicking and dragging the source mini canvas navigates world coordinates. Pointer position is correctly mapped through the recovered mini canvas's internal **7px x / 10px y** route drawing inset and its CSS size. Mobile uses the SAME mini canvas, already reparented to the board; no duplicate source art or fake touch overlay.
- Keyboard Arrow keys move the minimap's focus; Home / 0 return genuine active-pawn camera following. Same-player UI updates preserve manually explored camera coordinates until the user follows again or the participant turn genuinely changes.
- `dice-native-minimap-navigation.css` removes the prior hard-coded `pointer-events:none` from genuine source map controls without changing restored `IMG/minimap.png` dimensions, clipping source art or breaking nearby chat/zoom controls.
- PWA cache **v54** includes the source navigation stylesheet. Original `IMG/minimap.png`, `board-camera.js`, `game.js` and all original DMP map / TIS assets remain in the existing cold-offline cache.

## Actual QA

`tests/dice-native-minimap-navigation.cjs` drives a genuine hotseat Genesis game in Chromium and checks the exact source 172×152 frame + the one 152×112 Canvas, viewport bounds from actual camera, desktop click and drag to far-away world points, unchanged real participant coordinates, focusable arrow navigation and Home recovery, zoom changing the correctly normalized camera rectangle, 390px mobile map access and no page errors.

`tests/native-offline-cache.cjs` additionally performs a REAL first-offline game minimap click and verifies that the DMP game world transform changed while pawn positions did not. PR and main-branch Chromium jobs run it locally and the public Pages job checks the published live webapp.

## Limits

The original client may have used a different camera frame and input gestures. These are clearly **WEB UX reconstructions**. Original MVE 3D scene meshes, elevation, lighting, original camera rotation/projection and actor motion remain **not recovered**. The third DMP cell code appears to distinguish hex-grid connectivity/orientation, and must NOT be used as made-up height without verifying the binary semantics. This work is functional parity progress, not proof of original 3D rendering parity.
