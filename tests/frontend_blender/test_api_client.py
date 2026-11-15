"""Mocked-HTTP checks for the Blender add-on API client (no Blender or network needed).

Run from the repo root:  python -m unittest discover -s tests/frontend_blender -p 'test_*.py'
"""

import hashlib
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

# Import the module directly: the add-on package __init__ imports bpy, which only exists inside Blender.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend_blender'))

from api_client import APIClient  # noqa: E402
from utils import format_progress, waiting_for_warmup_text, warmup_status_text  # noqa: E402


def fake_response(body, status=200):
    response = MagicMock()
    response.read.return_value = json.dumps(body).encode('utf-8')
    response.status = status
    response.__enter__.return_value = response
    return response


def fake_stream(lines):
    """A streamed SSE response: iterating it yields encoded lines."""
    response = MagicMock()
    response.__iter__.return_value = iter([(line + '\n').encode('utf-8') for line in lines])
    response.__enter__.return_value = response
    return response


class APIClientTest(unittest.TestCase):
    def test_authenticate_posts_credentials_to_api_auth(self):
        client = APIClient('https://example.test/')
        with patch('api_client.urllib.request.urlopen', return_value=fake_response({'token': 'abc'})) as urlopen:
            result = client.authenticate('user@example.com', 'secret')

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.test/api/auth')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data), {'email': 'user@example.com', 'password': 'secret'})
        self.assertTrue(result.success)
        self.assertEqual(result.data, {'token': 'abc'})
        self.assertEqual(result.status_code, 200)

    def test_bearer_token_is_sent_once_set(self):
        client = APIClient('https://example.test')
        client.set_token('jwt-value')
        with patch('api_client.urllib.request.urlopen', return_value=fake_response({'conversations': []})) as urlopen:
            client.get_conversations()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer jwt-value')

    def test_token_is_also_sent_in_x_cognito_token(self):
        # CloudFront overwrites Authorization when it signs the request to Lambda.
        client = APIClient('https://example.test')
        client.set_token('jwt-value')
        with patch('api_client.urllib.request.urlopen', return_value=fake_response({})) as urlopen:
            client.get_conversations()

        # urllib stores header names with only the first letter capitalized.
        self.assertEqual(urlopen.call_args.args[0].get_header('X-cognito-token'), 'jwt-value')

    def test_body_hash_is_sent_for_cloudfront_signing(self):
        client = APIClient('https://example.test')
        with patch('api_client.urllib.request.urlopen', return_value=fake_response({})) as urlopen:
            client.get_conversations()
            client.authenticate('user@example.com', 'secret')
        with patch('api_client.urllib.request.urlopen', return_value=fake_stream([])) as stream_urlopen:
            client.chat_stream('find rigs')

        get_request, post_request = (call.args[0] for call in urlopen.call_args_list)
        chat_request = stream_urlopen.call_args.args[0]
        self.assertEqual(get_request.get_header('X-amz-content-sha256'), hashlib.sha256(b'').hexdigest())
        for request in (post_request, chat_request):
            self.assertEqual(
                request.get_header('X-amz-content-sha256'), hashlib.sha256(request.data).hexdigest()
            )

    def test_no_authorization_header_without_a_token(self):
        client = APIClient('https://example.test')
        with patch('api_client.urllib.request.urlopen', return_value=fake_response({})) as urlopen:
            client.get_conversations()

        self.assertIsNone(urlopen.call_args.args[0].get_header('Authorization'))

    def test_http_error_surfaces_the_server_message(self):
        client = APIClient('https://example.test')
        error = urllib.error.HTTPError(
            'https://example.test/api/auth', 401, 'Unauthorized', {}, io.BytesIO(b'{"error": "Invalid credentials"}')
        )
        with patch('api_client.urllib.request.urlopen', side_effect=error):
            result = client.authenticate('user@example.com', 'wrong')

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.error, 'Invalid credentials')

    def test_get_filters_requests_api_filters(self):
        client = APIClient('https://example.test')
        body = {'shows': [{'name': 'spring', 'file_count': 3}], 'file_types': []}
        with patch('api_client.urllib.request.urlopen', return_value=fake_response(body)) as urlopen:
            result = client.get_filters()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.test/api/filters')
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(result.data, body)

    def test_chat_sends_only_the_filters_that_are_set(self):
        client = APIClient('https://example.test')
        with patch('api_client.urllib.request.urlopen', return_value=fake_stream([])) as urlopen:
            client.chat_stream('find rigs', filters={'shows': ['spring'], 'file_types': []})
        self.assertEqual(
            json.loads(urlopen.call_args.args[0].data),
            {'query': 'find rigs', 'filters': {'shows': ['spring']}},
        )

    def test_chat_omits_filters_when_nothing_is_selected(self):
        client = APIClient('https://example.test')
        with patch('api_client.urllib.request.urlopen', return_value=fake_stream([])) as urlopen:
            client.chat_stream('find rigs', filters={'shows': [], 'file_types': []})
            client.chat_stream('find rigs')
        for call in urlopen.call_args_list:
            self.assertEqual(json.loads(call.args[0].data), {'query': 'find rigs'})

    def test_chat_text_reports_the_filters_the_server_applied(self):
        client = APIClient('https://example.test')
        lines = [
            'event: filters',
            'data: {"shows": ["spring"], "file_types": ["image", "blend"]}',
            '',
            'event: answer_chunk',
            'data: {"text": "Found 2."}',
        ]
        with patch('api_client.urllib.request.urlopen', return_value=fake_stream(lines)):
            result = client.chat_stream('find rigs', filters={'shows': ['spring']})

        self.assertTrue(result.success)
        self.assertIn('[Searching only]: shows: spring; types: image, blend', result.data['text'])
        self.assertTrue(result.data['text'].endswith('Found 2.'))

    def test_chat_reports_every_event_as_it_arrives(self):
        client = APIClient('https://example.test')
        lines = [
            'event: status',
            'data: {"stage": "generating_sql", "message": "Writing a database query"}',
            '',
            ': heartbeat',
            '',
            'event: sql_query',
            'data: {"query": "SELECT 1", "attempt": 1}',
        ]
        seen = []
        with patch('api_client.urllib.request.urlopen', return_value=fake_stream(lines)):
            client.chat_stream('q', on_event=lambda event, data: seen.append((event, data)))

        self.assertEqual(seen, [
            ('status', {'stage': 'generating_sql', 'message': 'Writing a database query'}),
            ('sql_query', {'query': 'SELECT 1', 'attempt': 1}),
        ])

    def test_progress_text_shows_steps_and_current_stage(self):
        events = [
            {'event': 'status', 'data': {'message': 'Analyzing your request'}},
            {'event': 'enhanced_query', 'data': {'query': 'Count images'}},
            {'event': 'status', 'data': {'message': 'Running the query'}},
        ]
        text = format_progress(events)
        self.assertIn('[Enhanced Query]: Count images', text)
        self.assertTrue(text.endswith('Running the query...'))
        self.assertNotIn('Analyzing', text)

    def test_progress_text_drops_the_stage_once_the_answer_streams(self):
        events = [
            {'event': 'status', 'data': {'message': 'Writing the answer'}},
            {'event': 'answer_start', 'data': {}},
            {'event': 'answer_chunk', 'data': {'text': 'There are 205.'}},
        ]
        self.assertTrue(format_progress(events).endswith('There are 205.'))
        self.assertEqual(format_progress([]), 'Thinking...')

    def test_connection_failure_is_reported_not_raised(self):
        client = APIClient('https://example.test')
        with patch('api_client.urllib.request.urlopen', side_effect=urllib.error.URLError('refused')):
            result = client.get_conversations()

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 0)
        self.assertIn('Connection error', result.error)


class WarmupTest(unittest.TestCase):
    def test_warmup_stream_posts_signed_empty_body_and_reports_each_status(self):
        client = APIClient('https://example.test/', token='tok')
        lines = [
            'event: status', 'data: {"stage": "server_ready", "message": "Server is up"}', '',
            ': heartbeat', '',
            'event: status', 'data: {"stage": "warming", "message": "Waking the database"}', '',
            'event: status', 'data: {"stage": "ready", "message": "Ready"}', '',
        ]
        seen = []
        with patch('urllib.request.urlopen', return_value=fake_stream(lines)) as urlopen:
            result = client.warmup_stream(on_event=lambda event, data: seen.append((event, data['stage'])))

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.test/api/warmup/stream')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('X-amz-content-sha256'), hashlib.sha256(b'').hexdigest())
        self.assertTrue(result.success)
        self.assertEqual(seen, [('status', 'server_ready'), ('status', 'warming'), ('status', 'ready')])

    def test_warmup_failure_is_returned_not_raised(self):
        client = APIClient('https://example.test/', token='tok')
        with patch('urllib.request.urlopen', side_effect=OSError('offline')):
            result = client.warmup_stream()
        self.assertFalse(result.success)

    def test_status_line_text(self):
        self.assertEqual(warmup_status_text('warming', 'Waking the database'), 'Waking the database')
        self.assertEqual(warmup_status_text('ready', 'Ready'), 'Ready')
        self.assertEqual(warmup_status_text('warming', ''), 'Warming up')

    def test_question_sent_during_warmup_says_so_in_the_chat(self):
        text = waiting_for_warmup_text('Waking the database')
        self.assertIn('still starting up (waking the database)', text)
        self.assertIn('will be sent as soon as it is ready', text)
        self.assertIn('starting the server', waiting_for_warmup_text(''))


if __name__ == '__main__':
    unittest.main()
