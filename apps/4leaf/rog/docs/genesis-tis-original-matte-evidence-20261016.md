# 4LEAF Genesis TIS original chroma matte restoration — 2026-10-16

## Source evidence
The recovered `original/Tiles/0000.png` and `0001.png` are genuine 145×97 sprites with pink/salmon outer mattes. `original/Tiles/0015.png` has a red outer matte. These backgrounds are not part of the raised platform. Historical `apps/4leaf/assets/board.jpg` shows overlapping raised game spaces without opaque red/pink rectangles.

Previous `game.js::drawBoard()` rendered these raw PNG backgrounds directly. The static six-vertex clip in `dice-native-tis-depth.css` approximated source geometry but could clip parts of original sprite details. The 145×97 source-size change from PR #80 is preserved.

## Rendering change
`dice-native-tis-alpha.js` decodes each UNIQUE 145×97 source bitmap into RGBA pixels once. A bounded flood-fill begins along the source image perimeter and removes only exterior pixels matching that specific PNG's corner matte. It NEVER removes every red/pink interior pixel, protecting the authentic source game symbols. The original survivors' RGB/alpha remain byte-for-byte unchanged.
Every preexisting, independent DMP-linked live tile uses the cleaned source sprite. A multi-vertex click polygon is derived from visible source alpha rows, rather than imposing the same guessed six-point hex on all 32 original source pictures. Native grid pitch, source DMP cell indexes, true 145×97 dimensions, world camera, live pawns and game rules are untouched.

**VERIFIED-ARCHIVE**: bitmap identities, source dimensions and opaque red/pink external colors. **INFERRED WEB RESTORATION**: old EXE's exact chroma-key tolerance, native alpha hit-test and shading are unknown; the decoded exterior matte and row polygon are honest reconstructed browser methods, not proved byte-identical engine instructions.

## Reliability and tests
Source PNGs load independently with bounded retries. If file:// browser security forbids canvas `getImageData()`, existing source sprite and polygon fallback stay playable. On same-origin HTTP(S) and cached GitHub Pages, the recovered true-alpha sprite displays. PWA revision v49 caches the renderer and original TIS sprites.
`tests/dice-native-tis-alpha.cjs` checks a genuine 4LEAF match's 104 live DMP cells, central source pixels unchanged, outer source alpha removed for both pink and red source examples, asset cache reuse, character turn, pan/zoom and mobile. It also checks file-origin fallback. Regression runs in archive, world/chat and published Pages Chromium jobs.

## Unfinished original parity
Unrecovered MVE 3D terrain meshes/elevation, real 3D camera/lighting and full-body attack animation remain incomplete; this repair is one substantial visible original-graphics discrepancy, not the completion of the 3D engine.