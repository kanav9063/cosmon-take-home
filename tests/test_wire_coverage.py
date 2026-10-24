"""Raw-wire adversarial controls corresponding to the original coverage matrix."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from bundle_factory import encoded, refresh_inventory, scenario_bundle, sha256
from eval_state import reconstruct
from evaluate import evaluate_one, load_cases
from trace_adapter import load_run


class WireCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = scenario_bundle(self.root / "run")
        self.case = load_cases()[0]["bracket_v3"]

    def events(self):
        return [json.loads(line) for line in (self.path / "events.jsonl").read_bytes().splitlines()]

    def write_events(self, events, *, resequence=True):
        if resequence:
            for seq, event in enumerate(events, 1):
                event["seq"] = seq
                event["event_id"] = f"e{seq:04d}"
        (self.path / "events.jsonl").write_bytes(b"".join(encoded(event).replace(b"\n", b"") + b"\n"
                                                        for event in events))
        refresh_inventory(self.path)

    def replace_stdout(self, cli_id, raw):
        events = self.events()
        event = next(e for e in events if e["kind"] == "cli_finished" and e["cli_id"] == cli_id)
        reference = event["data"]["stdout_ref"]
        (self.path / reference["path"]).write_bytes(raw)
        event["data"]["stdout_ref"] = {"path": reference["path"], "sha256": sha256(raw), "bytes": len(raw)}
        self.write_events(events)

    def load(self):
        return load_run(self.path, self.case)

    def test_malformed_json_tail_preserves_known_prefix_and_reports_incomplete(self):
        with (self.path / "events.jsonl").open("ab") as stream:
            stream.write(b'{"event_id":"unfinished"')
        refresh_inventory(self.path, status="interrupted")
        run = self.load()
        self.assertIn("TRACE_PARSE_ERROR", [i.code for i in run.issues])
        self.assertFalse(run.execution_complete)
        self.assertIsNotNone(reconstruct(run, self.case).baseline)

    def test_missing_completion_never_certifies_capture(self):
        (self.path / "completion.json").unlink()
        run = self.load()
        self.assertFalse(run.complete)
        self.assertFalse(run.execution_complete)
        self.assertIn("TRACE_INCOMPLETE", [i.code for i in run.issues])

    def test_missing_terminal_cli_result_retains_unknown_attempt(self):
        events = self.events()
        cli_id = next(e["cli_id"] for e in events if e["kind"] == "cli_requested"
                      and e["data"]["argv"][1] == "set-parameter")
        self.write_events([e for e in events if not (e["kind"] == "cli_finished" and e["cli_id"] == cli_id)])
        run = self.load()
        self.assertIn("CALL_RESULT_MISSING", [i.code for i in run.issues])
        self.assertFalse(run.execution_complete)
        action = next(a for a in run.actions if a.cli_id == cli_id)
        self.assertIsNone(action.success)
        self.assertIsNone(reconstruct(run, self.case).states[cli_id].parameters)

    def test_terminal_result_without_request_is_not_admitted_as_execution(self):
        events = self.events()
        cli_id = next(e["cli_id"] for e in events if e["kind"] == "cli_requested"
                      and e["data"]["argv"][1] == "set-parameter")
        self.write_events([e for e in events if not (e["kind"] == "cli_requested" and e["cli_id"] == cli_id)])
        run = self.load()
        self.assertIn("EXECUTION_AMBIGUOUS", [i.code for i in run.issues])
        self.assertNotIn(cli_id, [a.cli_id for a in run.actions])
        self.assertFalse(run.execution_complete)

    def test_duplicate_conflicting_terminal_results_are_rejected(self):
        events = self.events()
        finish = next(e for e in events if e["kind"] == "cli_finished")
        duplicate = deepcopy(finish)
        duplicate["data"]["exit_code"] = 1
        events.insert(events.index(finish) + 1, duplicate)
        self.write_events(events)
        run = self.load()
        self.assertIn("EXECUTION_AMBIGUOUS", [i.code for i in run.issues])
        self.assertFalse(run.execution_complete)

    def test_overlapping_mutating_attempts_do_not_get_a_favorable_order(self):
        events = self.events()
        mesh = next(e["cli_id"] for e in events if e["kind"] == "cli_requested"
                    and e["data"]["argv"][1] == "mesh")
        load = next(e["cli_id"] for e in events if e["kind"] == "cli_requested"
                    and e["data"]["argv"][1] == "apply-load")
        end = next(e for e in events if e["kind"] == "cli_finished" and e["cli_id"] == mesh)
        events.remove(end)
        load_end = next(e for e in events if e["kind"] == "cli_finished" and e["cli_id"] == load)
        events.insert(events.index(load_end) + 1, end)
        self.write_events(events)
        run = self.load()
        self.assertIn("EXECUTION_AMBIGUOUS", [i.code for i in run.issues])
        self.assertTrue(all(a.uncertain_order for a in run.actions if a.cli_id in {mesh, load}))
        self.assertIsNone(reconstruct(run, self.case).baseline)

    def test_exit_envelope_contradiction_cannot_certify_transition(self):
        events = self.events()
        cli_id = next(e["cli_id"] for e in events if e["kind"] == "cli_requested"
                      and e["data"]["argv"][1] == "set-parameter")
        next(e for e in events if e["kind"] == "cli_finished" and e["cli_id"] == cli_id)["data"]["exit_code"] = 1
        self.write_events(events)
        run = self.load()
        self.assertIn("EVIDENCE_CONTRADICTION", [i.code for i in run.issues])
        self.assertIsNone(next(a for a in run.actions if a.cli_id == cli_id).success)
        self.assertIsNone(reconstruct(run, self.case).states[cli_id].parameters)

    def test_producer_parse_cannot_override_raw_cli_result(self):
        events = self.events()
        finish = next(e for e in events if e["kind"] == "cli_finished")
        finish["data"]["parsed_envelope"] = {"ok": False, "error": "invented"}
        self.write_events(events)
        run = self.load()
        self.assertIn("EVIDENCE_CONTRADICTION", [i.code for i in run.issues])
        self.assertTrue(next(a for a in run.actions if a.cli_id == finish["cli_id"]).success)

    def test_unsupported_schema_never_certifies_capture(self):
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        manifest["schema_version"] = "future/99"
        (self.path / "manifest.json").write_bytes(encoded(manifest))
        refresh_inventory(self.path)
        run = self.load()
        self.assertIn("UNSUPPORTED_EVIDENCE", [i.code for i in run.issues])
        self.assertFalse(run.profile_supported)
        self.assertFalse(run.execution_complete)
        self.assertIsNone(reconstruct(run, self.case).baseline)

    def test_unsupported_command_never_becomes_an_ignored_readonly_action(self):
        events = self.events()
        next(e for e in events if e["kind"] == "cli_requested")["data"]["argv"][1] = "unknown-mutate"
        self.write_events(events)
        run = self.load()
        self.assertIn("UNSUPPORTED_EVIDENCE", [i.code for i in run.issues])
        self.assertTrue(run.profile_supported)
        self.assertFalse(run.execution_complete)
        self.assertIsNone(reconstruct(run, self.case).baseline)

    def test_nonfinite_and_duplicate_key_raw_json_is_rejected(self):
        cli_id = next(e["cli_id"] for e in self.events() if e["kind"] == "cli_requested"
                      and e["data"]["argv"][1] == "set-parameter")
        for raw in (b'{"ok":true,"result":{"new_value":NaN}}',
                    b'{"ok":true,"result":{"new_value":Infinity}}',
                    b'{"ok":true,"ok":false,"result":{}}'):
            with self.subTest(raw=raw):
                self.replace_stdout(cli_id, raw)
                run = self.load()
                self.assertIn("TRACE_PARSE_ERROR", [i.code for i in run.issues])
                self.assertIsNone(next(a for a in run.actions if a.cli_id == cli_id).success)

    def test_boolean_and_unit_strings_do_not_become_numeric_safety_factors(self):
        events = self.events()
        cli_id = [e["cli_id"] for e in events if e["kind"] == "cli_requested"
                  and e["data"]["argv"][1] == "solve"][-1]
        finish = next(e for e in events if e["kind"] == "cli_finished" and e["cli_id"] == cli_id)
        original = json.loads((self.path / finish["data"]["stdout_ref"]["path"]).read_bytes())
        for value in (True, "2.4", "2.4 MPa"):
            with self.subTest(value=value):
                modified = deepcopy(original)
                modified["result"]["safety_factor"] = value
                self.replace_stdout(cli_id, encoded(modified))
                report = evaluate_one(self.path, self.case)
                analysis = next(c for c in report["checks"] if c["check_id"] == "analysis_validity"
                                and c["scope"] == "selected")
                self.assertEqual("unknown", analysis["status"])
                self.assertNotEqual("pass", report["summary"]["final_correctness"]["status"])

    def test_artifact_hash_mismatch_remains_an_integrity_failure(self):
        artifact = self.path / "artifacts/a0001.json"
        artifact.write_bytes(artifact.read_bytes() + b" ")
        # Deliberately preserve both the event digest and completion inventory.
        report = evaluate_one(self.path, self.case)
        self.assertIn("ARTIFACT_HASH_MISMATCH", [f["code"] for f in report["findings"]])
        self.assertEqual("fail", report["summary"]["capture_integrity"]["status"])

    def test_hash_valid_artifact_with_wrong_geometry_fails_content_check(self):
        events = self.events()
        event = next(e for e in events if e["kind"] == "artifact_saved")
        reference = event["data"]["artifact_ref"]
        content = json.loads((self.path / reference["path"]).read_bytes())
        content["parameters"]["thickness_mm"] = 9
        raw = encoded(content)
        (self.path / reference["path"]).write_bytes(raw)
        event["data"]["artifact_ref"] = {"path": reference["path"], "sha256": sha256(raw), "bytes": len(raw)}
        self.write_events(events)
        report = evaluate_one(self.path, self.case)
        self.assertIn("ARTIFACT_STATE_MISMATCH", [f["code"] for f in report["findings"]])

    def test_equivalent_platform_separators_preserve_logical_publication(self):
        events = self.events()
        publication = next(e for e in events if e["kind"] == "artifact_published")
        publication["data"]["path"] = "outputs\\bracket_v3.json"
        self.write_events(events)
        report = evaluate_one(self.path, self.case)
        self.assertEqual("pass", report["summary"]["delivery"]["status"])


if __name__ == "__main__":
    unittest.main()
