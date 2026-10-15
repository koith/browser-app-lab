# 4LEAF ChatRoom Room Master — recovered original owner dialogue (2026-10-16)

## Source verified

- `original/ChatRoom/ownerdialog.png` is a recovered **338×282** source atlas with an upper-left **309×126** Korean room-master form and independent bottom strips with native OK and Cancel state artwork. Source was previously unused by `social-chat.js`.
- Historical album/screenshot pixel equality of the original Room Master popup is **NOT verified**. These component dimensions and visual text/labels are archive-proven, while UI placement inferred from the bitmap coordinates and overlaid live controls is reconstructed WEB UX.
- Main historical screenshot `chat_ref.jpg` verifies the native room interior, not the room-owner popup. Never claim pixel registration of this form against that screenshot.

## Actual frontend implementation

- `chatroom-native-owner-dialog.js` loads and chroma-keys only saturated green source pixels, then draws the top-left original 309×126 source panel plus independently cropped native 62×23 OK/Cancel art. It does **not** paste a static game screenshot on a hidden clickable DOM.
- `chatroom-native-owner-dialog.css` registers real editable room title at source x57 y28, capacity dropdown x57 y51, password input x83 y99; original Korean source labels and border pixels remain visible. The extra room-background selector below the image is explicitly **WEB UX**, not claimed as original.
- Original-era 공개/비공개 and 비밀번호 semantics are exposed with working radio controls: private mode requires actual password input and uses the existing `deriveRoomProof()` and central authority admission. Selecting public clears password rather than creating a secretly password-protected room. This particular radio/validation model is **inferred**, as the complete native room creation protocol was not extracted.
- Pressing the genuine-looking OK submits the same authenticated, capacity-aware actual create-room handler. Cancel and Escape close the modal without inventing any room.
- A temporary source CDN 503 causes exponential retries; if the archive cannot be decoded or `file://` isolates canvas, the old readable generic HTML form continues to function without claiming authentic bitmap rendering.
- Service worker v41 pre-caches the source atlas and new script/CSS, so the first offline Room Master opening can still render exact native pixels.

## QA

- `tests/chatroom-native-owner-dialog.cjs`: real Chromium original PNG decode/alpha, source top-left crop, 2 transient HTTP 503 retries, real field positions, missing private-password blocking, real password-protected room creation with capacity/background, Cancel and mobile.
- `tests/native-offline-cache.cjs`: cold-offline original native Room Master before any prior popup visits.
- `.github/workflows/rog-world-chat.yml` and `rog-chat-live.yml`: local/central regressions and separately published GitHub Pages browser QA.

## Still unresolved

Original room-owner caption pixel font mapping, full states of `ownerdialog.png`, 2002 room management permissions and old ChatTown room estate terrain are not proven and remain priorities. This isolated original sprite restoration does not imply overall 4LEAF visual completion.
