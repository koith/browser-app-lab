# Restoring full-size original Genesis World TIS raised platform geometry — 2026-10-16

## Verified original resources

- Recovered `original/Tiles/0000.png`, `0015.png`, `0024.png` and other original TIS tiles have **145×97 native PNG** size, with **their own already-painted hexagonal raised 3D-style rim and event artwork**. This is **VERIFIED-ARCHIVE**.
- Original `original/maps.js` contains **25 DMP map routes** of integer grid records `[x,y,cellCode,action,param,warp]`. `game.js::chooseSourcePath()` maps consecutive original integer grid columns to **70px horizontal** and **47px vertical** logical steps inside the 1450×1120 world. The source `cellCode` is preserved but its specific old executable interpretation/elevation role is **not verified**.
- Historical `apps/4leaf/assets/board.jpg` contains prominent overlapping raised hexagonal original tile planes around the forest and chessmen; the larger footprint matches the retained extracted native artwork. The original real 3D renderer mesh/projection is still unavailable.

## Significant old discrepancy

The revival's `dice-native-tis-clean.css` deliberately rendered every **145×97 original bitmap at 70×47**, half the source width and height, on exactly the same **70×47 map grid pitch**. This produced a separated field of miniature game tiles. It removed the close-fitting, overlapping raised-platform original-board appearance and substantially downsampled genuine source art.

## Implemented restoration (source pixels verified; 2D painter order inferred)

- `game.js::drawBoard()` keeps the same real DMP-backed tile data, player positions and event click handlers while registering each actual source grid `x,y,cellCode` and a source-based `data-native-tis-size=145x97` on its independent actual tile DOM node.
- New `dice-native-tis-depth.css`, loaded after previous half-size styles, renders the original sprite **145×97 logical px at 1:1** with the existing source-backed background image. It keeps the original rectangular PNG independent and uses a **visually inferred regular hexagon clip** to restrict pointer events to the artwork silhouette, avoiding invisible overlapping corner hitboxes. The exact original hex polygon edge pixels and click mask remain **INFERRED**, not decoded EXE hit detection.
- Neighboring DMP cell centers stay spaced by **70×47**. A 145×97 original raised platform therefore correctly overlaps its neighboring real tiles. Per-tile stacking follows the actual DMP vertical screen coordinate (greater y paints in front) while preserving the independently loaded `Registry/savaXX` actors above the platform layer.
- This is **not** an invented mesh, fake stacked screenshot, or a claim that full 2003 real-time 3D lighting/elevation was recovered. Original `IMG/bgtile.png` forest, UI frame, live party, dice, map logic, ability, items and camera continue functioning.
- All **32 recovered actual TIS PNGs** plus this stylesheet are included in PWA cache v48, so original full-size hex art also survives first cold-offline game entry.

## Verification

- `tests/dice-native-tis-depth.cjs` uses real Chromium and an actual 4LEAF 104-cell match to decode original PNG dimensions, enforce **145×97 full-size DOM draw pixels for all 104 cells**, check real original DMP grid coordinates and live map cell codes, verify source PNG URI, real clickable cell handlers, hex clip, **physically overlapping** adjacent tile planes, DMP screen-depth sorting, original terrain and real player count, actual zoom and narrow mobile.
- `tests/dice-native-frame.cjs` now rejects the previous 70×47 half-size layout as a regression, in addition to original 800×600 game frame and true 145:97 aspect.
- `tests/native-offline-cache.cjs` verifies a brand-new **offline** 4LEAF match draws native 145×97 original PNGs.
- GitHub Actions original archive coverage, local WorldMap/ChatRoom and public Pages Chromium suites separately run this test after real deployed source CSS is byte-matched.

## Remaining major gap

The original Genesis World used **real 3D platform meshes, lighting and camera**, and original standing 3D chessmen/characters with attack particles. The web revival still uses authentic 2D source artwork and an inferred 2D painter order; neither this source-size correction nor the arena CSS podium should be marked as a full 3D renderer reconstruction. A historically faithful true 3D subsystem remains highest-priority P1.
