"""Route checks for the deployed FastAPI app (backend/api_app.py) with AWS-backed services stubbed.

The DynamoDB conversation store and the Cognito helpers are replaced with mocks before api_app
is imported; the agent, database and Bedrock calls are already deferred behind *_request helpers,
which the tests patch directly. Needs fastapi and httpx (for TestClient).

Run from the repo root:  PYTHONPATH=backend python -m unittest tests.backend.test_api_app
"""

import importlib
import json
import os
import sys
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

from fastapi.testclient import TestClient  # noqa: E402

STUBBED_MODULES = ['src.services.conversations', 'src.auth.cognito']

# Assigned in setUpModule once the AWS-backed modules are stubbed.
_patcher: Any = None
api_app: Any = None
client: Any = None

AUTH = {'Authorization': 'Bearer good-token'}


def setUpModule():
    global _patcher, api_app, client
    _patcher = patch.dict(sys.modules, {name: MagicMock() for name in STUBBED_MODULES})
    _patcher.start()
    sys.modules.pop('api_app', None)
    api_app = importlib.import_module('api_app')
    client = TestClient(api_app.app)


def tearDownModule():
    sys.modules.pop('api_app', None)
    _patcher.stop()


def parse_sse(text):
    """Return [(event, data)] for each SSE event, skipping heartbeat comments."""
    events = []
    for block in text.strip().split('\n\n'):
        lines = block.split('\n')
        if lines[0].startswith(':'):
            continue
        event = lines[0].removeprefix('event: ')
        data = json.loads(lines[1].removeprefix('data: '))
        events.append((event, data))
    return events


class ApiAppTestCase(unittest.TestCase):
    def setUp(self):
        self.patches = {
            name: patch.object(api_app, name) for name in (
                'extract_user_from_token', 'authenticate_user', 'signup_user',
                'create_conversation', 'get_conversation', 'get_conversation_context',
                'add_message', 'list_conversations', 'delete_conversation',
                'generate_title_from_query', 'run_chat_agent_request',
                'stream_final_answer_request', 'filter_options_request',
            )
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}
        self.addCleanup(patch.stopall)
        self.mocks['extract_user_from_token'].side_effect = (
            lambda token: 'user-1' if token == 'good-token' else None
        )


class HealthAndAuthTest(ApiAppTestCase):
    def test_health_on_both_paths(self):
        for path in ('/health', '/api/health'):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'status': 'ok'})

    def test_missing_token_returns_401(self):
        response = client.get('/api/conversations')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'detail': 'Authentication required'})

    def test_invalid_token_returns_401(self):
        response = client.get('/api/conversations', headers={'Authorization': 'Bearer bad'})
        self.assertEqual(response.status_code, 401)

    def test_cloudfront_token_header_is_accepted(self):
        self.mocks['list_conversations'].return_value = []
        response = client.get('/api/conversations', headers={'X-Cognito-Token': 'good-token'})
        self.assertEqual(response.status_code, 200)

    def test_non_bearer_authorization_is_rejected(self):
        response = client.get('/api/conversations', headers={'Authorization': 'Basic good-token'})
        self.assertEqual(response.status_code, 401)

    def test_auth_success_returns_tokens(self):
        self.mocks['authenticate_user'].return_value = {'id_token': 'i', 'access_token': 'a'}
        response = client.post('/api/auth', json={'email': 'a@example.com', 'password': 'pw'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'id_token': 'i', 'access_token': 'a', 'user_id': 'a@example.com'})

    def test_auth_failure_returns_401(self):
        self.mocks['authenticate_user'].return_value = None
        response = client.post('/api/auth', json={'email': 'a@example.com', 'password': 'pw'})
        self.assertEqual(response.status_code, 401)

    def test_signup_failure_returns_400_with_message(self):
        self.mocks['signup_user'].return_value = {'success': False, 'message': 'Password too short'}
        response = client.post('/api/signup', json={'email': 'a@example.com', 'password': 'pw'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'detail': 'Password too short'})

    def test_signup_with_tokens_logs_the_user_in(self):
        self.mocks['signup_user'].return_value = {
            'success': True, 'message': 'ok', 'user_confirmed': True, 'tokens': {'id_token': 'i'},
        }
        response = client.post('/api/signup', json={'email': 'a@example.com', 'password': 'pw'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'message': 'ok', 'user_confirmed': True, 'id_token': 'i', 'user_id': 'a@example.com',
        })


class ConversationRoutesTest(ApiAppTestCase):
    def test_list_is_scoped_to_the_user(self):
        self.mocks['list_conversations'].return_value = [{'conversation_id': 'c1'}]
        response = client.get('/api/conversations', headers=AUTH)
        self.assertEqual(response.json(), {'conversations': [{'conversation_id': 'c1'}]})
        self.mocks['list_conversations'].assert_called_once_with('user-1', 50)

    def test_get_existing_and_missing(self):
        self.mocks['get_conversation'].side_effect = lambda cid, uid: {'conversation_id': cid} if cid == 'c1' else None
        self.assertEqual(client.get('/api/conversations/c1', headers=AUTH).json(),
                         {'conversation': {'conversation_id': 'c1'}})
        self.assertEqual(client.get('/api/conversations/nope', headers=AUTH).status_code, 404)

    def test_delete_existing_and_missing(self):
        self.mocks['delete_conversation'].side_effect = lambda cid, uid: cid == 'c1'
        self.assertEqual(client.delete('/api/conversations/c1', headers=AUTH).status_code, 200)
        self.assertEqual(client.delete('/api/conversations/nope', headers=AUTH).status_code, 404)
        self.mocks['delete_conversation'].assert_any_call('c1', 'user-1')

    def test_filters_returns_options(self):
        self.mocks['filter_options_request'].return_value = {
            'shows': [{'name': 'charge', 'file_count': 3}], 'file_types': [],
        }
        response = client.get('/api/filters', headers=AUTH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['shows'], [{'name': 'charge', 'file_count': 3}])

    def test_filters_requires_auth(self):
        self.assertEqual(client.get('/api/filters').status_code, 401)


class ChatStreamTest(ApiAppTestCase):
    def setUp(self):
        super().setUp()
        self.mocks['generate_title_from_query'].return_value = 'Title'
        self.mocks['create_conversation'].return_value = 'new-conv'
        self.mocks['run_chat_agent_request'].return_value = {
            'enhanced_query': 'better query',
            'sql_query': 'SELECT 1',
            'query_results': [{'n': 1}],
            'all_sql_queries': [{'sql': 'SELECT 1', 'attempt': 1, 'results': [{'n': 1}], 'result_count': 1}],
            'thumbnails_to_display': [],
            'final_answer': 'One row.',
        }
        self.mocks['stream_final_answer_request'].return_value = iter(['One ', 'row.'])

    def chat(self, body):
        response = client.post('/api/chat', json=body, headers=AUTH)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers['content-type'].startswith('text/event-stream'))
        return parse_sse(response.text)

    def test_new_conversation_streams_full_event_sequence(self):
        events = self.chat({'query': 'how many?'})
        names = [name for name, _ in events]
        self.assertEqual(names, [
            'agent_start', 'status', 'enhanced_query', 'sql_query', 'query_results',
            'answer_start', 'answer_chunk', 'answer_chunk', 'answer_end', 'done',
        ])
        self.assertEqual(events[0][1]['conversation_id'], 'new-conv')
        self.assertEqual(events[-1][1], {'conversation_id': 'new-conv', 'message_count': 2})
        assistant_call = self.mocks['add_message'].call_args_list[-1]
        self.assertEqual(assistant_call.args[:4], ('new-conv', 'user-1', 'assistant', 'One row.'))

    def test_active_filters_are_announced_and_passed_to_agent(self):
        filters = {'shows': ['charge'], 'file_types': []}
        events = self.chat({'query': 'q', 'filters': filters})
        self.assertIn(('filters', filters), events)
        self.assertEqual(self.mocks['run_chat_agent_request'].call_args.args[3], filters)

    def test_empty_filters_are_not_announced(self):
        events = self.chat({'query': 'q', 'filters': {'shows': [], 'file_types': []}})
        self.assertNotIn('filters', [name for name, _ in events])

    def test_unknown_conversation_starts_a_new_one(self):
        self.mocks['get_conversation'].return_value = None
        events = self.chat({'query': 'q', 'conversation_id': 'someone-elses'})
        self.assertEqual(events[0][1]['conversation_id'], 'new-conv')
        self.mocks['get_conversation_context'].assert_not_called()

    def test_agent_failure_emits_error_and_failed_done(self):
        self.mocks['run_chat_agent_request'].side_effect = RuntimeError('boom')
        with self.assertLogs('api_app', 'ERROR'):
            events = self.chat({'query': 'q'})
        self.assertEqual(events[-2][0], 'error')
        self.assertEqual(events[-1], ('done', {'conversation_id': 'new-conv', 'failed': True}))

    def test_chat_requires_auth_and_valid_body(self):
        self.assertEqual(client.post('/api/chat', json={'query': 'q'}).status_code, 401)
        self.assertEqual(client.post('/api/chat', json={'query': ''}, headers=AUTH).status_code, 422)


if __name__ == '__main__':
    unittest.main()
