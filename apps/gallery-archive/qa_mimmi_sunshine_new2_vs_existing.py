"""Read-only live-registry pixel audit of 2 newly stored Mimmi summer photos."""
import json
from pathlib import Path
from photo_visual_dedupe import WorkVisualIndex

ROOT=Path(__file__).resolve().parents[2]
MODEL='mimmi'
WORK='djawa-in-the-summer-sunshine-part-1'
SLOTS={51,52}


def inspect(root=ROOT):
    base=Path(root)/'apps'/f'{MODEL}-gallery'
    manifest=json.loads((base/'stored-albums.json').read_text())
    work=next((a for a in manifest['albums'] if a.get('id')==WORK),None)
    if work is None:
        raise AssertionError('Expected public work not found')
    added=[p for p in work['images'] if p.get('number') in SLOTS]
    old=[p for p in work['images'] if p.get('number') not in SLOTS]
    if len(added)!=2 or {p['number'] for p in added}!=SLOTS:
        raise AssertionError('The exact two new SHA rows are unavailable')
    fingerprints=WorkVisualIndex(base,{'id':WORK,'images':old})
    findings=[]
    for p in added:
        path=(base/p['url']).resolve()
        assert path.is_relative_to(base.resolve())
        raw=path.read_bytes()
        evidence=fingerprints.classify(raw)
        findings.append({'new_number':p['number'],'size':[p['width'],p['height']],
                         'bytes':p['bytes'],'sha':p['sha256'],
                         'verified_same_frame_old_photo':evidence})
    result={'model':MODEL,'album':WORK,'old_photos_scanned':len(fingerprints.entries),
            'old_missing':fingerprints.reference_missing,'old_corrupt':fingerprints.reference_corrupt,
            'new_sha_distinct_files':2,
            'already_existing_frame_matches':sum(bool(x['verified_same_frame_old_photo']) for x in findings),
            'actual_distinct_photo_cuts_not_proven':sum(not x['verified_same_frame_old_photo'] for x in findings),
            'findings':findings,'mode':'evidence_only_no_mutation'}
    print('MIMMI_NEW2_SUNSHINE_PIXEL_EVIDENCE',json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    inspect()
