#!/usr/bin/env python3
"""Remove only two publisher JPEGs proved SAME PIXEL CUT as existing photos.

This exact one-time reversible correction keeps original photos 41 and 44.
It refuses mutation on partial, changed, corrupt, newly improved, or unverified
results; never touches owner originals. Default is --plan-only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from photo_visual_dedupe import WorkVisualIndex

ROOT=Path(__file__).resolve().parents[2]
WORK='djawa-in-the-summer-sunshine-part-1'
ORIGIN='https://djawaphoto.com/portfolio/in-the-summer-sunshine-part-1/'
EXACT={
  51:'b90a6ba53555784341172f58e5d96ceeaa6bb6909b78a830db772f63787e6d66',
  52:'70684a2fa6458881dcf44008a9a4fb3a7c91f06e3c0e8b3fbd9fd1b2bc0fc517',
}
REFERENCE={51:41,52:44}


def correct(root=ROOT,apply=False):
    base=Path(root)/'apps/mimmi-gallery'
    source=base/'stored-albums.json'
    doc=json.loads(source.read_text(encoding='utf-8'))
    work=next((a for a in doc['albums'] if a.get('id')==WORK),None)
    if work is None:
        raise AssertionError('Target work does not exist')
    added=[p for p in work['images'] if p.get('number') in EXACT]
    if not added:
        result={'state':'ALREADY_CORRECTED_OR_OLDER_SOURCE',
                'false_new_rows_removed_this_run':0,
                'old_originals_retained':len(work['images']),
                'mode':'no_mutation'}
        print('GALLERY_CORRECT_SUMMER_TWO_FALSE_NEW_CUTS',
              json.dumps(result,ensure_ascii=False),flush=True)
        return result
    if len(added)!=2 or {p['number'] for p in added}!=set(EXACT):
        raise AssertionError('Partial or changed summer album; refuse mutation')
    previous=[p for p in work['images'] if p.get('number') not in EXACT]
    assert len(previous)>=48
    originals={p.get('number'):p for p in previous}
    assert 41 in originals and 44 in originals
    matcher=WorkVisualIndex(base,{'id':WORK,'images':previous})
    assert matcher.reference_missing==0 and matcher.reference_corrupt==0, (
        'All old actual photos required for exact pixel proof')
    assert len(matcher.entries)>=48
    for row in added:
        number=row['number']
        assert row.get('sha256')==EXACT[number]
        assert row.get('origin_page')==ORIGIN
        rel=row.get('url','')
        assert rel.startswith(f'stored-albums/{WORK}/')
        physical=(base/rel).resolve()
        assert physical.is_relative_to(base.resolve()) and physical.is_file()
        raw=physical.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==EXACT[number]
        assert len(raw)==row['bytes']
        match=matcher.classify(raw)
        assert match is not None and match['existing_number']==REFERENCE[number], (
            'Exact old photo identity not proven',number,match)
        assert not match['needs_replacement_transaction'], (
            'A potential higher-quality source must never be silently discarded')
    redundant_paths=[]
    shared={p.get('url') for album in doc['albums'] for p in album.get('images',[])
            if p not in added}
    for p in added:
        if p['url'] not in shared:
            redundant_paths.append((base/p['url']).resolve())
    result={'work':WORK,'false_new_rows_removed_this_run':2,
            'prior_photos_retained':len(previous),
            'duplicate_files_eligible_for_git_removal':len(redundant_paths),
            'genuine_new_cuts_removed':0,
            'confirmed_quality_improvements_removed':0,
            'mode':'apply' if apply else 'plan_only'}
    if apply:
        work['images']=previous
        if 'physical_verified_image_count' in doc:
            doc['physical_verified_image_count']=sum(
                len(a.get('images',[])) for a in doc['albums'])
        temp=source.with_name(source.name+'.pending')
        temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(source)
        for path in redundant_paths:
            path.unlink()
    print('GALLERY_CORRECT_SUMMER_TWO_FALSE_NEW_CUTS',
          json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    correct(apply=args.apply)
