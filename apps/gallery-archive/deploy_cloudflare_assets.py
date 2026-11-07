"""Owner-authorized Free Workers Assets replica; no billing or public Git writes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from email.parser import BytesParser
from email.policy import default
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener

from check_cloudflare_connection import reader, account_for, NoRedirect, ProbeError
from cloudflare_assets_snapshot import Snapshot, MODELS, KIND, checked

NAME = 'gallery-archive-free'
WRANGLER = '4.158.0'
API = 'https://api.cloudflare.com/client/v4'
ORIGIN = 'https://koith.github.io'
ROOT = Path(__file__).resolve().parents[2]


class CF:
    def __init__(self, token, account):
        self.token, self.account = token, account
        self.opener = build_opener(NoRedirect())

    def call(self, tail, method='GET', body=None, raw=False, multipart=None):
        # No subscription, billing mutation, R2 or arbitrary host endpoints.
        allowed = {'GET': r'(?:workers/scripts(?:/' + NAME + r'/(?:content|secrets))?|workers/subdomain|subscriptions)',
                   'PUT': r'workers/(?:subdomain|scripts/' + NAME + r'(?:/secrets)?)',
                   'POST': r'workers/(?:workers|scripts/' + NAME + r'/subdomain)'}
        if method not in allowed or not re.fullmatch(allowed[method], tail):
            raise ValueError('UNAPPROVED_CF_CONTROL_CALL')
        if multipart is not None and (method != 'PUT' or tail != 'workers/scripts/' + NAME or body is not None):
            raise ValueError('UNAPPROVED_MULTIPART_CALL')
        if method == 'PUT' and tail == 'workers/scripts/' + NAME and multipart is None:
            raise ValueError('SCRIPT_UPLOAD_REQUIRES_VALIDATED_MULTIPART')
        # Only fixed endpoint labels; never account IDs, tokens, body or names.
        phase = 'CF_' + method + '_' + tail.replace(NAME, 'archive').replace('/', '_').upper()
        print('CF_CONTROL_PHASE', phase, flush=True)
        payload = json.dumps(body).encode() if body is not None else None
        content_type = 'application/json'
        if multipart is not None:
            content_type, payload = multipart
        req = Request(API + '/accounts/' + self.account + '/' + tail, method=method, data=payload,
                      headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': content_type})
        try:
            with self.opener.open(req, timeout=40) as response:
                data = response.read(20_000_001)
                mime = response.headers.get('Content-Type', '')
        except HTTPError as error:
            codes, category = [], 'PROVIDER_REJECTED'
            body_format, null_codes, challenge = 'unparsed', 0, error.headers.get('cf-mitigated') == 'challenge'
            try:
                raw_error = error.read(8192)
                body_format = 'html' if raw_error.lstrip().startswith(b'<') else 'text'
                detail = json.loads(raw_error)
                body_format = 'json'
                errors = detail.get('errors', [])
                null_codes = sum(isinstance(e, dict) and e.get('code') is None for e in errors)
                codes = [e['code'] for e in errors if isinstance(e, dict)
                         and type(e.get('code')) is int and 0 < e['code'] < 1_000_000]
                messages = ' '.join(e.get('message', '') for e in errors
                                    if isinstance(e, dict) and isinstance(e.get('message'), str)).lower()
                if 'email' in messages and ('verif' in messages or 'confirm' in messages):
                    category = 'EMAIL_VERIFICATION_REQUIRED'
                elif 'no access to the specified resource' in messages:
                    category = 'RESOURCE_ACCESS_DENIED'
                elif 'permission' in messages or 'authentic' in messages or 'unauthoriz' in messages:
                    category = 'TOKEN_PERMISSION_OR_AUTH_REQUIRED'
                elif 'terms' in messages or 'onboard' in messages:
                    category = 'ACCOUNT_ONBOARDING_REQUIRED'
            except (ValueError, TypeError, OSError):
                pass
            if body_format == 'html' or challenge:
                category = 'EDGE_OR_CHALLENGE_REJECTED_NOT_PERMISSION_PROOF'
            print('CF_CONTROL_DENIAL', phase, 'http', error.code, 'codes', codes, 'category', category, flush=True)
            print('CF_CONTROL_DENIAL_SHAPE', json.dumps({'body_format': body_format,
                'null_error_codes': null_codes, 'challenge_header': challenge}, sort_keys=True), flush=True)
            raise ProbeError(phase, error.code) from None
        except (URLError, TimeoutError, OSError):
            raise ProbeError('CF_CONTROL_TRANSPORT') from None
        if len(data) > 20_000_000:
            raise ValueError('CF_CONTROL_RESPONSE_LIMIT')
        if raw:
            return mime, data
        result = json.loads(data)
        if result.get('success') is not True:
            raise ProbeError('CF_CONTROL_REJECTED')
        return result


def existing_catalogs(mime, raw):
    # Catalog Text modules remain inside the private Worker control plane.
    message = BytesParser(policy=default).parsebytes(b'MIME-Version: 1.0\r\nContent-Type: ' + mime.encode('ascii') + b'\r\n\r\n' + raw)
    found = {}
    if not message.is_multipart():
        raise ValueError('EXISTING_WORKER_NOT_OUR_PRIVATE_MULTIPART')
    for part in message.iter_parts():
        data = part.get_payload(decode=True)
        if not data or len(data) > 6_000_000:
            continue
        try:
            doc = json.loads(data)
        except (ValueError, UnicodeError):
            continue
        if isinstance(doc, dict) and doc.get('archive_kind') == KIND and doc.get('model') in MODELS:
            model = doc['model']
            if model in found or doc.get('schema_version') != 1 or not isinstance(doc.get('albums'), list):
                raise ValueError('EXISTING_PRIVATE_CATALOG_INVALID')
            found[model] = doc
    if set(found) != set(MODELS):
        raise ValueError('REFUSE_TO_REPLACE_UNKNOWN_OR_INCOMPLETE_WORKER')
    return found


def media_bytes(base, model, album, photo):
    opener = build_opener(NoRedirect())
    sign = Request(base + '/api/v1/sign', method='POST',
        headers={'Origin': ORIGIN, 'Content-Type': 'application/json'},
        data=json.dumps({'model': model, 'album': album, 'number': photo['number'],
                         'variant': 'original', 'sha256': photo['sha256']}).encode())
    with opener.open(sign, timeout=35) as response:
        data = json.loads(response.read(4097))
    url = urlsplit(data.get('url', ''))
    if (url.scheme + '://' + url.netloc != base or url.username or url.password or
        url.path != '/api/v1/media/' + '/'.join((model, album, str(photo['number']), 'original')) or
        data.get('sha256') != photo['sha256'] or data.get('bytes') != photo['bytes']):
        raise ValueError('REMOTE_SIGNED_PHOTO_MISMATCH')
    with opener.open(Request(data['url']), timeout=45) as response:
        raw = response.read(8_000_001)
    checked(photo, raw)
    return raw


def free_account_and_existing(cf):
    billing = cf.call('subscriptions')
    rows = billing.get('result')
    total = billing.get('result_info', {}).get('total_count', len(rows) if isinstance(rows, list) else -1)
    # This deployment never upgrades a plan or purchases a subscription. Only
    # the default Free account, with a complete empty account subscription list,
    # may proceed. This is not a promise about unrelated/future account usage.
    if rows != [] or total != 0:
        raise ValueError('FREE_DEFAULT_ACCOUNT_NOT_ESTABLISHED')
    scripts = cf.call('workers/scripts').get('result')
    if not isinstance(scripts, list):
        raise ValueError('SCRIPT_LIST_INVALID')
    exists = any(s.get('id') == NAME for s in scripts)
    old = None
    if exists:
        mime, raw = cf.call('workers/scripts/' + NAME + '/content', raw=True)
        old = existing_catalogs(mime, raw)
    return old


def subdomain(cf, register=False):
    try:
        result = cf.call('workers/subdomain')['result']
    except ProbeError as error:
        if error.status != 404:
            raise
        if not register:
            return None
        name = 'gallery-' + hashlib.sha256(cf.account.encode()).hexdigest()[:12]
        # Free workers.dev registration only. No domain purchase or paid plan.
        result = cf.call('workers/subdomain', 'PUT', {'subdomain': name})['result']
    domain = result.get('subdomain')
    if not isinstance(domain, str) or not re.fullmatch(r'[a-z0-9-]{1,63}', domain):
        raise ValueError('WORKERS_SUBDOMAIN_NOT_READY')
    return 'https://' + NAME + '.' + domain + '.workers.dev'


def bootstrap_missing_worker(cf, release):
    """Direct official upload, independent of Wrangler/Assets/subdomain APIs.

    Only create our fixed, absent Worker; never overwrite an existing script.
    Empty private catalogs make this recognizable and safely resumable. The
    bootstrap returns404 for every request and has no storage/billing bindings.
    """
    if free_account_and_existing(cf) is not None:
        raise ValueError('BOOTSTRAP_REFUSES_EXISTING_WORKER')
    # Independent official JSON creation API: establish the Worker resource
    # before multipart source/Assets upload. No domain, billing or paid binding.
    created = cf.call('workers/workers', 'POST', {'name': NAME,
        'tags': ['gallery-bootstrap-' + release[:12]], 'observability': {'enabled': False}, 'logpush': False})['result']
    if not isinstance(created, dict) or created.get('name') != NAME or not re.fullmatch(r'[a-f0-9]{32}', created.get('id', '')):
        raise ValueError('CREATED_WORKER_IDENTITY_UNVERIFIED')
    print('CF_OFFICIAL_WORKER_RESOURCE_CREATED', 'photo_uploads=0', flush=True)
    entry = ("import mimmi from './private-mimmi-catalog.txt';\n"
             "import yui from './private-yui-catalog.txt';\n"
             "export default {fetch(){void mimmi;void yui;return new Response('Not found',{status:404})}};\n").encode()
    metadata = {'main_module': 'entry.mjs', 'compatibility_date': '2026-11-01',
                'bindings': [], 'tags': ['gallery-bootstrap-' + release[:12]]}
    parts = [('metadata', 'application/json', json.dumps(metadata).encode()),
             ('entry.mjs', 'application/javascript+module', entry)]
    for model in MODELS:
        catalog = {'schema_version': 1, 'model': model, 'archive_kind': KIND, 'albums': []}
        parts.append((f'private-{model}-catalog.txt', 'text/plain', json.dumps(catalog).encode()))
    boundary = 'gallery-' + secrets.token_hex(24)
    body = b''
    for name, mime, value in parts:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}"\r\n'
                 f'Content-Type: {mime}\r\n\r\n').encode() + value + b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    cf.call('workers/scripts/' + NAME, 'PUT', multipart=('multipart/form-data; boundary=' + boundary, body))
    mime, raw = cf.call('workers/scripts/' + NAME + '/content', raw=True)
    catalogs = existing_catalogs(mime, raw)
    message = BytesParser(policy=default).parsebytes(b'MIME-Version: 1.0\r\nContent-Type: ' + mime.encode('ascii') + b'\r\n\r\n' + raw)
    if any(catalogs[m]['albums'] for m in MODELS) or not any(
            part.get_payload(decode=True) == entry for part in message.iter_parts()):
        raise ValueError('BOOTSTRAP_REMOTE_CODE_AND_CATALOG_READBACK_FAILED')
    print('CF_ACTUAL_SCRIPT_WRITE_AND_REMOTE_CODE_READBACK_VERIFIED', 'photo_uploads=0', flush=True)
    return catalogs


def write_deploy_sources(source, assets, catalogs, account, release):
    source.mkdir(parents=True, exist_ok=True)
    original = ROOT / 'apps/gallery-archive/cloudflare-owner-gateway'
    for name in ('worker.mjs', 'private-s3.mjs', 'bound-assets.mjs'):
        shutil.copyfile(original / name, source / name)
    for model in MODELS:
        (source / f'private-{model}-catalog.txt').write_text(json.dumps(catalogs[model], separators=(',', ':')))
    entry = '''import worker from './worker.mjs';
import mimmi from './private-mimmi-catalog.txt';
import yui from './private-yui-catalog.txt';
const catalogs={mimmi,yui};
export default {fetch(request,env){
 if(request.method==='GET'&&new URL(request.url).pathname==='/api/v1/health')return new Response(JSON.stringify({schema_version:1,repository:'koith/browser-app-lab',source_commit:env.ARCHIVE_RELEASE,transport:'cloudflare-bound-assets',full_P0_restored:false}),{headers:{'content-type':'application/json','cache-control':'no-store'}});
 return worker.fetch(request,{...env,ARCHIVE_CATALOGS:catalogs});
}};
'''
    (source / 'entry.mjs').write_text(entry)
    config = {'name': NAME, 'main': 'entry.mjs', 'account_id': account,
              # Official unrouted deployment: do not require account-level
              # workers.dev registration to upload code and private Assets.
              'compatibility_date': '2026-11-01', 'workers_dev': False,
              'preview_urls': False, 'keep_vars': True,
              'send_metrics': False,
              'observability': {'enabled': False},
              'vars': {'PAGE_ORIGIN': ORIGIN, 'PAGES_READ_POLICY': 'existing-sha-pinned-gallery',
                       'ARCHIVE_RELEASE': release, 'ARCHIVE_REPOSITORY': 'koith/browser-app-lab'},
              'rules': [{'type': 'Text', 'globs': ['**/private-*-catalog.txt'], 'fallthrough': False}],
              'assets': {'directory': str(assets.resolve()), 'binding': 'ARCHIVE_ASSETS',
                         'run_worker_first': True, 'html_handling': 'none', 'not_found_handling': 'none'}}
    (source / 'wrangler.json').write_text(json.dumps(config))


def main(args):
    print('BOUND_ASSET_PHASE', 'read_existing_free_account', flush=True)
    token = os.environ.get('CLOUDFLARE_API_TOKEN', '').strip()
    account, _ = account_for(reader(token), os.environ.get('CLOUDFLARE_ACCOUNT_ID', '').strip())
    cf = CF(token, account)
    old = free_account_and_existing(cf)
    release = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if old is None:
        # Test the actual script write before expensive owner reads. This also
        # initializes the first Worker before its Assets upload session.
        old = bootstrap_missing_worker(cf, release)
    work = Path(args.directory).resolve()
    assets, source = work / 'assets', work / 'source'
    snapshot = Snapshot(ROOT, assets)
    base = subdomain(cf)
    retained = {m: 0 for m in MODELS}
    if old and any(a['images'] for m in MODELS for a in old[m]['albums']):
        if base is None:
            # Never replace an existing replica if its original bytes cannot
            # first be recovered and checked. No assumption about Write access.
            raise ValueError('EXISTING_REPLICA_READBACK_ROUTE_REQUIRED')
        print('BOUND_ASSET_PHASE', 'retain_all_previous_verified_originals', flush=True)
        for model in MODELS:
            for album in old[model]['albums']:
                for photo in album['images']:
                    snapshot.add(model, album, photo, media_bytes(base, model, album['id'], photo), photo.get('replica_source', 'existing-verified-bound-replica'))
                    retained[model] += 1
    print('BOUND_ASSET_PHASE', 'copy_exact_existing_public_originals', flush=True)
    public = snapshot.public_originals()
    print('BOUND_ASSET_PHASE', 'read_exact_existing_private_originals', flush=True)
    owner = {model: snapshot.existing_owner(model, args.max_new_per_model) for model in MODELS}
    catalogs = snapshot.finish()
    if any(not catalogs[m]['albums'] for m in MODELS):
        raise ValueError('BOTH_MODELS_REQUIRE_ACTUAL_FILES')
    write_deploy_sources(source, assets, catalogs, account, release)
    # Recheck the actual billing state immediately before the deployment.
    if free_account_and_existing(cf) != old:
        raise ValueError('CONCURRENT_REPLICA_CHANGE_REFUSED')
    print('BOUND_ASSET_PHASE', 'deploy_default_free_worker_and_assets', flush=True)
    command = ['npx', '--yes', 'wrangler@' + WRANGLER, 'deploy', '--config', str(source / 'wrangler.json')]
    process = subprocess.run(command, cwd=source, env={**os.environ, 'CLOUDFLARE_ACCOUNT_ID': account,
        'WRANGLER_SEND_METRICS': 'false'}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1200)
    if process.returncode:
        clean = re.sub(rb'\x1b\[[0-9;]*[A-Za-z]', b'', process.stdout)
        codes = sorted(set(re.findall(rb'(?i)code[\s:=\"]+(\d{3,6})', clean)))
        print('WRANGLER_DEPLOY_FAILED', process.returncode, [x.decode() for x in codes], flush=True)
        # Wrangler's full diagnostics may contain private file names/account IDs.
        # Keep only fixed operation labels, never the raw request or response.
        operations = []
        for tail, label in ((b'/assets-upload-session', 'CREATE_ASSET_UPLOAD_SESSION'),
                            (b'/workers/assets/upload', 'UPLOAD_ASSET_BYTES'),
                            (b'/workers/scripts/' + NAME.encode(), 'UPLOAD_OR_INSPECT_WORKER'),
                            (b'/workers/subdomain', 'ACCOUNT_SUBDOMAIN'),
                            (b'/workers/dispatch', 'DISPATCH')):
            if tail in process.stdout:
                operations.append(label)
        print('WRANGLER_FAILED_OPERATION_LABELS', operations, flush=True)
        # Allowlisted classes only, not arbitrary provider messages or paths.
        words = clean.lower()
        categories = [label for needle, label in (
            (b'authentication error', 'AUTHENTICATION_OR_SCOPE_DENIED'),
            (b'permission', 'PERMISSION_DIAGNOSTIC_PRESENT'),
            (b'email', 'EMAIL_DIAGNOSTIC_PRESENT'),
            (b'onboard', 'ONBOARDING_DIAGNOSTIC_PRESENT'),
            (b'not exist', 'RESOURCE_ABSENT_DIAGNOSTIC_PRESENT'),
            (b'not registered', 'REGISTRATION_DIAGNOSTIC_PRESENT'),
            (b'forbidden', 'HTTP_FORBIDDEN'), (b'403', 'STATUS_403_PRESENT'),
            (b'free plan', 'FREE_PLAN_DIAGNOSTIC_PRESENT'),
            (b'invalid', 'INVALID_ARGUMENT_DIAGNOSTIC_PRESENT')) if needle in words]
        print('WRANGLER_FAILURE_CLASSES', categories, flush=True)
        from audit_cloudflare_recovery import inspect
        print('CLOUDFLARE_AFTER_UPLOAD_FAILURE_AUDIT', json.dumps(inspect(token, account), sort_keys=True), flush=True)
        raise ValueError('WORKER_DEPLOY_NOT_VERIFIED')
    print('CF_UNROUTED_WORKER_AND_ASSETS_UPLOAD_SUCCEEDED', flush=True)
    # Registration is a separate operation. An upload success proves that a
    # previous registration denial did not establish missing Scripts Write.
    base = subdomain(cf, register=True)
    cf.call('workers/scripts/' + NAME + '/subdomain', 'POST',
            {'enabled': True, 'previews_enabled': False})
    # Secrets never appear in config, source modules, logs or public image URLs.
    print('BOUND_ASSET_PHASE', 'configure_worker_only_signing_secret', flush=True)
    keys = cf.call('workers/scripts/' + NAME + '/secrets')['result']
    if not any(k.get('name') == 'SIGNING_KEY' for k in keys):
        cf.call('workers/scripts/' + NAME + '/secrets', 'PUT',
                {'name': 'SIGNING_KEY', 'text': secrets.token_urlsafe(48), 'type': 'secret_text'})
    print('BOUND_ASSET_PHASE', 'verify_actual_remote_originals', flush=True)
    ready = False
    for _ in range(15):
        try:
            with build_opener(NoRedirect()).open(base + '/api/v1/health', timeout=10) as response:
                health = json.loads(response.read(4096))
            if health.get('source_commit') == release and health.get('transport') == 'cloudflare-bound-assets':
                ready = True
                break
        except (OSError, ValueError):
            pass
        time.sleep(2)
    if not ready:
        raise ValueError('ACTUAL_WORKER_RELEASE_NOT_OBSERVED')
    tasks = [(m, a['id'], p) for m in MODELS for a in catalogs[m]['albums'] for p in a['images']]
    def verify(task):
        model, album, photo = task
        try:
            media_bytes(base, model, album, photo)
            return model, None
        except HTTPError as error:
            return model, {'model': model, 'album': album, 'number': photo['number'], 'http_status': error.code}
        except Exception as error:
            return model, {'model': model, 'album': album, 'number': photo['number'], 'failure_type': type(error).__name__}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(verify, tasks))
    passed = {m: sum(model == m and failure is None for model, failure in results) for m in MODELS}
    failures = [failure for _, failure in results if failure is not None]
    failed = len(failures)
    # Independently verify that raw object and catalog namespaces stay closed.
    opener = build_opener(NoRedirect())
    for model in MODELS:
        sample = catalogs[model]['albums'][0]['images'][0]
        for path in (model + '/metadata/catalog.json', model + '/' + sample['key']):
            try:
                opener.open(base + '/' + quote(path, safe='/'), timeout=30)
            except HTTPError as error:
                if error.code == 404:
                    continue
            raise ValueError('RAW_ASSET_EXPOSURE_OR_UNVERIFIED_GUARD')
    report = {'source_commit': release, 'endpoint': base, 'wrangler_version': WRANGLER,
              'retained_rows': retained, 'existing_public_rows_added': public,
              'existing_private_owner_reads': owner, 'remote_original_SHA_bytes_pixels_pass': passed,
              'remote_original_failures': failed, 'raw_paths_denied': True,
              'failed_originals_first_30': failures[:30],
              'newly_collected_photos': 0, 'subscriptions_changed': 0,
              'gallery_activated': False, 'full_P0_restored': False}
    (work / 'verification.json').write_text(json.dumps(report, indent=2))
    print('CLOUDFLARE_ACTUAL_ASSET_READBACK', json.dumps(report, sort_keys=True), flush=True)
    if failed:
        raise ValueError('REMOTE_PHOTO_READBACK_FAILED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--max-new-per-model', type=int, default=32)
    args = parser.parse_args()
    if not 0 <= args.max_new_per_model <= 10000:
        raise SystemExit('INVALID_OWNER_READ_LIMIT')
    try:
        main(args)
    except ProbeError as error:
        print('CLOUDFLARE_ASSET_OPERATION_BLOCKED', error.phase, error.status, flush=True)
        raise SystemExit(2) from None
    except Exception as error:
        # Unexpected exceptions may contain private paths/URLs. No traceback.
        print('CLOUDFLARE_ASSET_OPERATION_FAILED', type(error).__name__, flush=True)
        raise SystemExit(2) from None
