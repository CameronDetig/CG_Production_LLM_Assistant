"""Routing and error-handling checks for lambda_function.lambda_handler with heavy dependencies stubbed.

CI installs only boto3, python-jose and requests, so the database, model and agent modules that
lambda_function imports at load time are replaced with mocks for the duration of this module.

Run from the repo root:  PYTHONPATH=backend python -m unittest tests.backend.test_lambda_handler
                    or:  PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_*.py'
"""

import importlib
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# The code under test lives in backend/; make it importable without needing PYTHONPATH.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

STUBBED_MODULES = [
    'src.services.database',
    'src.services.conversations',
    'src.core.chat_agent',
    'src.services.bedrock_client',
]

_patcher = None
lambda_function = None


def setUpModule():
    global _patcher, lambda_function
    os.environ['SKIP_DB_INIT'] = '1'
    _patcher = patch.dict(sys.modules, {name: MagicMock() for name in STUBBED_MODULES})
    _patcher.start()
    sys.modules.pop('lambda_function', None)
    lambda_function = importlib.import_module('lambda_function')


def tearDownModule():
    sys.modules.pop('lambda_function', None)
    _patcher.stop()
    os.environ.pop('SKIP_DB_INIT', None)


def api_gateway_event(method, path, headers=None):
    return {'httpMethod': method, 'path': path, 'headers': headers or {}}


def function_url_event(method, path, headers=None):
    return {'requestContext': {'http': {'method': method}}, 'rawPath': path, 'headers': headers or {}}


class LambdaHandlerRoutingTest(unittest.TestCase):
    def body(self, response):
        return json.loads(response['body'])

    def test_health_returns_ok(self):
        response = lambda_function.lambda_handler(api_gateway_event('GET', '/health'), None)
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(self.body(response), {'status': 'ok'})

    def test_api_prefix_is_stripped_for_cloudfront_routes(self):
        response = lambda_function.lambda_handler(api_gateway_event('GET', '/api/health'), None)
        self.assertEqual(response['statusCode'], 200)

    def test_function_url_event_shape_is_supported(self):
        response = lambda_function.lambda_handler(function_url_event('GET', '/api/health'), None)
        self.assertEqual(response['statusCode'], 200)

    def test_unknown_route_returns_404(self):
        response = lambda_function.lambda_handler(api_gateway_event('GET', '/nope'), None)
        self.assertEqual(response['statusCode'], 404)
        self.assertIn('/nope', self.body(response)['error'])

    def test_wrong_method_on_known_path_returns_404(self):
        response = lambda_function.lambda_handler(api_gateway_event('POST', '/health'), None)
        self.assertEqual(response['statusCode'], 404)

    def test_conversations_require_a_token(self):
        response = lambda_function.lambda_handler(api_gateway_event('GET', '/api/conversations'), None)
        self.assertEqual(response['statusCode'], 401)
        self.assertEqual(self.body(response), {'error': 'Authentication required'})

    def test_unexpected_handler_error_returns_500_json(self):
        with patch.object(lambda_function, 'handle_list_conversations', side_effect=RuntimeError('boom')):
            response = lambda_function.lambda_handler(api_gateway_event('GET', '/conversations'), None)
        self.assertEqual(response['statusCode'], 500)
        self.assertEqual(self.body(response)['error'], 'Internal server error')

    def test_responses_carry_cors_headers(self):
        response = lambda_function.lambda_handler(api_gateway_event('GET', '/health'), None)
        self.assertIn('Access-Control-Allow-Origin', response['headers'])


if __name__ == '__main__':
    unittest.main()
