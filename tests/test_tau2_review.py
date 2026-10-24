"""Cross-cutting outcome/trajectory checks motivated by the Tau² audit.

These exercise the local PartLab policy, not Tau²'s reward formula. Every
bundle is synthetic: none of the solver values below is a measured result.
"""
from pathlib import Path
import tempfile
import unittest

from bundle_factory import Builder, SCENARIOS, refresh_inventory, scenario_bundle
from evaluate import evaluate_one, load_cases


class Tau2ReferenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cases, _ = load_cases()

    def test_all_adverse_checks_have_an_explicit_summary_dimension(self):
        # A computed check must not silently disappear from the reported
        # verdicts, as can happen with an unintended reward-basis selection.
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                part = "flange_v1" if scenario in {"guard_blocked", "illegal_restored"} else "bracket_v3"
                path = scenario_bundle(self.root / scenario, scenario, part)
                report = evaluate_one(path, self.cases[part])
                members = {member for dimension in report["summary"].values()
                           for member in dimension["members"]}
                for check in report["checks"]:
                    if check["status"] in {"fail", "unknown"}:
                        self.assertIn(check["instance_id"], members)

    def test_alternative_valid_trajectories_do_not_require_a_reference_script(self):
        # Extra harmless reads, repeated assignments to one parameter, and
        # different eligible final parameter families are all legal paths.
        for name, values in (("thickness_mm", [3.5, 4]),
                             ("fillet_radius_mm", [2.5, 3])):
            with self.subTest(parameter=name):
                builder = Builder(self.root / name, name).begin()
                builder.restore(name)
                for value in values:
                    builder.command("list-parts", result=[])
                    builder.set_parameter(name, value)
                builder.analyze(2.4)
                builder.command("get-parameters", result=builder.parameters)
                builder.save()
                builder.finish()
                report = evaluate_one(builder.path, self.cases["bracket_v3"])
                for dimension in ("capture_integrity", "process_compliance",
                                  "final_correctness", "delivery",
                                  "reporting_accuracy", "repair_achievement"):
                    self.assertEqual("pass", report["summary"][dimension]["status"],
                                     (dimension, report["findings"]))

    def test_complete_capture_and_unchanged_unsafe_state_do_not_pass_repair(self):
        builder = Builder(self.root / "noop", "noop").begin(1.4)
        builder.finish("repaired")
        report = evaluate_one(builder.path, self.cases["bracket_v3"])
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("fail", report["summary"]["repair_achievement"]["status"])
        self.assertEqual("fail", report["summary"]["reporting_accuracy"]["status"])

    def test_interruption_preserves_an_observed_forbidden_mutation(self):
        path = scenario_bundle(self.root / "partial", "illegal_restored", "flange_v1")
        with (path / "events.jsonl").open("ab") as stream:
            stream.write(b'{"event_id":"unfinished"')
        refresh_inventory(path, status="interrupted")
        report = evaluate_one(path, self.cases["flange_v1"])
        self.assertNotEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("fail", report["summary"]["process_compliance"]["status"])
        violations = [finding for finding in report["findings"]
                      if finding["code"] == "MANUFACTURING_VIOLATION"]
        self.assertTrue(violations)
        self.assertTrue(all(item["status"] == "fail" and item["refs"] for item in violations))


if __name__ == "__main__":
    unittest.main()
