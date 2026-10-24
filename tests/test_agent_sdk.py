"""Exercise actual SDK dispatch/capture without any network or model service."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from agents import Model
from agents.items import ModelResponse
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

import cosmon_agent.agent as runner
import cosmon_agent.engine as engine_module
from cosmon_agent.__main__ import part_name


class InertClient:
    """No request methods: unexpected network use fails immediately."""

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class ScriptedModel(Model):
    """Test actions exercise the runtime; this is never a submitted agent run."""

    def __init__(self, actions, final):
        self.actions = actions
        self.final = final
        self.calls = 0

    async def get_response(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= len(self.actions):
            name, arguments = self.actions[self.calls - 1]
            item = ResponseFunctionToolCall(
                type="function_call", id=f"fc{self.calls}", call_id=f"call{self.calls}",
                name=name, arguments=arguments,
            )
        else:
            text = self.final()
            item = ResponseOutputMessage(
                type="message", id=f"msg{self.calls}", role="assistant", status="completed",
                content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
            )
        return ModelResponse(output=[item], usage=Usage(), response_id=f"offline-{self.calls}")

    async def stream_response(self, *args, **kwargs):
        raise AssertionError("The tested runner must use non-streaming calls")
        yield


class FinalClaimTests(unittest.TestCase):
    def setUp(self):
        self.claim = {
            "status": "repaired", "initial_sf": 1.428, "final_sf": 2.25,
            "changed_parameter": {"name": "thickness_mm", "from": 3.0, "to": 5.0},
            "artifact_id": "a0001",
        }

    def test_unrounded_matching_claim(self):
        self.assertEqual(runner.validate_final_claim(json.dumps(self.claim), self.claim), (True, "verified"))

    def test_claim_mismatch_is_not_corrected(self):
        wrong = {**self.claim, "final_sf": 9.0}
        self.assertEqual(runner.validate_final_claim(json.dumps(wrong), self.claim), (False, "final_claim_mismatch"))

    def test_oversized_boolean_and_nonfinite_final_numbers_are_rejected(self):
        for field in ("initial_sf", "final_sf", "from", "to"):
            for value in (10**400, True, float("inf"), float("nan")):
                claim = json.loads(json.dumps(self.claim))
                target = claim["changed_parameter"] if field in ("from", "to") else claim
                target[field] = value
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.assertFalse(runner.validate_final_claim(json.dumps(claim), self.claim)[0])

    def test_duplicate_or_extra_keys_rejected(self):
        self.assertFalse(runner.validate_final_claim('{"status":"repaired","status":"already_safe"}', self.claim)[0])
        self.assertFalse(runner.validate_final_claim(json.dumps({**self.claim, "extra": 1}), self.claim)[0])

    def test_tool_arguments_remain_strict(self):
        invalid = (
            "{", "[]", '{"name":"thickness_mm","value":true}',
            '{"name":"thickness_mm","value":NaN}',
            '{"name":"thickness_mm","value":4,"value":5}',
            json.dumps({"name": "thickness_mm", "value": 10**400}),
        )
        for text in invalid:
            with self.subTest(text=text[:70]):
                self.assertIn("__invalid_arguments__", runner.parse_arguments("set_parameter", text))


class ConfigurationTests(unittest.TestCase):
    def test_third_and_fourth_parts_and_parameters_are_configured(self):
        policy = runner.load_policy(runner.DEFAULT_POLICY)
        policy["exploration_ranges"] = {
            "fixture_plate_v3": {"width_mm": [3, 12]},
            "fixture_rib_v4": {"height_mm": [2, 20]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy))
            self.assertEqual(runner.load_policy(path), policy)
        self.assertEqual(part_name("fixture_plate_v3"), "fixture_plate_v3")
        self.assertEqual(part_name("fixture_rib_v4"), "fixture_rib_v4")
        self.assertEqual(runner.parse_arguments("set_parameter", '{"name":"width_mm","value":7}'), {"name": "width_mm", "value": 7})

    def test_invalid_ranges_and_path_like_names_rejected(self):
        for supplied in ({}, {"new_part": {}}, {"new_part": {"width_mm": [3, 2]}}, {"new_part": {"width_mm": [2, float("inf")]}}):
            with self.subTest(ranges=supplied), tempfile.TemporaryDirectory() as directory:
                policy = runner.load_policy(runner.DEFAULT_POLICY)
                policy["exploration_ranges"] = supplied
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(policy))
                with self.assertRaises(ValueError):
                    runner.load_policy(path)
        import argparse
        for name in ("../bracket_v3", "parts/new_part", ""):
            with self.subTest(name=name), self.assertRaises(argparse.ArgumentTypeError):
                part_name(name)


class SDKCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="partlab-sdk-test-")
        self.test_dir = Path(self.temporary.name)
        self.policy = runner.load_policy(runner.DEFAULT_POLICY) | {"evidence_kind": "preparation_check"}
        self.config = {
            "OPENROUTER_API_KEY": "offline-no-network",
            "OPENROUTER_MODEL": "offline-scripted-test",
            "OPENROUTER_REASONING_EFFORT": "medium",
        }
        self.engine = None
        original = json.loads((runner.ROOT / "parts/bracket_v3.json").read_text())
        self.load = json.dumps(original["default_load"])

    async def asyncTearDown(self):
        self.temporary.cleanup()

    def final_claim(self):
        outcome = self.engine.outcome(None)
        return json.dumps({key: outcome[key] for key in ("status", "initial_sf", "final_sf", "changed_parameter", "artifact_id")})

    async def run_script(self, model, *, part="bracket_v3", root=runner.ROOT, output_name="trace"):
        test = self

        class CapturedEngine(engine_module.Engine):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                test.engine = self

        with patch.object(engine_module, "Engine", CapturedEngine), patch.object(runner, "AsyncOpenAI", InertClient), patch.object(runner, "OpenAIChatCompletionsModel", return_value=model):
            outcome = await runner.run_agent(
                part, self.test_dir / output_name, self.config, self.policy, root=root,
                publish_dir=self.test_dir / "published",
            )
        events = [json.loads(line) for line in (self.test_dir / output_name / "events.jsonl").read_text().splitlines()]
        return outcome, events

    async def test_real_sdk_captures_malformed_proposal_recovers_and_saves(self):
        candidate = self.policy["exploration_ranges"]["bracket_v3"]["thickness_mm"][1]
        actions = [
            ("open_part", "{"), ("open_part", "{}"), ("mesh", "{}"),
            ("apply_load", self.load), ("solve", "{}"), ("open_part", "{}"),
            ("set_parameter", json.dumps({"name": "thickness_mm", "value": candidate})),
            ("mesh", "{}"), ("apply_load", self.load), ("solve", "{}"), ("save_part", "{}"),
        ]
        outcome, events = await self.run_script(ScriptedModel(actions, self.final_claim))
        self.assertEqual(outcome["status"], "repaired", outcome)
        self.assertTrue(outcome["final_claim_check"]["valid"])
        self.assertEqual(outcome["model_calls"], len(actions) + 1)
        proposals = [event for event in events if event["kind"] == "tool_proposed"]
        self.assertEqual(len(proposals), len(actions))
        self.assertEqual(proposals[0]["data"]["arguments"], "{")
        first_call = proposals[0]["call_id"]
        self.assertTrue(any(e["kind"] == "guard_decision" and e["call_id"] == first_call and e["data"]["decision"] == "block" for e in events))
        self.assertFalse(any(e["kind"] == "cli_requested" and e["call_id"] == first_call for e in events))
        self.assertTrue((self.test_dir / "published/bracket_v3.json").exists())
        self.assertTrue((self.test_dir / "trace/completion.json").exists())
        requests = list((self.test_dir / "trace/raw/model").glob("*.request.json"))
        self.assertEqual(len(requests), len(actions) + 1)
        for path in requests:
            # Check actual next model inputs, including serialized tool results.
            self.assertNotIn('\\"log\\":', path.read_text())
        unsupported = {"model_run_completed", "runner_failed", "final_claim_checked"}
        self.assertFalse({e["kind"] for e in events} & unsupported)

    async def test_oversized_final_claim_keeps_raw_evidence_and_completion(self):
        text = json.dumps({"status": "no_repair_found", "initial_sf": 10**400, "final_sf": None, "changed_parameter": None, "artifact_id": None})
        outcome, events = await self.run_script(ScriptedModel([], lambda: text))
        self.assertEqual(outcome["status"], "execution_failure")
        self.assertEqual(outcome["reason_code"], "final_output_invalid_schema")
        self.assertEqual((self.test_dir / "trace/raw/model/final.txt").read_text(), text)
        self.assertTrue((self.test_dir / "trace/completion.json").exists())

    async def test_model_failure_is_safe_and_recorded_without_fabricated_response(self):
        class FailingModel(ScriptedModel):
            async def get_response(self, *args, **kwargs):
                raise RuntimeError("secret-exception-sentinel")

        outcome, events = await self.run_script(FailingModel([], lambda: ""))
        self.assertEqual(outcome["status"], "execution_failure")
        self.assertTrue(any(e["kind"] == "model_failed" for e in events))
        self.assertFalse(any(e["kind"] == "model_returned" for e in events))
        self.assertIsNone(outcome["final_message_ref"])
        for path in (self.test_dir / "trace").rglob("*"):
            if path.is_file():
                self.assertNotIn(b"secret-exception-sentinel", path.read_bytes())

    async def test_tool_budget_stops_before_another_model_request_including_rejections(self):
        self.policy["max_tool_calls"] = 2
        model = ScriptedModel([("open_part", "{")] * 5, self.final_claim)
        outcome, events = await self.run_script(model)
        self.assertEqual(outcome["status"], "execution_failure")
        self.assertEqual(outcome["reason_code"], "tool_call_budget")
        self.assertEqual(model.calls, 2)
        self.assertEqual(self.engine.tool_calls, 2)
        self.assertIsNone(outcome["final_message_ref"])
        self.assertEqual(outcome["runner_failure"]["completed_tool_calls"], 2)
        self.assertEqual(outcome["runner_failure"]["unexecuted_tool_call_ids"], [])
        for kind in ("model_requested", "model_returned", "tool_proposed", "tool_returned"):
            self.assertEqual(sum(e["kind"] == kind for e in events), 2, kind)
        self.assertFalse(any(e["kind"] == "model_failed" for e in events))
        # The only CLI call initializes the isolated session; neither malformed
        # request nor any later scripted request reaches the CLI.
        self.assertEqual(sum(e["kind"] == "cli_requested" for e in events), 1)
        self.assertTrue((self.test_dir / "trace/completion.json").exists())

    async def test_tool_budget_caps_multiple_calls_from_one_model_response(self):
        self.policy["max_tool_calls"] = 1

        class MultiCallModel(ScriptedModel):
            async def get_response(self, *args, **kwargs):
                self.calls += 1
                output = [ResponseFunctionToolCall(
                    type="function_call", id=f"fc{i}", call_id=f"call{i}",
                    name=name, arguments="{}",
                ) for i, name in enumerate(("open_part", "mesh", "get_parameters"), start=1)]
                return ModelResponse(output=output, usage=Usage(), response_id="offline-batch")

        model = MultiCallModel([], self.final_claim)
        outcome, events = await self.run_script(model)
        self.assertEqual(outcome["status"], "execution_failure")
        self.assertEqual(outcome["reason_code"], "tool_call_budget")
        self.assertEqual(model.calls, 1)
        self.assertEqual(self.engine.tool_calls, 1)
        self.assertEqual(sum(e["kind"] == "tool_proposed" for e in events), 3)
        self.assertEqual(sum(e["kind"] == "tool_returned" for e in events), 1)
        self.assertEqual(outcome["runner_failure"]["unexecuted_tool_call_ids"], ["call2", "call3"])
        self.assertFalse(any(e["kind"] == "cli_requested" and e["call_id"] in {"call2", "call3"} for e in events))
        self.assertEqual(sum(e["kind"] == "model_requested" for e in events), 1)
        self.assertEqual(sum(e["kind"] == "model_returned" for e in events), 1)
        self.assertFalse(any(e["kind"] == "model_failed" for e in events))
        self.assertTrue((self.test_dir / "trace/completion.json").exists())

    async def test_new_named_parts_run_and_engine_still_rejects_unknown_parameters(self):
        fixture_root = self.test_dir / "fixture-root"
        (fixture_root / "parts").mkdir(parents=True)
        shutil.copy2(runner.ROOT / "partlab", fixture_root / "partlab")
        shutil.copy2(runner.ROOT / "TASK.md", fixture_root / "TASK.md")
        source = json.loads((runner.ROOT / "parts/bracket_v3.json").read_text())
        names = ("fixture_plate_v3", "fixture_rib_v4")
        ranges = self.policy["exploration_ranges"]["bracket_v3"]
        self.policy["exploration_ranges"] = {name: ranges for name in names}
        for name in names:
            # Explicitly synthetic renamed fixtures, never submission artifacts.
            (fixture_root / "parts" / f"{name}.json").write_text(json.dumps({**source, "name": name}))
            actions = [("open_part", "{}"), ("mesh", "{}"), ("apply_load", self.load), ("solve", "{}"),
                       ("set_parameter", '{"name":"unknown_width_mm","value":7}')]
            outcome, events = await self.run_script(ScriptedModel(actions, self.final_claim), part=name, root=fixture_root, output_name=name)
            self.assertEqual(outcome["status"], "no_repair_found", outcome)
            self.assertIsNotNone(outcome["initial_sf"])
            proposed = [e for e in events if e["kind"] == "tool_proposed"][-1]
            self.assertEqual(proposed["data"]["arguments"], actions[-1][1])
            call_id = proposed["call_id"]
            self.assertTrue(any(e["kind"] == "guard_decision" and e["call_id"] == call_id and e["data"]["decision"] == "block" for e in events))
            self.assertFalse(any(e["kind"] == "cli_requested" and e["call_id"] == call_id for e in events))


if __name__ == "__main__":
    unittest.main()
