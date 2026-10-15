# Original WorldMap Notice source and permanent overlay (2026-10-16)

## Proven source

- Archived source: `original/WorldMap/notice.png`, exactly **184×61**, with winged **Notice** title, white message field and pure-green chroma key at the corners. **VERIFIED-ARCHIVE**.
- Independent period screenshot: `apps/4leaf/assets/sky.jpg` at 794×528 shows the notice panel at approximately **(23,9)**, remaining on screen without pointer hover, separate from the island art. In that September 2003 screenshot the message announces an old Chuseok event. **VERIFIED-SCREENSHOT**.
- The room and main WorldMap are independently reconstructed from actual `WorldMap/worldmapback.png` plus six canvas sprite sheets. Do not paint a complete screenshot over them.

## Code correction

- Before: `world-map.js` registered the native `WorldMap/notice.png` bitmap only on `.world-location-tip` hover labels. The **permanent top-left panel was missing**, despite the historical screenshot.
- Now: a single standalone `#world-native-notice` DOM element is composited over the WorldMap at **23×9**, using the **same chroma-key-decoded original bitmap** as the real hover labels; both retain genuine click handlers for six regions. It is not a screenshot rectangle.
- The original Chuseok announcement is historical, not a live service event. The live webapp instead renders a simple truthful navigation hint in the source message area; this wording is **WEB UX / not native 2003 event text**. The panel's exact 2003 font pixels and event navigation semantics are not yet decoded.
- Pointer events on this panel are disabled so historic WorldMap hotspots remain usable; hover notices retain their separate functional roles.
- A `file://`-only chroma-key canvas restriction falls back to readable text without stopping the client. Real hosted HTTP(S) uses the genuine keyed pixels, not a CSS approximation.
- `tests/world-map-moon.cjs` now verifies permanent single instance, source dimensions, transparent keyed corner on HTTP(S), original scene coordinates and separate North/South ChatTown navigation. Historical screenshot similarity beyond this panel remains **UNVERIFIED**.

## Screenshot watermark is not an in-game Notice

The `MainFrame/snaplogo.png` file is separate archive artwork associated with the original screenshot watermark; do not use it to substitute the always-present Notice source or manufacture historical events.
