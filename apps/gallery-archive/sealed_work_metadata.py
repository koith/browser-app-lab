"""Metadata-only handoff to the existing authenticated storage worker.

No image bytes, owner cookie or private key belong in a public repository.
The running worker's ephemeral recipient and the predeclared plaintext digest
bind the encrypted JSON. This never changes a live gallery's permissions.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re

from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPOSITORY='koith/browser-app-lab'
WORKS={'v2ph-actor-z63984ma','v2ph-actor-amn8o34z','v2ph-actor-zo5n754z'}
IMAGE_FIELDS={'sha256','bytes','width','height','extension','preview_sha256','preview_bytes',
    'preview_width','preview_height','source_photo_number','work_identity_saved_cut_anchors'}
COVERAGE_FIELDS={'source','known_web_edition_photos','observed_filename_numbers','saved_cut_correspondence',
    'uncertain_source_numbers','unresolved_source_numbers','source_files_decoded',
    'source_edition_all_files_decoded','source_edition_all_files_accounted_for'}
ANCHOR_FIELDS={'source_file_number','owner_archive_number','owner_sha256','source_sha256','whole_frame_visual_error'}
HEX=re.compile('[a-f0-9]{64}\\Z')


def encode(data):return (json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()


def metadata_only(plan):
    if plan.get('schema_version')!=1 or plan.get('model')!='mimmi':raise ValueError('Wrong existing model')
    albums=[]
    for a in plan.get('albums',[]):
        if a.get('id') not in WORKS:raise ValueError('Unreviewed work is outside this recovery')
        if any(set(p)-IMAGE_FIELDS for p in a['images']):raise ValueError('Only scalar file metadata is allowed')
        coverage=a.get('source_coverage',{})
        if set(coverage)-COVERAGE_FIELDS:raise ValueError('Only bounded source evidence is allowed')
        if any(set(p)-ANCHOR_FIELDS for p in coverage.get('saved_cut_correspondence',[])):
            raise ValueError('Only bounded source correspondence metadata is allowed')
        albums.append({'id':a['id'],'source_coverage':coverage,'images':a['images']})
    if not 1<=len(albums)<=3 or not 1<=sum(len(a['images']) for a in albums)<=300:
        raise ValueError('Existing-work recovery exceeds its scope')
    return {'schema_version':1,'metadata_only':True,'model':'mimmi','albums':albums}


def validate(data,owner,reviewed):
    if (set(data)!={'schema_version','metadata_only','model','albums'} or data.get('metadata_only') is not True
            or owner.get('model')!='mimmi' or owner.get('schema_version')!=1):
        raise ValueError('Wrong metadata-only owner scope')
    normalized=metadata_only(data)
    if normalized!=data:raise ValueError('Unexpected metadata fields')
    existing={a['id']:a for a in owner['albums']};seen_ids=set();all_sha=set()
    for a in data['albums']:
        aid=a['id'];book=reviewed.get(aid)
        if aid in seen_ids or aid not in existing or not book or not book.get('visual_reference_required'):
            raise ValueError('A reviewed existing owner work is required')
        seen_ids.add(aid);c=a['source_coverage'];total=book['public_web_edition_photos']
        if (c.get('source')!=book['source'] or c.get('known_web_edition_photos')!=total
                or c.get('source_files_decoded')!=total or c.get('source_edition_all_files_accounted_for') is not True
                or c.get('unresolved_source_numbers')!=[] or c.get('uncertain_source_numbers')!=[]
                or c.get('observed_filename_numbers')!=list(range(1,total+1))):
            raise ValueError('Complete prior observed source evidence is required')
        old={p['number']:p for p in existing[aid]['images']};numbers=set();anchors=set()
        for p in c.get('saved_cut_correspondence',[]):
            n=p['source_file_number'];reference=old.get(p['owner_archive_number'])
            if (type(n) is not int or not 1<=n<=total or n in numbers or not reference
                    or p['owner_sha256']!=reference['sha256'] or not HEX.fullmatch(p['source_sha256'])
                    or type(p['whole_frame_visual_error']) not in (int,float)
                    or not 0<=p['whole_frame_visual_error']<=4):raise ValueError('Exact saved-cut anchors changed')
            numbers.add(n);anchors.add(p['owner_sha256'])
        if len(anchors)<3:raise ValueError('At least three exact saved-cut anchors are required')
        for p in a['images']:
            n=p.get('source_photo_number')
            if (set(p)!=IMAGE_FIELDS or not HEX.fullmatch(p['sha256']) or not HEX.fullmatch(p['preview_sha256'])
                    or p['sha256'] in all_sha or type(n) is not int or n in numbers or not 1<=n<=total
                    or type(p['work_identity_saved_cut_anchors']) is not int or p['work_identity_saved_cut_anchors']<3
                    or p['extension'] not in ('jpg','jpeg','png','webp')):raise ValueError('Invalid exact photo metadata')
            for key,lower,upper in [('bytes',4500,35000000),('preview_bytes',1,35000000),
                    ('width',300,20000),('height',300,20000),('preview_width',1,20000),('preview_height',1,20000)]:
                if type(p[key]) is not int or not lower<=p[key]<=upper:raise ValueError('Invalid media bounds')
            if p['width']*p['height']>40000000:raise ValueError('Original exceeds existing decode budget')
            numbers.add(n);all_sha.add(p['sha256'])
        if numbers!=set(range(1,total+1)):raise ValueError('Source numbering must remain fully accounted for')
    return data


def associated(recipient):
    if (recipient.get('repository')!=REPOSITORY or recipient.get('model')!='mimmi'
            or type(recipient.get('run_id')) is not int or recipient['run_id']<=0
            or type(recipient.get('attempt')) is not int or recipient['attempt']<=0
            or not HEX.fullmatch(recipient.get('metadata_sha256',''))):raise ValueError('Invalid ephemeral metadata recipient')
    return f"metadata-only\n{REPOSITORY}\n{recipient['run_id']}\n{recipient['attempt']}\n{recipient['metadata_sha256']}".encode()


def seal(raw,recipient):
    aad=associated(recipient)
    if len(raw)>2000000 or hashlib.sha256(raw).hexdigest()!=recipient['metadata_sha256']:
        raise ValueError('Metadata differs from the predeclared exact digest')
    data=json.loads(raw)
    if metadata_only(data)!=data:raise ValueError('Only exact scalar metadata can be sealed')
    key=os.urandom(32);nonce=os.urandom(12)
    public=serialization.load_pem_public_key(recipient['public_key_pem'].encode())
    if not isinstance(public,rsa.RSAPublicKey) or public.key_size<2048:raise ValueError('Invalid ephemeral recipient key')
    wrapped=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=aad))
    b64=lambda value:base64.b64encode(value).decode()
    return {'schema_version':1,'metadata_only':True,'run_id':recipient['run_id'],'attempt':recipient['attempt'],
        'metadata_sha256':recipient['metadata_sha256'],'wrapped_key':b64(wrapped),'nonce':b64(nonce),
        'ciphertext':b64(AESGCM(key).encrypt(nonce,raw,aad))}


def unseal(envelope,recipient,private):
    aad=associated(recipient)
    if (set(envelope)!={'schema_version','metadata_only','run_id','attempt','metadata_sha256','wrapped_key','nonce','ciphertext'}
            or envelope.get('schema_version')!=1 or envelope.get('metadata_only') is not True
            or any(envelope.get(k)!=recipient[k] for k in ('run_id','attempt','metadata_sha256'))):
        raise ValueError('Wrong metadata envelope scope')
    dec=lambda key:base64.b64decode(envelope[key],validate=True)
    key=private.decrypt(dec('wrapped_key'),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=aad))
    raw=AESGCM(key).decrypt(dec('nonce'),dec('ciphertext'),aad)
    if len(raw)>2000000 or hashlib.sha256(raw).hexdigest()!=recipient['metadata_sha256']:
        raise ValueError('Exact metadata digest changed')
    return json.loads(raw)


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    a=s.add_parser('prepare');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a=s.add_parser('seal');a.add_argument('--metadata',type=Path,required=True);a.add_argument('--recipient',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.mode=='prepare':
        raw=encode(metadata_only(json.loads(args.manifest.read_text())))
        fd=os.open(args.out,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw)
        print('EXACT_METADATA_ONLY_DIGEST',hashlib.sha256(raw).hexdigest(),'IMAGE_BYTES_INCLUDED',False)
    else:
        envelope=seal(args.metadata.read_bytes(),json.loads(args.recipient.read_text()))
        args.out.write_bytes(encode(envelope));print('SEALED_METADATA_ONLY_READY',envelope['run_id'],envelope['attempt'])
