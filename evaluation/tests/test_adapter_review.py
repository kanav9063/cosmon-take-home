"""Independent regression cases for untrusted input at the adapter boundary."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from bundle_factory import Builder, encoded, refresh_inventory, scenario_bundle, sha256
from evaluate import evaluate_batch, evaluate_one, load_cases
from trace_adapter import load_run


class AdapterReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases, _ = load_cases()
        self.case = self.cases["bracket_v3"]
        self.path = scenario_bundle(self.root / "bundle")

    def edit_events(self, change):
        events = [json.loads(raw) for raw in (self.path / "events.jsonl").read_bytes().splitlines()]
        change(events)
        (self.path / "events.jsonl").write_bytes(b"".join(json.dumps(e).encode() + b"\n" for e in events))
        refresh_inventory(self.path)

    def edit_manifest(self, change):
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        change(manifest)
        (self.path / "manifest.json").write_bytes(encoded(manifest))
        refresh_inventory(self.path)

    def assertIncomplete(self):
        run = load_run(self.path, self.case)
        self.assertFalse(run.execution_complete)
        self.assertTrue(run.issues)
        return run

    def raw_ref(self, relative, value):
        raw = encoded(value)
        path = self.path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": relative, "bytes": len(raw), "sha256": sha256(raw)}

    def simulated_live(self):
        # Wire-profile tests only. These temporary synthetic bytes do not turn
        # checked-in fixtures into live-agent evidence or claim a provider call.
        def change(manifest):
            manifest["evidence_kind"] = "live_agent"
            manifest["capture"]["model_calls"] = True
            manifest["capture"]["description"] = "SIMULATED live-agent profile for an isolated unit test; no model execution."
        self.edit_manifest(change)

    def boundary_event(self, kind, data, *, model_call_id="m1", call_id=None):
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        return {"event_id": "temporary", "seq": 0, "kind": kind,
                "run_id": manifest["run_id"], "actor": "runner", "trial_id": None,
                "call_id": call_id, "cli_id": None, "model_call_id": model_call_id, "data": data}

    def test_simulated_live_profile_with_raw_boundaries_is_complete(self):
        self.simulated_live()
        request = self.raw_ref("raw/model/request.json", {"messages": [{"role": "user", "content": "Reset the session."}]})
        response = self.raw_ref("raw/model/response.json", {"tool_calls": [{"id": "provider-t1", "name": "reset", "arguments": "{}"}]})
        tool_result = self.raw_ref("raw/tools/result.txt", {"ok": True, "result": {"state_path": "/fixture/.partlab/state.json"}})
        prefix = [self.boundary_event("model_requested", {"request_ref": request}),
                  self.boundary_event("model_returned", {"response_ref": response}),
                  self.boundary_event("tool_proposed", {"name": "reset", "arguments": "{}"}, call_id="t1")]
        returned = self.boundary_event("tool_returned", {"result_ref": tool_result}, call_id="t1")
        def change(events):
            reset = events[:3]
            for event in reset:
                event["call_id"] = "t1"
            events[:] = prefix + reset + [returned] + events[3:]
            for seq, event in enumerate(events, 1):
                event.update(seq=seq, event_id=f"e{seq:04}")
        self.edit_events(change)
        run = load_run(self.path, self.case)
        self.assertTrue(run.execution_complete, run.issues)
        self.assertEqual(run.metrics["model_calls"], 1)
        self.assertEqual(run.actions[0].call_id, "t1")
        self.assertFalse(run.issues)

    def test_simulated_failed_model_capture_can_complete_without_tool(self):
        self.path = Builder(self.root / "failed-model", "simulated-model-failure").finish(
            "execution_failure", reason_code="MODEL_TRANSPORT_FAILURE", completion_status="failed")
        self.simulated_live()
        request = self.raw_ref("raw/model/request.json", {"messages": [{"role": "user", "content": "Start the task."}]})
        failure = self.raw_ref("raw/model/failure.json", {"error": "Simulated transport failure; no provider call occurred."})
        prefix = [self.boundary_event("model_requested", {"request_ref": request}),
                  self.boundary_event("model_failed", {"error_ref": failure, "reason_code": "TRANSPORT_FAILURE"})]
        def change(events):
            events[:0] = prefix
            for seq, event in enumerate(events, 1):
                event.update(seq=seq, event_id=f"e{seq:04}")
        self.edit_events(change)
        run = load_run(self.path, self.case)
        self.assertTrue(run.execution_complete, run.issues)
        self.assertFalse(run.actions)
        self.assertFalse(any(e.kind.startswith("tool_") for e in run.events))
        report = evaluate_one(self.path, self.case)
        self.assertEqual(report["declared_outcome"], "execution_failure")
        self.assertEqual(report["summary"]["reporting_accuracy"]["status"], "pass")

    def test_malformed_event_kind_yields_issue_not_exception(self):
        self.edit_events(lambda events: events[0].update(kind=[]))
        self.assertIncomplete()

    def test_malformed_artifact_solve_reference_yields_issue_not_exception(self):
        def change(events):
            data = next(e["data"] for e in events if e["kind"] == "artifact_saved")
            data.pop("solve_cli_id")
            data["solve_event_id"] = []
        self.edit_events(change)
        self.assertIncomplete()

    def test_malformed_artifact_path_yields_issue_not_exception(self):
        def change(events):
            data = next(e["data"] for e in events if e["kind"] == "artifact_saved")
            data["artifact_ref"]["path"] = []
        self.edit_events(change)
        self.assertIncomplete()

    def test_embedded_null_path_yields_issue_not_exception(self):
        def change(events):
            finish = next(e for e in events if e["kind"] == "cli_finished")
            finish["data"]["stdout_ref"]["path"] = "raw/\0"
        self.edit_events(change)
        self.assertIncomplete()

    def test_malformed_case_identity_not_certified(self):
        self.edit_manifest(lambda manifest: manifest.update(case=[]))
        self.assertIncomplete()

    def test_malformed_direct_artifact_solve_id_not_certified(self):
        def change(events):
            data = next(e["data"] for e in events if e["kind"] == "artifact_saved")
            data["solve_cli_id"] = []
        self.edit_events(change)
        self.assertIncomplete()

    def test_malformed_outcome_status_yields_report_not_exception(self):
        outcome = json.loads((self.path / "outcome.json").read_bytes())
        outcome["status"] = []
        raw = encoded(outcome)
        (self.path / "outcome.json").write_bytes(raw)
        def change(events):
            events[-1]["data"]["outcome_ref"] = {"path": "outcome.json",
                                                  "bytes": len(raw), "sha256": sha256(raw)}
        self.edit_events(change)
        report = evaluate_one(self.path, self.case)
        self.assertNotEqual(report["summary"]["reporting_accuracy"]["status"], "pass")

    def test_unknown_capture_profile_not_certified(self):
        self.edit_manifest(lambda m: m.update(capture_profile="unknown/99"))
        run = self.assertIncomplete()
        self.assertFalse(run.profile_supported)

    def test_manifest_context_reference_is_validated(self):
        self.edit_manifest(lambda m: m.update(task_ref={"path": "../../outside", "bytes": 0, "sha256": "0" * 64}))
        self.assertIncomplete()

    def test_empty_model_event_labels_do_not_prove_live_capture(self):
        self.edit_manifest(lambda m: m.update(evidence_kind="live_agent"))
        def change(events):
            end = events.pop()
            for name in ("model_requested", "model_returned", "tool_proposed", "tool_returned"):
                seq = len(events) + 1
                events.append({"event_id": f"e{seq:04}", "seq": seq, "kind": name,
                               "run_id": end["run_id"], "actor": "runner", "trial_id": None,
                               "call_id": None, "cli_id": None, "data": {}})
            end.update(seq=len(events) + 1, event_id=f"e{len(events)+1:04}")
            events.append(end)
        self.edit_events(change)
        self.assertIncomplete()

    def test_terminal_run_event_cannot_precede_execution(self):
        def change(events):
            end = events.pop()
            events.insert(0, end)
            for seq, event in enumerate(events, 1):
                event.update(seq=seq, event_id=f"e{seq:04}")
        self.edit_events(change)
        self.assertIncomplete()

    def test_terminal_run_event_requires_outcome_reference(self):
        self.edit_events(lambda events: events[-1]["data"].clear())
        self.assertIncomplete()

    def test_terminal_run_event_must_reference_loaded_outcome(self):
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        self.edit_events(lambda events: events[-1]["data"].update(outcome_ref=manifest["original"]["part_ref"]))
        self.assertIncomplete()

    def test_malformed_bundle_does_not_abort_other_inputs(self):
        self.edit_events(lambda events: events[0].update(kind=[]))
        other = scenario_bundle(self.root / "other", "already_safe")
        manifest = self.root / "inputs.json"
        manifest.write_bytes(encoded({"inputs": [
            {"id": "bad", "case": "bracket_v3", "path": str(self.path)},
            {"id": "good", "case": "bracket_v3", "path": str(other)},
        ]}))
        summary = evaluate_batch(manifest, self.root / "reports")
        self.assertEqual(summary["requested"], 2)
        self.assertEqual(len(summary["reports"]), 2)
        bad = json.loads((self.root / "reports/report-bad.json").read_bytes())
        good = json.loads((self.root / "reports/report-good.json").read_bytes())
        self.assertFalse(bad["coverage"]["execution_complete"])
        self.assertTrue(good["coverage"]["execution_complete"])

    def test_batch_permutation_does_not_change_reports(self):
        other = scenario_bundle(self.root / "other", "already_safe")
        entries = [{"id": "b", "case": "bracket_v3", "path": str(self.path)},
                   {"id": "a", "case": "bracket_v3", "path": str(other)}]
        for index, ordering in enumerate((entries, list(reversed(entries)))):
            manifest = self.root / f"inputs{index}.json"
            manifest.write_bytes(encoded({"inputs": ordering}))
            evaluate_batch(manifest, self.root / f"reports{index}")
        for name in ("report-a.json", "report-b.json", "summary.json"):
            self.assertEqual((self.root / "reports0" / name).read_bytes(),
                             (self.root / "reports1" / name).read_bytes())

    def test_summary_input_id_does_not_overwrite_batch_metadata(self):
        manifest = self.root / "summary-input.json"
        manifest.write_bytes(encoded({"inputs": [{"id": "summary", "case": "bracket_v3",
                                                  "path": str(self.path)}]}))
        result = evaluate_batch(manifest, self.root / "summary-reports")
        self.assertEqual(result["reports"][0]["report"], "report-summary.json")
        report = json.loads((self.root / "summary-reports/report-summary.json").read_bytes())
        metadata = json.loads((self.root / "summary-reports/summary.json").read_bytes())
        self.assertEqual(report["input_id"], "summary")
        self.assertEqual(report["report_version"], "partlab.eval/1")
        self.assertEqual(metadata["report_version"], "partlab.eval-batch/1")
        self.assertEqual(metadata["requested"], 1)

    def test_duplicate_run_rejection_does_not_depend_on_order(self):
        entries = [{"id": name, "case": "bracket_v3", "path": str(self.path)} for name in ("a", "b")]
        for index, ordering in enumerate((entries, list(reversed(entries)))):
            manifest = self.root / f"duplicates{index}.json"
            manifest.write_bytes(encoded({"inputs": ordering}))
            summary = evaluate_batch(manifest, self.root / f"duplicate_reports{index}")
            self.assertEqual(summary["explicitly_rejected"], 2)
        self.assertEqual((self.root / "duplicate_reports0/summary.json").read_bytes(),
                         (self.root / "duplicate_reports1/summary.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
