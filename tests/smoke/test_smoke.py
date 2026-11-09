"""Unit tests for the smoke script's own check logic (no network).

Run from the repo root:  python -m unittest discover -s tests/smoke -p 'test_*.py'
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import smoke  # noqa: E402

SHELL = b'<!doctype html><div id="root"></div>'
CONFIG = json.dumps({'cognitoDomain': 'x.auth.us-east-1.amazoncognito.com', 'cognitoClientId': 'abc'}).encode()
HEALTH = json.dumps({'status': 'ok'}).encode()


def healthy_site(**overrides):
    routes = {
        '/': (200, SHELL),
        '/config.json': (200, CONFIG),
        '/api/health': (200, HEALTH),
        '/api/conversations': (401, b'{"message":"Unauthorized"}'),
    }
    routes.update(overrides)

    def get(url):
        return routes[url.split('example.test', 1)[1] or '/']

    return get


def run(get, attempts=1):
    return smoke.run_checks('https://example.test/', get=get, attempts=attempts, delay=0, sleep=lambda _: None, log=lambda _: None)


class SmokeChecksTest(unittest.TestCase):
    def failures(self, results):
        return {name: detail for name, passed, detail in results if not passed}

    def test_healthy_site_passes_every_check(self):
        results = run(healthy_site())
        self.assertEqual(len(results), 4)
        self.assertEqual(self.failures(results), {})

    def test_placeholder_config_fails(self):
        placeholder = json.dumps({'cognitoDomain': '', 'cognitoClientId': ''}).encode()
        failures = self.failures(run(healthy_site(**{'/config.json': (200, placeholder)})))
        self.assertIn('cognitoDomain, cognitoClientId', failures['runtime config'])

    def test_non_app_html_fails(self):
        failures = self.failures(run(healthy_site(**{'/': (200, b'<html>error page</html>')})))
        self.assertIn('app shell', failures)

    def test_unhealthy_api_fails(self):
        for response in [(502, b''), (200, b'{"status":"degraded"}'), (200, b'not json')]:
            with self.subTest(response=response):
                self.assertIn('api health', self.failures(run(healthy_site(**{'/api/health': response}))))

    def test_protected_route_must_be_401_not_open_or_erroring(self):
        for status in (200, 403, 500):
            with self.subTest(status=status):
                failures = self.failures(run(healthy_site(**{'/api/conversations': (status, b'')})))
                self.assertIn('authorizer rejects anonymous', failures)

    def test_transient_failure_is_retried(self):
        calls = {'n': 0}
        site = healthy_site()

        def flaky(url):
            if url.endswith('/api/health'):
                calls['n'] += 1
                if calls['n'] < 3:
                    raise OSError('connection reset')
            return site(url)

        self.assertEqual(self.failures(run(flaky, attempts=4)), {})
        self.assertEqual(calls['n'], 3)

    def test_persistent_failure_stops_after_the_attempt_limit(self):
        calls = {'n': 0}

        def down(url):
            calls['n'] += 1
            raise OSError('unreachable')

        results = run(down, attempts=3)
        self.assertEqual(len(self.failures(results)), 4)
        self.assertEqual(calls['n'], 12)

    def test_main_rejects_missing_or_insecure_url(self):
        self.assertEqual(smoke.main(['smoke.py']), 2)
        self.assertEqual(smoke.main(['smoke.py', 'http://example.test']), 2)


if __name__ == '__main__':
    unittest.main()
