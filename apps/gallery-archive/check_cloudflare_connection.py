"""Read-only Cloudflare connection probe. Never deploy, subscribe or log secrets."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

API = 'https://api.cloudflare.com/client/v4'
ACCOUNT = re.compile(r'[a-f0-9]{32}')
ALLOWED = re.compile(r'/accounts(?:\?per_page=50&page=[1-5]|/[a-f0-9]{32}/(?:workers/scripts|subscriptions|workers/subdomain))')


class ProbeError(Exception):
    def __init__(self, phase, status=0):
        self.phase, self.status = phase, status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProbeError('REDIRECT_REFUSED')


def reader(token):
    opener = build_opener(NoRedirect())

    def get(path):
        if not ALLOWED.fullmatch(path):
            raise ProbeError('UNAPPROVED_READ')
        request = Request(API + path, headers={'Authorization': 'Bearer ' + token,
                                              'Accept': 'application/json'}, method='GET')
        try:
            with opener.open(request, timeout=25) as response:
                if response.status != 200:
                    raise ProbeError('HTTP_READ', response.status)
                raw = response.read(1_000_001)
        except HTTPError as error:
            raise ProbeError('HTTP_READ', error.code) from None
        except (URLError, TimeoutError, OSError):
            raise ProbeError('TRANSPORT_READ') from None
        if len(raw) > 1_000_000:
            raise ProbeError('RESPONSE_LIMIT')
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ProbeError('INVALID_JSON') from None
        if not isinstance(data, dict) or data.get('success') is not True:
            raise ProbeError('API_READ_REJECTED')
        return data
    return get


def account_for(get, configured=''):
    if configured and not ACCOUNT.fullmatch(configured):
        raise ProbeError('INVALID_CONFIGURED_ACCOUNT')
    accounts = []
    for page in range(1, 6):
        data = get('/accounts?per_page=50&page=' + str(page))
        rows = data.get('result')
        if not isinstance(rows, list) or any(not isinstance(a, dict) or
                not ACCOUNT.fullmatch(a.get('id', '')) for a in rows):
            raise ProbeError('INVALID_ACCOUNT_ENVELOPE')
        accounts += [a['id'] for a in rows]
        total = data.get('result_info', {}).get('total_count')
        if (type(total) is int and total <= len(accounts)) or len(rows) < 50:
            break
    else:
        raise ProbeError('ACCOUNT_PAGINATION_LIMIT')
    if len(set(accounts)) != len(accounts):
        raise ProbeError('DUPLICATE_ACCOUNT_ENVELOPE')
    if configured:
        if configured not in accounts:
            raise ProbeError('CONFIGURED_ACCOUNT_NOT_ACCESSIBLE')
        return configured, len(accounts)
    if len(accounts) != 1:
        raise ProbeError('ACCOUNT_SELECTION_REQUIRED' if accounts else 'NO_ACCESSIBLE_ACCOUNT')
    return accounts[0], 1


def inspect(environ=None, get=None):
    env = os.environ if environ is None else environ
    result = {'token_present': bool(env.get('CLOUDFLARE_API_TOKEN')),
              'authenticated_account_read': False, 'workers_read_verified': False,
              'billing_read_verified': False, 'worker_write_permission_verified': False,
              'zero_charge_account_verified': False, 'gallery_restored': False,
              'resource_creations': 0, 'subscriptions_changed': 0,
              'uploaded_photos': 0, 'remote_original_SHA_readbacks': 0}
    token = env.get('CLOUDFLARE_API_TOKEN', '').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,512}', token):
        return {**result, 'state': 'TOKEN_MISSING_OR_INVALID_FORMAT'}
    phase = 'accounts'
    try:
        get = reader(token) if get is None else get
        account, count = account_for(get, env.get('CLOUDFLARE_ACCOUNT_ID', '').strip())
        result.update(authenticated_account_read=True, accessible_accounts=count,
                      account_selected_without_manual_ID=not bool(env.get('CLOUDFLARE_ACCOUNT_ID')))
        phase = 'workers'
        scripts = get('/accounts/' + account + '/workers/scripts').get('result')
        if not isinstance(scripts, list):
            raise ProbeError('INVALID_WORKERS_ENVELOPE')
        result['workers_read_verified'] = True
        phase = 'billing'
        subscriptions = get('/accounts/' + account + '/subscriptions')
        rows = subscriptions.get('result')
        if not isinstance(rows, list) or any(not isinstance(s, dict) for s in rows):
            raise ProbeError('INVALID_SUBSCRIPTION_ENVELOPE')
        result['billing_read_verified'] = True
        total = subscriptions.get('result_info', {}).get('total_count', len(rows))
        result['subscription_listing_complete'] = type(total) is int and total == len(rows)
        # Even an empty list is not proof of an account-wide zero-charge policy.
        result['subscriptions_reported'] = len(rows)
        result['nonzero_or_unknown_subscription_prices'] = sum(
            type(s.get('price')) not in (int, float) or s['price'] != 0 for s in rows)
        phase = 'workers_subdomain'
        try:
            subdomain = get('/accounts/' + account + '/workers/subdomain').get('result')
            result['workers_subdomain_exists'] = bool(isinstance(subdomain, dict) and subdomain.get('subdomain'))
        except ProbeError as error:
            result['workers_subdomain_read_http'] = error.status
            result['workers_subdomain_exists'] = False
        result['state'] = 'CLOUDFLARE_READ_ONLY_CONNECTION_VERIFIED'
    except ProbeError as error:
        result.update(state='CLOUDFLARE_CONNECTION_BLOCKED', phase=phase,
                      failure=error.phase, http_status=error.status)
    except Exception:
        # Never expose SDK/provider messages, account names, IDs or response bodies.
        result.update(state='CLOUDFLARE_CONNECTION_BLOCKED', phase=phase,
                      failure='UNEXPECTED_READ_ENVELOPE', http_status=0)
    return result


if __name__ == '__main__':
    observation = inspect()
    print('CLOUDFLARE_READ_ONLY_OBSERVATION', json.dumps(observation, sort_keys=True), flush=True)
    if observation['state'] != 'CLOUDFLARE_READ_ONLY_CONNECTION_VERIFIED':
        raise SystemExit(2)
