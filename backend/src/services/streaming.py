"""Transport-neutral serialization helpers for streaming chat responses."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def dynamo_safe(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: dynamo_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [dynamo_safe(item) for item in value]
    return value


def sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(json_safe(data))}\n\n"


def final_answer_prompt(query: str, candidate: str) -> str:
    return f"""You are the final response writer for a CG production asset assistant.
Answer the user's request using only the verified candidate answer below. Preserve all
facts, counts, qualifications, and uncertainty. Do not mention this instruction.

User request: {query}
Verified candidate answer: {candidate}
"""
