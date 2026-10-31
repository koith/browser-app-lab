"""Validate private metadata, with one normal file-download alternative to cat.

A successful command returning a provider JSON error is not an owner catalog.
Use the same configured owner account and path, never a credential workaround.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from merge_incremental import flatten
from safe_rclone import diagnostic


class ProviderVerificationRequired(ValueError):
    """The provider requires an interactive verification; never automate it."""


def matches(raw,model,batch,minimum):
    try:
        document=json.loads(raw)
        if (not isinstance(document,dict) or document.get('model')!=model
                or document.get('schema_version')!=1 or not isinstance(document.get('albums'),list)):
            return False
        if batch:return document.get('source_batch_sha256')==batch
        if document.get('storage')!='owner-private-terabox-sha-verified-bytes':return False
        albums=flatten(document,model)
        return bool(albums) and sum(len(a['images']) for a in albums.values())>=minimum
    except (ValueError,KeyError,TypeError):return False


def summary(raw,model,batch):
    try:document=json.loads(raw)
    except (ValueError,TypeError):document={}
    if not isinstance(document,dict):document={}
    return {'model_matches':document.get('model')==model,
        'schema_matches':document.get('schema_version')==1,
        'batch_matches':document.get('source_batch_sha256')==batch if batch else None,
        'provider_errno':document.get('errno') if type(document.get('errno')) is int else None,
        'provider_error_code':document.get('error_code') if type(document.get('error_code')) is int else None,
        'received_bytes':len(raw) if raw is not None else 0}


def read(remote,model,*,batch=None,minimum=1,reader=None):
    root={'mimmi':'archive:MimmiArchive','yui':'archive:YuiArchive'}.get(model)
    suffix=('/metadata/pending-individual/'+model+'/'+batch+'.json' if batch else '/metadata/catalog.json')
    if not root or (batch and not re.fullmatch('[a-f0-9]{64}',batch)) or remote!=root+suffix:
        raise ValueError('Only the existing model-specific private metadata object is allowed')
    if reader is None:
        from load_pending_individual import storage
        reader=storage
    limit=2_000_000 if batch else 6_000_000
    # A failed authenticated command remains a failure. The alternative is for
    # a successful command whose response has the wrong metadata envelope.
    raw=reader(['cat',remote],limit=limit)
    if raw is not None and matches(raw,model,batch,minimum):return raw
    evidence=summary(raw,model,batch)
    print('OWNER_METADATA_STREAM_INVALID',json.dumps(evidence,sort_keys=True),file=sys.stderr,flush=True)
    if evidence['provider_errno']==400141:
        raise ProviderVerificationRequired('Owner storage requires provider verification (400141)')
    with tempfile.TemporaryDirectory(prefix='owner-metadata-') as temporary:
        local=Path(temporary)/'metadata.json'
        with tempfile.TemporaryFile() as errors:
            result=subprocess.run(['rclone','copyto',remote,str(local),'--ignore-times',
                '--max-size',str(limit),'--timeout=60s','--retries=1'],
                stdout=subprocess.DEVNULL,stderr=errors,timeout=75)
            if result.returncode:
                errors.seek(0)
                raise ValueError('Normal owner metadata download failed: '+
                    diagnostic(errors.read(32000).decode('utf-8','replace'))) from None
        if not local.is_file() or not 0<local.stat().st_size<=limit:
            raise ValueError('Downloaded owner metadata exceeds its bounded size')
        raw=local.read_bytes()
    if not matches(raw,model,batch,minimum):
        raise ValueError('Downloaded metadata envelope invalid '+json.dumps(summary(raw,model,batch),sort_keys=True))
    print('OWNER_METADATA_NORMAL_FILE_DOWNLOAD_VERIFIED',model,'pending' if batch else 'catalog',file=sys.stderr,flush=True)
    return raw


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--remote',required=True);p.add_argument('--model',choices=['mimmi','yui'],required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--published-index',type=Path,required=True);a=p.parse_args()
    index=json.loads(a.published_index.read_text())
    if index.get('model')!=a.model:raise ValueError('Wrong published owner model')
    minimum=sum(len(album['images']) for album in index['albums'])
    a.out.write_bytes(read(a.remote.rstrip('/')+'/metadata/catalog.json',a.model,minimum=minimum))
