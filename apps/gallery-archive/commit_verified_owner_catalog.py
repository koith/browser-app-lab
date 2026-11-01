"""Commit only fully remotely verified owner media metadata with exact readback.

TeraBox's upload response may precede metadata visibility. Never confuse
a successful API command with a verified catalog; independently read every byte,
including an alternate normal remote-to-local operation when cat is stale.
"""
import argparse
import json
from pathlib import Path
import re

from private_collection_snapshot import REMOTES,exact_journal_readback
from safe_rclone import run


def commit(stage,model,remote,destination,uploader=run,reader=exact_journal_readback):
    stage=Path(stage)
    if model not in REMOTES or remote!=REMOTES[model]:
        raise ValueError('Owner catalog remote/model mismatch')
    catalog_path=stage/'metadata/catalog.json'
    proof_path=stage/'metadata/remote-verification.json'
    if not catalog_path.is_file() or not proof_path.is_file():
        raise ValueError('Catalog cannot be written before exact remote photo proof')
    raw=catalog_path.read_bytes()
    catalog=json.loads(raw)
    proof=json.loads(proof_path.read_bytes())
    if (catalog.get('model')!=model or catalog.get('schema_version')!=1
            or catalog.get('storage')!='owner-private-terabox-sha-verified-bytes'
            or proof.get('model')!=model or proof.get('failed')!=0
            or proof.get('full_SHA256_verified')!=proof.get('media_checked')
            or proof.get('media_checked',0)<1
            or not re.fullmatch('[a-f0-9]{64}',proof.get('verified_specs_sha256',''))):
        raise ValueError('Refuse unverified photo catalog publication')
    target=remote+'/metadata/catalog.json'
    rc=uploader(['copyto',str(catalog_path),target,
                 '--ignore-times','--timeout=60s','--retries=1'])
    # A nonzero final stat may follow a successful write. Only independently
    # reread exact bytes can recover it. If the write actually failed, this
    # raises and NEVER claims a new catalog was committed.
    method=reader(stage,target,raw)
    Path(destination).write_bytes(raw)
    print('OWNER_CATALOG_REMOTE_EXACT_READBACK',model,
          'photos_verified',proof['photos'],
          'verified_media',proof['full_SHA256_verified'],
          'read_method',method,'write_command_exit',rc,
          'catalog_published_only_after_full_readback',True,flush=True)
    return {'model':model,'photos_verified':proof['photos'],
            'read_method':method,'write_command_exit':rc}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--model',choices=sorted(REMOTES),required=True)
    p.add_argument('--remote',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    commit(a.stage,a.model,a.remote,a.out)
