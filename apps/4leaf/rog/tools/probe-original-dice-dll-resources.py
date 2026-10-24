#!/usr/bin/env python3
"""Read-only 2002 4LEAF Dice.dll PE asset provenance audit.

NEVER executes the archived Windows client or treats a resource header as a
decoded D4/D6 original model. Input must come from SHA1-verified installer.
Only section structure, SHA256, resource names/sizes/signature prefixes and
model-relevant string references are written; no copyrighted binary emitted.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

MAX_BYTES = 40 * 1024 * 1024
SIGS = {
    b"DDS ": "dds-texture-candidate",
    b"\x89PNG\r\n\x1a\n": "png-image-candidate",
    b"BM": "windows-bitmap-candidate",
    b"RIFF": "riff-container-candidate",
    b"GIF8": "gif-image-candidate",
    b"\x1f\x8b": "gzip-data-candidate",
}
KEYWORDS = re.compile(
    rb"(?i)(?:D3D|Direct3D|DirectDraw|D3DX|dice|roll|tetra|cube|vertex|vertices|"
    rb"texture|material|\.mve\b|\.dds\b|\.bmp\b|\.x\b|\.3ds\b)"
)
TYPE_NAMES = {2: "RT_BITMAP", 3: "RT_ICON", 6: "RT_STRING",
              10: "RT_RCDATA", 14: "RT_GROUP_ICON"}


def parse(path: Path):
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError("refusing oversized untrusted original executable")
    result = {"source": path.name, "bytes": len(data),
              "sha256": hashlib.sha256(data).hexdigest(),
              "decodedNativeD4Mesh": False, "decodedNativeD6Mesh": False,
              "decodedNativeTexture": False, "decodedNativeRollTimeline": False,
              "sections": [], "resources": [], "matchedTextHints": []}

    def u16(off):
        if off < 0 or off + 2 > len(data):
            raise ValueError("truncated PE u16")
        return struct.unpack_from("<H", data, off)[0]

    def u32(off):
        if off < 0 or off + 4 > len(data):
            raise ValueError("truncated PE u32")
        return struct.unpack_from("<I", data, off)[0]

    if data[:2] != b"MZ":
        result["fileType"] = "NOT-PE-DLL"
        return result
    pe = u32(0x3C)
    if pe > len(data) - 26 or data[pe:pe+4] != b"PE\0\0":
        result["fileType"] = "DOS-STUB-NO-VALID-PE"
        return result
    nsections, optional_size = u16(pe+6), u16(pe+20)
    opt = pe+24
    magic = u16(opt)
    if magic not in (0x10B, 0x20B):
        result["fileType"] = "UNKNOWN-PE-OPTIONAL-MAGIC"
        result["magic"] = hex(magic)
        return result
    result["fileType"] = "PE32+" if magic == 0x20B else "PE32"
    result["machine"] = hex(u16(pe+4))
    result["sectionCount"] = nsections
    dd = opt + (112 if magic == 0x20B else 96)
    table = opt + optional_size
    sections = []
    for i in range(min(nsections, 96)):
        off = table + 40*i
        if off+40 > len(data):
            result["parseWarning"] = "truncated-section-table"
            break
        name = data[off:off+8].split(b"\0", 1)[0].decode("ascii", "replace")
        vsize, va, rawsize, rawpos = struct.unpack_from("<IIII", data, off+8)
        sections.append((va, max(vsize, rawsize), rawpos, rawsize))
        result["sections"].append({"name": name, "rva": va,
                                   "virtualSize": vsize, "rawBytes": rawsize})
    def locate(rva, size=0):
        for va, span, start, rawlen in sections:
            offset = start + rva - va
            if va <= rva and rva+size <= va+span and 0 <= offset and offset+size <= len(data):
                return offset
        raise ValueError("resource-RVA-outside-PE-sections")

    if dd+24 <= table:
        res_rva, res_size = u32(dd+16), u32(dd+20)
        result["resourceDirectory"] = {"rva": res_rva, "bytes": res_size}
        if res_rva and 0 < res_size < 32*1024*1024:
            try:
                base = locate(res_rva)
                visited = set()
                def name_of(value):
                    if value & 0x80000000:
                        npos = base + (value & 0x7fffffff)
                        nchars = u16(npos)
                        if nchars > 128:
                            raise ValueError("invalid-resource-name")
                        return data[npos+2:npos+2+2*nchars].decode("utf-16le", "replace")
                    return str(value)
                def walk(relative, lineage=(), depth=0):
                    if depth > 4 or relative in visited or len(visited)>12000:
                        return
                    visited.add(relative)
                    off = base + relative
                    named, integer = u16(off+12),u16(off+14)
                    if named+integer > 12000:
                        raise ValueError("resource-directory-entry-overflow")
                    for i in range(named+integer):
                        e = off+16+i*8
                        label, target = u32(e), u32(e+4)
                        chain = lineage + (name_of(label),)
                        if target & 0x80000000:
                            walk(target & 0x7fffffff, chain, depth+1)
                        else:
                            d = base+target
                            raw_rva, length, codepage = u32(d),u32(d+4),u32(d+8)
                            if length > MAX_BYTES:
                                continue
                            try:
                                pos = locate(raw_rva, length)
                                blob = data[pos:pos+length]
                                sig = next((label for prefix,label in SIGS.items()
                                            if blob.startswith(prefix)), "unknown-binary")
                                result["resources"].append({
                                    "path": "/".join(chain), "type": TYPE_NAMES.get(
                                      int(chain[0]),chain[0]) if chain[0].isdigit() else chain[0],
                                    "bytes": length, "codepage": codepage,
                                    "sha256": hashlib.sha256(blob).hexdigest(),
                                    "header16": blob[:16].hex(), "signature": sig
                                })
                            except ValueError:
                                result["parseWarning"] = "some-resource-data-outside-section"
                walk(0)
            except (ValueError, struct.error, RecursionError) as error:
                result["resourceParseError"] = str(error)
    # Evidence only: names from raw ASCII/UTF16 binary strings, NO disassembly
    # or interpretation of a 3D mesh from a symbolic import.
    hits = []
    for encoding, blob in (("ASCII", data), ("UTF16LE", data[::2])):
        for m in KEYWORDS.finditer(blob):
            start = max(0, m.start()-24)
            end = min(len(blob), m.end()+38)
            snippet = re.sub(rb"[^\x20-\x7e]",b".",blob[start:end])
            label = snippet.decode("ascii","replace")
            if label not in hits:
                hits.append(label)
            if len(hits) >= 150:
                break
    result["matchedTextHints"] = hits
    result["resourceCount"] = len(result["resources"])
    result["resourceTypes"] = sorted(set(x["type"] for x in result["resources"]))
    result["evidenceLimits"] = (
        "PE resource / ASCII references do not prove an original 3D D4/D6 "
        "geometry, texture or bounce keyframe format. Native game code may "
        "generate dice procedurally. A verified graphical and timeline "
        "match is required before production source promotion."
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original_dice_dll", type=Path)
    parser.add_argument("report_json", type=Path)
    args = parser.parse_args()
    proof = parse(args.original_dice_dll)
    args.report_json.parent.mkdir(parents=True,exist_ok=True)
    args.report_json.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n")
    print("DICE_DLL_NATIVE_READ_ONLY_FORENSICS",
          json.dumps({k:proof.get(k) for k in (
              "source","sha256","fileType","sectionCount","resourceCount",
              "resourceTypes","decodedNativeD4Mesh","decodedNativeD6Mesh")},
              ensure_ascii=False))
