import json
import unittest
from datetime import datetime
from decimal import Decimal

from src.services.streaming import dynamo_safe, final_answer_prompt, json_safe, sse


class StreamingHelpersTest(unittest.TestCase):
    def test_sse_serializes_aws_values(self):
        event = sse("query_results", {"count": Decimal("2"), "at": datetime(2026, 1, 2, 3, 4, 5)})
        self.assertTrue(event.startswith("event: query_results\ndata: "))
        payload = json.loads(event.split("data: ", 1)[1])
        self.assertEqual(payload, {"count": 2, "at": "2026-01-02T03:04:05"})
        self.assertTrue(event.endswith("\n\n"))

    def test_dynamo_safe_converts_nested_floats(self):
        self.assertEqual(dynamo_safe({"rows": [{"score": 0.25}]}), {"rows": [{"score": Decimal("0.25")} ]})

    def test_json_safe_preserves_nested_shapes(self):
        self.assertEqual(json_safe([Decimal("1.5"), {"value": Decimal("3")}]), [1.5, {"value": 3}])

    def test_final_prompt_marks_candidate_as_verified(self):
        prompt = final_answer_prompt("How many?", "There are 12.")
        self.assertIn("How many?", prompt)
        self.assertIn("There are 12.", prompt)
        self.assertIn("using only", prompt)


if __name__ == "__main__":
    unittest.main()
