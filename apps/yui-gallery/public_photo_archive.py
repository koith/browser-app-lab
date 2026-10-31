"""Byte-preserving, resumable individual files for explicitly public photographs."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import threading
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image

USER_AGENT = 'YuiPublicArchive/0.13 (+https://github.com/koith/browser-app-lab)'


class PublicOriginPaused(PermissionError):
    def __init__(self,status,reason,retry_after=None,*,policy=False):
        self.status_code,self.reason,self.retry_after=status,reason,retry_after
        self.policy=policy
        super().__init__(reason)


def public_failure(error):
    """Classify failures without response bodies, cookies or signed URLs."""
    response=getattr(error,'response',None)
    status=response.status_code if response is not None else getattr(error,'status_code',None)
    cause=({401:'authentication_required',403:'access_denied',404:'public_resource_missing',
            410:'public_resource_gone',429:'rate_limited',451:'legal_restriction'}).get(status)
    if status is not None and status>=500:cause='origin_temporarily_unavailable'
    if not cause:
        cause=('transport_timeout' if isinstance(error,requests.Timeout) else
               'robots_or_origin_paused' if isinstance(error,PermissionError) else
               'transport_error' if isinstance(error,requests.RequestException) else 'validation_error')
    result={'exception':type(error).__name__,'http_status':status,'cause':cause}
    result['response_scope']='robots_policy' if getattr(error,'policy',False) else 'resource' if status is not None else 'unknown'
    if getattr(error,'retry_after',None) is not None:result['retry_after_seconds']=error.retry_after
    return result


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PublicSession:
    """Respect robots, redirects and rate limits; never create authenticated sessions."""

    def __init__(self, delay=0.5, allow_local_test=False):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT
        self.delay = delay
        self.allow_local_test = allow_local_test
        self.robots = {}
        self.robot_status = {}
        self.blocked_origins = set()
        self.block_status = {}
        self.cooldowns = {}
        self.last_request = {}
        self.lock = threading.Lock()

    def _origin(self, url):
        parsed = urlsplit(url)
        local_test = self.allow_local_test and parsed.hostname == '127.0.0.1'
        if (parsed.scheme != 'https' and not local_test) or parsed.username or parsed.password:
            raise ValueError('Only public HTTPS URLs are accepted')
        return parsed.scheme + '://' + parsed.netloc

    def _raw(self, url):
        origin = self._origin(url)
        with self.lock:
            remaining = self.delay - (time.monotonic() - self.last_request.get(origin, 0))
            if remaining > 0:
                time.sleep(remaining)
            self.last_request[origin] = time.monotonic()
            # No automatic redirects: every target must pass its own robots check.
            response = self.session.get(url, timeout=(12, 30), allow_redirects=False, stream=True)
            data = bytearray()
            try:
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 32_000_000:
                        raise ValueError('Public resource exceeds 32 MB')
                response._content = bytes(data)
                response._content_consumed = True
            finally:
                response.close()
            return response

    def allowed(self, url):
        origin = self._origin(url)
        if origin not in self.robots:
            policy_url = origin + '/robots.txt'
            for _ in range(6):
                response = self._raw(policy_url)
                if response.status_code not in (301, 302, 303, 307, 308):
                    break
                policy_url = urljoin(policy_url, response.headers.get('Location', ''))
            parser = urllib.robotparser.RobotFileParser()
            # RFC 9309 §2.3.1.3: an unavailable robots file (4xx) is not
            # a Disallow directive for a different public resource. Object
            # storage commonly answers a missing robots.txt with 403.
            # Authentication, rate/legal restrictions and unreachable policies
            # remain closed; the actual resource must independently return 2xx.
            if response.status_code in (403, 404, 410):
                parser.allow_all = True
            elif response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                # An inaccessible/redirected policy is unverified, never implicit permission.
                parser.disallow_all = True
            self.robots[origin] = parser
            self.robot_status[origin]=response.status_code
        return self.robots[origin].can_fetch(USER_AGENT, url)

    def get(self, url):
        for _ in range(6):
            origin=self._origin(url)
            if origin in self.blocked_origins:
                raise PublicOriginPaused(self.block_status.get(origin),'Stopped this origin after an access/rate-limit response')
            until,status=self.cooldowns.get(origin,(0,None))
            if time.monotonic()<until:
                raise PublicOriginPaused(status,'Origin is cooling down after an unavailable response',int(until-time.monotonic())+1)
            if not self.allowed(url):
                raise PublicOriginPaused(self.robot_status.get(origin),'robots policy blocks or cannot verify the public origin',policy=True)
            response = self._raw(url)
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get('Location', ''))
                continue
            # Resource access, rate and legal denials stop the origin.
            if response.status_code in (401, 403, 429, 451):
                self.blocked_origins.add(self._origin(url))
                self.block_status[self._origin(url)]=response.status_code
            elif response.status_code in (500,502,503,504,521,522,523,524):
                # A broken origin should not receive the same request once for
                # every candidate work. No automatic retries or host changes.
                delay=response.headers.get('Retry-After','')
                seconds=min(900,max(120,int(delay))) if delay.isascii() and delay.isdigit() and len(delay)<=6 else 300
                self.cooldowns[self._origin(url)]=(time.monotonic()+seconds,response.status_code)
            response.raise_for_status()
            return response
        raise ValueError('Too many public redirects')


def inspect_bytes(raw):
    with Image.open(io.BytesIO(raw)) as image:
        image.verify()
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        width, height, format_name = image.width, image.height, image.format
    extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'AVIF': 'avif'}.get(format_name)
    if not extension or min(width, height) < 250:
        raise ValueError('Not a supported photograph of at least 250px on each edge')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'width': width, 'height': height, 'extension': extension}


def verified_record(root, row):
    path = (Path(root) / row['file']).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Unsafe relative photo path')
    actual = inspect_bytes(path.read_bytes())
    for key in ('sha256', 'bytes', 'width', 'height'):
        if actual[key] != row[key]:
            raise ValueError('Stored photograph integrity mismatch: ' + key)
    return actual


def download_individuals(records, output, client=None, source_kind='public_social_attachments'):
    """Incremental checkpoint after every file; preserve all distinct prior input copies."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    client = client or PublicSession()
    manifest_path = output / 'manifest.json'
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'images': []}
    images = list(old['images'])
    by_url = {row['url']: row for row in images}
    by_hash = {row['sha256']: row for row in images}
    for row in images:
        verified_record(output, row)
    failures, new_hashes = [], []
    skipped_existing = 0
    for index, record in enumerate(records, 1):
        if record['url'] in by_url:
            skipped_existing += 1
            continue
        try:
            response = client.get(record['url'])
            raw = response.content
            info = inspect_bytes(raw)
            if info['sha256'] in by_hash:
                filename = by_hash[info['sha256']]['file']
            else:
                filename = 'images/' + info['sha256'] + '.' + info['extension']
                path = output / filename
                path.parent.mkdir(exist_ok=True)
                # The response bytes are written exactly; no image encoder is invoked.
                if path.exists() and path.read_bytes() != raw:
                    raise ValueError('Existing content-addressed file differs')
                path.write_bytes(raw)
                new_hashes.append(info['sha256'])
            row = {**record, **info, 'file': filename, 'downloaded_at': utcnow(),
                   'response_url': response.url, 'publisher_original_verified': False,
                   'site_watermark_review': {'status': 'unknown'}}
            verified_record(output, row)
            images.append(row)
            by_url[row['url']] = row
            by_hash[row['sha256']] = row
        except Exception as error:
            failures.append({'url': record['url'], 'error': str(error)[:350]})
        report = {'generated_at': utcnow(), 'kind': source_kind, 'not_private_cloud': True,
                  'not_complete_photobook': True, 'images': images, 'failures': failures,
                  'new_unique_files_this_run': len(new_hashes),
                  'unique_files': len({row['sha256'] for row in images}),
                  'skipped_existing_urls': skipped_existing}
        atomic_json(manifest_path, report)
        if index % 20 == 0 or index == len(records):
            print('PUBLIC_INDIVIDUAL_FILES', index, '/', len(records), 'new', len(new_hashes),
                  'failed', len(failures), flush=True)
    report = {'generated_at': utcnow(), 'kind': source_kind, 'not_private_cloud': True,
              'not_complete_photobook': True, 'images': images, 'failures': failures,
              'new_unique_files_this_run': len(new_hashes), 'unique_files': len(by_hash),
              'skipped_existing_urls': skipped_existing}
    atomic_json(manifest_path, report)
    return json.loads(manifest_path.read_text())
