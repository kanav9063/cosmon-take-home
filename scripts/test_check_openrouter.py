"""Offline regression checks for the live provider smoke test."""

import json
import unittest

from agents.usage import Usage
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails

from check_openrouter import serialize_usage


class UsageSerializationTest(unittest.TestCase):
    def test_nested_usage_survives_json_report(self):
        usage = Usage()
        usage.add(Usage(
            requests=1, input_tokens=100, output_tokens=20, total_tokens=120,
            input_tokens_details=InputTokensDetails(cached_tokens=10, cache_write_tokens=3),
            output_tokens_details=OutputTokensDetails(reasoning_tokens=5),
        ))

        report = json.loads(json.dumps({"usage": serialize_usage(usage)}, allow_nan=False))
        result = report["usage"]
        self.assertEqual(result["total_tokens"], 120)
        self.assertEqual(result["input_tokens_details"], {"cached_tokens": 10, "cache_write_tokens": 3})
        self.assertEqual(result["output_tokens_details"], {"reasoning_tokens": 5})
        self.assertEqual(len(result["request_usage_entries"]), 1)
        entry = result["request_usage_entries"][0]
        self.assertEqual(entry["input_tokens_details"], result["input_tokens_details"])
        self.assertEqual(entry["output_tokens_details"], result["output_tokens_details"])


if __name__ == "__main__":
    unittest.main()
