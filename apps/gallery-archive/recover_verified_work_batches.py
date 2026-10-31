"""Queue whole verified works after another work fails; never hide that failure.

The failed collection job remains failed. Only a later normal publisher may
independently re-read these exact objects and publish the resulting photos.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from defer_verified_batch import prepare,persist,serialize
from merge_incremental import checked_row
from private_collection_snapshot import REMOTES


def recover(stage,owner,remote):
    model=owner['model']
    if remote!=REMOTES[model]:raise ValueError('Wrong existing owner archive')
    proof_path=stage/'metadata/remote-verification.json'
    if not proof_path.exists():
        print('NO_COMPLETED_REMOTE_AUDIT_NOTHING_RECOVERED',model,flush=True);return 0
    proof=json.loads(proof_path.read_text())
    if proof.get('model')!=model:raise ValueError('Wrong failed-audit model')
    works=proof.get('work_verification',{})
    if not works:
        print('NO_PER_WORK_EXACT_REMOTE_PROOF_NOTHING_RECOVERED',model,flush=True);return 0
    for key in ('media_checked','full_SHA256_verified','failed'):
        if any(type(w.get(key)) is not int or w[key]<0 for w in works.values()):
            raise ValueError('Invalid per-work remote audit counts')
        if proof.get(key)!=sum(w[key] for w in works.values()):
            raise ValueError('Per-work remote counts do not reconcile with the failed batch')
    catalog=json.loads((stage/'metadata/catalog.json').read_text())
    audit=json.loads((stage/'metadata/collection-audit.json').read_text())
    if catalog.get('model')!=model or audit.get('model')!=model:
        raise ValueError('Wrong staged collection model')
    evidence={a['id']:a for a in audit['results']}
    queued=0;held=0
    for album in catalog['albums']:
        aid=album['id'];verdict=works.get(aid)
        if not verdict:continue
        if verdict.get('failed') or verdict.get('media_checked')!=verdict.get('full_SHA256_verified'):
            held+=1;continue
        # Existing catalog rows have no files in the incremental staging tree.
        # Do not infer their source positions or add them to this new queue.
        rows=[p for p in album['images'] if (stage/p['key']).is_file()
              or (p.get('preview') and (stage/p['preview']).is_file())]
        if not rows:continue
        specs=[]
        for p in rows:
            checked_row(model,aid,p)
            for key,size,digest in [('key','bytes','sha256'),('preview','preview_bytes','preview_sha256')]:
                path=(stage/p[key]).resolve()
                if not path.is_relative_to(stage.resolve()) or not path.is_file():
                    raise ValueError('Recovered work must retain every exact local original and preview')
                specs.append((p[key],p[size],p[digest]))
        fingerprint=hashlib.sha256(json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest()
        if verdict.get('media_checked')!=len(specs) or verdict.get('verified_specs_sha256')!=fingerprint:
            raise ValueError('Per-work exact remote proof differs from staged media')
        source=evidence.get(aid,{})
        if not source.get('saved_reference_anchors',0)>=3:
            # Generic article rows and unidentified cuts remain withheld.
            held+=1;continue
        target=stage/'verified-work-recovery'/aid
        metadata=target/'metadata';metadata.mkdir(parents=True,exist_ok=False)
        for p in rows:
            for key in ('key','preview'):
                local=target/p[key];local.parent.mkdir(parents=True,exist_ok=True)
                if not local.exists():os.link(stage/p[key],local)
        (metadata/'catalog.json').write_bytes(serialize({'schema_version':1,'model':model,
            'albums':[{**album,'images':rows}]}))
        (metadata/'collection-audit.json').write_bytes(serialize({**audit,'results':[source]}))
        prepared=prepare(target,owner)
        # prepare may normalize legacy names. Bind proof to the keys actually
        # read remotely: a renamed object has no corresponding remote proof.
        prepared_specs=[(p[key],p[size],p[digest]) for a in prepared['albums'] for p in a['images']
            for key,size,digest in [('key','bytes','sha256'),('preview','preview_bytes','preview_sha256')]]
        if sorted(prepared_specs)!=sorted(specs):raise ValueError('Recovery cannot rename an unverified remote object')
        (metadata/'remote-verification.json').write_bytes(serialize({'model':model,**verdict,
            'photos':len(rows),'scope':'every_original_and_preview_of_this_complete_work_read_this_failed_job'}))
        persist(target,remote);queued+=len(rows)
    print('WHOLE_VERIFIED_WORKS_RECOVERED_PRIVATELY',model,queued,'HELD_WORKS',held,
        'FAILED_COLLECTION_JOB_REMAINS_FAILED',True,'GALLERY_PUBLISHED',False,flush=True)
    return queued


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--owner',type=Path,required=True);p.add_argument('--remote',required=True);a=p.parse_args()
    recover(a.stage,json.loads(a.owner.read_text()),a.remote)
