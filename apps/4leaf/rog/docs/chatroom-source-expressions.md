# Original ChatRoom expression graphics & live peer integration (2026-10-16)

## Verified source

The archived `ChatRoom/expdialogbtn.png` is **196×267** pixels. Its top two columns are different visual states of six 66×22 Korean facial-expression button rows, reading **하하, 우씨, 으앙, 좋아, 헉, 기타**. The bitmap is **VERIFIED-ARCHIVE**; the precise historical display location of the selector and old binary emotion protocol remain **UNVERIFIED**.

Previously the recovered file was wholly unused: `social-chat.js` could display only static 75×141 Registry figures and speech bubbles. The original character expression artwork never appeared during play.

## Restoration and honest inference

- `chatroom-native-expressions.js` mounts one accessible native-source expression trigger to the original room toolbar, without displacing the six functioning MainFrame native tools. Opening it exposes exactly six independent, real, clickable expression controls.
- `chatroom-native-expressions.css` paints each button from one real **66×22** source strip in the recovered PNG, switching between the original first and second visual state on hover. It also crops an original 23×22 face onto the **actual participant avatar** above their source character. It is not a full screenshot overlay or a generated emoji illustration.
- A selected expression is dispatched as genuine chat content `[표정] <label>` by the *existing* `__LEAF_SOCIAL__.send()` path. This uses existing local BroadcastChannel, WebRTC and central authoritative chat, and normal history is retained. The exact text packet is clearly **INFERRED WEB PROTOCOL**, not asserted as the 2002 binary wire format. No ghost users or fake server data.
- Source face display is ephemeral and is removed when leaving the room. Selecting another face replaces the same figure's previous face; mouse, keyboard Escape and mobile controls remain accessible. A missing native image shows accessible Korean labels instead of crashing, with retries on CDN failures.
- The original artist sprites of full-body changes, historic pose animation frames, original expression persistence rules and actual emotional-expression packet encoding are not recovered. Static avatars still remain incomplete compared with the 2004 footage.

## Tests and deployment

- `tests/chatroom-native-expressions.cjs` validates source dimensions, six pixel-backed genuine buttons, one real created room with **two real live browser tabs**, chat event propagation and remote avatar face, original sprite use, room leave, keyboard Escape and mobile.
- `tests/native-offline-cache.cjs` verifies the source atlas and first offline expression use after PWA cold install (v42).
- `rog-world-chat.yml` and public `rog-chat-live.yml` run the actual Chromium test; central server, Dice, world map and existing room interactions must stay green.
