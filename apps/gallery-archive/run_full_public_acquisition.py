#!/usr/bin/env python3
"""Collect REAL, distinct, decoded photos for all registered Mimmi/Yui public works.

Only public HTML and image URLs that existing direct_photo_pipeline validates:
no paid media, authentication bypass, Cloudflare rereads, ZIPs or synthetic rows.
Stages are persistent for the job; publication can be safely replayed onto an
updated GitHub main without re-downloading upstream images.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/'apps/gallery-archive'
MAX_REGISTERED_PAGES_PER_WORK=60  # Per-run safety bound, NOT a lifetime or edition-page ceiling
MAX_CHROMIUM_WEAK_PAGES_PER_BATCH=4
MAX_RECOVERY_SINGLE_WORKS_PER_RUN=14
MAX_RECOVERY_PER_TIMEOUT_GROUP=7
RECOVERY_SINGLE_WORK_TIMEOUT=180
SLOW_PUBLIC_SOURCE_TIMEOUT=180
PRIORITY={
 'mimmi':(
  'djawa-pop-kitty-party','djawa-nikke-yuni',
  'djawa-janus-scary-lantern-night','djawa-rudy2-codename-wolfgirl',
  'djawa-twin-bunnies-affair','djawa-my-summer-vacation-vol-5',
 ),
 'yui':(
  'yui-meow-public-samples','artgravia-677-yui-public-samples',
  'crazygiant-player5-public','djawa-privaty-public-samples',
  'yui-summer-public-samples',
 ),
}


def work_batches(model, run_number, base=ROOT, batch_size=7, source_evidence=None):
    """Prioritize gaps and include independently proven new source-edition IDs.

    The stored-source registry is deliberately smaller than the owner-index.
    A verified reverse result for an owner work that was absent from that
    registry must still reach --album-id, or the downstream extractor will
    silently discard its evidence even though the source was found.
    """
    if model not in PRIORITY or batch_size<1:
        raise ValueError('INVALID_COLLECTION_MODEL_OR_BATCH')
    path=Path(base)/f'apps/{model}-gallery/public-work-pages.json'
    registry=json.loads(path.read_text(encoding='utf-8'))
    works=registry.get('albums')
    if not isinstance(works,list) or not works:
        raise ValueError('PUBLIC_SOURCE_REGISTRY_MISSING')
    all_ids=[a['id'] for a in works]
    if len(all_ids)!=len(set(all_ids)):
        raise ValueError('DUPLICATE_PUBLIC_WORK_IDS')
    # One legacy Rudy² source is indexed under a URL-escaped ID, which the
    # image collector correctly rejects as an invalid album slug. Map only
    # this known, exact alias to the existing canonical same-work ID; never
    # allow a malformed ID to abort the other six registered works.
    import re
    known_aliases={'mimmi':{
        'djawa-rudy%c2%b2-codename-wolfgirl':'djawa-rudy2-codename-wolfgirl'}}
    def canonical_id(value):
        if not isinstance(value,str):
            return None
        normalized=known_aliases.get(model,{}).get(value,value)
        return normalized if re.fullmatch(
            r'[a-z0-9][a-z0-9-]{1,100}',normalized) else None
    # The small public-work-pages manifest is NOT the full owner inventory.
    # The collector itself merges the exhaustive registered corpus. Schedule
    # that same corpus here or the scheduler silently discards owner works
    # discovered by the extractor before it even executes them.
    registry=Path(base)/'apps/gallery-archive/global_source_registry.json'
    if registry.is_file():
        from collector_full_census import census
        from direct_photo_pipeline import safe_registered_public_page
        inventory=census(base)
        for row in inventory['targets']:
            if row.get('kind')!='work' or row.get('model')!=model:
                continue
            canon=canonical_id(row.get('id'))
            if not canon:
                continue
            if (any(safe_registered_public_page(url,model)
                    for url in row.get('urls',[]))
                    and canon not in all_ids):
                all_ids.append(canon)
    # Every scheduled ID must correspond to an observed, registered edition;
    # unknown search snippets are added only via the proven source bridge.
    # A name-search result alone must never register an album. Require the
    # exact edition page proof that the physical collector checks again.
    if source_evidence is not None and Path(source_evidence).is_file():
        import re
        from verified_source_bridge import eligible_source_pages
        from direct_photo_pipeline import safe_registered_public_page
        evidence=json.loads(Path(source_evidence).read_text(encoding='utf-8'))
        if evidence.get('model')!=model or evidence.get('schema_version')!=1:
            raise ValueError('EXTERNAL_SOURCE_EVIDENCE_MODEL_OR_SCHEMA_MISMATCH')
        proven=eligible_source_pages(evidence,model,safe_registered_public_page)
        if len(proven)>100:
            raise ValueError('EXCESSIVE_VERIFIED_NEW_SOURCE_WORKS')
        target_rows=evidence.get('targets',[])
        if not isinstance(target_rows,list) or len(target_rows)>200:
            raise ValueError('INVALID_VERIFIED_TARGET_ROWS')
        target_urls={row['id']:set(row.get('urls',[]))
                     for row in target_rows
                     if isinstance(row,dict) and isinstance(row.get('id'),str)
                     and isinstance(row.get('urls'),list)}
        for aid,source_urls in sorted(proven.items()):
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid):
                raise ValueError('UNSAFE_VERIFIED_SOURCE_ALBUM_ID')
            # Collector reads targets as its work registry. Do not schedule
            # work that the collector cannot create from a proven target URL.
            if source_urls & target_urls.get(aid,set()) and aid not in all_ids:
                all_ids.append(aid)
    # Official recorded DJAWA sample URLs already represented by saved SHA
    # do not deserve the repeated first batch. Keep them in the normal round-
    # robin scan so new public variants are still discoverable.
    from official_sample_supply import exhausted_official_samples
    exhausted=exhausted_official_samples(base,model)
    priority=[aid for aid in PRIORITY[model] if aid in all_ids and aid not in exhausted]
    rest=[aid for aid in all_ids if aid not in priority]
    if rest:
        offset=((max(run_number,1)-1)*batch_size)%len(rest)
        rest=rest[offset:]+rest[:offset]
    # Keep priority works in a separate, longer-pagination batch.
    # V2PH public multi-page sites historically exhaust whole seven-work
    # batches. Isolate them: a slow source must never hide other editions.
    # A dedicated single-work timeout keeps the full inventory scheduled.
    slow=[aid for aid in rest if aid.startswith('v2ph-actor-')]
    normal=[aid for aid in rest if not aid.startswith('v2ph-actor-')]
    return ([priority] if priority else []) + [
        normal[i:i+batch_size] for i in range(0,len(normal),batch_size)
    ] + [[aid] for aid in slow]


def execute(args):
    batches=work_batches(args.model,args.run_number,ROOT,args.batch_size,
                         source_evidence=args.source_evidence)
    stage=Path(args.stage).resolve()
    if args.plan_only:
        print('GALLERY_MISSING_FULL_PLAN',json.dumps({
          'model':args.model,'registered_work_count':sum(map(len,batches)),
          'priority_count':len(batches[0]) if batches else 0,
          'batches':batches},ensure_ascii=False),flush=True)
        return 0
    stage.mkdir(parents=True,exist_ok=True)
    source_evidence=Path(args.source_evidence).resolve() if args.source_evidence else None
    reports=[]
    collected=0
    quality_upgrades=0
    # A seven-work timeout must not permanently strand the other six works.
    # Bounded, one-level single-work followups run only for timed-out groups.
    # The run-number rotates which works get the recovery budget.
    work_queue=list(batches)
    recovery_scheduled=0
    for index,ids in enumerate(work_queue):
        target=stage/('batch-'+str(index).zfill(2))
        catalog=target/'metadata/catalog.json'
        command=[sys.executable,str(ARCHIVE/'direct_photo_pipeline.py'),
          '--model',args.model,'--owner',f'apps/{args.model}-gallery/owner-index.json',
          '--out',str(target),'--max-new',str(args.max_per_batch),
          '--max-pages',str(MAX_REGISTERED_PAGES_PER_WORK),
          '--page-cycle',str(args.run_number),'--render-budget',
          str(MAX_CHROMIUM_WEAK_PAGES_PER_BATCH if args.alternate_priority else 0),
          '--reviewed-source-only']
        if source_evidence and source_evidence.is_file():
            command.extend(['--reverse-evidence',str(source_evidence)])
        # The old first-batch-only guard left every secondary work without
        # independent Scrapy/Chromium extraction. Keep every work subject to
        # existing exact-edition, published-HTML and SHA checks instead.
        if args.alternate_priority:
            command.append('--alternative-engines')
        for aid in ids:
            command.extend(['--album-id',aid])
        print('FULL_COLLECTION_BATCH_START',args.model,index,'work_count',len(ids),flush=True)
        try:
            timeout=(min(args.batch_timeout,RECOVERY_SINGLE_WORK_TIMEOUT)
                     if index>=len(batches) else
                     min(args.batch_timeout,SLOW_PUBLIC_SOURCE_TIMEOUT)
                     if len(ids)==1 and ids[0].startswith('v2ph-actor-')
                     else args.batch_timeout)
            result=subprocess.run(command,cwd=ROOT,timeout=timeout,check=False)
            collector_code=result.returncode
            collection_error=None
        except subprocess.TimeoutExpired:
            # One slow public origin must not discard the other works' verified
            # files or prevent bounded attempts against the remaining albums.
            collector_code=124
            collection_error='collector_timeout'
        row={'batch':index,'works':ids,'collector_returncode':collector_code,
             'single_work_recovery':index>=len(batches),
             'new_sha_verified_originals':0,'total_bytes_added':0}
        # Nonzero exit may come from ONE invalid page/album and must not
        # strand all the valid works sharing its batch. Recover individually
        # from both timeout and process errors, with finite per-run limits.
        if (collector_code!=0 or collection_error) and len(ids)>1:
            available=MAX_RECOVERY_SINGLE_WORKS_PER_RUN-recovery_scheduled
            count=min(available,MAX_RECOVERY_PER_TIMEOUT_GROUP,len(ids))
            if count:
                offset=max(args.run_number-1,0)%len(ids)
                chosen=[ids[(offset+i)%len(ids)] for i in range(count)]
                work_queue.extend([[aid] for aid in chosen])
                recovery_scheduled+=count
                row['recovery_scheduled_work_ids']=chosen
        if collection_error:
            row['collection_error']=collection_error
        if collector_code==0 and not catalog.is_file():
            row['collection_error']='missing_finalized_stage_catalog'
        if collector_code==0 and catalog.is_file():
            # A finalized catalogue does not mean every requested edition was
            # actually scanned. The collector can filter out works while
            # returning 0. Keep any valid staged files publishable, but do
            # not count filtered works as completed.
            audit_path=target/'metadata/collection-audit.json'
            if audit_path.is_file():
                try:
                    detail=json.loads(audit_path.read_text(encoding='utf-8'))
                    verified_ids={v.get('id') for v in detail.get('results',[])
                                  if isinstance(v,dict)}
                    row['unvisited_registered_work_ids']=[
                        aid for aid in ids if aid not in verified_ids]
                    row['work_ids_with_media_candidates']=[
                        v['id'] for v in detail.get('results',[])
                        if isinstance(v,dict) and v.get('id') in ids
                        and int(v.get('published_image_candidates') or 0)>0]
                except (OSError,ValueError,TypeError) as exc:
                    row['unvisited_registered_work_ids']=list(ids)
                    row['coverage_error']='invalid_collector_audit_'+type(exc).__name__
            try:
                proc=subprocess.run([sys.executable,str(ARCHIVE/'publish_new_public_photos_to_pages.py'),
                    '--model',args.model,'--stage',str(target),
                    '--limit',str(args.max_per_batch),'--budget',str(args.bytes_per_batch)],
                    cwd=ROOT,timeout=180,check=False)
                row['publisher_returncode']=proc.returncode
                if proc.returncode==0:
                    publication=json.loads((target/'metadata/pages-publication.json').read_text())
                    row['new_sha_verified_originals']=publication['new_sha_verified_originals']
                    row['total_bytes_added']=publication['total_bytes_added']
                    collected+=row['new_sha_verified_originals']
                    row['higher_visual_quality_replacements']=int(
                        publication.get('higher_visual_quality_replacements',0))
                    quality_upgrades+=row['higher_visual_quality_replacements']
            except (ValueError,OSError,subprocess.TimeoutExpired) as error:
                row['publication_error']=type(error).__name__
        reports.append(row)
        print('FULL_COLLECTION_BATCH_RESULT',json.dumps(row,ensure_ascii=False),flush=True)
    timed_out=[x['batch'] for x in reports if x.get('collection_error')=='collector_timeout']
    unresolved=[x for x in reports if x['collector_returncode']!=0
                or x.get('publisher_returncode')!=0
                or x.get('collection_error')
                or x.get('publication_error')]
    # A failed multi-work batch may have partially recovered via successful
    # individually audited followups. Count unique work IDs, never attempts.
    scheduled=list(dict.fromkeys(aid for group in batches for aid in group))
    successes={aid for row in reports if row not in unresolved
               for aid in row['works']
               if aid not in row.get('unvisited_registered_work_ids',[])}
    incomplete_works=[aid for aid in scheduled if aid not in successes]
    success_count=len(successes)
    # "Scheduled" is NOT the same as "collected": a timed-out group may
    # never have reached some of its listed work IDs. Keep partial results
    # and replay the verified bytes, but expose the incomplete works.
    report={'model':args.model,
            'registered_works_scheduled':len(scheduled),
            'registered_works_visited':success_count,
            'registered_works_in_successful_batches':success_count,
            'registered_work_ids_in_incomplete_batches':incomplete_works,
            'works_with_real_image_candidates':len(set(
                aid for row in reports
                for aid in row.get('work_ids_with_media_candidates',[]))),
            'source_filtered_or_unvisited_work_ids':sorted(set(
                aid for row in reports
                for aid in row.get('unvisited_registered_work_ids',[]))),
            'incomplete_batch_count':len(unresolved),
            'single_work_recovery_scheduled':recovery_scheduled,
            'single_work_recovery_succeeded':sum(
                1 for x in reports if x.get('single_work_recovery') and x not in unresolved),
            'batches':reports,'new_local_verified_SHA':collected,
            'verified_optical_quality_replacements_staged':quality_upgrades,
            'timed_out_batches':timed_out,
            'collection_complete_without_batch_timeouts':not timed_out,
            'collection_all_batches_success':not incomplete_works,
            'new_remote_SHA_readback_verified':0,
            'new_public_Pages_verified':0,
            'scope':'public_authenticated-free_only',
            'state':('LOCAL_STAGED_PARTIAL_INCOMPLETE_BATCHES' if incomplete_works
                     else 'LOCAL_PUBLICATION_STAGED_NOT_DEPLOYED')}
    (stage/'full-collection-summary.json').write_text(
       json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('FULL_COLLECTION_MODEL_RESULT',json.dumps(report,ensure_ascii=False),flush=True)
    # GitHub Actions step success means the runner completed, NOT that every
    # public edition was checked. Make timeouts/incomplete work IDs prominent
    # in job logs and the actual human-visible step summary.
    if incomplete_works:
        print('::warning::GALLERY_COLLECTION_INCOMPLETE model='+args.model+
              ' scheduled='+str(report['registered_works_scheduled'])+
              ' successfully_batched='+str(success_count)+
              ' unresolved='+','.join(incomplete_works),flush=True)
    step_summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if step_summary:
        with Path(step_summary).open('a',encoding='utf-8') as summary:
            summary.write('### Actual '+args.model+' public image collection\n\n')
            summary.write('- Registered works scheduled: '+str(report['registered_works_scheduled'])+'\n')
            summary.write('- Works in successful batches: '+str(success_count)+'\n')
            summary.write('- Incomplete work IDs: '+(', '.join(incomplete_works) or 'none')+'\n')
            summary.write('- New SHA files staged (not yet Pages verified): '+str(collected)+'\n')
            summary.write('- Same-frame verified optical replacements staged: '+str(quality_upgrades)+'\n')
            summary.write('- Full collection completed: '+str(not incomplete_works).lower()+'\n\n')
    if success_count==0:
        # Process returncode 0 alone is not a completed collection: it needs
        # the finalized stage catalog AND successful SHA-staged publication.
        return 2
    if any(x.get('publisher_returncode') not in (None,0)
           or x.get('publication_error') for x in reports):
        return 3
    # Exit 4 means incomplete, NOT success. The Actions wrapper must still
    # publish independently finalized files before surfacing this failure.
    if incomplete_works:
        return 4
    return 0


def replay(model,stage,max_per_batch,bytes_per_batch):
    from publish_new_public_photos_to_pages import publish
    stage=Path(stage)
    summary=stage/'full-collection-summary.json'
    if not summary.is_file():
        # Never trust partial/stale catalogs without a completed collection
        # audit. Missing stage is a genuine no-op, not a successful publish.
        if any(stage.glob('batch-*/metadata/catalog.json')):
            raise ValueError('UNVERIFIED_COLLECTION_STAGE_AUDIT_MISSING')
        print('FULL_COLLECTION_REBASED_MAIN_NEW_SHA',model,0,flush=True)
        return 0
    audit=json.loads(summary.read_text(encoding='utf-8'))
    if audit.get('model')!=model or not isinstance(audit.get('batches'),list):
        raise ValueError('COLLECTION_REPLAY_AUDIT_INVALID')
    allowed=set()
    for row in audit['batches']:
        if (row.get('collector_returncode')==0
                and row.get('publisher_returncode')==0
                and not row.get('collection_error')
                and not row.get('publication_error')):
            allowed.add('batch-'+str(row['batch']).zfill(2))
    # Only replay catalogs from successful, SHA-verified publication
    # substeps. A timed-out collector can leave partial catalog files.
    count=0
    upgrades=0
    for folder in sorted(stage.glob('batch-*')):
        if folder.name not in allowed:
            continue
        if not (folder/'metadata/catalog.json').is_file():
            continue
        doc=publish(model,folder,root=ROOT,budget=bytes_per_batch,limit=max_per_batch)
        count+=doc['new_sha_verified_originals']
        upgrades+=int(doc.get('higher_visual_quality_replacements',0))
    (stage/'full-replay-summary.json').write_text(json.dumps({
        'model':model,'new_sha_verified_originals':count,
        'higher_visual_quality_replacements':upgrades,
        'real_files_merged_to_working_checkout':count+upgrades},indent=2)+'\n')
    print('FULL_COLLECTION_REBASED_MAIN_NEW_SHA',model,count,
          'VERIFIED_QUALITY_UPGRADES',upgrades,flush=True)
    return count


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',choices=tuple(PRIORITY),required=True)
    p.add_argument('--run-number',type=int,default=1)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--source-evidence',type=Path)
    p.add_argument('--batch-size',type=int,default=7)
    p.add_argument('--max-per-batch',type=int,default=48)
    p.add_argument('--bytes-per-batch',type=int,default=36000000)
    p.add_argument('--batch-timeout',type=int,default=1200)
    p.add_argument('--alternate-priority',action='store_true')
    p.add_argument('--plan-only',action='store_true')
    p.add_argument('--replay-only',action='store_true')
    a=p.parse_args()
    if (not 1<=a.batch_size<=20 or not 1<=a.max_per_batch<=90 or
            not 1000000<=a.bytes_per_batch<=80000000 or
            not 60<=a.batch_timeout<=2000 or a.run_number<0):
        raise SystemExit('INVALID_SAFE_COLLECTION_BOUNDS')
    if a.replay_only:
        replay(a.model,a.stage,a.max_per_batch,a.bytes_per_batch)
        return
    sys.exit(execute(a))


if __name__=='__main__':
    main()
