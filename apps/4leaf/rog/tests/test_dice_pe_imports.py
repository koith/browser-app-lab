#!/usr/bin/env python3
"""Synthetic safe PE32 import-table validation; never executes native code."""
import importlib.util
import struct
import tempfile
from pathlib import Path

tool = Path(__file__).resolve().parents[1] / "tools" / "probe-original-dice-dll-resources.py"
spec = importlib.util.spec_from_file_location("dice_pe_probe", tool)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def synthetic(dll=b"d3d8.dll\0", name=b"Direct3DCreate8\0", thunk=0x2080):
    raw = bytearray(0x500)
    raw[:2] = b"MZ"
    struct.pack_into("<I", raw, 0x3c, 0x80)
    raw[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", raw, 0x86, 1)       # one section
    struct.pack_into("<H", raw, 0x94, 0xe0)    # PE32 optional header
    struct.pack_into("<H", raw, 0x98, 0x10b)   # PE32, never execute
    struct.pack_into("<II", raw, 0x100, 0x2000, 40)  # import table
    raw[0x178:0x180] = b".idata\0\0"
    struct.pack_into("<IIII", raw, 0x180, 0x200, 0x2000, 0x200, 0x200)
    struct.pack_into("<IIIII", raw, 0x200, 0x2040, 0, 0, 0x2060, 0x2040)
    struct.pack_into("<II", raw, 0x240, thunk, 0)
    raw[0x260:0x260+len(dll)] = dll
    raw[0x280:0x282] = b"\0\0"       # IMAGE_IMPORT_BY_NAME hint
    raw[0x282:0x282+len(name)] = name
    return raw


with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "synthetic-Dice.dll"
    path.write_bytes(synthetic())
    ok = module.parse(path)
    assert ok["fileType"] == "PE32", ok
    assert ok["resourceCount"] == 0, ok
    assert ok["staticImports"] == [
        {"dll": "d3d8.dll", "names": ["Direct3DCreate8"]}
    ], ok
    assert ok["staticImportCount"] == 1, ok
    assert ok["graphicsImportHints"] == [
        {"dll": "d3d8.dll", "api": "Direct3DCreate8"}
    ], ok
    assert all(ok[x] is False for x in (
        "decodedNativeD4Mesh", "decodedNativeD6Mesh",
        "decodedNativeTexture", "decodedNativeRollTimeline")), ok
    # A bound violation must be marked as a warning, not crash, nor assert
    # that native body geometry has been reconstructed.
    path.write_bytes(synthetic(thunk=0x400000))
    invalid = module.parse(path)
    assert invalid["staticImportCount"] == 0, invalid
    assert "importParseWarning" in invalid, invalid
    path.write_bytes(synthetic(thunk=0x80000001))
    ordinal = module.parse(path)
    assert ordinal["staticImports"] == [
        {"dll": "d3d8.dll", "names": ["#ordinal-1"]}
    ], ordinal
    path.write_bytes(b"not an executable")
    not_pe = module.parse(path)
    assert not_pe["fileType"] == "NOT-PE-DLL", not_pe

print("SYNTHETIC_DICE_PE32_STATIC_IMPORTS_PASS",
      "named-api/ordinal/bad-rva/non-pe, never native execution")
