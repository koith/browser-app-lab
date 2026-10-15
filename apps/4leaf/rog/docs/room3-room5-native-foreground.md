# 4LEAF Room3/Room5 original foreground sprite dimensions (2026-10-16)

## Archive evidence and defect

The extracted original `ChatRoom.pak` resources contain distinct room
backgrounds and red-keyed furniture foregrounds:

| file | Recovered native PNG dimensions | Previous web CSS paint dimensions | Current native paint dimensions |
| --- | --- | --- | --- |
| `room3t.png` | **272×102** | **568×213** (~2.09×) | **272×102** |
| `room5t.png` | **176×128** | **260×170** (nonuniform 1.48×, 1.33×) | **176×128** |
| `room4t.png` | **115×103** | Previously 157×143 | **115×103**, precisely registered in two 2004 screenshots by PR #67 |

**VERIFIED-ARCHIVE** is the bitmap size and source artwork; source red
chroma key requires masking to transparent rather than rendering red areas.

## Renderer corrections

`social-chat.js` retained source-sized RGBA canvas buffers but previously
stretched them through mismatched CSS `width` and `height`. This caused a
huge green table in room3 and misshapen orange table in room5.

Both foregrounds now render 1:1 at the following **WEB-RECONSTRUCTED,
INFERRED**, not historically measured, anchors:

- Room3 (272×102) left 261, top 363, depth 80. This centers the foreground over
  the table supports indicated by the recovered room3 background.
- Room5 (176×128) left 307, top 357, depth 78. This centers the foreground
  over the rug and table shadow in the recovered room5 background.

These anchors remain **UNVERIFIED**. They are not claims about the 2001–2004
native engine's room placement. Unlike room4, no contemporary screenshots
confirm either coordinate yet. Future evidence must replace the estimate.

`tests/chatroom-native-furniture-sizes.cjs` renders the real client in
Chromium, creates genuine empty rooms with background 3 and 5, and checks
source native size equals CSS draw size, RGBA red-key transparency, native
background, live occupant count, and instantaneous seat movement. Both source
assets remain separate from real users and clickable surfaces.

## Further P0 work

Acquire genuine contemporaneous room3/room5 screenshots or client placement
data and repeat the room4 quantitative sprite correlation method rather than
calling current inferred positions verified. Continue to protect the original
ChatRoom source, online peer synchronization, and 1-frame seat teleport.
