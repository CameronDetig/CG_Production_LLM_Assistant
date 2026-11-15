"""Checks for how the backend borrows database connections (mocked, no database).

The metadata database closes sessions that sit idle so it can pause, so a pooled
connection may be dead by the time a warm container uses it again.

Run from the repo root:  python -m unittest discover -s tests/backend -p 'test_*.py'
Needs psycopg2 and sqlglot.
"""

import os
import sys
import unittest
from unittest import mock

# The code under test lives in backend/; make `src` importable without needing PYTHONPATH.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

import psycopg2  # noqa: E402

from src.services import database  # noqa: E402


def _connection(*, closed=0, probe_error=None):
    conn = mock.MagicMock()
    conn.closed = closed
    cursor = conn.cursor.return_value.__enter__.return_value
    if probe_error is not None:
        cursor.execute.side_effect = probe_error
    return conn


def _pool(*connections):
    fake = mock.MagicMock()
    fake.maxconn = 5
    fake.getconn.side_effect = list(connections)
    return fake


class CheckoutTests(unittest.TestCase):
    def test_live_connection_is_returned_with_no_open_transaction(self):
        live = _connection()
        fake = _pool(live)

        self.assertIs(database._checkout(fake), live)
        live.rollback.assert_called_once_with()
        fake.putconn.assert_not_called()

    def test_connection_closed_by_the_server_is_replaced(self):
        # psycopg2 still reports the connection open; only the probe reveals it is gone.
        stale = _connection(probe_error=psycopg2.OperationalError("terminating connection due to idle-session timeout"))
        live = _connection()
        fake = _pool(stale, live)

        self.assertIs(database._checkout(fake), live)
        fake.putconn.assert_called_once_with(stale, close=True)

    def test_connection_already_marked_closed_is_replaced_without_a_probe(self):
        closed = _connection(closed=1)
        live = _connection()
        fake = _pool(closed, live)

        self.assertIs(database._checkout(fake), live)
        closed.cursor.assert_not_called()
        fake.putconn.assert_called_once_with(closed, close=True)

    def test_gives_up_when_no_connection_survives(self):
        dead = [_connection(closed=1) for _ in range(6)]
        fake = _pool(*dead)

        with self.assertRaises(psycopg2.OperationalError):
            database._checkout(fake)
        self.assertEqual(fake.putconn.call_count, 6)


class PoolSettingsTests(unittest.TestCase):
    def test_pools_let_the_database_pause_and_wait_for_it_to_resume(self):
        with mock.patch.object(database.psycopg2.pool, 'SimpleConnectionPool') as create:
            database._create_pool('reader', 'secret')

        settings = create.call_args.kwargs
        self.assertEqual(settings['user'], 'reader')
        self.assertEqual(settings['options'], '-c idle_session_timeout=300000')
        # Resuming a paused database takes about 15 seconds.
        self.assertGreaterEqual(settings['connect_timeout'], 20)

    def test_readonly_requests_borrow_through_the_stale_check(self):
        live = _connection()
        with mock.patch.object(database, 'readonly_connection_pool', _pool(live)):
            self.assertIs(database.get_readonly_connection(), live)
        live.cursor.assert_called_once()


if __name__ == '__main__':
    unittest.main()
