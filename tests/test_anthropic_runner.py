"""Native Anthropic ToolRunner regression using mock HTTP and the real CLI."""

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx2

try:
    from cosmon_agent import anthropic_runner as runner
except ModuleNotFoundError as error:
    if error.name != "anthropic":
        raise
    runner = None


@unittest.skipIf(runner is None, "Install requirements-anthropic.txt for the optional native harness")
class NativeRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_tool_runner_preserves_capture_and_blocks_manufacturing_violation(self):
        policy = runner.load_policy(runner.DEFAULT_POLICY)
        policy["evidence_kind"] = "synthetic_fixture"
        model = "anthropic/claude-sonnet-5.5"
        actions = [
            ("open_part", {}),
            ("mesh", {}),
            ("apply_load", {"face_id": "face_mating", "force_N": 8000, "direction": "-Z"}),
            ("solve", {}),
            ("open_part", {}),
            ("set_parameter", {"name": "thickness_mm", "value": 5.5}),
        ]
        final = json.dumps({"status": "no_repair_found", "initial_sf": 0.212, "final_sf": 0.212,
                            "changed_parameter": None, "artifact_id": None})
        requests, responses = [], []

        def handler(request):
            self.assertEqual("https://openrouter.ai/api/v1/messages", str(request.url))
            index = len(requests)
            requests.append(request.content)
            self.assertEqual(model, json.loads(request.content)["model"])
            if index < len(actions):
                name, args = actions[index]
                content = [{"type": "tool_use", "id": f"tool{index + 1}", "name": name, "input": args}]
                stop = "tool_use"
            else:
                self.assertEqual(len(actions), index, "Unexpected request after final response")
                content, stop = [{"type": "text", "text": final}], "end_turn"
            response = httpx2.Response(200, json={
                "id": f"message-{index + 1}", "type": "message", "role": "assistant", "model": model,
                "content": content, "stop_reason": stop, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }, request=request)
            responses.append(response.content)
            return response

        native_client = httpx2.AsyncClient

        def client_factory(**kwargs):
            return native_client(transport=httpx2.MockTransport(handler), **kwargs)

        with tempfile.TemporaryDirectory(prefix="anthropic-runner-check-") as directory:
            base = Path(directory)
            # Patch only the runner's module binding; preserve the actual client
            # type seen by Anthropic and preserve both native HTTP event hooks.
            with patch.object(runner, "httpx2", SimpleNamespace(AsyncClient=client_factory)):
                outcome = await runner.run_anthropic_agent(
                    "flange_v1", base / "trace", {"OPENROUTER_API_KEY": "offline-test-only", "OPENROUTER_MODEL": model},
                    policy, publish_dir=base / "outputs",
                )
            self.assertEqual("no_repair_found", outcome["status"], outcome)
            self.assertTrue(outcome["final_claim_check"]["valid"], outcome)
            self.assertEqual(7, len(requests))
            trace = base / "trace"
            manifest = json.loads((trace / "manifest.json").read_bytes())
            self.assertEqual("synthetic_fixture", manifest["evidence_kind"])
            events = [json.loads(line) for line in (trace / "events.jsonl").read_bytes().splitlines()]
            requested = [e for e in events if e["kind"] == "model_requested"]
            returned = [e for e in events if e["kind"] == "model_returned"]
            self.assertEqual(len(requests), len(requested))
            self.assertEqual(len(responses), len(returned))
            for event, expected in zip(requested, requests):
                self.assertEqual(expected, (trace / event["data"]["request_ref"]["path"]).read_bytes())
            for event, expected in zip(returned, responses):
                self.assertEqual(expected, (trace / event["data"]["response_ref"]["path"]).read_bytes())
            self.assertTrue(any(e["kind"] == "guard_decision" and e["call_id"] == "tool6"
                                and e["data"].get("reason_code") == "manufacturing.constraint" for e in events))
            self.assertFalse(any(e["kind"] == "cli_requested" and e["call_id"] == "tool6" for e in events))
            final_request = json.loads(requests[-1])
            tool_returns = [block for message in final_request["messages"] if isinstance(message.get("content"), list)
                            for block in message["content"] if block.get("type") == "tool_result"]
            self.assertEqual(6, len(tool_returns))
            self.assertEqual(final, (trace / "raw/model/final.txt").read_text())
            completion = json.loads((trace / "completion.json").read_bytes())
            self.assertEqual(len(events), completion["event_count"])
            for name, ref in completion["files"].items():
                payload = (trace / name).read_bytes()
                self.assertEqual(len(payload), ref["bytes"])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), ref["sha256"])
            self.assertFalse((base / "outputs/flange_v1.json").exists())


if __name__ == "__main__":
    unittest.main()
