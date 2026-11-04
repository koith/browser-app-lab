#!/usr/bin/env python3
"""Read real committed image pixels, flag possible upscales/soft copies for review.

This is NOT a blind-image-quality oracle: a soft-focus photograph and a modern
codec may have legitimately low sharpness/bytes. Never auto-delete/overwrite
images from this report. TeraBox-only originals are outside this scan.
"""
import argparse
import json
import math
import hashlib
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parents[1]
RESAMPLE = Image.Resampling.LANCZOS

def metric(file: Path):
    with Image.open(file) as source:
        width,height=source.size
        photo=ImageOps.exif_transpose(source)
        photo.thumbnail((560, 560), RESAMPLE)
        gray=ImageOps.grayscale(photo)
        pad_w=max(1,gray.width//10);pad_h=max(1,gray.height//10)
        gray=gray.crop((pad_w,pad_h,gray.width-pad_w,gray.height-pad_h))
        contrast=ImageStat.Stat(gray).stddev[0]
        diff=ImageChops.difference(gray,gray.filter(ImageFilter.GaussianBlur(1.2)))
        high_frequency=ImageStat.Stat(diff).mean[0]
        return {"decoded_width":width,"decoded_height":height,
                "center_detail_index":round(high_frequency/max(contrast,4.0),5),
                "high_frequency":round(high_frequency,3),
                "contrast":round(contrast,3)}

def verify_saved_sha(file: Path, expected: str) -> None:
    """Verify bytes, not only an image header or a claimed 4K pixel size."""
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("manifest_sha_missing_or_invalid")
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("committed_file_sha256_mismatch")


def run(out: Path, limit: int):
    results=[];failed=[];total=0
    for model in ("yui","mimmi"):
        model_dir=ROOT/(model+"-gallery")
        manifest=json.loads((model_dir/"stored-albums.json").read_text(encoding="utf-8"))
        for album in manifest.get("albums",[]):
            for photo in album.get("images",[]):
                url=photo.get("url","")
                if not url.startswith("stored-albums/"):continue
                filename=model_dir/url
                if not filename.is_file():failed.append({"model":model,"album":album.get("id"),"reason":"missing"});continue
                if limit and total>=limit:break
                total+=1
                try:
                    verify_saved_sha(filename, photo.get("sha256"))
                    visual=metric(filename)
                    pixel=visual["decoded_width"]*visual["decoded_height"]
                    byte_density=filename.stat().st_size/max(pixel,1)
                    if visual["decoded_width"]!=photo.get("width") or visual["decoded_height"]!=photo.get("height"):
                        failed.append({"model":model,"album":album.get("id"),"reason":"manifest_dimensions_disagree"})
                    result={"model":model,"album":album.get("id"),"number":photo.get("number"),
                            "name":filename.name,"megapixels":round(pixel/1e6,3),
                            "file_bytes":filename.stat().st_size,
                            "bytes_per_pixel":round(byte_density,5),
                            "from_pixibb": "pixibb" in str(photo.get("source_url","")).lower(),**visual}
                    results.append(result)
                except Exception as exc:
                    reason = (str(exc) if isinstance(exc, ValueError) and
                              str(exc) in {"manifest_sha_missing_or_invalid",
                                           "committed_file_sha256_mismatch"}
                              else type(exc).__name__)
                    failed.append({"model":model,"album":album.get("id"),"reason":reason})
            if limit and total>=limit:break
        if limit and total>=limit:break
    by_album=defaultdict(list)
    for r in results:by_album[(r["model"],r["album"])].append(r)
    suspects=[]
    for entries in by_album.values():
        detail=sorted(x["center_detail_index"] for x in entries)
        median=detail[len(detail)//2]
        for row in entries:
            poor_density=row["megapixels"]>=2 and row["bytes_per_pixel"] < (0.028 if row["name"].lower().endswith(".webp") else 0.042)
            weak_vs_neighbors=len(entries)>=6 and median>0.08 and row["center_detail_index"]<median*0.42
            if poor_density or weak_vs_neighbors:
                suspects.append({**row,
                    "review_flags":(["very_low_encoded_bits_per_pixel"] if poor_density else [])
                        + (["very_low_relative_center_detail"] if weak_vs_neighbors else []),
                    "review_priority":"high" if poor_density and weak_vs_neighbors else "medium",
                    "verified_high_quality":False})
    counts={}
    for row in results:counts[row["model"]]=counts.get(row["model"],0)+1
    report={
        "scope":"decoded physically committed public gallery bytes; does not access private TeraBox-only originals",
        "limits":"heuristic image-detail evidence, not authoritative optical resolution or watermark recognition; manual review before any replacement",
        "verified_sha256_file_counts":counts,
        "integrity_policy":"All decoded public images must match their manifest SHA-256; no image is overwritten or automatically promoted as high quality",
        "watermark_status":"not_verified_by_this_optical_audit",
        "decoded_file_counts":counts,
        "decode_errors":failed[:100],
        "suspected_for_review":len(suspects),
        "suspects":suspects
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DECODED_LOCAL_IMAGE_QUALITY_AUDIT",json.dumps({"decoded":counts,"possible_quality_risks":len(suspects),"decode_errors":len(failed),"out":str(out)},ensure_ascii=False),flush=True)
    assert not failed, f"Expected every manifest file to decode and match dimensions: {failed[:4]}"

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("gallery-visual-quality-audit.json"))
    parser.add_argument("--limit",type=int,default=0)
    args=parser.parse_args()
    run(args.out,args.limit)
