# 4LEAF genuine D4/D6 — original Dice.dll PE inspection (2026-10-24)

## Status: original 3D dice still NOT recovered
An original 2002 4LEAF archive, exactly SHA1 `86526d89679ae39b85fe9808da97ad871b7888d9`, was re-extracted with the already-verified read-only toolchain; Windows binaries were **never executed**. Job [#40072513335](https://github.com/koith/browser-app-lab/actions/runs/40072513335) succeeded, including the new original client PE resource scanner.

The native `4Leaf_Files/Dice/Dice.dll` has:
- Exact SHA256 `0987e96cb2d954b98e5815396874488d3bd50560f364df3bcacb588024270060`.
- Valid **PE32**, three PE sections.
- **Zero PE resource-directory records enumerated** by our read-only PE scanner. Neither original D4 nor original D6 polygon models, palettes, UVs or animation/keyframes were decoded.
- The archive also contains 713 indexed Dice PAK members: 26 `DMP.pak/*.mve` files correspond to maps, not verified physical dice. `roll.spr` (4 source frames) and `eventRoll1.spr` (16 frames) are **authentic control UI sprites**, not dice body.
- Resource count zero only excludes a directly enumerable native PE resource tree; it **does not** prove that 3D geometry is absent from compiled `.text/.data`, registered external assets, Direct3D procedural shapes or unexamined 2003/2004 builds.

## Actual new tooling
`tools/probe-original-dice-dll-resources.py` validates PE DOS/NT headers and section bounds, follows PE resource names and data RVA with size checks, fingerprints candidate original BMP/DDS/PNG/RCDATA resource members, reports import/textual die/texture/vertex keywords as *unverified clues* only, never exports copyrighted executable bytes and never labels geometry recovered. `.github/workflows/rog-obs-bulk-recovery.yml` performs this check after the original installer SHA1 gate and uploads the `4leaf-Dice-dll-original-PE-static-resource-proof` artifact (JSON only).

## Remaining original acquisition/decode gates
1. Reassess all three PE sections and imports for **procedural D4/D6 mesh construction**, per-result edge normals and rendering matrices; static resource absence is not a verdict on compiled game logic.
2. Obtain a checksum-verified **2003–2004 native browser client**, ideally multiple source patches. The publicly advertised official `v0.96d` is the 2002-07-16 build; no newer verified native client has been recovered in this task.
3. Find authentic dice-specific original video evidence of 1–4/1–6 outcomes including full fall/spin/bounce/land timeline, lighting, texture and camera; a JPG screenshot of the old board does not contain editable 3D geometry.
4. Only after actual vertices/UV/body texture + outcome-specific original timing have matching source signatures and screenshot/video acceptance should `dice-fall.css` be **replaced** rather than polished.
5. Historical D4/D6 source still **P0 pending**, no estimated completeness claim. Do not falsely count 2D roll controls or map MVE as native 3D dice.

_Source verified through GitHub Actions [#40072513335](https://github.com/koith/browser-app-lab/actions/runs/40072513335), manifest and PE forensics artifact._
