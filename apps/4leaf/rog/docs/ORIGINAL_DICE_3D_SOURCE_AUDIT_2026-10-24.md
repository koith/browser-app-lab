# 4LEAF original D4/D6 model acquisition — source evidence (2026-10-24)

## Priority
Real original die body/texture/trajectory replaces continued WEB CSS approximation work. Original MVE model, texture and deterministic impact/body keyframes are **not recovered**; neither 4-sided nor 6-sided original dice may be called restored.

## Sources independently established
- SHA1-verified 2002 client archive: `86526d89679ae39b85fe9808da97ad871b7888d9`. Existing `.github/workflows/rog-obs-bulk-recovery.yml` verifies it before unpacking original InstallShield resource CAB *without ever executing Windows binaries*.
- Verified `Dice/IMG.pak:roll.spr`: **4 sprite frames** for the source **ROLL control**; `eventRoll1.spr`: **16 sprite frames** for the source rolling control. These are original **2D UI assets**, not the actual thrown D4/D6 polyhedron or texture atlas. `original/SourceSPR/manifest.json` is the authoritative decoder evidence.
- `apps/4leaf/assets/board.jpg` and `battle.jpg`: source 2004 battle reference of original die face/color, multiple actual combat dice, and 3D scene. A screenshot cannot recover a 3D mesh and native result-specific frame timing.
- `apps/4leaf/rog/dice-d4-source-fallback.css` / `dice-fall.css` and `dice-fall.js` are **WEB approximations**; previous D4/CSS geometry regression improvements do not mean original body reconstruction.
- `apps/4leaf/rog/tools/audit-original-dice-resources.py` now reports exact per-package original SHA256 and candidate 3D names/extensions/first16 bytes, labels high-risk extensions as *candidates only*, excludes both native 2D roll controls from mesh results, inventories possibly embedded EXE/DLL sources, and explicitly reports all D4/D6 3D verification gates FALSE until parsed. The established `4LEAF recover native OBS chessman poses` CI creates `4leaf-original-Dice-package-manifest` artifact after SHA verification.

## Missing exact source, not a CSS rendering problem
1. Source member path and SHA for D4/D6 actual vertices, face topology/normals, UV texture atlas and historical color/palette.
2. Original 3D camera perspective, physical scale, light/material mapping and whether body vertices are stored in individual data files or client EXE/DLL.
3. The result-specific D4 1–4 and D6 1–6 native roll sequences: initial height, spin, collisions, bounce time curves, settled orientation, original FPS.
4. Full comparison frames from the *same original game state* for ordinary DMP move rolls, not only historical duel screenshots.
5. Another authentic 2003/2004 client release and verifiable archive hash if the required data isn't present in the 2002 source. Archive 2002 absence by filename alone cannot prove no embedded die model.

## Source acceptance gate
Do not replace actual gameplay with a pasted screenshot, copied Unicode die face or 'original' label based on the 2D UI roll button. Require original member/format proof -> original vertices/textures/keyframes decode -> same-result in-game 3D screenshot/video matching -> Chrome/WebKit QA -> Pages deployed SHA. Keep `DIE-01`, `DIE-02`, `P0-DICE` open until then.

## Research execution / status
- Repository source inventory scanner updated and real verified-client GitHub Actions extraction triggered.
- Check the most recent run under `.github/workflows/rog-obs-bulk-recovery.yml`; inspect original `4leaf-original-Dice-package-manifest` artifact for `dieBody3dInvestigation`.
- A named candidate may prove to be an unrelated animation or binary blob. **This document does not report that an original 3D mesh has been recovered.**
