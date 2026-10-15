# Native 4LEAF Recordable / KnightTown six-region restoration (2026-10-16)

## Original resource classification — important correction

The native client archive contains **three different systems**; do not mix them:

| Original source | 794×404 role | Original evidence |
| --- | --- | --- |
| `ChatTown/northback.png`, `southback.png` | Eight North/South Haiacan chatting districts | Native drawn wooden signboards and names |
| `KnightTown/knightback.png` | **Six Recordable/KnightTown regional destinations** | Original illustrated snow/forest/sea panels, region names, independent sprites |
| `Map/mapback.png` | Genesis World **Dice ROOM SELECT** | Explicit 주사위의 잔영 / dice graphics, original CREATE/JOIN controls |
| `Region/regionback.png` | Genesis World **Dice TOWN SELECT channel list** | Seven dice channels, independent from both social destinations |

It is **incorrect** to interpret `Map/mapback.png` as the Haiacan chat room list. That image is *already* correctly used by the existing Dice lobby. This correction follows inspecting the actual original pixel atlas; it supersedes an earlier premature identification. **VERIFIED-ARCHIVE**.

## Verified Recordable original source

- `KnightTown/knightback.png` **794×404**, intact six signboard backdrop, has its own source region title and background art. The previous webapp linked the WorldMap Recordable hotspot directly to a synthetic `RECORDABLE` bulletin with unrelated `WorldMap/worldmapback.png` graphics and did not render this authentic KnightTown scene at all.
- Six independent recovered `KnightTown/{sea01,sea02,sea03,snow01,plain01,plain02}.png` atlases measure **568×74**, four visual states of **142×74** per atlas, corresponding to:
  - `sea01`: 모험의 바다
  - `plain01`: 패왕의 대지
  - `snow01`: 침묵의 설원
  - `sea02`: 도전의 바다
  - `sea03`: 찬란한 바다
  - `plain02`: 영광의 대지

**VERIFIED-ARCHIVE:** Source images, literal region names, native pixel dimensions and the four-state sprite layout.

**INFERRED REGISTRATION:** Button hitboxes and hover sprite anchors are approximated from the recovered composited `knightback.png` at 794×404. Region click actions in the original server are not available; the existence of a region selection does *not* prove the 2002 room estate data protocol.

## Code changes

- Original WorldMap `knights` region now enters its own `knighttown` view rather than skipping the screen. `knighttown-native.js` renders the recovered **original PNG** with six separate semantic, keyboard/touch-clickable hotspot buttons. `knighttown-native.css` uses an authentic independent 568×74 sprite atlas on each sign's hover/pressed/focus state, not an old screenshot or a fabricated modern list.
- The KnightTown view scales on its own **794×404** logical source coordinate system, independent of ChatRoom's **794×528** and the Dice ROOM SELECT. The adjacent ChatRoom roster never blocks the source map.
- Choosing one of the six native Recordable regions exposes the **previously existing functional web bulletin** with actual local/tab-shared user posts. It is explicitly **WEB RECONSTRUCTION**, not a claim that an archival source screen or original server behavior for that interior has been recovered. The true historic regional room estate and protocol remain unverified. Back returns first to the real six-sign scene, then to the WorldMap. Toolbar access to the existing bulletin remains available.
- `sw.js` v43 precaches all seven original KnightTown bitmaps and related JS/CSS so even the first offline visit shows the real original art.

## Verification

- `tests/knighttown-original.cjs`: Chromium native 794×404 bitmap, all six distinct source atlas PNGs and 142×74 states, actual focus/click functionality, real bulletin, correct two-step back navigation, zoom/mobile and no fake occupants or Dice art.
- `tests/world-chat.cjs`: existing 2-browser Recordable create/view data now travels via the native six-region page; rest of ChatTown, WorldMap, WebRTC and Dice unaffected.
- `tests/native-offline-cache.cjs`: first offline KnightTown visit and original snow area navigation.
- PR and public GitHub Pages workflows include the new tests and source assets.

## Remaining work

Native KnightTown room estate contents, character model motion, six-region server chat rooms, native post operations, exact hover sprite pixel registration and source-era occupancy are not recovered. This is a real original *regional navigation scene*, not completion of all Recordable gameplay.
