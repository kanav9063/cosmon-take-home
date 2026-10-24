"""A nonnull tool-call link must identify its captured causal boundary."""
import json
from pathlib import Path
import tempfile
import unittest

from bundle_factory import encoded, refresh_inventory, scenario_bundle, sha256
from evaluate import load_cases
from trace_adapter import load_run


class CaptureLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = scenario_bundle(Path(self.temp.name) / "trace")
        self.case = load_cases()[0]["bracket_v3"]
        self.events = [json.loads(line) for line in
                       (self.path / "events.jsonl").read_bytes().splitlines()]
        self.run_id = self.events[0]["run_id"]
        raw = b'{"ok":true}\n'
        relative = "raw/tools/captured-boundary.result"
        (self.path / relative).parent.mkdir(parents=True, exist_ok=True)
        (self.path / relative).write_bytes(raw)
        self.tool_result = {"path": relative, "sha256": sha256(raw), "bytes": len(raw)}

    def event(self, kind, data, call_id="captured-call"):
        return {"event_id": "resequence", "seq": 0, "kind": kind,
                "run_id": self.run_id, "actor": "runner", "trial_id": None,
                "call_id": call_id, "cli_id": None, "data": data}

    def save_load(self):
        for seq, event in enumerate(self.events, 1):
            event["event_id"], event["seq"] = f"e{seq:04d}", seq
        (self.path / "events.jsonl").write_bytes(b"".join(
            encoded(e).replace(b"\n", b"") + b"\n" for e in self.events))
        refresh_inventory(self.path)
        return load_run(self.path, self.case)

    def assert_broken_link(self):
        run = self.save_load()
        self.assertFalse(run.execution_complete)
        self.assertIn("CALL_LINK_INVALID", [issue.code for issue in run.issues])

    def command_events(self, call_id="captured-call"):
        cli_id = self.events[0]["cli_id"]
        command = [e for e in self.events if e["cli_id"] == cli_id]
        for event in command:
            event["call_id"] = call_id
        return command

    def proposal(self):
        return self.event("tool_proposed", {"name": "reset", "arguments": "{}"})

    def returned(self):
        return self.event("tool_returned", {"result_ref": self.tool_result})

    def test_nonnull_cli_call_requires_captured_tool_proposal(self):
        self.command_events("orphan-call")
        self.assert_broken_link()

    def test_guard_call_requires_captured_tool_proposal(self):
        self.events.insert(-1, self.event("guard_decision", {"decision": "block"}, "orphan-call"))
        self.assert_broken_link()

    def test_guard_cannot_omit_call_id(self):
        self.events.insert(-1, self.event("guard_decision", {"decision": "block"}, None))
        self.assert_broken_link()

    def test_tool_cannot_return_before_linked_cli_finishes(self):
        command = self.command_events()
        self.events.insert(0, self.proposal())
        self.events.insert(self.events.index(command[-1]), self.returned())
        self.assert_broken_link()

    def test_linked_cli_cannot_precede_its_proposal(self):
        command = self.command_events()
        index = self.events.index(command[-1]) + 1
        self.events[index:index] = [self.proposal(), self.returned()]
        self.assert_broken_link()

    def test_null_harness_calls_remain_valid(self):
        run = self.save_load()
        self.assertTrue(run.execution_complete, run.issues)

    def test_linked_tool_with_enclosed_cli_remains_valid(self):
        command = self.command_events()
        self.events.insert(0, self.proposal())
        self.events.insert(self.events.index(command[-1]) + 1, self.returned())
        run = self.save_load()
        self.assertTrue(run.execution_complete, run.issues)


if __name__ == "__main__":
    unittest.main()
