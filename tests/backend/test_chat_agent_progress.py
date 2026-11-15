"""The chat agent reports each step through on_event while the graph runs.

Run from the repo root:  python -m unittest discover -s tests/backend -p 'test_*.py'
Needs langgraph and pyyaml. Bedrock, the database and the embedding models are stubbed.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

STUBBED_MODULES = ('src.services.database', 'src.services.bedrock_client', 'src.services.embeddings')

with patch.dict(sys.modules, {name: MagicMock() for name in STUBBED_MODULES}):
    sys.modules.pop('src.core.chat_agent', None)
    from src.core import chat_agent  # noqa: E402


def router(is_database_query=True, needs_text_embedding=False):
    return json.dumps({
        'is_database_query': is_database_query,
        'enhanced_query': 'Count the images in Big Buck Bunny',
        'intent': {'search_type': 'count', 'needs_text_embedding': needs_text_embedding,
                   'needs_visual_embedding': False},
        'direct_answer': 'Hello!',
    })


def evaluation(satisfactory, feedback=''):
    return json.dumps({'satisfactory': satisfactory, 'feedback': feedback, 'summary': 'There are 205 images.'})


class FakeBedrock:
    """Answers each agent prompt from a script keyed by the node that sent it."""

    def __init__(self, router_reply, sql_replies=(), eval_replies=()):
        self.router_reply = router_reply
        self.sql_replies = list(sql_replies)
        self.eval_replies = list(eval_replies)

    def __call__(self, prompt, **kwargs):
        if 'routing it to the appropriate node' in prompt:
            return self.router_reply
        if 'PostgreSQL query generator' in prompt:
            return self.sql_replies.pop(0)
        if 'Evaluate if the SQL query results' in prompt:
            return self.eval_replies.pop(0)
        raise AssertionError(f'unexpected prompt: {prompt[:80]}')


class ChatAgentProgressTest(unittest.TestCase):
    def run_agent(self, bedrock, rows=({'count': 205},)):
        events = []
        with patch.object(chat_agent, 'invoke_bedrock', side_effect=bedrock), \
                patch.object(chat_agent, 'execute_generated_sql', return_value=list(rows)), \
                patch.object(chat_agent, 'generate_text_embedding', return_value=[0.1, 0.2]):
            result = chat_agent.run_chat_agent(
                'how many images in big buck bunny?', on_event=lambda e, d: events.append((e, d))
            )
        return result, events

    def test_database_query_reports_each_step_in_order(self):
        result, events = self.run_agent(FakeBedrock(
            router(), ['{"sql": "SELECT COUNT(*) FROM images"}'], [evaluation(True)],
        ))
        self.assertEqual([name for name, _ in events], [
            'enhanced_query', 'status', 'sql_query', 'status', 'query_results', 'status',
        ])
        self.assertEqual(events[0][1], {'query': 'Count the images in Big Buck Bunny'})
        self.assertEqual([d['stage'] for name, d in events if name == 'status'],
                         ['generating_sql', 'running_sql', 'evaluating'])
        self.assertEqual(events[2][1], {'query': 'SELECT COUNT(*) FROM images', 'attempt': 1})
        self.assertEqual(events[4][1], {'count': 1, 'attempt': 1, 'results': [{'count': 205}]})
        self.assertEqual(result['final_answer'], 'There are 205 images.')

    def test_similarity_search_reports_embedding_stage(self):
        _, events = self.run_agent(FakeBedrock(
            router(needs_text_embedding=True), ['{"sql": "SELECT 1"}'], [evaluation(True)],
        ))
        self.assertEqual(events[1], ('status', {'stage': 'embedding', 'message': 'Preparing similarity search'}))

    def test_retry_reports_feedback_and_second_attempt(self):
        _, events = self.run_agent(FakeBedrock(
            router(),
            ['{"sql": "SELECT 1"}', '{"sql": "SELECT 2"}'],
            [evaluation(False, 'Count only images'), evaluation(True)],
        ))
        names = [name for name, _ in events]
        self.assertEqual(names, [
            'enhanced_query',
            'status', 'sql_query', 'status', 'query_results', 'status', 'retry_feedback',
            'status', 'sql_query', 'status', 'query_results', 'status',
        ])
        self.assertEqual(events[6][1], {'feedback': 'Count only images', 'attempt': 1})
        self.assertEqual(events[7][1]['message'], 'Revising the database query (attempt 2)')
        self.assertEqual(events[8][1], {'query': 'SELECT 2', 'attempt': 2})
        self.assertEqual(events[10][1]['attempt'], 2)

    def test_general_question_reports_no_database_steps(self):
        result, events = self.run_agent(FakeBedrock(router(is_database_query=False)))
        self.assertEqual(events, [])
        self.assertEqual(result['final_answer'], 'Hello!')

    def test_without_on_event_the_result_is_unchanged(self):
        with patch.object(chat_agent, 'invoke_bedrock', side_effect=FakeBedrock(
                router(), ['{"sql": "SELECT 1"}'], [evaluation(True)])), \
                patch.object(chat_agent, 'execute_generated_sql', return_value=[{'count': 205}]):
            result = chat_agent.run_chat_agent('q')
        self.assertEqual(result['sql_query'], 'SELECT 1')
        self.assertEqual(result['all_sql_queries'][0]['result_count'], 1)

    def test_nodes_can_still_be_called_outside_a_graph_run(self):
        chat_agent._emit('status', {'stage': 'x', 'message': 'y'})  # must not raise


if __name__ == '__main__':
    unittest.main()
