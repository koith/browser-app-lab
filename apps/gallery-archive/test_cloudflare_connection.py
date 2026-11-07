import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
from check_cloudflare_connection import inspect, account_for, reader, ProbeError

TOKEN = 'dummy_token_never_a_real_credential_1234567890'
A, B = 'a' * 32, 'b' * 32


def known(path):
    if path.startswith('/accounts?'):
        return {'success': True, 'result': [{'id': A, 'name': 'PRIVATE ACCOUNT NAME'}]}
    if path.endswith('/workers/subdomain'):
        return {'success': True, 'result': {'subdomain': 'PRIVATE SUBDOMAIN'}}
    return {'success': True, 'result': []}


class CloudflareConnection(unittest.TestCase):
    def test_missing_token_never_calls_provider(self):
        def denied(_): raise AssertionError('must not call')
        self.assertEqual(inspect({}, denied)['state'], 'TOKEN_MISSING_OR_INVALID_FORMAT')

    def test_single_scoped_account_needs_no_manual_id_and_report_has_no_secret(self):
        calls = []
        def get(path): calls.append(path); return known(path)
        report = inspect({'CLOUDFLARE_API_TOKEN': TOKEN}, get)
        self.assertEqual(report['state'], 'CLOUDFLARE_READ_ONLY_CONNECTION_VERIFIED')
        self.assertEqual(len(calls), 4)
        self.assertTrue(report['billing_read_verified'])
        self.assertTrue(report['account_selected_without_manual_ID'])
        self.assertFalse(report['zero_charge_account_verified'])
        self.assertFalse(report['worker_write_permission_verified'])
        for private in (TOKEN, A, 'PRIVATE ACCOUNT NAME', 'PRIVATE SUBDOMAIN'):
            self.assertNotIn(private, json.dumps(report))

    def test_multiple_accounts_cannot_be_guessed(self):
        def get(_): return {'result': [{'id': A}, {'id': B}]}
        with self.assertRaisesRegex(ProbeError, 'ACCOUNT_SELECTION_REQUIRED'):
            account_for(get)
        self.assertEqual(account_for(get, B), (B, 2))
        with self.assertRaises(ProbeError): account_for(get, 'c' * 32)

    def test_paginated_accounts_do_not_silently_pick_first_page(self):
        first = [{'id': format(i, '032x')} for i in range(50)]
        def get(path):
            return {'result': first if path.endswith('=1') else [{'id': A}],
                    'result_info': {'total_count': 51}}
        self.assertEqual(account_for(get, A), (A, 51))
        with self.assertRaises(ProbeError): account_for(get)

    def test_http_rejection_is_not_absence_or_free_account(self):
        for status in (401, 403, 429, 503):
            def denied(_): raise ProbeError('HTTP_READ', status)
            r = inspect({'CLOUDFLARE_API_TOKEN': TOKEN}, denied)
            self.assertEqual(r['http_status'], status)
            self.assertFalse(r['authenticated_account_read'])
            self.assertFalse(r['zero_charge_account_verified'])

    def test_provider_errors_and_redirects_cannot_leak_token(self):
        with patch('check_cloudflare_connection.build_opener') as build:
            error = HTTPError('https://private.example/' + TOKEN, 403, TOKEN, {}, io.BytesIO(TOKEN.encode()))
            build.return_value.open.side_effect = error
            report = inspect({'CLOUDFLARE_API_TOKEN': TOKEN})
            self.assertNotIn(TOKEN, json.dumps(report))
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(request.host, 'api.cloudflare.com')
        with self.assertRaises(ProbeError): reader(TOKEN)('/accounts/' + A + '/subscriptions/create')

    def test_existing_paid_or_unknown_prices_are_not_zero_charge(self):
        def get(path):
            if path.endswith('/subscriptions'):
                return {'result': [{'price': 5}, {'rate_plan': {'public_name': 'Free'}}]}
            return known(path)
        r = inspect({'CLOUDFLARE_API_TOKEN': TOKEN}, get)
        self.assertEqual(r['nonzero_or_unknown_subscription_prices'], 2)
        self.assertFalse(r['zero_charge_account_verified'])
        self.assertEqual(r['resource_creations'], 0)


if __name__ == '__main__': unittest.main()
