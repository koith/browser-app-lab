"""Bounded GET-only recovery audit; no provider bodies, identities or secrets in logs."""
import hashlib
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from check_cloudflare_connection import API, ACCOUNT, NoRedirect, ProbeError, account_for, reader

PERMISSIONS = {'Workers Scripts Read', 'Workers Scripts Write', 'Workers Scripts Edit',
               'Workers Admin', 'Workers Editor', 'Workers Content Read-Only', 'Workers Metadata Read-Only',
               'Individual Workers Admin', 'Individual Workers Editor',
               'Individual Workers Content Read-Only', 'Individual Workers Metadata Read-Only',
               'Account Settings Read', 'Account Settings Write', 'Account Settings Edit',
               'Billing Read', 'Billing Write', 'Pages Read', 'Pages Write', 'Pages Edit'}


class Audit:
    def __init__(self, token, account):
        self.token, self.account = token, account
        self.opener = build_opener(NoRedirect())
        self.observations = {}

    def get(self, label, path):
        # Never accept arbitrary hosts, mutations, token lists, or another token ID.
        allowed = {'account': '/accounts/' + self.account,
                   'user': '/user', 'user_token_verify': '/user/tokens/verify',
                   'account_token_verify': '/accounts/' + self.account + '/tokens/verify'}
        allowed.update({name: '/accounts/' + self.account + '/' + tail for name, tail in {
            'scripts': 'workers/scripts', 'services': 'workers/services',
            'domains': 'workers/domains', 'subdomain': 'workers/subdomain',
            'worker_settings': 'workers/account-settings', 'entitlements': 'entitlements',
            'pages_projects': 'pages/projects'}.items()})
        if label == 'own_token_details':
            if path != getattr(self, 'own_token_path', None):
                raise ValueError('UNAPPROVED_TOKEN_READ')
        elif allowed.get(label) != path:
            raise ValueError('UNAPPROVED_AUDIT_READ')
        observation = {'method': 'GET', 'http': 0, 'success': False, 'error_codes': []}
        self.observations[label] = observation
        req = Request(API + path, method='GET', headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'})
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(2_000_001)
                observation['http'] = response.status
        except HTTPError as error:
            observation['http'] = error.code
            raw = error.read(8192)
        except (URLError, OSError, TimeoutError, ProbeError):
            return None
        if len(raw) > 2_000_000:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            return None
        if not isinstance(data, dict):
            return None
        observation['success'] = observation['http'] == 200 and data.get('success') is True
        errors = data.get('errors', [])
        if isinstance(errors, list):
            observation['error_codes'] = [e['code'] for e in errors if isinstance(e, dict)
                and type(e.get('code')) is int and 0 < e['code'] < 1_000_000]
        return data.get('result') if observation['success'] else None


def policies_summary(details, account):
    if not isinstance(details, dict) or not isinstance(details.get('policies'), list):
        return {'own_policy_inspection_verified': False}
    result = {'own_policy_inspection_verified': True, 'allow_permissions_on_selected_account': [],
              'explicit_other_account_scope_present': False}
    granted = set()
    for policy in details['policies']:
        if not isinstance(policy, dict):
            continue
        resources = policy.get('resources', {})
        if not isinstance(resources, dict):
            continue
        selected = any(key in ('*', 'com.cloudflare.api.account.*', 'com.cloudflare.api.account.' + account)
                       for key in resources)
        result['explicit_other_account_scope_present'] |= any(
            key.startswith('com.cloudflare.api.account.') and
            key not in ('com.cloudflare.api.account.*', 'com.cloudflare.api.account.' + account)
            for key in resources)
        if policy.get('effect') == 'allow' and selected:
            for permission in policy.get('permission_groups', []):
                if isinstance(permission, dict) and permission.get('name') in PERMISSIONS:
                    granted.add(permission['name'])
    result['allow_permissions_on_selected_account'] = sorted(granted)
    # An allow list is evidence of grants, not proof that no deny policy applies.
    result['deny_policy_present'] = any(isinstance(p, dict) and p.get('effect') == 'deny' for p in details['policies'])
    return result


def inspect(token, configured='', get_accounts=None, audit_factory=Audit):
    account, count = account_for(reader(token) if get_accounts is None else get_accounts, configured)
    audit = audit_factory(token, account)
    result = {'accessible_accounts': count, 'configured_account_verified_in_accessible_list': bool(configured),
              'selected_account_fingerprint': hashlib.sha256(account.encode()).hexdigest()[:12],
              'token_kind': 'account' if token.startswith('cfat_') else 'user' if token.startswith('cfut_') else 'legacy_or_unspecified',
              'worker_write_permission_verified': False, 'permission_change_required': 'UNVERIFIED',
              'resource_creations': 0, 'uploaded_photos': 0, 'gallery_restored': False}
    info = audit.get('account', '/accounts/' + account)
    result['account_details_match_selected_account'] = isinstance(info, dict) and info.get('id') == account
    prefix = '/accounts/' + account + '/tokens/' if result['token_kind'] == 'account' else '/user/tokens/'
    verified = audit.get('account_token_verify' if result['token_kind'] == 'account' else 'user_token_verify', prefix + 'verify')
    result['own_token_active_verified'] = isinstance(verified, dict) and verified.get('status') == 'active'
    if isinstance(verified, dict) and ACCOUNT.fullmatch(verified.get('id', '')):
        audit.own_token_path = prefix + verified['id']
        details = audit.get('own_token_details', audit.own_token_path)
        result.update(policies_summary(details, account))
    else:
        result['own_policy_inspection_verified'] = False
    user = audit.get('user', '/user')
    result['user_email_verified'] = user.get('email_verified') if isinstance(user, dict) and type(user.get('email_verified')) is bool else 'UNVERIFIED'
    for label, tail in (('scripts', 'workers/scripts'), ('services', 'workers/services'),
                        ('domains', 'workers/domains'), ('pages_projects', 'pages/projects')):
        rows = audit.get(label, '/accounts/' + account + '/' + tail)
        result[label + '_count'] = len(rows) if isinstance(rows, list) else 'UNVERIFIED'
        if label == 'scripts' and isinstance(rows, list):
            result['existing_gallery_worker'] = any(isinstance(x, dict) and x.get('id') == 'gallery-archive-free' for x in rows)
    domain = audit.get('subdomain', '/accounts/' + account + '/workers/subdomain')
    result['existing_workers_subdomain'] = bool(isinstance(domain, dict) and domain.get('subdomain'))
    settings = audit.get('worker_settings', '/accounts/' + account + '/workers/account-settings')
    result['worker_account_settings_read_verified'] = isinstance(settings, dict)
    entitlements = audit.get('entitlements', '/accounts/' + account + '/entitlements')
    result['entitlements_read_verified'] = isinstance(entitlements, (dict, list))
    result['endpoint_observations'] = audit.observations
    return result


if __name__ == '__main__':
    try:
        result = inspect(os.environ.get('CLOUDFLARE_API_TOKEN', '').strip(), os.environ.get('CLOUDFLARE_ACCOUNT_ID', '').strip())
        print('CLOUDFLARE_READ_ONLY_RECOVERY_AUDIT', json.dumps(result, sort_keys=True), flush=True)
    except Exception as error:
        print('CLOUDFLARE_AUDIT_BLOCKED', type(error).__name__, flush=True)
        raise SystemExit(2) from None
