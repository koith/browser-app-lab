"""Validate private metadata, with one normal file-download alternative to cat.

A successful command returning a provider JSON error is not an owner catalog.
Use the same configured owner account and path, never a credential workaround.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit,quote

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
        if batch:
            albums=document.get('albums')
            return (document.get('source_batch_sha256')==batch
                    and isinstance(albums,list) and bool(albums)
                    and all(isinstance(a,dict)
                            and isinstance(a.get('id'),str) and a.get('id')
                            and isinstance(a.get('images'),list) and a['images']
                            for a in albums))
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
    # A provider JSON error returned by streaming 'cat' is not file bytes.
    # Try the ordinary SAME-ACCOUNT file download once. This does not solve
    # a verification challenge, change credentials, or use another account;
    # a successful download must pass the complete private catalog schema
    # and previous published row floor. If both normal methods fail on
    # 400141, preserve the explicit verification-required state.
    challenged=evidence['provider_errno']==400141
    with tempfile.TemporaryDirectory(prefix='owner-metadata-') as temporary:
        local=Path(temporary)/'metadata.json'
        with tempfile.TemporaryFile() as errors:
            result=subprocess.run(['rclone','copyto',remote,str(local),'--ignore-times',
                '--max-size',str(limit),'--timeout=60s','--retries=1'],
                stdout=subprocess.DEVNULL,stderr=errors,timeout=75)
            if result.returncode:
                if challenged:
                    return signed_pending_gateway_read_or_hold(remote,model,batch,minimum)
                errors.seek(0)
                raise ValueError('Normal owner metadata download failed: '+
                    diagnostic(errors.read(32000).decode('utf-8','replace'))) from None
        if not local.is_file() or not 0<local.stat().st_size<=limit:
            raise ValueError('Downloaded owner metadata exceeds its bounded size')
        raw=local.read_bytes()
    if not matches(raw,model,batch,minimum):
        if challenged:
            return signed_pending_gateway_read_or_hold(remote,model,batch,minimum)
        raise ValueError('Downloaded metadata envelope invalid '+json.dumps(summary(raw,model,batch),sort_keys=True))
    print('OWNER_METADATA_NORMAL_FILE_DOWNLOAD_VERIFIED',model,'pending' if batch else 'catalog',file=sys.stderr,flush=True)
    return raw





def signed_pending_gateway_read_or_hold(remote,model,batch,minimum):
    """Strict optional recovery of already-existing SHA-named owner queue.

    Never relax the catalog preflight, substitute public Pages metadata, or
    import a queue before the independently verified original+preview read.
    """
    if (not batch or os.environ.get('GALLERY_AUTHORIZED_PENDING_READ')!='1'):
        raise ProviderVerificationRequired(
            'Owner storage verification required; private queue held unchanged')
    raw=read_via_existing_owner_gateway(remote,model,minimum=minimum,batch=batch)
    if not matches(raw,model,batch,minimum):
        raise ProviderVerificationRequired(
            'Owner signed pending metadata did not match exact source batch')
    print('OWNER_PENDING_GATEWAY_MATCHED_EXACT_BATCH',model,batch[:12],
          'IMPORTED',False,'MEDIA_VERIFIED',False,
          file=sys.stderr,flush=True)
    return raw


def read_via_existing_owner_gateway(remote,model,*,minimum=1,batch=None,opener=None):
    """Fallback ONLY to an authorized, fresh private catalog from our gateway.

    The gateway and this repo's main-branch collector authenticate each other
    with a short-lived GitHub Actions OIDC identity. No token, cookie, private
    storage key or raw catalog is committed to GitHub or sent to public Pages.
    """
    base={'mimmi':'archive:MimmiArchive','yui':'archive:YuiArchive'}.get(model)
    if batch is not None and not re.fullmatch(r'[a-f0-9]{64}',batch):
        raise ValueError('Invalid exact owner pending SHA')
    expected=(base+('/metadata/pending-individual/'+model+'/'+batch+'.json'
                    if batch else '/metadata/catalog.json')) if base else None
    if remote!=expected:
        raise ValueError('Unapproved private model / catalog / pending object')
    request_url=os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL','')
    request_token=os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN','')
    target=urlsplit(request_url)
    if (target.scheme!='https' or not target.hostname
            or not target.hostname.endswith('.actions.githubusercontent.com')
            or target.username or target.password or not request_token):
        raise ProviderVerificationRequired('Collector GitHub OIDC identity unavailable')

    if opener is None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):
                raise ProviderVerificationRequired('Authenticated catalog redirect rejected')
        opener=urllib.request.build_opener(NoRedirect()).open

    def fetch(request,limit,timeout,phase):
        try:
            with opener(request,timeout=timeout) as response:
                if getattr(response,'status',200)!=200:
                    raise ProviderVerificationRequired('Owner gateway HTTP read unavailable')
                raw=response.read(limit+1)
                if not raw or len(raw)>limit:
                    raise ProviderVerificationRequired('Owner gateway read exceeds bounds')
                return raw
        except urllib.error.HTTPError as error:
            # Only phase + status are recorded. No URL, bearer, body,
            # private paths or owner material ever enter Actions logs.
            print('OWNER_SIGNED_REMOTE_HTTP',model,phase,error.code,
                  'PRIVATE_ENDPOINTS_LOGGED',False,file=sys.stderr,flush=True)
            raise ProviderVerificationRequired('Owner gateway signed read unavailable') from None
        except (urllib.error.URLError,TimeoutError,OSError) as error:
            print('OWNER_SIGNED_REMOTE_TRANSPORT',model,phase,
                  type(error).__name__,'PRIVATE_ENDPOINTS_LOGGED',False,
                  file=sys.stderr,flush=True)
            raise ProviderVerificationRequired('Owner gateway signed read unavailable') from None

    audience='gallery-archive-terabox-sync'
    sep='&' if target.query else '?'
    request=urllib.request.Request(
        request_url+sep+'audience='+quote(audience),
        headers={'Authorization':'Bearer '+request_token})
    try:
        id_token=json.loads(fetch(request,24000,30,'oidc')).get('value')
    except (ValueError,TypeError,AttributeError):
        raise ProviderVerificationRequired('Collector GitHub identity response invalid') from None
    if not isinstance(id_token,str) or not 80<=len(id_token)<=12000:
        raise ProviderVerificationRequired('Collector OIDC token missing')
    path=('/internal/gallery-owner-pending/'+model+'/'+batch) if batch else (
          '/internal/gallery-owner-catalog/'+model)
    endpoint='https://mimmi-private-gallery-free.onrender.com'+path
    request=urllib.request.Request(endpoint,method='POST',data=b'',
                                   headers={'Authorization':'Bearer '+id_token,
                                            'Content-Type':'application/octet-stream'})
    raw=fetch(request,2_000_000 if batch else 6_000_000,125,'pending' if batch else 'catalog')
    if not matches(raw,model,batch,minimum):
        raise ProviderVerificationRequired('Gateway owner metadata identity or batch SHA invalid')
    print('OWNER_REMOTE_AUTHENTICATED_GATEWAY_READ',model,
          'KIND','pending' if batch else 'catalog',
          'RAW_BYTES',len(raw),'PRIVATE_PATHS_LOGGED',False,
          file=sys.stderr,flush=True)
    return raw


def read_with_current_owner_web_session(remote,model,*,minimum=1,reader=None,refresh=None,gateway_fallback=False,gateway_reader=None):
    """Try the owner's *existing*, authenticated /main session before metadata IO.

    The archive client can use its ordinary jsToken for API requests. The
    previous production sequence only obtained this web token *after* the
    metadata preflight, where provider 400141 caused an early exit. This is
    a legitimate same-account session refresh, not a challenge workaround.

    A rejected login/verification remains rejected. Never accept a public
    GitHub index in place of fresh remotely authenticated owner metadata.
    """
    expected={'mimmi':'archive:MimmiArchive/metadata/catalog.json',
              'yui':'archive:YuiArchive/metadata/catalog.json'}.get(model)
    if remote!=expected:
        raise ValueError('Only the original model-specific owner catalog may refresh web state')
    optional_network_errors=()
    if refresh is None:
        from owner_upload_web_token import update_current_process
        import httpx
        optional_network_errors=(httpx.RequestError,)
        refresh=update_current_process
    try:
        token=refresh()
        if not isinstance(token,str) or not token:
            raise ValueError('No owner web token')
        print('OWNER_AUTHENTICATED_WEB_STATE_READY_BEFORE_CATALOG',model,
              'TOKEN_DISCLOSED',False,file=sys.stderr,flush=True)
    except Exception as error:
        if not isinstance(error,(ValueError,OSError,TimeoutError)+optional_network_errors):
            raise
        # A normal credential refresh failure does not license a different
        # account, source host, signed URL, or verification challenge bypass.
        print('OWNER_AUTHENTICATED_WEB_STATE_UNAVAILABLE',model,
              type(error).__name__,'COOKIE_ONLY_READ_REMAINS_SHA_GATED',True,
              file=sys.stderr,flush=True)
    try:
        return read(remote,model,minimum=minimum,reader=reader)
    except ProviderVerificationRequired:
        if not gateway_fallback:
            raise
        if gateway_reader is None:
            gateway_reader=read_via_existing_owner_gateway
        # Existing remote metadata is still verified against the published
        # photo baseline; do not accept public/unauthenticated index guesses.
        raw=gateway_reader(remote,model,minimum=minimum)
        if not matches(raw,model,None,minimum):
            raise ProviderVerificationRequired('Signed gateway remote catalog failed complete identity and baseline validation')
        return raw


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--remote',required=True);p.add_argument('--model',choices=['mimmi','yui'],required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--published-index',type=Path,required=True);p.add_argument('--refresh-existing-web-session',action='store_true');p.add_argument('--signed-gateway-catalog-fallback',action='store_true');a=p.parse_args()
    index=json.loads(a.published_index.read_text())
    if index.get('model')!=a.model:raise ValueError('Wrong published owner model')
    minimum=sum(len(album['images']) for album in index['albums'])
    remote=a.remote.rstrip('/')+'/metadata/catalog.json'
    if a.refresh_existing_web_session:
        raw=read_with_current_owner_web_session(remote,a.model,minimum=minimum,gateway_fallback=a.signed_gateway_catalog_fallback)
    else:
        raw=read(remote,a.model,minimum=minimum)
    a.out.write_bytes(raw)
