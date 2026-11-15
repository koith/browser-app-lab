#!/usr/bin/env python3
"""Check whether 20 recently committed public JPEGs are 20 *different cuts*.

SHA/byte-verified JPEG files can still be re-encoded or low-quality versions
of a photograph that the gallery already shows. This evidence-only audit
never deletes, replaces, renumbers, fetches, or republishes any photograph.
"""
from __future__ import annotations
import json
from pathlib import Path
from perceptual_duplicate_audit import scan_image, candidate_relation
from photo_quality_evidence import preferred_pair

ROOT=Path(__file__).resolve().parents[2]
MODEL="mimmi"
WORK="djawa-christmas-special-2021-mimmi"
NEW_NUMBERS=set(range(171,191))


def run(root=ROOT):
    base=Path(root)/"apps"/f"{MODEL}-gallery"
    record=json.loads((base/"stored-albums.json").read_text(encoding="utf-8"))
    album=next((a for a in record["albums"] if a.get("id")==WORK),None)
    if not album:
        raise AssertionError("Original work unavailable; cannot claim new cuts")
    new=[p for p in album["images"] if p.get("number") in NEW_NUMBERS]
    old=[p for p in album["images"] if p.get("number") not in NEW_NUMBERS]
    if len(new)!=20 or {p["number"] for p in new}!=NEW_NUMBERS:
        raise AssertionError("Committed 20 JPEG slots not present")
    if not old:
        raise AssertionError("No prior work photos available for comparison")
    cache={};missing=[];wrong=[]
    def load(p):
        rel=p.get("url","")
        if not isinstance(rel,str) or not rel.startswith("stored-albums/"+WORK+"/"):
            raise AssertionError("Unexpected public photo pathname")
        path=(base/rel).resolve()
        if not path.is_relative_to(base.resolve()):
            raise AssertionError("Photo path escapes gallery")
        if not path.is_file():
            missing.append(p["number"])
            return None
        if str(path) not in cache:
            image=scan_image(path.read_bytes())
            cache[str(path)]=image
        image=cache[str(path)]
        if image["sha256"]!=p.get("sha256") or image["width"]!=p.get("width") or image["height"]!=p.get("height"):
            wrong.append(p["number"])
            return None
        return image
    prior=[(p,load(p)) for p in old]
    prior=[(p,img) for p,img in prior if img is not None]
    added=[(p,load(p)) for p in new]
    if wrong:
        raise AssertionError(f"Stored image bytes differ from manifest: {wrong}")
    if len(added)!=20 or any(img is None for _,img in added):
        raise AssertionError("A newly added physical photo is inaccessible")
    strong=[];weak=[];nearest=[];quality=[]
    for p,candidate in added:
        distances=[]
        for earlier,reference in prior:
            relation,distance,mean=candidate_relation(candidate,reference)
            if distance is not None:
                distances.append((distance,mean if mean is not None else 999.0,earlier["number"]))
            if relation is not None:
                result={"new_number":p["number"],"old_number":earlier["number"],
                        "relation":relation,"dhash_distance":distance,
                        "mean_rgb_difference":mean}
                (strong if relation=="perceptually_similar_review" else weak).append(result)
        if distances:
            best=min(distances)
            nearest.append({"new_number":p["number"],"prior_number":best[2],
                            "dhash_distance":best[0],"rgb_difference":None if best[1]==999.0 else best[1]})
            matched=next(old for old,_ in prior if old["number"]==best[2])
            old_bytes=(base/matched["url"]).read_bytes()
            new_bytes=(base/p["url"]).read_bytes()
            superior,evidence=preferred_pair(old_bytes,new_bytes,matched["sha256"])
            quality.append({"new_number":p["number"],"previous_number":matched["number"],
                            "new_pixels":[p["width"],p["height"]],"prior_pixels":[matched["width"],matched["height"]],
                            "new_bytes":p["bytes"],"prior_bytes":matched["bytes"],
                            "visual_relation":evidence.get("relation"),
                            "measured_fine_detail_prior":evidence.get("previous_detail"),
                            "measured_fine_detail_new":evidence.get("candidate_detail"),
                            "new_is_proven_quality_upgrade":superior})
    report={
        "model":MODEL,"work":WORK,
        "published_photo_slots_prior":len(old),
        "published_photo_slots_new_SHA_unique":len(added),
        "prior_photo_bytes_checked":len(prior),
        "unavailable_prior_reference_numbers":missing[:60],
        "strong_same_frame_review_candidates":strong,
        "weak_visual_review_candidates":weak,
        "new_files_without_strong_same_frame_candidate":len({
            p["number"] for p,_ in added
        }-{r["new_number"] for r in strong}),
        "nearest_dhash_candidate_per_new":nearest,
        "same_photo_quality_comparisons":quality,
        "new_files_proven_quality_upgrade_count":sum(x["new_is_proven_quality_upgrade"] for x in quality),
        "claim":"SHA-unique and pixel-decoded files are not automatically unique photographs",
        "mutations":0
    }
    print("MIMMI_2021_NEW20_VS_EXISTING_VISUAL_EVIDENCE",
          json.dumps(report,ensure_ascii=False),flush=True)
    return report


if __name__=="__main__":
    run()
