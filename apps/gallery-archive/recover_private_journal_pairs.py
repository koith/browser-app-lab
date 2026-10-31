"""Recover individually verified pairs from an exact private producer journal.

Originals/previews are READ ONLY. Only complete SHA-verified pairs become a
delta. Failed pairs remain explicitly held; no retry, alternate identity,
source recrawl, replacement, re-encoding or live upload endpoint is used.
"""
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re

import requests
from PIL import Image

from defer_verified_batch import serialize
from load_pending_individual import storage
from merge_incremental import checked_row
from native_qa_checkpoint import metadata_fingerprint
from private_collection_snapshot import REMOTES,STATE
from publish_owner_index import clean_catalog

ROOT=Path(__file__).resolve().parents[2]
REPO='koith/browser-app-lab'
HEX=re.compile(r'[a-f0-9]{64}\Z')
CREATORS={'yui':'https://teapawt.net/super_yuisan','mimmi':'https://teapawt.net/Mimmi_official'}


def github(path):
    response=requests.get('https://api.github.com/repos/'+REPO+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'},timeout=(12,45))
    response.raise_for_status();return response.json()


def producer_proof(request):
    run=github('/actions/runs/'+str(request['producer_run']))
    if (run.get('head_sha')!=request['producer_head'] or run.get('head_branch')!='main'
            or run.get('head_repository',{}).get('full_name')!=REPO
            or run.get('path')!='.github/workflows/gallery-direct-individual-archive.yml'):
        raise ValueError('Private journal producer is not the exact same-repository main workflow')
    jobs=github(f"/actions/runs/{request['producer_run']}/attempts/{request['producer_attempt']}/jobs?per_page=100")
    if jobs.get('total_count',101)>100:raise ValueError('Producer job list exceeds bound')
    matches=[j for j in jobs['jobs'] if j['name']=='collect-store-readback ('+request['model']+')']
    if len(matches)!=1:raise ValueError('Expected one exact producer job')
    job=matches[0]
    if not any(s.get('name')=='Preserve unverified source correspondence privately before any original transfer'
            and s.get('conclusion')=='success' for s in job.get('steps',[])):
        raise ValueError('Source journal was not independently preserved by the producer')
    response=requests.get(f"https://api.github.com/repos/{REPO}/actions/jobs/{job['id']}/logs",
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']},timeout=(12,45))
    response.raise_for_status()
    if len(response.content)>5_000_000:raise ValueError('Producer logs exceed bound')
    pattern=r'PRIVATE_UNVERIFIED_SOURCE_JOURNAL_PRESERVED '+request['model']+r' (\d+) METADATA_SHA ([a-f0-9]{64})'
    evidence=re.findall(pattern,response.text)
    if evidence!=[(str(request['expected_collected_photos']),request['journal_sha256'])]:
        raise ValueError('Private journal differs from the actual producer log digest/count')


class HeldPhoto(ValueError):pass


def exact_image(photo,field,remote,reader):
    size,digest=('bytes','sha256') if field=='key' else ('preview_bytes','preview_sha256')
    raw=reader(['cat',remote+'/'+photo[field]],limit=photo[size]+1)
    if raw is None:raise HeldPhoto('missing_existing_object')
    if len(raw)!=photo[size] or hashlib.sha256(raw).hexdigest()!=photo[digest]:
        if len(raw)<=512:
            try:code=json.loads(raw).get('errno')
            except (ValueError,TypeError,AttributeError):code=None
            if type(code) is int:raise HeldPhoto('provider_errno_'+str(code))
        raise HeldPhoto('exact_SHA_or_byte_length_mismatch')
    with Image.open(BytesIO(raw)) as image:image.verify()
    with Image.open(BytesIO(raw)) as image:
        image.load()
        if field=='key':
            if image.format not in ('JPEG','PNG','WEBP') or image.size!=(photo['width'],photo['height']):
                raise HeldPhoto('original_decoded_dimensions_or_format_changed')
        elif image.format!='WEBP' or not (0<image.width<=photo['width'] and 0<image.height<=photo['height']):
            raise HeldPhoto('invalid_separate_preview')
    return raw


def recover(snapshot,owner,reviewed,stage,reader=storage):
    model=owner['model'];remote=REMOTES[model]
    if (snapshot.get('schema_version')!=1 or snapshot.get('model')!=model
            or snapshot.get('state')!=STATE or snapshot.get('remote_media_verified') is not False
            or snapshot.get('pending_admission_queue') is not False):
        raise ValueError('Only the exact private unverified producer journal is allowed')
    catalog=snapshot['catalog'];audit=snapshot['collection_audit']
    if catalog.get('model')!=model or catalog.get('schema_version')!=1 or audit.get('model')!=model:
        raise ValueError('Wrong private journal model')
    if not 1<=sum(len(a['images']) for a in catalog['albums'])<=500:raise ValueError('Journal photo bound exceeded')
    existing={a['id']:a for a in owner['albums']}
    seen={p['sha256'] for a in owner['albums'] for p in a['images']}
    evidence={a['id']:a for a in audit['results']}
    accepted=[];held=[];skipped=0;specs=[];results=[];processed=0
    def progress():
        nonlocal processed
        processed+=1
        if processed%10==0:print('EXISTING_PRIVATE_PAIR_CHECK_PROGRESS',model,processed,
            'COMPLETE_PAIRS',len(specs)//2,'HELD',len(held),flush=True)
    for album in catalog['albums']:
        aid=album['id'];book=reviewed.get(aid);context=evidence.get(aid,{})
        if aid not in existing or not book:raise ValueError('Recovery only supplements reviewed existing works')
        visual=book.get('visual_reference_required') is True
        if visual:
            if context.get('source')!=book['source'] or context.get('saved_reference_anchors',0)<3:
                raise ValueError('Visual work has no trusted saved-cut source context')
            old={p['number']:p['sha256'] for p in existing[aid]['images']}
            anchors={p['owner_sha256'] for p in context.get('saved_cut_correspondence',[])
                if old.get(p['owner_archive_number'])==p['owner_sha256'] and 0<=p.get('whole_frame_visual_error',999)<=4}
            if len(anchors)<3:raise ValueError('Saved-cut identity anchors changed')
        elif book.get('source')!=CREATORS[model] or context.get('engine')!='requests_scoped_public_pagination':
            raise ValueError('Nonvisual recovery requires the reviewed professional creator feed')
        rows=[];next_number=max(p['number'] for p in existing[aid]['images'])+1
        for photo in album['images']:
            checked_row(model,aid,photo)
            for field,prefix,extensions in [('key','originals','jpg|jpeg|png|webp'),('preview','previews','webp')]:
                if not re.fullmatch(re.escape(prefix+'/'+aid+'/')+r'[a-z0-9-]+\.(?:'+extensions+r')',photo[field]):
                    raise ValueError('Unsafe exact existing private object key')
            if photo['sha256'] in seen:skipped+=1;continue
            if photo.get('higher_resolution_replacement'):
                held.append({'work':aid,'archive_collection_number':photo['number'],'cause':'replacement_outside_append_only_recovery'});continue
            if visual and (photo.get('work_identity_saved_cut_anchors',0)<3
                    or type(photo.get('source_photo_number')) is not int
                    or photo['source_photo_number'] in context.get('unresolved_source_numbers',[])):
                raise ValueError('Unresolved source identity cannot enter a recovered pair')
            failure={'work':aid,'archive_collection_number':photo['number'],
                'source_file_number':photo.get('source_photo_number'),'source_numbering':photo.get('source_numbering')}
            try:
                if not 300<=photo['width']<=20000 or not 300<=photo['height']<=20000 or photo['width']*photo['height']>40_000_000:
                    raise HeldPhoto('original_dimensions_outside_existing_budget')
                failure['role']='original';original=exact_image(photo,'key',remote,reader)
                failure['role']='preview';preview=exact_image(photo,'preview',remote,reader)
            except Exception as error:
                failure['cause']=str(error) if isinstance(error,HeldPhoto) else 'private_read_or_image_decode_failed'
                held.append(failure);progress();continue
            for field,raw in [('key',original),('preview',preview)]:
                path=stage/photo[field];path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists():
                    if path.read_bytes()!=raw:raise ValueError('Existing staged bytes differ')
                else:
                    with path.open('xb') as output:output.write(raw)
            row={**photo,'number':next_number,'numbering_provenance':'archive_append_order_not_publisher_number'}
            next_number+=1;rows.append(row);seen.add(row['sha256'])
            specs.extend([(row['key'],row['bytes'],row['sha256']),
                          (row['preview'],row['preview_bytes'],row['preview_sha256'])])
            progress()
        if rows:accepted.append({'id':aid,'title':existing[aid]['title'],'images':rows,'complete':False})
        source_held=[h['source_file_number'] for h in held if h['work']==aid and type(h.get('source_file_number')) is int]
        results.append({**context,'id':aid,'recovered_existing_remote_photos':len(rows),
            'unresolved_source_numbers':sorted(set(context.get('unresolved_source_numbers',[]))|set(source_held)),
            'source_edition_all_files_accounted_for':False,'publisher_original_numbering_known':False})
    count=sum(len(a['images']) for a in accepted)
    fingerprint=hashlib.sha256(json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest()
    metadata=stage/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_bytes(serialize({'schema_version':1,'model':model,'albums':accepted}))
    (metadata/'remote-verification.json').write_bytes(serialize({'model':model,'media_checked':len(specs),
        'full_SHA256_verified':len(specs),'failed':0,'photos':count,'verified_specs_sha256':fingerprint,
        'scope':'only_selected_complete_existing_remote_pairs_not_the_whole_source_journal'}))
    (metadata/'collection-audit.json').write_bytes(serialize({'model':model,'new_local_individual_files':0,
        'recovered_existing_remote_files':count,'new_photo_positions':count,'higher_resolution_replacements':0,
        'remote_verified_files':count,'gallery_open_verified_files':0,'photo_bundles_created':0,
        'held_photos':held,'already_indexed_source_rows_skipped':skipped,'results':results}))
    print('EXISTING_PRIVATE_PAIRS_RECOVERED',model,count,'HELD_PHOTOS',len(held),'ALREADY_INDEXED',skipped,
        'ORIGINALS_OR_PREVIEWS_UPLOADED',0,'GALLERY_PUBLISHED',False,flush=True)
    return {'photos':count,'held':len(held),'skipped':skipped}


def main():
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True)
    p.add_argument('--model',choices=REMOTES,required=True);p.add_argument('--owner',type=Path,required=True)
    p.add_argument('--stage',type=Path,required=True);p.add_argument('--github-output',type=Path,required=True);a=p.parse_args()
    os.umask(0o077)
    document=json.loads(a.request.read_text())
    if document.get('schema_version')!=1 or document.get('scope')!='existing_private_photos_only':
        raise ValueError('An explicit protected-branch read-only-photo recovery request is required')
    request=document['models'][a.model]
    if (request['model']!=a.model or not HEX.fullmatch(request['journal_sha256'])
            or not HEX.fullmatch(request['baseline_owner_fingerprint'])
            or not re.fullmatch('[a-f0-9]{40}',request['producer_head'])
            or type(request['producer_run']) is not int or request['producer_run']<=0
            or type(request['producer_attempt']) is not int or not 1<=request['producer_attempt']<=1000
            or type(request['expected_collected_photos']) is not int or not 1<=request['expected_collected_photos']<=500):
        raise ValueError('Invalid exact producer request')
    producer_proof(request)
    owner=json.loads(a.owner.read_text())
    if metadata_fingerprint(clean_catalog(owner,a.model))!=request['baseline_owner_fingerprint']:
        raise ValueError('Current inventory differs from the explicitly QA-completed publication baseline')
    key=f"metadata/unverified-collection-staging/{request['producer_run']}-{request['producer_attempt']}-{a.model}.json"
    raw=storage(['cat',REMOTES[a.model]+'/'+key],limit=2_000_000)
    if raw is None or hashlib.sha256(raw).hexdigest()!=request['journal_sha256']:
        raise ValueError('Exact private journal readback failed; no image was requested')
    data=json.loads(raw)
    if sum(len(x['images']) for x in data['catalog']['albums'])!=request['expected_collected_photos']:
        raise ValueError('Private producer photo count changed')
    reviewed={b['id']:b for b in json.loads((ROOT/f'apps/{a.model}-gallery/public-work-pages.json').read_text())['albums']}
    result=recover(data,owner,reviewed,a.stage)
    with a.github_output.open('a') as output:
        output.write('changed='+str(bool(result['photos'])).lower()+'\nheld='+str(result['held'])+'\n')


if __name__=='__main__':main()
