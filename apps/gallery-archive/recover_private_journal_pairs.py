"""Recover individually verified pairs from an exact private producer journal.

Originals/previews are READ ONLY. Normally both variants must verify. The
explicit Mimmi preview-hold mode reads only the already healthy original;
the existing viewer can use those exact bytes for its thumbnail as well.
No denied preview/original retry, alternate identity, source recrawl,
replacement, re-encoding or live upload endpoint is used.
"""
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

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
# One interrupted, already reviewed collector transaction; never a general
# permission to admit article rehosts or an arbitrary private journal.
ARTICLE_PRODUCER={'model':'mimmi','producer_run':44779438809,'producer_attempt':1,
    'producer_head':'48a6271b32361dac81aa818c0b469af78fbe6c57',
    'journal_sha256':'0dd943f0afa7c878ca4e77552ff7fef0032617563b3fc875e0a4de8448a2b8e1',
    'expected_collected_photos':500}
ARTICLE_RECOVERY={'run':44888685318,'attempt':1,'head':'c5bc7b2deb50f27c3e8b94389fbfee1c0fdb282a'}
ARTICLE_COUNTS={'already_indexed':24,'original_unavailable':341,'original_verified':135,'preview_verified':134}
ARTICLE_WORK_COUNTS={'djawa-pop-kitty-party':120,'v2ph-actor-z4m985xa':3,
    'djawa-christmas-special-2023-mimmi':36,'djawa-blossom-reverie':21,
    'djawa-christmas-special-2025-mimmi-the-christmas-witch':97,
    'djawa-in-the-summer-sunshine-part-1':65,'djawa-rei-beyond-the-heart':73,
    'djawa-asuna-the-maid':30,'djawa-christmas-special-2021-mimmi':55}
ARTICLE_ENGINE='requests_scrapy_chromium_article_photo'


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
    try:
        response=requests.get(f"https://api.github.com/repos/{REPO}/actions/jobs/{job['id']}/logs",
            headers={'Authorization':'Bearer '+os.environ['GH_TOKEN']},timeout=(12,45))
        response.raise_for_status()
    except requests.RequestException as error:
        # Redirected log URLs may contain temporary credentials. Never include
        # a requests exception/URL in a public Actions traceback.
        raise ValueError('Exact producer log retrieval failed HTTP '+str(
            getattr(error.response,'status_code',None))) from None
    if len(response.content)>5_000_000:raise ValueError('Producer logs exceed bound')
    pattern=r'PRIVATE_UNVERIFIED_SOURCE_JOURNAL_PRESERVED '+request['model']+r' (\d+)(?: READBACK_METHOD [a-z_]+)? METADATA_SHA ([a-f0-9]{64})'
    evidence=re.findall(pattern,response.text)
    if evidence!=[(str(request['expected_collected_photos']),request['journal_sha256'])]:
        raise ValueError('Private journal differs from the actual producer log digest/count')
    return {'job':job,'log':response.text}


def trusted_article_producer(request,proof):
    """Bind the previously audited source/model/work checks to one exact run."""
    if (any(request.get(k)!=v for k,v in ARTICLE_PRODUCER.items())
            or request.get('trusted_article_recovery')!=ARTICLE_RECOVERY
            or request.get('storage_census_only') or request.get('preview_only_hold_from')
            or request.get('official_publisher_sha_only')):
        raise ValueError('Article continuation is restricted to the exact reviewed producer and recovery')
    job=proof['job'];log=re.sub(r'\x1b\[[0-9;]*m','',proof['log'])
    if job.get('id')!=136439087942 or not any(
            s.get('name')=='Collect all observed public pages into individually verified files, without photo ZIPs'
            and s.get('conclusion')=='success' for s in job.get('steps',[])):
        raise ValueError('Exact reviewed collector did not complete')
    commands=[line for line in log.splitlines() if 'python apps/gallery-archive/direct_photo_pipeline.py ' in line]
    if len(commands)!=1 or not all(flag in commands[0] for flag in (
            '--model "$MODEL"','--owner "$RUNNER_TEMP/owner-before.json"',
            '--max-new 500','--max-pages 60','--alternative-engines','--reviewed-source-only')):
        raise ValueError('Exact collector reviewed-source-only invocation is not proven')
    counts={}
    for aid,body in re.findall(r'DIRECT_WORK_SOURCE_EVIDENCE mimmi ([a-z0-9-]+) (\{[^\n]+\})',log):
        record=json.loads(body)
        if record.get('individual_files_saved',0):
            if aid in counts or record.get('new_staged_files_from_alternative_engines')!=record['individual_files_saved']:
                raise ValueError('Ambiguous exact producer work evidence')
            counts[aid]=record['individual_files_saved']
    if counts!=ARTICLE_WORK_COUNTS:raise ValueError('Exact producer per-work counts changed')


class HeldPhoto(ValueError):pass


def preview_hold_selection(audit,model):
    if model!='mimmi' or audit.get('model')!=model:
        raise ValueError('Original thumbnail recovery is restricted to Mimmi')
    held=audit.get('held_photos')
    if not isinstance(held,list) or len(held)>500:raise ValueError('Invalid prior private held-photo audit')
    selected=set()
    for p in held:
        if p.get('role')!='preview':continue
        key=(p.get('work'),p.get('archive_collection_number'))
        if not isinstance(key[0],str) or type(key[1]) is not int or key[1]<1 or key in selected:
            raise ValueError('Ambiguous prior preview-only hold')
        selected.add(key)
    return selected


def prior_recovery_proof(request,model):
    run_id=request['run'];attempt=request['attempt'];head=request['head']
    if (type(run_id) is not int or run_id<1 or type(attempt) is not int or not 1<=attempt<=1000
            or not isinstance(head,str) or not re.fullmatch('[a-f0-9]{40}',head)):
        raise ValueError('Invalid exact prior recovery request')
    run=github('/actions/runs/'+str(run_id))
    if (run.get('head_sha')!=head or run.get('head_branch')!='main'
            or run.get('head_repository',{}).get('full_name')!=REPO
            or run.get('path')!='.github/workflows/gallery-existing-private-journal-recovery.yml'):
        raise ValueError('Prior private audit is not from the exact same-repository recovery')
    jobs=github(f'/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100')
    if jobs.get('total_count',101)>100:raise ValueError('Prior recovery job bound exceeded')
    matches=[j for j in jobs['jobs'] if j['name']=='recover-already-stored-pairs ('+model+')']
    if len(matches)!=1 or not any(s.get('name')=='Preserve complete per-photo held reasons in the SAME private account'
            and s.get('conclusion')=='success' for s in matches[0].get('steps',[])):
        raise ValueError('Prior private held-photo audit was not independently preserved')
    return {'run':run,'job':matches[0]}


def completed_baseline_proof(document):
    run_id=document.get('completed_baseline_native_QA_run')
    head=document.get('completed_owner_index_commit')
    if type(run_id) is not int or run_id<1 or not isinstance(head,str) or not re.fullmatch('[a-f0-9]{40}',head):
        raise ValueError('An exact completed native baseline is required')
    run=github('/actions/runs/'+str(run_id))
    if (run.get('conclusion')!='success' or run.get('status')!='completed'
            or run.get('head_sha')!=head or run.get('head_branch')!='main'
            or run.get('head_repository',{}).get('full_name')!=REPO
            or run.get('path')!='.github/workflows/gallery-newly-stored-photo-qa.yml'):
        raise ValueError('Exact baseline native QA has not completed successfully')


def copyto_bytes(path,limit,command=None):
    """Normal read via the SAME authenticated account; no remote mutation.

    Called only after the exact source returned errno 400141. The caller
    verifies complete byte length, SHA-256 and image decoding independently.
    """
    with tempfile.TemporaryDirectory(prefix='pair-recovery-copyto-') as tmp:
        dest=Path(tmp)/'readback'
        cmd=([str(x).replace('{dest}',str(dest)).replace('{src}',path) for x in command] if command
             else ['rclone','copyto',path,str(dest),'--timeout=65s','--retries=1'])
        try:proc=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False,timeout=75)
        except subprocess.TimeoutExpired:raise HeldPhoto('copyto_read_deadline') from None
        except FileNotFoundError:raise HeldPhoto('copyto_client_unavailable') from None
        if proc.returncode or not dest.is_file():raise HeldPhoto('copyto_read_failed')
        if dest.stat().st_size>limit:raise HeldPhoto('copyto_oversized')
        return dest.read_bytes()


def exact_image(photo,field,remote,reader,copyto=None):
    size,digest=('bytes','sha256') if field=='key' else ('preview_bytes','preview_sha256')
    raw=reader(['cat',remote+'/'+photo[field]],limit=photo[size]+1)
    if raw is None:raise HeldPhoto('missing_existing_object')
    if len(raw)!=photo[size] or hashlib.sha256(raw).hexdigest()!=photo[digest]:
        code=None
        if len(raw)<=512:
            try:code=json.loads(raw).get('errno')
            except (ValueError,TypeError,AttributeError):code=None
        if code==400141 and copyto is not None:
            raw=copyto(remote+'/'+photo[field],photo[size])
            if len(raw)!=photo[size] or hashlib.sha256(raw).hexdigest()!=photo[digest]:
                raise HeldPhoto('copyto_exact_SHA_or_byte_length_mismatch')
            print('PAIR_RECOVERY_COPYTO_EXACT_SHA256',field,flush=True)
        elif type(code) is int:raise HeldPhoto('provider_errno_'+str(code))
        else:raise HeldPhoto('exact_SHA_or_byte_length_mismatch')
    with Image.open(BytesIO(raw)) as image:image.verify()
    with Image.open(BytesIO(raw)) as image:
        image.load()
        if field=='key':
            if image.format not in ('JPEG','PNG','WEBP') or image.size!=(photo['width'],photo['height']):
                raise HeldPhoto('original_decoded_dimensions_or_format_changed')
        elif image.format!='WEBP' or not (0<image.width<=photo['width'] and 0<image.height<=photo['height']):
            raise HeldPhoto('invalid_separate_preview')
    return raw


def publisher_exact_samples(document, reviewed):
    """Only previously recorded official publisher bytes, never an arbitrary URL."""
    from official_sample_recovery import _publisher_page, _publisher_photo
    result={}
    for a in document.get('albums',[]):
        aid=a.get('id')
        book=reviewed.get(aid,{})
        if (a.get('publisher')!='DJAWA' or a.get('source')!=book.get('source')
                or not _publisher_page(a.get('source'))):
            continue
        result[aid]={(p.get('sha256'),p.get('bytes'),p.get('width'),p.get('height'))
            for p in a.get('samples',[]) if _publisher_photo(p.get('url'))
            and isinstance(p.get('sha256'),str) and HEX.fullmatch(p['sha256'])}
    return result


def recover(snapshot,owner,reviewed,stage,reader=storage,preview_hold_audit=None,copyto=None,
            publisher_samples=None):
    model=owner['model'];remote=REMOTES[model]
    preview_holds=None if preview_hold_audit is None else preview_hold_selection(preview_hold_audit,model)
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
            'COMPLETE_PHOTOS',sum(len(a['images']) for a in accepted)+len(rows),'HELD',len(held),flush=True)
    for album in catalog['albums']:
        aid=album['id'];book=reviewed.get(aid);context=evidence.get(aid,{})
        if publisher_samples is not None and (aid not in existing or not book or aid not in publisher_samples):
            for photo in album['images']:
                if photo['sha256'] in seen:skipped+=1;continue
                held.append({'work':aid,'archive_collection_number':photo['number'],
                             'source_file_number':photo.get('source_photo_number'),
                             'cause':'no_exact_publisher_manifest_work'})
            continue
        if aid not in existing or not book:raise ValueError('Recovery only supplements reviewed existing works')
        visual=book.get('visual_reference_required') is True and publisher_samples is None
        if visual:
            if context.get('source')!=book['source'] or context.get('saved_reference_anchors',0)<3:
                raise ValueError('Visual work has no trusted saved-cut source context')
            old={p['number']:p['sha256'] for p in existing[aid]['images']}
            anchors={p['owner_sha256'] for p in context.get('saved_cut_correspondence',[])
                if old.get(p['owner_archive_number'])==p['owner_sha256'] and 0<=p.get('whole_frame_visual_error',999)<=4}
            if len(anchors)<3:raise ValueError('Saved-cut identity anchors changed')
        elif publisher_samples is None and (book.get('source')!=CREATORS[model] or context.get('engine')!='requests_scoped_public_pagination'):
            raise ValueError('Nonvisual recovery requires the reviewed professional creator feed')
        rows=[];next_number=max(p['number'] for p in existing[aid]['images'])+1
        for photo in album['images']:
            if preview_holds is not None and (aid,photo['number']) not in preview_holds:continue
            checked_row(model,aid,photo)
            for field,prefix,extensions in [('key','originals','jpg|jpeg|png|webp'),('preview','previews','webp')]:
                if not re.fullmatch(re.escape(prefix+'/'+aid+'/')+r'[a-z0-9-]+\.(?:'+extensions+r')',photo[field]):
                    raise ValueError('Unsafe exact existing private object key')
            if photo['sha256'] in seen:skipped+=1;continue
            if publisher_samples is not None and (photo['sha256'],photo['bytes'],photo['width'],photo['height']) not in publisher_samples[aid]:
                held.append({'work':aid,'archive_collection_number':photo['number'],
                             'source_file_number':photo.get('source_photo_number'),
                             'cause':'no_exact_publisher_manifest_photo'})
                progress();continue
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
                failure['role']='original';original=exact_image(photo,'key',remote,reader,copyto)
                if preview_holds is None:
                    failure['role']='preview';preview=exact_image(photo,'preview',remote,reader,copyto)
            except Exception as error:
                failure['cause']=str(error) if isinstance(error,HeldPhoto) else 'private_read_or_image_decode_failed'
                held.append(failure);progress();continue
            variants=[('key',original)] if preview_holds is not None else [('key',original),('preview',preview)]
            for field,raw in variants:
                path=stage/photo[field];path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists():
                    if path.read_bytes()!=raw:raise ValueError('Existing staged bytes differ')
                else:
                    with path.open('xb') as output:output.write(raw)
            row={**photo,'number':next_number,'numbering_provenance':'archive_append_order_not_publisher_number'}
            if preview_holds is not None:
                for key in ('preview','preview_bytes','preview_sha256'):row.pop(key,None)
                row['preview_fallback']='verified-original'
                checked_row(model,aid,row)
            next_number+=1;rows.append(row);seen.add(row['sha256'])
            specs.append((row['key'],row['bytes'],row['sha256']))
            if preview_holds is None:specs.append((row['preview'],row['preview_bytes'],row['preview_sha256']))
            progress()
        if rows:accepted.append({'id':aid,'title':existing[aid]['title'],'images':rows,'complete':False})
        prior_held=[] if preview_hold_audit is None else preview_hold_audit['held_photos']
        recovered_numbers={r.get('source_photo_number') for r in rows}
        source_held=[h['source_file_number'] for h in held+prior_held
            if h['work']==aid and type(h.get('source_file_number')) is int and h['source_file_number'] not in recovered_numbers]
        results.append({**context,'id':aid,'recovered_existing_remote_photos':len(rows),
            'unresolved_source_numbers':sorted(set(context.get('unresolved_source_numbers',[]))|set(source_held)),
            'source_edition_all_files_accounted_for':False,'publisher_original_numbering_known':False})
    count=sum(len(a['images']) for a in accepted)
    fingerprint=hashlib.sha256(json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest()
    metadata=stage/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_bytes(serialize({'schema_version':1,'model':model,'albums':accepted}))
    (metadata/'remote-verification.json').write_bytes(serialize({'model':model,'media_checked':len(specs),
        'full_SHA256_verified':len(specs),'failed':0,'photos':count,'verified_specs_sha256':fingerprint,
        'scope':('selected_prior_preview_holds_exact_original_readonly_no_preview_request'
                 if preview_holds is not None else 'only_selected_complete_existing_remote_pairs_not_the_whole_source_journal')}))
    (metadata/'collection-audit.json').write_bytes(serialize({'model':model,'new_local_individual_files':0,
        'recovered_existing_remote_files':count,'new_photo_positions':count,'higher_resolution_replacements':0,
        'remote_verified_files':count,'gallery_open_verified_files':0,'photo_bundles_created':0,
        'held_photos':held,'already_indexed_source_rows_skipped':skipped,'results':results,
        'prior_held_photos_not_retried':[] if preview_hold_audit is None else [h for h in preview_hold_audit['held_photos']
            if h.get('role')!='preview'],
        'exact_original_used_as_thumbnail':preview_holds is not None}))
    print('EXISTING_PRIVATE_ORIGINAL_THUMBNAILS_RECOVERED' if preview_holds is not None else 'EXISTING_PRIVATE_PAIRS_RECOVERED',
        model,count,'HELD_PHOTOS',len(held),'ALREADY_INDEXED',skipped,
        'ORIGINALS_OR_PREVIEWS_UPLOADED',0,'GALLERY_PUBLISHED',False,flush=True)
    return {'photos':count,'held':len(held),'skipped':skipped}


def census_journal_storage(snapshot,owner,stage,reader=storage):
    """Check exact stored object names and sizes without source filtering or media reads.

    Storage existence is diagnostic only; it is not proof of rights, byte
    integrity, correct album identity or publication eligibility.
    """
    from collections import Counter
    model=owner['model'];remote=REMOTES[model]
    catalog=snapshot['catalog']
    if catalog.get('model')!=model or catalog.get('schema_version')!=1:
        raise ValueError('Wrong model for journal inventory')
    seen={p['sha256'] for a in owner['albums'] for p in a['images']}
    counts=Counter()
    details=[]
    for album in catalog['albums']:
        aid=album['id']
        missing=[p for p in album['images'] if p['sha256'] not in seen]
        counts['already_indexed']+=len(album['images'])-len(missing)
        if not missing:continue
        # Validate all journal paths before any storage operation.
        for photo in missing:
            checked_row(model,aid,photo)
            for field,prefix,ext in [('key','originals','jpg|jpeg|png|webp'),('preview','previews','webp')]:
                if not re.fullmatch(re.escape(prefix+'/'+aid+'/')+r'[a-z0-9-]+\.(?:'+ext+r')',photo[field]):
                    raise ValueError('Unsafe journal key')
        sizes={}
        for prefix in ('originals','previews'):
            try:
                raw=reader(['lsjson',remote+'/'+prefix+'/'+aid,'--files-only','--max-depth','1'],limit=2_000_000)
                entries=json.loads(raw) if raw is not None else None
                if not isinstance(entries,list):raise ValueError('Listing unavailable')
                listing={}
                for item in entries:
                    name=item.get('Name',item.get('Path'));size=item.get('Size')
                    if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z0-9._-]+',name) or type(size) is not int or size<0 or name in listing:
                        raise ValueError('Invalid listing entry')
                    listing[name]=size
                sizes[prefix]=listing
            except (ValueError,TypeError,AttributeError,OSError,TimeoutError):
                sizes[prefix]=None
        for photo in missing:
            statuses=[]
            for field,prefix,size_field in [('key','originals','bytes'),('preview','previews','preview_bytes')]:
                listing=sizes[prefix]
                name=photo[field].rsplit('/',1)[1]
                status=('unknown' if listing is None else 'missing' if name not in listing
                        else 'size_match' if listing[name]==photo[size_field] else 'size_mismatch')
                counts[prefix+'_'+status]+=1
                statuses.append(status)
            counts['pairs_size_match' if statuses==['size_match','size_match']
                   else 'pairs_unknown' if 'unknown' in statuses else 'pairs_incomplete']+=1
            details.append({'work':aid,'archive_collection_number':photo['number'],
                            'original_status':statuses[0],'preview_status':statuses[1]})
    count=sum(len(a['images']) for a in catalog['albums'])
    report={'model':model,'journal_rows':count,'not_indexed':len(details),
            'counts':dict(counts),'media_read':False,'sha_verified':False,
            'gallery_published':False,'details':details}
    target=stage/'metadata';target.mkdir(parents=True,exist_ok=True)
    (target/'collection-audit.json').write_bytes(serialize(report))
    print('JOURNAL_STORAGE_CENSUS',model,json.dumps({k:v for k,v in report.items() if k!='details'},sort_keys=True),flush=True)
    return report


def verify_existing_private_inventory(snapshot, owner, stage, reader=storage):
    """Save a private index of files already held by the owner.

    No source requests, media uploads, public catalog changes, or admission
    decisions. A size match alone is not enough for an indexed original.
    """
    from collections import Counter
    census=census_journal_storage(snapshot,owner,stage,reader)
    states={(p['work'],p['archive_collection_number']):p for p in census['details']}
    counts=Counter()
    albums=[]
    seen={p['sha256'] for a in owner['albums'] for p in a['images']}
    remote=REMOTES[owner['model']]
    for album in snapshot['catalog']['albums']:
        aid=album['id'];rows=[]
        for photo in album['images']:
            if photo['sha256'] in seen:
                counts['already_indexed']+=1;continue
            state=states.get((aid,photo['number']))
            if not state or state['original_status']!='size_match':
                counts['original_unavailable']+=1;continue
            try:
                # No alternate account, provider endpoint or challenge retry.
                exact_image(photo,'key',remote,reader,copyto=None)
            except Exception as exc:
                counts['original_verification_failed']+=1
                continue
            row={k:photo[k] for k in ('number','key','sha256','bytes','width','height')}
            if state['preview_status']=='size_match':
                try:
                    exact_image(photo,'preview',remote,reader,copyto=None)
                    row.update({k:photo[k] for k in ('preview','preview_bytes','preview_sha256')})
                    counts['preview_verified']+=1
                except Exception:
                    counts['preview_verification_failed']+=1
            if 'preview' not in row:
                row['preview_status']='unverified_or_missing'
            rows.append(row);seen.add(photo['sha256']);counts['original_verified']+=1
            if counts['original_verified']%10==0:
                print('PRIVATE_RECOVERY_ORIGINALS_VERIFIED',counts['original_verified'],flush=True)
        if rows:albums.append({'id':aid,'title':album.get('title',aid),'images':rows})
    manifest={'schema_version':1,'model':owner['model'],
              'scope':'private_existing_object_inventory_not_publication',
              'source_journal_rows':census['journal_rows'],
              'verified_originals':counts['original_verified'],
              'albums':albums,'counts':dict(counts),
              'new_media_uploaded':0,'public_gallery_published':False}
    (stage/'metadata/private-recovered-index.json').write_bytes(serialize(manifest))
    report={**census,'private_verified_counts':dict(counts),'media_read':True}
    (stage/'metadata/collection-audit.json').write_bytes(serialize(report))
    print('PRIVATE_RECOVERY_MANIFEST_READY',owner['model'],json.dumps(dict(counts),sort_keys=True),flush=True)
    return manifest


def require_live_published_inventory(owner, model, published):
    """Permit appended photos, but never discard or overwrite a published slot."""
    current=clean_catalog(owner,model)
    if (published.get('schema_version')!=1 or published.get('model')!=model
            or published.get('storage')!='sha-verified-owner-metadata-only'):
        raise ValueError('Invalid current published inventory')
    def slot_map(doc):
        rows={}
        for album in doc['albums']:
            for photo in album['images']:
                key=(album['id'],photo['number'])
                if key in rows:raise ValueError('Duplicated published position')
                rows[key]=photo
        if len(rows)!=doc['physical_originals_indexed'] or not rows:
            raise ValueError('Published inventory count mismatch')
        return rows
    before=slot_map(published);after=slot_map(current)
    if any(after.get(key)!=row for key,row in before.items()):
        raise ValueError('Current private inventory would lose or change a published photo')
    print('LIVE_RECOVERY_BASELINE_VERIFIED',model,'PUBLISHED',len(before),
          'PRIVATE',len(after),'EXTRA',len(after)-len(before),flush=True)


def article_recovery_selection(snapshot,recovery,audit,owner,producer_owner,reviewed):
    """Intersect exact private inventory signatures with the immutable journal.

    The original collector enforced reviewed media or model/work-scoped article
    extraction before storing bytes. Its fixed commit/run is checked separately.
    This does not invent lost per-file source URLs or saved-cut anchor claims.
    """
    if (snapshot.get('schema_version')!=1 or snapshot.get('model')!='mimmi'
            or snapshot.get('state')!=STATE or snapshot.get('remote_media_verified') is not False
            or snapshot.get('pending_admission_queue') is not False
            or snapshot.get('catalog',{}).get('model')!='mimmi'
            or snapshot.get('catalog',{}).get('schema_version')!=1
            or snapshot.get('collection_audit',{}).get('model')!='mimmi'
            or owner.get('model')!='mimmi' or producer_owner.get('model')!='mimmi'):
        raise ValueError('Invalid exact article journal or owner model')
    if (recovery.get('schema_version')!=1 or recovery.get('model')!='mimmi'
            or recovery.get('scope')!='private_existing_object_inventory_not_publication'
            or recovery.get('source_journal_rows')!=sum(ARTICLE_WORK_COUNTS.values())
            or recovery.get('verified_originals')!=ARTICLE_COUNTS['original_verified']
            or recovery.get('counts')!=ARTICLE_COUNTS or recovery.get('new_media_uploaded')!=0
            or recovery.get('public_gallery_published') is not False
            or audit.get('model')!='mimmi' or audit.get('private_verified_counts')!=ARTICLE_COUNTS
            or audit.get('media_read') is not True or audit.get('gallery_published') is not False):
        raise ValueError('Exact private recovery inventory and audit counts differ')
    existing={a['id'] for a in owner['albums']};prior={a['id'] for a in producer_owner['albums']}
    expected={};counts={};contexts={}
    for context in snapshot['collection_audit']['results']:
        if context.get('id') in ARTICLE_WORK_COUNTS:
            if context['id'] in contexts:raise ValueError('Repeated producer work evidence')
            contexts[context['id']]=context
    for album in snapshot['catalog']['albums']:
        aid=album['id']
        if aid in counts or aid not in existing or aid not in prior:
            raise ValueError('Article recovery requires a registered existing producer and current work')
        counts[aid]=len(album['images']);context=contexts.get(aid,{})
        if (context.get('engine')!=ARTICLE_ENGINE or context.get('individual_files_saved')!=counts[aid]
                or context.get('new_staged_files_from_alternative_engines')!=counts[aid]):
            raise ValueError('Private journal article engine or work counts changed')
        for photo in album['images']:
            checked_row('mimmi',aid,photo)
            for field,prefix,ext in [('key','originals','jpg|jpeg|png|webp'),('preview','previews','webp')]:
                if not re.fullmatch(re.escape(prefix+'/'+aid+'/')+r'[a-z0-9-]+\.(?:'+ext+r')',photo[field]):
                    raise ValueError('Unsafe exact article object key')
            slot=(aid,photo['number'])
            if slot in expected:raise ValueError('Duplicate article journal slot')
            expected[slot]=photo
    if counts!=ARTICLE_WORK_COUNTS:raise ValueError('Private journal work distribution differs from producer')
    details={}
    for item in audit['details']:
        slot=(item['work'],item['archive_collection_number'])
        if slot not in expected or slot in details:raise ValueError('Invalid private recovery audit slot')
        details[slot]=item
    available={slot for slot,item in details.items() if item['original_status']=='size_match'}
    selected={};seen=set();previews=0
    for album in recovery['albums']:
        aid=album['id']
        for row in album['images']:
            slot=(aid,row['number']);photo=expected.get(slot)
            if (photo is None or slot in selected or row['sha256'] in seen
                    or any(row.get(k)!=photo.get(k) for k in ('key','sha256','bytes','width','height'))):
                raise ValueError('Private recovery original signature does not match the exact journal')
            has_preview='preview' in row
            if has_preview:
                if any(row.get(k)!=photo.get(k) for k in ('preview','preview_bytes','preview_sha256')):
                    raise ValueError('Private recovery preview signature differs from journal')
                previews+=1
            elif (row.get('preview_status')!='unverified_or_missing'
                    or any(k in row for k in ('preview_bytes','preview_sha256'))):
                raise ValueError('Invalid prior original-only recovery selection')
            selected[slot]=(photo,has_preview);seen.add(row['sha256'])
    if (set(selected)!=available or len(selected)!=ARTICLE_COUNTS['original_verified']
            or previews!=ARTICLE_COUNTS['preview_verified']
            or sum(item['original_status']=='missing' for item in details.values())!=ARTICLE_COUNTS['original_unavailable']
            or len(expected)-len(details)!=ARTICLE_COUNTS['already_indexed']):
        raise ValueError('Private recovery selection is not the exact verified inventory intersection')
    return expected,selected,contexts


def recover_trusted_article(snapshot,recovery,audit,owner,producer_owner,reviewed,exclusions,stage,reader=storage):
    expected,selected,contexts=article_recovery_selection(snapshot,recovery,audit,owner,producer_owner,reviewed)
    existing={a['id']:a for a in owner['albums']}
    seen={p['sha256'] for a in owner['albums'] for p in a['images']}
    excluded_ids=set(exclusions.get('excluded_album_ids',[]))|set(exclusions.get('excluded_source_ids',[]))
    excluded_shas=set(exclusions.get('excluded_image_sha256',[]));excluded_urls=set(exclusions.get('excluded_source_urls',[]))
    accepted=[];held=[];skipped=0;specs=[];results=[];fallbacks=0;verified=0
    for aid in ARTICLE_WORK_COUNTS:
        rows=[];next_number=max(p['number'] for p in existing[aid]['images'])+1
        book=reviewed.get(aid,{})
        for (work,number),photo in expected.items():
            if work!=aid:continue
            if photo['sha256'] in seen:skipped+=1;continue
            failure={'work':aid,'archive_collection_number':number,'source_file_number':photo.get('source_photo_number')}
            if (aid,number) not in selected:
                held.append({**failure,'cause':'not_in_prior_verified_original_inventory','role':'original'});continue
            if (aid in excluded_ids or photo['sha256'] in excluded_shas
                    or excluded_urls.intersection([book.get('source')]+book.get('source_pages',[]))):
                held.append({**failure,'cause':'current_identity_exclusion'});continue
            if photo.get('higher_resolution_replacement'):
                held.append({**failure,'cause':'replacement_outside_append_only_recovery'});continue
            has_preview=selected[(aid,number)][1]
            try:
                if not 300<=photo['width']<=20000 or not 300<=photo['height']<=20000 or photo['width']*photo['height']>40_000_000:
                    raise HeldPhoto('original_dimensions_outside_existing_budget')
                failure['role']='original';original=exact_image(photo,'key',REMOTES['mimmi'],reader)
                variants=[('key',original)]
                if has_preview:
                    failure['role']='preview';variants.append(('preview',exact_image(photo,'preview',REMOTES['mimmi'],reader)))
            except Exception as exc:
                held.append({**failure,'cause':str(exc) if isinstance(exc,HeldPhoto) else 'private_read_or_image_decode_failed'});continue
            for field,raw in variants:
                path=stage/photo[field];path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists():
                    if path.read_bytes()!=raw:raise ValueError('Existing staged original differs')
                else:
                    with path.open('xb') as output:output.write(raw)
            row={**photo,'number':next_number,'numbering_provenance':'archive_append_order_not_publisher_number'}
            if not has_preview:
                for key in ('preview','preview_bytes','preview_sha256'):row.pop(key,None)
                row['preview_fallback']='verified-original';fallbacks+=1
            checked_row('mimmi',aid,row);rows.append(row);next_number+=1;seen.add(row['sha256'])
            verified+=1
            if verified%10==0:print('EXISTING_ARTICLE_FRESH_READBACK_PROGRESS',verified,'HELD',len(held),flush=True)
            specs.append((row['key'],row['bytes'],row['sha256']))
            if has_preview:specs.append((row['preview'],row['preview_bytes'],row['preview_sha256']))
        if rows:accepted.append({'id':aid,'title':existing[aid]['title'],'images':rows,'complete':False})
        result={'id':aid,'engine':ARTICLE_ENGINE,'recovered_existing_remote_photos':len(rows),
            'held_photos':sum(h['work']==aid for h in held),'source_edition_all_files_accounted_for':False,
            'publisher_original_numbering_known':False,'per_photo_source_url_preserved':False,
            'source_provenance':'exact_reviewed_source_only_collector_transaction'}
        results.append(result)
        print('EXISTING_ARTICLE_RECOVERY_WORK',aid,'RECOVERED',len(rows),'HELD',result['held_photos'],flush=True)
    count=sum(len(a['images']) for a in accepted);metadata=stage/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_bytes(serialize({'schema_version':1,'model':'mimmi','albums':accepted}))
    (metadata/'remote-verification.json').write_bytes(serialize({'model':'mimmi','media_checked':len(specs),
        'full_SHA256_verified':len(specs),'failed':0,'photos':count,
        'verified_specs_sha256':hashlib.sha256(json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest(),
        'scope':'exact_prior_private_inventory_intersection_fresh_readback'}))
    (metadata/'collection-audit.json').write_bytes(serialize({'model':'mimmi','new_local_individual_files':0,
        'recovered_existing_remote_files':count,'new_photo_positions':count,'new_unique_cuts_claimed':0,
        'higher_resolution_replacements':0,'remote_verified_files':count,'gallery_open_verified_files':0,
        'photo_bundles_created':0,'held_photos':held,'already_indexed_source_rows_skipped':skipped,
        'results':results,'exact_original_thumbnail_fallbacks':fallbacks,
        'producer':ARTICLE_PRODUCER,'prior_private_recovery':ARTICLE_RECOVERY,
        'prior_originals_unavailable':ARTICLE_COUNTS['original_unavailable']}))
    print('EXISTING_ARTICLE_ORIGINALS_RECOVERED',count,'HELD',len(held),'ALREADY_INDEXED',skipped,
          'NEW_PHOTOS_COLLECTED',0,'GALLERY_OPEN_VERIFIED',0,flush=True)
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
    proof=producer_proof(request)
    trusted_article=request.get('trusted_article_recovery') is not None
    if trusted_article:trusted_article_producer(request,proof)
    owner=json.loads(a.owner.read_text())
    if request.get('allow_live_append_only_baseline') is True:
        if (not trusted_article and request.get('official_publisher_sha_only') is not True) or request.get('preview_only_hold_from') is not None:
            raise ValueError('Live baseline is only allowed for exact publisher sample append recovery')
        from native_qa_checkpoint import github_fetch
        require_live_published_inventory(owner,a.model,github_fetch(f'raw:main:{a.model}'))
    elif metadata_fingerprint(clean_catalog(owner,a.model))!=request['baseline_owner_fingerprint']:
        raise ValueError('Current inventory differs from the explicitly QA-completed publication baseline')
    if request.get('preview_only_hold_from') is not None:
        completed_baseline_proof(document)
    key=f"metadata/unverified-collection-staging/{request['producer_run']}-{request['producer_attempt']}-{a.model}.json"
    raw=storage(['cat',REMOTES[a.model]+'/'+key],limit=2_000_000)
    if raw is None or hashlib.sha256(raw).hexdigest()!=request['journal_sha256']:
        raise ValueError('Exact private journal readback failed; no image was requested')
    data=json.loads(raw)
    if sum(len(x['images']) for x in data['catalog']['albums'])!=request['expected_collected_photos']:
        raise ValueError('Private producer photo count changed')
    if trusted_article:
        prior=prior_recovery_proof(ARTICLE_RECOVERY,a.model)
        if (prior['job'].get('id')!=136799768401 or prior['job'].get('conclusion')!='success'
                or not any(s.get('name')=='Save authenticated owner-only recovery index and verify remote readback'
                    and s.get('conclusion')=='success' for s in prior['job'].get('steps',[]))):
            raise ValueError('Exact verified private recovery index was not preserved')
        def private_document(key):
            raw=storage(['cat',REMOTES[a.model]+'/'+key],limit=2_000_000)
            if raw is None:raise ValueError('Exact prior private recovery metadata unavailable')
            return json.loads(raw)
        recovery=private_document('metadata/private-recovery/44888685318-1-mimmi.json')
        audit=private_document('metadata/audits/44888685318-1-mimmi-existing-pair-recovery.json')
        from native_qa_checkpoint import github_fetch
        producer_owner=github_fetch('raw:'+ARTICLE_PRODUCER['producer_head']+':mimmi')
        reviewed={b['id']:b for b in json.loads((ROOT/'apps/mimmi-gallery/public-work-pages.json').read_text())['albums']}
        exclusions=json.loads((ROOT/'apps/mimmi-gallery/identity-exclusions.json').read_text())
        result=recover_trusted_article(data,recovery,audit,owner,producer_owner,reviewed,exclusions,a.stage)
        with a.github_output.open('a') as output:
            output.write('changed='+str(bool(result['photos'])).lower()+'\nheld='+str(result['held'])+'\n')
        return
    if request.get('storage_census_only') is True:
        verified=request.get('verify_existing_private_files') is True
        if verified:
            verify_existing_private_inventory(data,owner,a.stage)
        else:
            census_journal_storage(data,owner,a.stage)
        with a.github_output.open('a') as output:
            output.write('changed=false\nheld=0\ncensus_only=true\n')
            output.write('private_recovery='+str(verified).lower()+'\n')
        return
    hold_audit=None
    if request.get('preview_only_hold_from') is not None:
        prior=request['preview_only_hold_from'];prior_recovery_proof(prior,a.model)
        key=f"metadata/audits/{prior['run']}-{prior['attempt']}-{a.model}-existing-pair-recovery.json"
        raw=storage(['cat',REMOTES[a.model]+'/'+key],limit=2_000_000)
        if raw is None:raise ValueError('Prior private hold audit unavailable; no image requested')
        hold_audit=json.loads(raw);preview_hold_selection(hold_audit,a.model)
    reviewed={b['id']:b for b in json.loads((ROOT/f'apps/{a.model}-gallery/public-work-pages.json').read_text())['albums']}
    publisher_samples=None
    if request.get('official_publisher_sha_only') is True:
        if a.model!='mimmi' or hold_audit is not None:
            raise ValueError('Invalid exact-publisher journal recovery scope')
        publisher_samples=publisher_exact_samples(json.loads((ROOT/'apps/mimmi-gallery/official-previews.json').read_text()),reviewed)
    result=recover(data,owner,reviewed,a.stage,preview_hold_audit=hold_audit,copyto=copyto_bytes,publisher_samples=publisher_samples)
    with a.github_output.open('a') as output:
        output.write('changed='+str(bool(result['photos'])).lower()+'\nheld='+str(result['held'])+'\n')


if __name__=='__main__':main()
