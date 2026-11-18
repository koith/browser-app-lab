#!/usr/bin/env python3
"""G-07: publish *actual* verified downloaded public photo bytes from the
existing registered direct collector to free static Pages, never source URLs.

Source collector already enforces model/work/source identity and robots policy.
This layer independently checks immutable SHA, image decode, same-work scope,
global owner/local duplicates and files, then appends without overwriting.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from PIL import Image
from photo_visual_dedupe import WorkVisualIndex
from public_work_photo_extractor import ordinary_public_https_image

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_EXT = {'.jpg': 'JPEG','.jpeg': 'JPEG','.png': 'PNG','.webp': 'WEBP'}

def publish(model, stage, root=ROOT, budget=14_000_000, limit=18):
    assert model in ('mimmi','yui')
    base=Path(root)/'apps'/f'{model}-gallery'
    stage=Path(stage)
    owner=json.loads((base/'owner-index.json').read_text())
    old_path=base/'stored-albums.json'
    old=json.loads(old_path.read_text())
    registered=json.loads((base/'public-work-pages.json').read_text())
    approved_registered={a['id']:a for a in registered['albums']}
    owner_by_id={a['id']:a for a in owner['albums']}
    existing_sha={p['sha256'] for a in owner['albums'] for p in a['images']}
    existing_sha.update(p['sha256'] for a in old['albums'] for p in a['images'])
    byid={a['id']:a for a in old['albums']}
    stage_doc=json.loads((stage/'metadata/catalog.json').read_text())
    if stage_doc.get('model')!=model:
        raise ValueError('wrong model staged')
    # Exact-work discovery may identify a model's edition missing from the
    # older static registered-work list. An image can already have passed
    # SHA/decoder/edition validation and STILL be lost here if we only admit
    # old registered IDs. Require provenance recorded by the SAME collector
    # and reject unreviewed or ambiguous new IDs.
    claimed=stage_doc.get('verified_new_work_sources',[])
    if not isinstance(claimed,list) or len(claimed)>100:
        raise ValueError('INVALID_STAGED_NEW_WORK_PROVENANCE')
    approved_new={}
    for entry in claimed:
        if not isinstance(entry,dict):
            raise ValueError('INVALID_STAGED_NEW_WORK_PROVENANCE')
        aid=entry.get('id')
        src=entry.get('source')
        title=entry.get('title')
        pages=entry.get('verified_same_work_pages')
        if (not isinstance(aid,str)
                or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid)
                or aid in approved_registered or aid in approved_new
                or not isinstance(title,str) or len(title.strip())<4
                or entry.get('proof') not in (
                    'unique_named_work_page_model_and_edition',
                    'owner_catalog_work_with_reviewed_public_source')
                or (entry.get('proof')=='owner_catalog_work_with_reviewed_public_source'
                    and (aid not in owner_by_id
                         or owner_by_id[aid].get('title')!=title))
                or not isinstance(pages,list) or not 1<=len(pages)<=12
                or not isinstance(src,str) or src not in pages
                or not all(isinstance(u,str) and
                           ordinary_public_https_image(u,u) is not None for u in pages)):
            raise ValueError('UNVERIFIED_NEW_WORK_PUBLICATION_SOURCE')
        approved_new[aid]={'id':aid,'title':title,
                            'source':src,
                            'proof':entry['proof']}
    added=[];used=0
    visual_indexes={};same_frame_skipped=[];quality_replacement_deferred=[];quality_replacements=[]
    for album in stage_doc.get('albums',[]):
        aid=album.get('id')
        if (not isinstance(aid,str) or
                not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid)):
            continue
        source=approved_registered.get(aid) or approved_new.get(aid)
        if source is None:
            # Unverified search results remain research leads, not photos.
            continue
        rec=byid.get(aid)
        if rec is None:
            rec={'id':aid,'title':source.get('title') or album.get('title') or aid,
                 'source':source.get('source',''),'status':'public_verified_local_orig_files',
                 'images':[]}
        for photo in album.get('images',[]):
            digest=photo.get('sha256')
            if not isinstance(digest,str) or len(digest)!=64 or digest in existing_sha:
                continue
            key=photo.get('key','')
            stage_file=(stage/key).resolve()
            if not str(stage_file).startswith(str(stage.resolve())+os.sep) or not stage_file.is_file():
                raise ValueError('missing confined staged image')
            raw=stage_file.read_bytes()
            if len(raw)!=photo.get('bytes') or hashlib.sha256(raw).hexdigest()!=digest:
                raise ValueError('staged original physical SHA mismatch')
            if len(raw)>64_000_000 or used+len(raw)>budget or len(added)+len(quality_replacements)>=limit:
                continue
            ext=stage_file.suffix.lower()
            if ext not in ALLOWED_EXT:continue
            with Image.open(stage_file) as im:
                im.verify()
            with Image.open(stage_file) as im:
                im.load()
                if im.format!=ALLOWED_EXT[ext] or im.size!=(photo['width'],photo['height']):
                    raise ValueError('staged source decoded image mismatch')
                if min(im.size)<300:continue
            # An unrelated SHA can still be the exact same photo cut in a
            # different compression or size. This is the missing safety gate
            # that once falsely counted 20 re-encodes as 20 new Mimmi photos.
            visual=visual_indexes.get(aid)
            if visual is None:
                visual=WorkVisualIndex(base,rec)
                visual_indexes[aid]=visual
            match=visual.classify(raw)
            if match:
                row={'album':aid,'sha256':digest,**match}
                if match['needs_replacement_transaction']:
                    # Immutable verified upgrade transaction: only a *local*
                    # current same-work file can be replaced in the public
                    # index. The old bytes remain untouched on disk and their
                    # exact path/hash are retained in the version history.
                    former=next((p for p in rec['images']
                        if p.get('sha256')==match['existing_sha256']
                        and p.get('number')==match['existing_number']),None)
                    if former is None:
                        quality_replacement_deferred.append({
                            **row,'reason':'old_photo_not_in_current_public_index'})
                        continue
                    former_path=(base/str(former.get('url',''))).resolve()
                    if (not former_path.is_relative_to(base.resolve())
                            or not str(former.get('url','')).startswith('stored-albums/'+aid+'/')
                            or not former_path.is_file()):
                        quality_replacement_deferred.append({
                            **row,'reason':'old_photo_bytes_unavailable'})
                        continue
                    previous_raw=former_path.read_bytes()
                    if hashlib.sha256(previous_raw).hexdigest()!=former['sha256']:
                        raise ValueError('quality_upgrade_original_sha_readback_failed')
                    from photo_quality_evidence import preferred_pair
                    better,evidence=preferred_pair(
                        previous_raw,raw,former['sha256'],
                        former.get('watermark_status','unknown'),
                        photo.get('watermark_status','unknown'))
                    # Same-frame and REAL visual-quality improvement are
                    # mandatory. Do not silently swap compressed renditions,
                    # uncertain matches or unverified watermark claims.
                    if not (better and evidence.get('same_photo_verified')
                            and evidence.get('relation')=='higher'):
                        quality_replacement_deferred.append({
                            **row,'reason':'verified_visual_upgrade_not_proven'})
                        continue
                    rel=f'stored-albums/{aid}/{digest[:20]}{ext}'
                    dest=base/rel
                    if dest.exists() and dest.read_bytes()!=raw:
                        raise ValueError('immutable Pages upgrade collision')
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    if not dest.exists():
                        dest.write_bytes(raw)
                    # The existing gallery number and album identity remain
                    # stable. Preserve all historical versions and source
                    # provenance; never delete the original photo.
                    prior_history=list(former.get('previous_versions') or [])
                    prior_history.append({
                        'sha256':former['sha256'],'url':former['url'],
                        'bytes':former.get('bytes'),
                        'width':former.get('width'),'height':former.get('height'),
                        'quality':former.get('quality'),
                        'watermark_status':former.get('watermark_status','unknown')})
                    improved={**former,'sha256':digest,'url':rel,
                              'bytes':len(raw),'width':photo['width'],
                              'height':photo['height'],
                              'quality':'verified_same_frame_optical_upgrade',
                              'previous_versions':prior_history,
                              'quality_upgrade_evidence':evidence,
                              'quality_upgrade_source_url':photo.get('source_url','')}
                    if photo.get('watermark_status') in (
                            'verified_none','verified_absent','verified_no_watermark'):
                        improved['watermark_status']=photo['watermark_status']
                    for i,existing in enumerate(rec['images']):
                        if existing is former:
                            rec['images'][i]=improved
                            break
                    visual.remember(improved,raw)
                    existing_sha.add(digest)
                    quality_replacements.append({
                        'album':aid,'number':former['number'],
                        'previous_sha256':former['sha256'],
                        'new_sha256':digest,
                        'previous_bytes':len(previous_raw),
                        'new_bytes':len(raw),'relation':evidence['relation']})
                    used+=len(raw)
                else:
                    same_frame_skipped.append(row)
                continue
            rel=f'stored-albums/{aid}/{digest[:20]}{ext}'
            dest=base/rel
            if dest.exists() and dest.read_bytes()!=raw:
                raise ValueError('immutable Pages destination collision')
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():dest.write_bytes(raw)
            n=int(photo.get('number') or 0)
            occupied={int(p.get('number') or 0) for p in rec['images']}
            if n<1 or n in occupied:
                n=max(occupied|{0})+1
            # Preserve observed source-file numbering separately from our
            # immutable gallery slot. Losing this evidence prevents later
            # page-by-page missing-cut audits, and source sequence is never
            # represented as the publisher's original sequence.
            recorded={'number':n,'url':rel,
              'sha256':digest,'bytes':len(raw),'width':photo['width'],'height':photo['height'],
              'origin_page':source.get('source'),'source_url':photo.get('source_url',''),
              'quality':'direct_public_original_bytes_not_publisher_master_verified'}
            source_no=photo.get('source_photo_number')
            if type(source_no) is int and 1<=source_no<=25000:
                recorded['source_photo_number']=source_no
                recorded['source_numbering']='public_web_filename_not_publisher_original'
            provenance=photo.get('numbering_provenance')
            if provenance in {
                    'archive_append_order_not_publisher_number',
                    'published_source_order',
                    'official_source_unique_url_append_not_publisher_sequence',
                    'verified_creator_cached_public_feed_append'}:
                recorded['numbering_provenance']=provenance
            rec['images'].append(recorded)
            visual.remember(recorded,raw)
            existing_sha.add(digest);added.append((aid,digest,len(raw)))
            used+=len(raw)
        if rec['images']:
            byid[aid]=rec
    if added or quality_replacements:
        old['albums']=list(byid.values())
        # The manifest count must reflect real immutable photo rows, not the
        # stale cached number before newly acquired individual files.
        if 'physical_verified_image_count' in old:
            old['physical_verified_image_count']=sum(
                len(album.get('images',[])) for album in old['albums'])
        old_path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    result={'model':model,'new_sha_verified_originals':len(added),
       'higher_visual_quality_replacements':len(quality_replacements),
       'actual_quality_upgrade_evidence':quality_replacements[:25],
       'new_verified_source_work_ids':sorted({aid for aid,sha,n in added
                                             if aid in approved_new}),
       'total_bytes_added':used,'sha_samples':[{'album':a,'sha256':s,'bytes':n} for a,s,n in added],
       'real_files_in_pages':bool(added),'private_terabox_readback_verified':False,
       'photo_source_fallback_prohibited':True,
       'same_frame_duplicate_SHA_files_skipped':len(same_frame_skipped),
       'quality_upgrades_held_for_verified_replacement':len(quality_replacement_deferred),
       'same_frame_duplicate_evidence':same_frame_skipped[:25],
       'quality_upgrade_evidence':quality_replacement_deferred[:25]}
    (stage/'metadata/pages-publication.json').write_text(json.dumps(result,indent=2)+'\n')
    print('G07_ACTUAL_NEW_PUBLIC_PAGES_STORED_SHA',json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--model',choices=['mimmi','yui'],required=True)
    a.add_argument('--stage',type=Path,required=True)
    a.add_argument('--budget',type=int,default=14000000)
    a.add_argument('--limit',type=int,default=18)
    v=a.parse_args()
    publish(v.model,v.stage,budget=v.budget,limit=v.limit)
