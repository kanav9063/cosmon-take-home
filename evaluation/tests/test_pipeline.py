"""End-to-end contracts, API seam, isolation, and actionable defect detection."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bundle_factory import Builder, encoded, refresh_inventory, scenario_bundle
from eval_types import InputError, digest
from evaluate import evaluate_batch, evaluate_one, load_cases, main
from trace_adapter import ADAPTERS, Limits, load_run, register_adapter


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cases, self.policy = load_cases()

    def tearDown(self):
        self.temp.cleanup()

    def report(self, scenario="repaired", part=None):
        path = scenario_bundle(self.root / scenario, scenario, part)
        return evaluate_one(path, self.cases[part or ("flange_v1" if scenario in {"guard_blocked", "illegal_restored"} else "bracket_v3")])

    def test_valid_full_bundle_all_required_dimensions_pass(self):
        report = self.report()
        for name in ("capture_integrity", "process_compliance", "final_correctness", "delivery", "reporting_accuracy", "repair_achievement"):
            self.assertEqual(report["summary"][name]["status"], "pass", (name, report["findings"]))

    def test_custom_case_rejects_missing_identity_fields_before_grading(self):
        original = json.loads((Path(__file__).resolve().parents[2] / "parts/bracket_v3.json").read_bytes())
        for field in ("revision", "material"):
            damaged = {k: v for k, v in original.items() if k != field}
            raw = encoded(damaged)
            (self.root / "original.json").write_bytes(raw)
            config = {"cases": [{"case_id": "bracket_v3", "original_path": "original.json",
                                 "original_sha256": digest(raw), "target_sf": 2,
                                 "limits": {}, "output_path": "outputs/bracket_v3.json"}]}
            (self.root / "cases.json").write_bytes(encoded(config))
            with self.assertRaises(InputError):
                load_cases(self.root / "cases.json")

    def test_semantic_stale_detected_with_raw_evidence(self):
        report = self.report("stale_solve")
        stale = [f for f in report["findings"] if f["code"] == "STALE_SOLVE"]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["status"], "fail")
        self.assertGreaterEqual(len(stale[0]["refs"]), 3)
        self.assertEqual(report["summary"]["capture_integrity"]["status"], "pass")

    def test_guard_and_recovery_are_diagnostics(self):
        for name in ("guard_blocked", "recovered_cli"):
            report = self.report(name)
            self.assertEqual(report["summary"]["process_compliance"]["status"], "pass")
            self.assertTrue(report["diagnostics"])

    def test_old_violation_does_not_disappear_or_corrupt_final_artifact(self):
        report = self.report("illegal_restored")
        self.assertEqual(report["summary"]["process_compliance"]["status"], "fail")
        self.assertEqual(report["summary"]["final_correctness"]["status"], "pass")
        self.assertEqual(report["summary"]["repair_achievement"]["status"], "pass")

    def test_exhaustion_reporting_separate_from_achievement(self):
        report = self.report("honest_exhaustion")
        self.assertEqual(report["summary"]["reporting_accuracy"]["status"], "pass")
        self.assertEqual(report["summary"]["repair_achievement"]["status"], "fail")
        self.assertEqual(report["details"]["feasibility"], "unknown")

    def test_added_case_uses_data_including_non_mounting_default(self):
        report = self.report("repaired", "housing_v1")
        self.assertEqual(self.cases["housing_v1"].default_load["face_id"], "face_lid")
        self.assertEqual(report["summary"]["final_correctness"]["status"], "pass")

    def test_evaluation_has_no_process_or_network_dependency(self):
        path = scenario_bundle(self.root / "offline")
        with patch("subprocess.Popen", side_effect=AssertionError("offline must not spawn")), \
             patch("socket.socket", side_effect=AssertionError("offline must not connect")):
            report = evaluate_one(path, self.cases["bracket_v3"])
        self.assertEqual(report["summary"]["final_correctness"]["status"], "pass")

    def test_explicit_api_adapter_seam_preserves_grade(self):
        path = scenario_bundle(self.root / "api")
        calls = []
        def captured_api_adapter(path, case, limits):
            calls.append(str(path))
            # An integration may translate its persisted response into the same
            # internal records. The grading engine receives no API client.
            return load_run(path, case, limits)
        name = "test-captured-api"
        register_adapter(name, captured_api_adapter)
        try:
            normal = evaluate_one(path, self.cases["bracket_v3"])
            adapted = evaluate_one(path, self.cases["bracket_v3"], adapter=name)
            self.assertEqual(adapted["adapter"], name)
            self.assertEqual(normal["adapter"], "partlab")
            self.assertEqual({k: v for k, v in normal.items() if k != "adapter"},
                             {k: v for k, v in adapted.items() if k != "adapter"})
            self.assertEqual(len(calls), 1)
            with self.assertRaises(InputError):
                register_adapter(name, captured_api_adapter)
        finally:
            ADAPTERS.pop(name, None)

    def test_resource_limits_are_explicit_unknown_not_pass(self):
        path = scenario_bundle(self.root / "large")
        report = evaluate_one(path, self.cases["bracket_v3"], limits=Limits(max_file_bytes=200))
        self.assertNotEqual(report["summary"]["capture_integrity"]["status"], "pass")

    def test_warning_budgets_are_explicit_and_do_not_change_correctness(self):
        path = scenario_bundle(self.root / "budget")
        baseline = evaluate_one(path, self.cases["bracket_v3"])
        warned = evaluate_one(path, self.cases["bracket_v3"], policy={"warning_budgets": {"raw_bytes": 0}})
        self.assertEqual(baseline["summary"], warned["summary"])
        self.assertTrue(any(d["code"] == "EFFICIENCY_BUDGET_EXCEEDED" for d in warned["diagnostics"]))
        self.assertNotEqual(baseline["configuration_digest"], warned["configuration_digest"])
        self.assertEqual(warned["metrics"]["warning_thresholds"], "configured")
        for policy in ({"target_sf": 0}, {"warning_budgets": {"invented": 1}},
                       {"warning_budgets": {"raw_bytes": True}}, {"warning_budgets": {"raw_bytes": -1}}):
            with self.assertRaises(InputError):
                evaluate_one(path, self.cases["bracket_v3"], policy=policy)

    def test_200_mixed_inputs_preserve_denominator_and_exact_permutation_results(self):
        entries = []
        kinds = ("repaired", "stale_solve", "missing_artifact", "already_safe")
        for index in range(199):
            path = self.root / str(index) / "trace"
            path.parent.mkdir()
            scenario_bundle(path, kinds[index % len(kinds)])
            run_id = f"scale-{index:03}"
            manifest = json.loads((path / "manifest.json").read_bytes())
            manifest["run_id"] = run_id
            (path / "manifest.json").write_bytes(encoded(manifest))
            events = [json.loads(line) for line in (path / "events.jsonl").read_bytes().splitlines()]
            for event in events:
                event["run_id"] = run_id
            (path / "events.jsonl").write_bytes(b"".join(encoded(e).replace(b"\n", b"") + b"\n" for e in events))
            refresh_inventory(path)
            entries.append({"id": f"case-{index:03}", "case": "bracket_v3", "path": str(path)})
        # Two entries refer to one run: reject both; retain the requested denominator.
        entries[198]["path"] = entries[197]["path"]
        bad = self.root / "malformed"
        bad.mkdir()
        (bad / "manifest.json").write_text("{")
        entries.append({"id": "case-199", "case": "bracket_v3", "path": str(bad)})
        for index, order in enumerate((entries, list(reversed(entries)))):
            manifest_path = self.root / f"scale-inputs-{index}.json"
            manifest_path.write_bytes(encoded({"inputs": order}))
            summary = evaluate_batch(manifest_path, self.root / f"scale-reports-{index}")
            self.assertEqual((summary["requested"], summary["evaluated"], summary["explicitly_rejected"]), (200, 197, 3))
            self.assertEqual(len(summary["reports"]), 200)
            for dimension, counts in summary["dimensions"].items():
                self.assertEqual(sum(counts.values()), 200, dimension)
        first, second = self.root / "scale-reports-0", self.root / "scale-reports-1"
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()},
                         {p.name: p.read_bytes() for p in second.iterdir()})

    def test_report_pins_effective_case_and_installed_code(self):
        from copy import deepcopy
        path = scenario_bundle(self.root / "provenance")
        case = deepcopy(self.cases["bracket_v3"])
        initial = evaluate_one(path, case)
        self.assertEqual(initial["evaluator"]["sources"]["evaluate.py"],
                         digest((Path(__file__).resolve().parents[1] / "evaluate.py").read_bytes()))
        case.target_sf += 1
        changed = evaluate_one(path, case)
        self.assertNotEqual(initial["configuration_digest"], changed["configuration_digest"])
        self.assertNotEqual(initial["effective_case_policy"], changed["effective_case_policy"])

    def test_reports_cannot_overwrite_evidence_or_existing_runs(self):
        path = scenario_bundle(self.root / "valid")
        manifest = self.root / "inputs.json"
        manifest.write_text(json.dumps({"inputs": [{"id": "valid", "path": "valid", "case": "bracket_v3"}]}))
        before = (path / "manifest.json").read_bytes()
        for output in (path, path / "reports", self.root):
            with self.assertRaises(InputError):
                evaluate_batch(manifest, output)
        self.assertEqual((path / "manifest.json").read_bytes(), before)

    def test_cli_success_is_report_execution_not_engineering_verdict(self):
        scenario_bundle(self.root / "stale", "stale_solve")
        manifest = self.root / "inputs.json"
        manifest.write_text(json.dumps({"inputs": [{"id": "stale", "path": "stale", "case": "bracket_v3"}]}))
        self.assertEqual(main(["--inputs", str(manifest), "--output-dir", str(self.root / "reports")]), 0)
        report = json.loads((self.root / "reports/report-stale.json").read_text())
        self.assertEqual(report["summary"]["final_correctness"]["status"], "fail")
        self.assertEqual(main(["--inputs", str(manifest), "--output-dir", str(self.root / "reports")]), 2)

    def test_internal_error_is_not_reported_as_bad_agent_evidence(self):
        scenario_bundle(self.root / "valid")
        manifest = self.root / "inputs.json"
        manifest.write_text(json.dumps({"inputs": [{"id": "valid", "path": "valid", "case": "bracket_v3"}]}))
        with patch("evaluate.reconstruct", side_effect=RuntimeError("injected evaluator bug")):
            self.assertEqual(main(["--inputs", str(manifest), "--output-dir", str(self.root / "reports")]), 2)
        self.assertFalse((self.root / "reports/report-valid.json").exists())
        aborted = json.loads((self.root / "reports/aborted.json").read_text())
        self.assertEqual(aborted["unevaluated"], ["valid"])


if __name__ == "__main__":
    unittest.main()
