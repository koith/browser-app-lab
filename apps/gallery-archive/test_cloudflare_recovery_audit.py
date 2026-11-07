import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from audit_cloudflare_recovery import Audit, inspect, policies_summary
from check_cloudflare_connection import ProbeError

ACCOUNT = 'a' * 32
TOKEN_ID = 'b' * 32
SECRET = 'NEVER_LOG_THIS_TOKEN'


class AuditChecks(unittest.TestCase):
    def test_403_does_not_imply_missing_scripts_write_or_request_a_permission_change(self):
        class Reads(Audit):
            def get(self, label, path):
                self.observations[label] = {'method': 'GET', 'http': 403, 'success': False, 'error_codes': [10000]}
                return {'id': ACCOUNT} if label == 'account' else None
        report = inspect(SECRET, get_accounts=lambda _: {'result': [{'id': ACCOUNT}]}, audit_factory=Reads)
        self.assertFalse(report['worker_write_permission_verified'])
        self.assertEqual(report['permission_change_required'], 'UNVERIFIED')
        self.assertEqual(report['scripts_count'], 'UNVERIFIED')
        self.assertFalse(report['own_policy_inspection_verified'])
        self.assertEqual(report['resource_creations'], 0)
        for private in (SECRET, ACCOUNT, TOKEN_ID):
            self.assertNotIn(private, json.dumps(report))

    def test_own_token_policies_are_scoped_to_the_verified_selected_account(self):
        details = {'policies': [
            {'effect': 'allow', 'resources': {'com.cloudflare.api.account.' + ACCOUNT: '*'},
             'permission_groups': [{'name': 'Workers Scripts Read'}, {'name': SECRET}]},
            {'effect': 'allow', 'resources': {'com.cloudflare.api.account.' + TOKEN_ID: '*'},
             'permission_groups': [{'name': 'Workers Scripts Write'}]}]}
        report = policies_summary(details, ACCOUNT)
        self.assertEqual(report['allow_permissions_on_selected_account'], ['Workers Scripts Read'])
        self.assertTrue(report['explicit_other_account_scope_present'])
        self.assertNotIn(SECRET, json.dumps(report))
        self.assertNotIn(ACCOUNT, json.dumps(report))

    def test_configured_account_mismatch_fails_before_resource_requests(self):
        with self.assertRaises(ProbeError):
            inspect(SECRET, TOKEN_ID, get_accounts=lambda _: {'result': [{'id': ACCOUNT}]})

    def test_audit_cannot_write_or_read_arbitrary_tokens_or_provider_hosts(self):
        audit = Audit(SECRET, ACCOUNT)
        for label, path in [('own_token_details', '/user/tokens/' + TOKEN_ID),
                            ('scripts', 'https://untrusted.invalid'),
                            ('subscriptions', '/accounts/' + ACCOUNT + '/subscriptions')]:
            with self.assertRaises(ValueError): audit.get(label, path)

    def test_provider_errors_are_redacted_to_numeric_codes_only(self):
        audit = Audit(SECRET, ACCOUNT)
        raw = json.dumps({'errors': [{'code': 10000, 'message': SECRET + ACCOUNT}]}).encode()
        error = HTTPError('https://private.invalid/' + SECRET, 403, SECRET, {}, io.BytesIO(raw))
        with patch.object(audit.opener, 'open', side_effect=error):
            self.assertIsNone(audit.get('scripts', '/accounts/' + ACCOUNT + '/workers/scripts'))
        self.assertEqual(audit.observations['scripts']['error_codes'], [10000])
        for private in (SECRET, ACCOUNT): self.assertNotIn(private, json.dumps(audit.observations))

    def test_existing_resources_are_counted_without_exposing_names_or_domains(self):
        class Reads(Audit):
            def get(self, label, path):
                self.observations[label] = {'method': 'GET', 'http': 200, 'success': True, 'error_codes': []}
                return {'account': {'id': ACCOUNT}, 'user_token_verify': {'id': TOKEN_ID, 'status': 'active'},
                    'own_token_details': {'policies': []}, 'user': {'email_verified': True, 'email': SECRET},
                    'scripts': [{'id': 'gallery-archive-free'}, {'id': SECRET}],
                    'services': [], 'domains': [{'hostname': SECRET}], 'pages_projects': [],
                    'subdomain': {'subdomain': SECRET}, 'worker_settings': {}, 'entitlements': []}[label]
        report = inspect(SECRET, get_accounts=lambda _: {'result': [{'id': ACCOUNT}]}, audit_factory=Reads)
        self.assertEqual(report['scripts_count'], 2)
        self.assertTrue(report['existing_gallery_worker'])
        self.assertTrue(report['existing_workers_subdomain'])
        self.assertTrue(report['own_token_active_verified'])
        self.assertNotIn(SECRET, json.dumps(report))


if __name__ == '__main__': unittest.main()
