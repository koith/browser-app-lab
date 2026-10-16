# 4LEAF source-registered actor and DMP tile painter depth — 2026-10-16

## Original source and screenshot
Each true `ORIGINAL_LEAF_MAPS` DMP record supplies grid position and a source cell code. Tile planes are recovered 145×97 original `Tiles/*.png`, separated by the real 70×47 grid. Original `Registry/savaNN.png` actor images are 75×141 and are separately rendered as actual player standees. Source screenshot `apps/4leaf/assets/board.jpg` shows actors behind some nearer raised tiles.

Prior reconstruction painted ALL actors inside a separate parent `#board-pawns` above the whole `#board-nodes` tile layer. Old CSS had a full-layer z-index 8 and each character z-index 10, so source DMP cell painter depth did not affect foreground tile occlusion. It also drew a giant animated invented cyan oval under each avatar. This looked unlike original 3D spatial rendering.

## Implemented live rendering
`drawBoard()` preserves the existing source sprite pawn DOM across real tile redraws and nests `#board-pawns` in `#board-nodes`. `dice-native-pawn-dmp-depth.css` uses `display:contents` for this wrapper so it introduces no stacking context; actors and original native TIS sprite cells now share ONE actual painter-depth plane. `drawPawns()` reads the actual DMP tile's existing `style.zIndex`, and assigns the real actor exactly that integer plus one: above its own tile, underneath nearer source platforms. Moving/warping/resuming recomputes depths from genuine current game positions. This is more faithful 2.5D without manufacturing missing native height data.

CSS removes the invented turquoise oval and pulsing rune under actors, replacing it with a small nonblocking dark cast shadow (INFERRED browser visual, not source bitmap). All original Registry standee pixels and named actual players persist. No source actor animation is invented.

## Alpha source correction
Public Chromium decoded actual original PNG 0000 with corner alpha=0: many files were **already transparent** and only appeared pink/red/green in some thumbnail viewers. Previously treating all source TIS as opaque chroma key was incorrect. Now `dice-native-tis-alpha.js` retains original source URLs and pixels whenever `removed=0`. Only a demonstrably opaque exterior region gets masked. The per-source actual alpha-derived clickable contour remains. Existing tests in board-layout, dice-native-frame and dice-native-tis-depth were adjusted to accept exact original preserved PNG or truly masked data PNG based on source pixel facts.

## QA
`tests/dice-native-pawn-dmp-depth.cjs` runs a real browser 2-human hotseat match with 104 actual DMP tiles. It checks original actor assets loaded, presence only of actual two participants, tile/z depth equality, source characters behind nearer platforms, real game rendering through scene rebuild, actual zoom/movement, mobile and no errors. `tests/dice-native-tis-alpha.cjs` verifies six source image RGBA samples and preserves images where alpha already exists.
GitHub Actions world/chat, 25-map archive, original board layout and post-deploy public Pages all check this. PWA v50 precaches new CSS and source decoder.

## Honest limitations
No recovered original MVE elevation mesh, lighting vectors, 3D camera pitch, actor skeleton/action frames or EXE exact z-sort. DMP y painter order and subtle shadow are INFERRED browser restoration from VERIFIED DMP planar coordinates and original screenshots. This is a functional visual improvement, not finished 3D restoration.