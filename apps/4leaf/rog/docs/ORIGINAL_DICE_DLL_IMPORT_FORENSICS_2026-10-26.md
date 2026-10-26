# 4LEAF 2002 Dice.dll — PE import API forensic proof (2026-10-26)

## Source and execution boundaries

- Original 4leaf.zip **SHA1**: `86526d89679ae39b85fe9808da97ad871b7888d9` (64,537,476 bytes), verified before read-only extraction.
- Original `Dice.dll` **SHA256**: `0987e96cb2d954b98e5815396874488d3bd50560f364df3bcacb588024270060`.
- GitHub Actions [#40276169868](https://github.com/koith/browser-app-lab/actions/runs/40276169868) **SUCCESS**, running isolated `tests/test_dice_pe_imports.py` and actual extracted source with `tools/probe-original-dice-dll-resources.py`.
- The original executable or DLL was **NEVER EXECUTED**. The new tool only parses bounded PE32 import, resource and text records; no binary contents committed.

## What actual static parsing verified

| Evidence | Observed in original DLL |
| --- | --- |
| File type / sections | PE32 / 3 sections |
| Import entries | 10 named API imports |
| DirectDraw import | `DDRAW.dll!DirectDrawCreateEx` |
| Late-binding imports | `KERNEL32.DLL!LoadLibraryA`, `KERNEL32.DLL!GetProcAddress` |
| PE resources | **2** ordinary icon-resource leaves: `RT_GROUP_ICON`, `RT_ICON` |
| Native D4/D6 model, texture, UV/keyframes decoded | **NO / NO** |

**Correction to the earlier 2026-10-24 PE scanner report**: Previous scanner returned zero enumerated resources; the revised and independently regression-tested scanner now detects two *icon* resources, not 3D dice bodies. Keep the previous observation as historical failure/limitation. Resource count is an enumeration result, never proof that geometry is absent elsewhere.

## Practical inference and next work

**VERIFIED**: This Dice.dll imports `DirectDrawCreateEx`, `LoadLibraryA` and `GetProcAddress`. Therefore graphics initialization calls and potential dynamically loaded APIs are now concrete reverse-engineering leads.

**INFERRED**: Original D4/D6 may use a DirectDraw-surface/2.5D/software or dynamically resolved 3D path; these imports alone **do not** establish any geometry format, full graphics API, D4/D6 render pipeline or roll timing.

**UNVERIFIED**: Specific DLL functions constructing a tetrahedron/cube; external model lookups vs procedural geometry; texture atlas/UV; 1–4/1–6 original falling/bouncing and frame cadence.

Next: statically inspect **cross-references** from imports and string hints into `.text` and follow mapped file reads; identify exact vertex/face tables or procedural draw calls. If code is not in the 2002 client, check SHA-verified later client builds. Only promote actual rendered original D4/D6 once geometry, textures, outcome-specific motion and original screenshots/video agree. Meanwhile web approximations stay clearly flagged as approximations.

## Reproducible evidence

- `tools/probe-original-dice-dll-resources.py` (read-only PE import + resource parser)
- `tests/test_dice_pe_imports.py` (synthetic API name, ordinal thunk, bad RVA, non-PE regression)
- `.github/workflows/rog-obs-bulk-recovery.yml` (original SHA1 verification gate, test execution and JSON artifact `4leaf-Dice-dll-original-PE-static-resource-proof`)
- [GitHub Actions #40276169868](https://github.com/koith/browser-app-lab/actions/runs/40276169868) logs: `DICE_DLL_NATIVE_READ_ONLY_FORENSICS`, 10 imports, 2 icons, DirectDrawCreateEx; no mesh success claimed.
