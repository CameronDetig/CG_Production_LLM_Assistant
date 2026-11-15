"""Regression checks for src/services/warmup.py (no external services needed).

Run from the repo root:  PYTHONPATH=backend python tests/backend/test_warmup.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'backend'))

from src.services import warmup  # noqa: E402


def _reset(steps):
    warmup._warm = False
    warmup._models_warm = False
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


def _stream(awake):
    original = warmup._ensure_database_awake
    warmup._ensure_database_awake = awake
    try:
        return list(warmup.warm_up_events())
    finally:
        warmup._ensure_database_awake = original


def test_stream_reports_server_then_progress_then_ready():
    calls = []
    _reset({"agent_stack": lambda: calls.append("models"), "database_pools": lambda: calls.append("pools")})

    events = _stream(lambda: calls.append("awake"))

    stages = [event["stage"] for event in events]
    assert stages[0] == "server_ready" and stages[-1] == "ready", stages
    assert set(stages[1:-1]) == {"warming"}, stages
    assert events[1]["message"] == "Waking the database and loading models"
    assert set(events[-1]["steps"]) == {"database", "models"}
    assert sorted(calls) == ["awake", "models", "pools"], calls


def test_stream_checks_the_database_again_on_a_warm_container():
    model_loads = []
    wakes = []
    _reset({"agent_stack": lambda: model_loads.append(1), "database_pools": lambda: None})

    _stream(lambda: wakes.append(1))
    second = _stream(lambda: wakes.append(1))

    # The database pauses by itself, so only the models are remembered as warm.
    assert len(model_loads) == 1 and len(wakes) == 2, (model_loads, wakes)
    assert second[-1]["steps"]["models"] == "warm"


def test_stream_reports_an_unreachable_database_without_raising():
    _reset({"agent_stack": lambda: None, "database_pools": lambda: None})

    def unreachable():
        raise RuntimeError("database still resuming")

    events = _stream(unreachable)

    assert events[-1]["stage"] == "partial", events[-1]
    assert events[-1]["steps"]["database"] == "failed"
    assert "database" in events[-1]["message"]


if __name__ == "__main__":
    test_runs_each_step_once_then_short_circuits()
    test_failed_step_is_reported_not_raised_and_retried()
    test_stream_reports_server_then_progress_then_ready()
    test_stream_checks_the_database_again_on_a_warm_container()
    test_stream_reports_an_unreachable_database_without_raising()
    print("warmup tests passed")
