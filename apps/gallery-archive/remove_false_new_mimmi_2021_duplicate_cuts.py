#!/usr/bin/env python3
"""Reversibly correct falsely counted 20 public photo cuts, preserving originals.

Only the exact 20 numbered files added by commit 927b59f are eligible.
Nothing is changed until a current SHA/pixel comparison independently proves
that all 20 are same-frame variants of existing physical files and none is
a measurable quality improvement. --plan-only is read-only by default.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from qa_mimmi_2021_new20_vs_existing import run, ROOT, MODEL, WORK, NEW_NUMBERS

ORIGIN='https://djawaphoto.com/portfolio/christmas-special-2021-mimmi/'


def correct(root=ROOT, apply=False):
    root=Path(root)
    evidence=run(root)
    new_count=evidence['published_photo_slots_new_SHA_unique']
    matches={r['new_number'] for r in evidence['strong_same_frame_review_candidates']}
    assert new_count==len(NEW_NUMBERS)==len(matches), (
        'New photo visual matching incomplete: no automatic mutation')
    assert evidence['new_files_proven_quality_upgrade_count']==0, (
        'At least one candidate may improve photo quality; no automatic removal')
    assert not evidence['unavailable_prior_reference_numbers'], (
        'Existing saved-cut physical coverage incomplete')
    source=root/'apps'/f'{MODEL}-gallery'/'stored-albums.json'
    document=json.loads(source.read_text(encoding='utf-8'))
    album=next((row for row in document['albums'] if row.get('id')==WORK),None)
    assert album is not None
    newly_added=[p for p in album['images'] if p.get('number') in NEW_NUMBERS]
    assert len(newly_added)==20
    for photo in newly_added:
        assert (photo.get('origin_page')==ORIGIN and
                photo['url'].startswith(f'stored-albums/{WORK}/') and
                len(photo.get('sha256',''))==64), (
                'Photo no longer matches exact 20-item correction scope')
    survivors=[p for p in album['images'] if p.get('number') not in NEW_NUMBERS]
    survivor_shas={p['sha256'] for p in survivors}
    assert len(survivors)>=99, 'Unexpected prior work capacity'
    urls_other={p.get('url') for a in document['albums'] for p in a['images']
                if p not in newly_added}
    paths=[]
    base=source.parent.resolve()
    for p in newly_added:
        file=(base/p['url']).resolve()
        assert file.is_relative_to(base) and file.is_file()
        # This batch added standalone public copies; no owner-original
        # reference or unrelated gallery route is ever modified.
        if p['url'] not in urls_other and p['sha256'] not in survivor_shas:
            paths.append(file)
    result={
        'model':MODEL,'work':WORK,'removed_duplicate_photo_rows':len(newly_added),
        'retained_existing_photo_rows':len(survivors),
        'physical_duplicate_files_eligible_for_git_revert':len(paths),
        'independent_new_cuts_removed':0,
        'proven_quality_upgrades_lost':0,
        'mode':'apply' if apply else 'plan_only'
    }
    if apply:
        album['images']=survivors
        if 'physical_verified_image_count' in document:
            document['physical_verified_image_count']=sum(
                len(a.get('images',[])) for a in document['albums'])
        # Write manifest before deleting only dedicated redundant files.
        temp=source.with_name(source.name+'.pending')
        temp.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',
                        encoding='utf-8')
        temp.replace(source)
        for file in paths:
            file.unlink()
    print('GALLERY_REMOVE_20_FALSE_NEW_CUTS',
          json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    options=parser.parse_args()
    correct(apply=options.apply)
