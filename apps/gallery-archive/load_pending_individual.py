"""Admit only independently SHA-verified individual-file queues, never ZIPs.

The normal Actions concurrency lock protects the eventual live-catalog merge.
Slot numbers are newly appended here; source filename numbers remain separate.
"""
import argparse
import json
from pathlib import Path
import re
import selectors
import subprocess
import time
from merge_incremental import checked_row


def storage(args,*,limit=2_000_001,command=None):
    process=subprocess.Popen(command or ['rclone',*args,'--timeout=60s','--retries=1'],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    result=bytearray();deadline=time.monotonic()+75
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):raise TimeoutError('Pending-object read deadline')
                chunk=process.stdout.read1(min(65536,limit+1-len(result)))
                if not chunk:break
                result.extend(chunk)
                if len(result)>limit:raise ValueError('Pending metadata exceeds bounded read size')
        rc=process.wait(timeout=max(.01,deadline-time.monotonic()))
        if rc in (3,4):return None
        if rc:raise ValueError('Owner pending-object read failed')
        return bytes(result)
    finally:
        if process.poll() is None:process.kill();process.wait()
        process.stdout.close()


def load(owner,documents,model):
    if owner.get('model')!=model or owner.get('schema_version')!=1 or not owner.get('albums'):
        raise ValueError('A fresh existing owner catalogue is required')
    old={a['id']:a for a in owner['albums']}
    seen={p['sha256'] for a in old.values() for p in a['images']}
    next_number={aid:max(p['number'] for p in a['images'])+1 for aid,a in old.items()}
    albums={};batches=[];coverage={}
    for name,data in documents:
        match=re.fullmatch(r'([a-f0-9]{64})\.json',name)
        if not match:raise ValueError('Invalid individual queue filename')
        if (not isinstance(data,dict) or data.get('model')!=model or data.get('schema_version')!=1
                or data.get('source_batch_sha256')!=match[1]):
            value=data if isinstance(data,dict) else {}
            diagnostic={'queue_prefix':name[:12],'payload_type':type(data).__name__,
                'model_matches':value.get('model')==model,'schema_matches':value.get('schema_version')==1,
                'batch_matches_filename':value.get('source_batch_sha256')==match[1],
                'provider_errno':value.get('errno') if type(value.get('errno')) is int else None}
            raise ValueError('Invalid pending metadata envelope '+json.dumps(diagnostic,sort_keys=True))
        for album in data['albums']:
            aid=album['id']
            if aid not in old:raise ValueError('Queued work must already belong to this owner')
            if album.get('source_coverage'):coverage[aid]=album['source_coverage']
            for photo in sorted(album['images'],key=lambda p:p['source_photo_number']):
                checked_row(model,aid,photo)
                if (photo.get('work_identity_saved_cut_anchors',0)<3
                        or type(photo['source_photo_number']) is not int or photo['source_photo_number']<1
                        or min(photo['width'],photo['height'])<300):raise ValueError('Unverified source/work correspondence')
                if not re.fullmatch(r'originals/'+re.escape(aid)+'/'+photo['sha256']+r'\.(jpg|jpeg|png|webp)',photo['key']):
                    raise ValueError('Queued original is not content-addressed')
                if photo['preview']!='previews/'+aid+'/'+photo['preview_sha256']+'.webp':
                    raise ValueError('Queued preview is not content-addressed')
                if photo['sha256'] in seen:continue
                seen.add(photo['sha256'])
                row={**photo,'number':next_number[aid],
                     'numbering_provenance':'archive_append_order_not_publisher_number'}
                next_number[aid]+=1
                albums.setdefault(aid,{'id':aid,'title':old[aid].get('title',aid),'images':[]})['images'].append(row)
        batches.append(match[1])
    return {'schema_version':1,'model':model,'albums':[
        {**a,'source_coverage':coverage.get(a['id'],{})} for a in albums.values()]},batches


def accessible_documents(entries,remote,model,reader=None):
    """Keep inaccessible queues intact without blocking independent acquisition.

    A challenged object is never imported, deleted, retried with other credentials
    or treated as verified. All other malformed/untrusted metadata still fails.
    """
    from read_owner_metadata import read,ProviderVerificationRequired
    if reader is None:reader=read
    if not isinstance(entries,list) or len(entries)>30:
        raise ValueError('Invalid bounded individual queue list')
    documents=[];held=0
    prefix=remote.rstrip('/')+'/metadata/pending-individual/'+model
    for entry in entries:
        name=entry.get('Path','')
        if not re.fullmatch(r'[a-f0-9]{64}\.json',name):continue
        if type(entry.get('Size')) is not int or not 0<entry['Size']<=2_000_000:
            raise ValueError('Pending metadata entry has an invalid declared size')
        try:data=reader(prefix+'/'+name,model,batch=name[:-5])
        except ProviderVerificationRequired:
            held+=1
            print('OWNER_PENDING_PROVIDER_VERIFICATION_HELD',model,name[:12],
                  'IMPORTED',False,'REMOVED',False,'RETRIED',False,flush=True)
            continue
        if data is None or len(data)>2_000_000:raise ValueError('Pending queue unavailable or too large')
        documents.append((name,json.loads(data)))
    return documents,held


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--owner',type=Path,required=True);p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--remote',required=True);p.add_argument('--model',choices=['mimmi','yui'],required=True)
    p.add_argument('--github-output',type=Path,required=True);args=p.parse_args()
    prefix=args.remote.rstrip('/')+'/metadata/pending-individual/'+args.model
    raw=storage(['lsjson',prefix,'--files-only','--max-depth','1'])
    entries=json.loads(raw) if raw else []
    documents,held=accessible_documents(entries,args.remote,args.model)
    delta,batches=load(json.loads(args.owner.read_text()),documents,args.model)
    count=sum(len(a['images']) for a in delta['albums'])
    if count:
        root=args.stage/'metadata';root.mkdir(parents=True,exist_ok=True)
        (root/'catalog.json').write_text(json.dumps(delta,ensure_ascii=False,indent=2)+'\n')
        audit={'model':args.model,'new_local_individual_files':0,'new_photo_positions':count,
               'higher_resolution_replacements':0,'new_remote_pending_photos':count,'photo_bundles_created':0,
               'remote_verified_files':0,'gallery_open_verified_files':0,'source_batches':batches,
               'results':[{'id':a['id'],'individual_files_saved':len(a['images']),
                   'source_coverage':a.get('source_coverage',{}),
                   'engine':'signed_individual_bytes_then_independent_Actions_SHA_readback'} for a in delta['albums']]}
        (root/'collection-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    with args.github_output.open('a') as out:
        out.write('found='+str(bool(count)).lower()+'\n')
        out.write('provider_held_batches='+str(held)+'\n')
    print('OWNER_PENDING_PROVIDER_HELD_BATCHES',args.model,held,'NOT_IMPORTED_OR_REMOVED',True,flush=True)
    print('OWNER_PENDING_INDIVIDUAL_ROWS',args.model,count,'REMOTE_REVERIFICATION_REQUIRED',bool(count),flush=True)
