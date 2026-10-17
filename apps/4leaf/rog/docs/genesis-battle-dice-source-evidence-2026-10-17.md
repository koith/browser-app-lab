# Original Genesis duel: real six-sided dice and legible pip faces (2026-10-17)

## Historical screenshot and archive status

- The original **2004-02-11** battle screenshots `apps/4leaf/assets/board.jpg` and `battle.jpg` show independent **three-dimensional white six-sided dice** beneath the duel podiums. Black circular pips and a distinctive pink/red **single center pip** are clearly visible, with light faces, side thickness and cast shadows.
- **VERIFIED-SCREENSHOT:** pip topology, relative white/gray/black/pink palette, placement below each platform and full participant battle scores.
- **UNVERIFIED:** The exact original die mesh, die texture atlas, random roll tween and old engine's light direction. `original/IMG/` has no separately recovered 3D dice texture or mesh. Do not fabricate original texture file or render historical `battle.jpg` as the playable stage.

## Previous visible disparity

The previous `game.js::showBattleScene()` displayed the real rolled values using the Unicode symbols `⚀⚁⚂⚃⚄⚅` in generic 33px gradient boxes. Their shape varied by OS/browser font and did not reproduce the source screenshot's actual dark dotted white cube faces. This was plainly visible in every combat encounter.

## New source-grounded functioning stage

- **Actual existing** `combat()` player dice arrays are still the only source of face numbers and the full score calculation. `showBattleScene()` creates exactly one independent DOM white die per REAL rolled value, with semantic `data-eye=1..6` and accessible labels.
- Each die paints original-reference pip arrangements on a 3×3 CSS grid: 1=center, 2=top-left/bottom-right, 3=diagonal, 4=four corners, 5=corners+center, 6=two left/right columns. Its 3D white/gray thickness and shadow are source-picture-inspired CSS. The single-eye center uses the distinctive pink color from the original historical screenshot; other spots are dark.
- The CSS is **INFERRED 2.5D material reconstruction**, NOT a verified original mesh. There are no screenshots pasted beneath dummy controls, fake battles, or fabricated dice. Actual source `Registry/savaNN.png` actor sprites and existing independent mechanical podiums remain intact above the original `IMG/bgtile.png` forest.
- Responsive 26px dice on 390px devices preserve pip count and gameplay; desktop 42px approximates photo proportions. Confirmation action and real match turn/position data are unchanged.

## Browser and PWA verification

`tests/dice-native-battle-dice.cjs` opens a genuine 2-person hotseat game, requests actual `resolveBattle()`, checks real participant names and correct two-digit scores, verifies every die's literal current value, individual pip count and exact grid positions, source photo reference label, absence of Unicode glyphs, white face shading, 390px mobile layout, post-battle real gameplay resume and zero JS errors. Other source DMP/pawn/browser/WebRTC tests run unchanged.

PWA v55 precaches `dice-native-battle-dice.css`. Local source archive, world-chat integration, and public Pages Chromium tests all exercise this independent real encounter.

## Remaining major gaps

Exact historical 3D battlefield, level height meshes, posed full-body attacker/defender animations, original particle effects and native die tumbling are NOT recovered. This is one concrete photographed combat-visual discrepancy removed without claiming original-engine parity.
