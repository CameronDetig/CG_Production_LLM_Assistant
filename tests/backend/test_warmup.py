"""Regression checks for src/services/warmup.py (no external services needed).

Run from the repo root:  PYTHONPATH=backend python tests/backend/test_warmup.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

from src.services import warmup  # noqa: E402


def _reset(steps):
    warmup._warm = False
    warmup._STEPS.clear()
    warmup._STEPS.update(steps)


def test_runs_each_step_once_then_short_circuits():
    calls = []
    _reset({"a": lambda: calls.append("a"), "b": lambda: calls.append("b")})

    first = warmup.warm_up()
    second = warmup.warm_up()

    assert first["status"] == "warm" and set(first["steps"]) == {"a", "b"}
    assert second == {"status": "warm"}
    assert calls == ["a", "b"], calls


def test_failed_step_is_reported_not_raised_and_retried():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("database blip")

    ok_calls = []
    _reset({"flaky": flaky, "ok": lambda: ok_calls.append(1)})

    first = warmup.warm_up()
    assert first["status"] == "partial" and first["steps"]["flaky"] == "failed"

    second = warmup.warm_up()
    assert second["status"] == "warm", second
    assert attempts["n"] == 2


if __name__ == "__main__":
    test_runs_each_step_once_then_short_circuits()
    test_failed_step_is_reported_not_raised_and_retried()
    print("warmup tests passed")
