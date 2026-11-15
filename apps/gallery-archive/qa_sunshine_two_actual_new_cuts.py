#!/usr/bin/env python3
"""Pixel-audit the two new Mimmi Summer Sunshine 1 SHA-distinct JPG files.

No file or manifest mutation. Decoding the photo on GitHub Pages is not
sufficient to prove it is a new distinct cut; compare to ALL old same-work JPG
pixels before counting a novel photograph.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from perceptual_duplicate_audit import scan_image,candidate_relation
from photo_quality_evidence import preferred_pair

ROOT=Path(__file__).resolve().parents[2]
MODEL='mimmi'
WORK='djawa-in-the-summer-sunshine-part-1'
NEW_NUMBERS={51,52}


def run(root=ROOT):
    base=Path(root)/'apps'/f'{MODEL}-gallery'
    album=next((a for a in json.loads((base/'stored-albums.json').read_text())['albums']
                if a.get('id')==WORK),None)
    assert album is not None
    new=[p for p in album['images'] if p.get('number') in NEW_NUMBERS]
    previous=[p for p in album['images'] if p.get('number') not in NEW_NUMBERS]
    assert {p['number'] for p in new}==NEW_NUMBERS and len(new)==2
    def load(p):
        rel=p['url']
        assert rel.startswith(f'stored-albums/{WORK}/')
        path=(base/rel).resolve()
        assert path.is_relative_to(base.resolve()) and path.is_file()
        raw=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==p['sha256']
        return raw,scan_image(raw)
    old=[(p,*load(p)) for p in previous]
    verified=[]
    for p in new:
        raw,current=load(p)
        matches=[]
        for older,prior_raw,prior_scan in old:
            label,diff,delta=candidate_relation(prior_scan,current)
            if label=='perceptually_similar_review':
                better,detail=preferred_pair(prior_raw,raw,older['sha256'])
                if detail.get('same_photo_verified'):
                    matches.append({'old_number':older['number'],
                                    'hash_distance':diff,'mean_rgb_difference':delta,
                                    'new_quality_higher':better,
                                    'old_dimensions':[older['width'],older['height']],
                                    'new_dimensions':[p['width'],p['height']]})
        verified.append({'new_number':p['number'],'new_sha256':p['sha256'],
                         'same_photo_existing_candidates':matches})
    result={'model':MODEL,'album':WORK,'old_sha_verified_photo_cuts_compared':len(old),
            'new_sha_verified_files':2,
            'new_same_frame_existing_photo_count':sum(bool(x['same_photo_existing_candidates']) for x in verified),
            'new_files_without_detected_same_frame_match':sum(not x['same_photo_existing_candidates'] for x in verified),
            'results':verified,'state':'PIXEL_AUDIT_ONLY_NOT_PUBLISHER_MASTER_COMPLETENESS'}
    print('MIMMI_SUNSHINE_NEW2_SAME_FRAME_EVIDENCE',json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    run()
