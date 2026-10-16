# Original 4LEAF Registry Avatar Select reconstruction — 2026-10-16

## Recovered assets and defects (VERIFIED-ARCHIVE)

The original Registry.pak contains **three independent original UI images**, previously unused by the recovered HTML avatar selector:

| Actual original file | Natural source bitmap size | Original visible content |
| --- | --- | --- |
| `Registry/avatardialog1.png` | **111×34** | Real 4LEAF four-leaf logo and wordmark |
| `Registry/avatardialog2.png` | **168×23** | Original **Select your Avatar** title |
| `Registry/avatardialog3.png` | **368×205** | Original Korean name, job, level, FP/GP and knight info panel and separate portrait area |
| `Registry/sava00.png` etc | **75×141** each | 12 authentic standing characters; native PNG already has RGBA transparent background |

Above dimensions are measured directly from PNG source IHDR, not guessed from historical screen renders. The recovered 2004 ChatRoom screenshots (`assets/chat_ref.jpg`, `chat.jpg`) contain character actors in room scenes, **not** this popup. Full historical Registry popup coordinate-by-coordinate screenshot comparison is thus **not yet VERIFIED**.

Before this change `social-chat.js::openAvatarMenu()` displayed 12 source actors inside a generic modern 6-column blue HTML dialog but did **not** render **any** of the three original selector header/info PNGs. Clicking any thumbnail immediately committed the user avatar with no independent preview.

## Implemented functional reconstruction

- `registry-native-avatar-dialog.js` mounts the three separate original component images and uses a separate, actual `75×141` native sprite for the character preview. The live user nickname is overlaid in the name cell. **The job, level, FP and GP fields intentionally remain unfilled because those values were not recovered from a real Registry user-profile service.** No fake character statistics, GP, fake users or invented NPCs.
- Exactly 12 true native character sprite buttons remain independent live DOM controls in the list below the historic information panel. Selection previews the source avatar without changing the active participant until **선택** is pressed; **취소**, Esc or the original dialog's still-operable close button leave the actual player unchanged.
- After confirmation the app calls its **existing** `state.avatar`, `saveAvatar()`, `presence()`, `renderOccupants()` flow. The existing real BroadcastChannel, WebRTC and centralized presence paths distribute that participant's original actor selection. It never creates a simulated lobby user.
- `registry-native-avatar-dialog.css` preserves 368×205 source composition, a 75×141 independent actor preview and 111×34/168×23 header bitmaps at native pixel scale on desktop. Narrow clients uniformly scale the panel to fit; six selectable rows in a real keyboard/focus-accessible 6×2 gallery remain tappable.
- Individual original artwork requests retry transient HTTP failures up to five times. If source art cannot load, the independently clickable actors and native input buttons remain functional; no source screenshot is silently substituted.
- The bottom **선택 / 취소** actions and the exact info frame overlay coordinates are **WEB UX / INFERRED**. The source recovered PNGs are VERIFIED; no claim is made that the original EXE used this specific click-to-preview/confirm workflow or the same surrounding layout.

## Tests / regression and offline packaging

- `tests/registry-native-avatar-dialog.cjs`: real Chromium decoding and natural source size checks, distinct original header/info/preview components, all 12 actual source buttons, one and only one selected actor, visible original panel, cancel/keyboard/home/mobile, real persisted avatar selection and propagation to a **second real browser tab**, and *no ghost participants*.
- `tests/native-offline-cache.cjs`: a cold PWA install without prior selector use loads the same source image trio and commits an actual avatar on a live room while disconnected.
- `rog-world-chat.yml` and `rog-chat-live.yml` exercise the genuine source UI and existing online/room/game regressions. Post-deploy verification compares the published CSS/JS byte-for-byte with the main branch before claiming Pages success.
- The source assets and two new scripts/styles are included in PWA cache v47.

## Priority still outstanding

The 2004 original ChatRoom shows several **character gestures, different clothing/poses and actor-specific animation frames** not present in these static `savaXX` images. Native animation tracks, accurate room-to-room interaction semantics and the original game 3D mesh/terrain system remain major gaps. This change restores a full authentic interactive Registry selector, **not** the complete original avatar animation system.
