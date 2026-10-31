"""Persist a verified private batch without changing a live gallery during QA.

The existing pending loader independently reads every original again at release.
No photo bundles, public source mapping, credentials, or new upload capability.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from merge_incremental import checked_row
from transfer_individual_files import checked


def serialize(document):
    return (json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def prepare(stage,owner):
    manifest=stage/'metadata/catalog.json'
    document=json.loads(manifest.read_text())
    if document['model']!=owner['model'] or document.get('schema_version')!=1:
        raise ValueError('Wrong deferred owner archive')
    old={a['id']:a for a in owner['albums']}
    existing={p['sha256'] for a in old.values() for p in a['images']}
    audit=json.loads((stage/'metadata/collection-audit.json').read_text())
    evidence={a['id']:a for a in audit['results']}
    albums=[]
    for album in document['albums']:
        aid=album['id']
        if aid not in old:raise ValueError('Deferred publication only supplements existing works')
        source=evidence.get(aid,{})
        if not source.get('source_edition_all_files_accounted_for'):
            raise ValueError('Incomplete public edition must remain in local review')
        images=[]
        for photo in album['images']:
            checked_row(document['model'],aid,photo)
            if (photo['sha256'] in existing or photo.get('higher_resolution_replacement')
                    or photo.get('work_identity_saved_cut_anchors',0)<3
                    or type(photo.get('source_photo_number')) is not int
                    or photo['source_photo_number']<1):
                raise ValueError('Deferred queue requires independently identified missing cuts')
            targets={}
            for field,digest,size,prefix in [('key','sha256','bytes','originals'),
                    ('preview','preview_sha256','preview_bytes','previews')]:
                origin=(stage/photo[field]).resolve()
                if not origin.is_relative_to(stage.resolve()):raise ValueError('Unsafe staging path')
                _,dimensions,extension=checked(origin,photo[digest],photo[size])
                if field=='key' and dimensions!=(photo['width'],photo['height']):
                    raise ValueError('Original dimensions changed')
                if field=='preview' and extension!='webp':raise ValueError('Wrong preview format')
                relative=f'{prefix}/{aid}/{photo[digest]}.{extension}'
                target=stage/relative
                if origin!=target.resolve():
                    if target.exists():raise ValueError('Unexpected duplicate staged content path')
                    origin.replace(target)
                targets[field]=relative
            images.append({**photo,**targets})
            existing.add(photo['sha256'])
        albums.append({**album,'images':images,'source_coverage':{k:v for k,v in source.items()
            if k in ('source','known_web_edition_photos','observed_filename_numbers','saved_cut_correspondence',
                'uncertain_source_numbers','unresolved_source_numbers','source_files_decoded',
                'source_edition_all_files_accounted_for')}})
    document['albums']=albums
    manifest.write_bytes(serialize(document))
    (stage/'metadata/deferred-delta.json').write_bytes(serialize(document))
    return document


def verified_queue(stage):
    document=json.loads((stage/'metadata/deferred-delta.json').read_text())
    audit=json.loads((stage/'metadata/remote-verification.json').read_text())
    for album in document['albums']:
        for photo in album['images']:
            checked_row(document['model'],album['id'],photo)
            if photo.get('work_identity_saved_cut_anchors',0)<3:
                raise ValueError('Work correspondence evidence changed')
            _,dimensions,_=checked(stage/photo['key'],photo['sha256'],photo['bytes'])
            if dimensions!=(photo['width'],photo['height']):raise ValueError('Queued dimensions changed')
    specs=[(p[field],p[size],p[digest]) for a in document['albums'] for p in a['images']
        for field,size,digest in [('key','bytes','sha256'),('preview','preview_bytes','preview_sha256')]]
    fingerprint=hashlib.sha256(json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest()
    if (not specs or audit.get('model')!=document['model'] or audit.get('failed')!=0
            or audit.get('media_checked')!=len(specs) or audit.get('full_SHA256_verified')!=len(specs)
            or audit.get('verified_specs_sha256')!=fingerprint):
        raise ValueError('Every exact deferred object must pass remote SHA readback first')
    body={'schema_version':1,'model':document['model'],'albums':document['albums']}
    pin=hashlib.sha256(serialize(body)).hexdigest()
    body['source_batch_sha256']=pin
    return pin,serialize(body)


def persist(stage,remote):
    pin,raw=verified_queue(stage)
    local=stage/'metadata'/f'{pin}.json';local.write_bytes(raw)
    target=remote.rstrip('/')+'/metadata/pending-individual/'+json.loads(raw)['model']+'/'+pin+'.json'
    run=lambda args:subprocess.run(['rclone',*args,'--timeout=60s','--retries=1'],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=75,check=True).stdout
    run(['copyto',str(local),target,'--ignore-times'])
    if run(['cat',target])!=raw:raise ValueError('Private deferred queue readback mismatch')
    count=sum(len(a['images']) for a in json.loads(raw)['albums'])
    print('PRIVATE_VERIFIED_BATCH_DEFERRED',count,'OWNER_INDEX_PUBLISHED',False,'GALLERY_QA_PASSED',False,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','persist'])
    p.add_argument('--stage',type=Path,required=True);p.add_argument('--owner',type=Path);p.add_argument('--remote')
    a=p.parse_args()
    if a.operation=='prepare':prepare(a.stage,json.loads(a.owner.read_text()))
    else:persist(a.stage,a.remote)
