# 4LEAF original MainFrame native toolbar restoration — 2026-10-16

## Source evidence (VERIFIED-ARCHIVE)

Actual 4LEAF client `original/MainFrame/toolbarbtn.png`: **120×270** PNG, an independently extracted original UI component, **four 30px horizontal states** and **nine 30px icon rows**. The final (ninth) 30px row visually contains **OUT**, and the seventh/eighth rows contain camera and question-mark imagery. This is not a screenshot of a completed scene. Its same source frames already power working controls in `social-chat.js::addClassicRoomToolbar()`, and the ninth OUT frame is used in `dice-native-menu-chrome.css`.

`original/MainFrame/pannel.png` is an independently recovered **323×124** blue, softly patterned source tile. `original/MainFrame/title.png` is the existing **680×54** authentic blue 4LEAF wordmark strip. The previous top-level `index.html` global toolbar remained an oversized 49px modern gradient navbar with emoji glyphs despite those recovered sources already being available.

The 2004-02-11 archived **794×528 ChatRoom screenshots** `apps/4leaf/assets/chat.jpg`, `chat_ref.jpg` show a ChatRoom game-scene crop rather than the global client menu. They do not establish that the MainFrame toolbar was overlaid on the captured 794×528 **scene area**. This change deliberately keeps navigation **outside** the historic scene, not as a screenshot-sized fake overlay.

## Reconstructed navigation (source imagery verified; specific command mapping INFERRED)

`mainframe-native-toolbar.css` now displays all **eight pre-existing interactive route/utility HTML buttons** directly from original `toolbarbtn.png` sprite rectangles, each at unscaled 30×30 pixels:

| Existing web-app action | Original row (zero-indexed) | Source position |
|---|---:|---:|
| World map | 0 | 0px |
| Keltica street | 2 | -60px |
| Haiacan chat | 3 | -90px |
| Magic Carden | 4 | -120px |
| Genesis Dice | 1 | -30px |
| Account nickname editor | 6 | -180px |
| Background audio toggle | 5 | -150px |
| Help | 7 | -210px |

The exact old EXE dispatch for **each** toolbar icon is not recovered. Some icons may historically have meant a different action. This is an explicitly labeled web UX mapping to avoid lying about historical input semantics. The original pixels and four-frame atlas geometry are real.

All buttons keep their previous native `<button>` DOM, actual `data-route` or existing event callbacks, accessibility labels, keyboard focus, mouse/pointer and mobile touch. Native atlas columns: x=0 resting, x=-30 highlighted/focused, x=-60 pressed, x=-90 disabled; the active nav uses the source x=-30 state, replacing fake bright turquoise box shadow.

The 323×124 source `pannel.png` replaces the fabricated purple bar background. Row height is now **36px desktop, 34px mobile**, instead of 49px, while the original title strip and all WorldMap (796×528), ChatTown (794×404), ChatRoom (794×528), Keltica, Magic Carden and Dice interactions remain independent and functional. The developer-facing location string remains available at larger widths and hides only on narrow viewports so all eight genuine buttons remain reachable.

## Tests and preservation

- `tests/mainframe-native-toolbar.cjs`: real Chromium decode of the native 120×270 atlas, 323×124 panel and existing 680×54 source title; all eight real 30px HTML controls, independent icon rows, no visible emoji paint, hover frame, 36px chrome, WorldMap/Street/ChatTown/Shop/Dice/Help/rename functional navigation and 390px mobile clickability.
- Both the local/world-chat integration job and the post-deploy **public GitHub Pages** Chromium job execute this regression.
- PWA cache **v46** precaches the original atlas, panel and stylesheet. `tests/native-offline-cache.cjs` verifies decoded source art and restored interactive button sizes on a **cold offline boot**, while existing WorldMap, peer chat, original ChatRoom, KnightTown and game tests still run.

## Limits

No original EXE callback-to-icon command table or source toolbar absolute screen coordinate layout has been validated. The first-party PNG artwork is verified, but routing assignment and web window dimensions remain reconstructed. The 3D Genesis level meshes and missing historic chat-world architecture remain unsolved and are **not** claimed restored here.
