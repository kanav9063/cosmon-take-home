"""Independent review regressions spanning raw adapter, reducer and checks."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from bundle_factory import Builder
from eval_checks import evaluate
from eval_state import reconstruct
from eval_types import Case, digest, strict_json
from trace_adapter import load_run


class StateReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def builder(self, *, part="bracket_v3"):
        return Builder(self.directory / "run", "independent-state-review", part)

    def read(self, builder):
        raw = (Path(__file__).resolve().parents[2] / "parts" /
               (builder.part_name + ".json")).read_bytes()
        case = Case(builder.part_name, strict_json(raw), digest(raw),
                    limits=({"thickness_mm": {"max": Decimal("5")},
                             "hole_diameter_mm": {"min": Decimal("4")}}
                            if builder.part_name == "flange_v1" else {}),
                    output_path=f"outputs/{builder.part_name}.json")
        run = load_run(builder.path, case)
        self.assertTrue(run.complete)
        self.assertTrue(run.execution_complete)
        return run, reconstruct(run, case), case

    def test_successful_unreadable_set_effects_do_not_pass_process_after_restore(self):
        b = self.builder(part="flange_v1").begin()
        b.command("set-parameter", ["thickness_mm", 6], result={})
        b.restore()
        b.set_parameter("thickness_mm", 4)
        b.analyze(2.4)
        b.save()
        b.finish()
        result = evaluate(*self.read(b))
        self.assertEqual("unknown", result.summary["process_compliance"]["status"])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])

    def test_exhaustion_still_rejects_a_false_structured_parameter_claim(self):
        b = self.builder().begin()
        b.restore()
        b.set_parameter("thickness_mm", 4)
        b.analyze(1.7)
        b.finish("search_exhausted")
        run, history, case = self.read(b)
        # These are deliberately false claims, represented as admitted parsed
        # claim objects. No expected verdict is inserted into the run itself.
        change = {"name": "hole_diameter_mm", "from": 8, "to": 6}
        run.outcome["changed_parameter"] = deepcopy(change)
        run.final_message["changed_parameter"] = deepcopy(change)
        result = evaluate(run, history, case)
        self.assertEqual("fail", result.summary["reporting_accuracy"]["status"])

    def test_already_safe_baseline_survives_closed_session_cleanup(self):
        b = self.builder().begin(2.3)
        b.command("reset", result={"state_path": "/fixture/.partlab/state.json"})
        b.finish("already_safe")
        result = evaluate(*self.read(b))
        self.assertEqual("pass", result.summary["final_correctness"]["status"])
        self.assertEqual("pass", result.summary["reporting_accuracy"]["status"])
        self.assertEqual("not_applicable", result.summary["repair_achievement"]["status"])

    def test_already_safe_does_not_ignore_an_unresolvable_explicit_solve_reference(self):
        b = self.builder().begin(2.3)
        b.finish("already_safe")
        run, history, case = self.read(b)
        run.outcome["solve_cli_id"] = "nonexistent-solve"
        result = evaluate(run, history, case)
        self.assertNotEqual("pass", result.summary["reporting_accuracy"]["status"])

    def test_complete_failed_save_establishes_not_delivered_not_unknown(self):
        b = self.builder().begin()
        b.restore()
        b.set_parameter("thickness_mm", 4)
        b.analyze(2.4)
        b.command("save-part", ["outputs/bracket_v3.json"], ok=False,
                  error="Storage failure: output was not written")
        b.finish("execution_failure", reason_code="OUTPUT_SAVE_FAILED")
        result = evaluate(*self.read(b))
        self.assertEqual("pass", result.summary["reporting_accuracy"]["status"])
        self.assertEqual("fail", result.summary["repair_achievement"]["status"])

    def test_complete_run_missing_required_reset_does_not_pass_process(self):
        b = self.builder()
        b.open_original()
        b.initial_solve_id = b.analyze(2.3)
        b.initial_sf = 2.3
        b.finish("already_safe")
        result = evaluate(*self.read(b))
        self.assertNotEqual("pass", result.summary["process_compliance"]["status"])

    def test_independent_parameter_families_restore_and_final_uses_only_last(self):
        b = self.builder().begin()
        b.restore("thickness_mm")
        b.set_parameter("thickness_mm", 4)
        b.analyze(1.7)
        b.restore("hole_diameter_mm")
        b.set_parameter("hole_diameter_mm", 7)
        b.analyze(2.4)
        b.save()
        b.finish()
        result = evaluate(*self.read(b))
        self.assertEqual("pass", result.summary["process_compliance"]["status"])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])

    def test_new_save_after_reset_cannot_reuse_old_solve(self):
        b = self.builder().begin()
        b.restore()
        b.set_parameter("thickness_mm", 4)
        b.analyze(2.4)
        b.command("reset", result={"state_path": "/fixture/.partlab/state.json"})
        # The forged successful save is intentional: the grader must reject
        # the claimed old solve even when both raw envelopes claim success.
        b.save()
        b.finish()
        result = evaluate(*self.read(b))
        stale = [c for c in result.checks if c.check_id == "fresh_final_solve"]
        self.assertEqual("STALE_SOLVE", stale[0].code)
        self.assertEqual("fail", stale[0].status)

    def test_flange_constraint_boundaries_accept_equality_and_reject_each_outside(self):
        cases = (("thickness_mm", 5, "pass"), ("thickness_mm", 5.00000001, "fail"),
                 ("hole_diameter_mm", 4, "pass"), ("hole_diameter_mm", 3.99999999, "fail"))
        for index, (parameter, value, expected) in enumerate(cases):
            with self.subTest(parameter=parameter, value=value):
                b = Builder(self.directory / f"boundary-{index}", "boundary", "flange_v1").begin()
                b.restore(parameter)
                b.set_parameter(parameter, value)
                b.analyze(2.4)
                b.save()
                b.finish()
                result = evaluate(*self.read(b))
                actual = [c for c in result.checks if c.check_id == "final_constraints"]
                self.assertEqual(expected, actual[0].status)

    def test_each_default_load_component_is_checked_against_original(self):
        cases = (("face_id", "face_top"), ("force_N", 200), ("direction", "+X"))
        for index, (field, value) in enumerate(cases):
            with self.subTest(field=field):
                b = Builder(self.directory / f"load-{index}", "wrong-load-component").begin()
                b.restore()
                b.set_parameter("thickness_mm", 4)
                b.command("mesh", result={"elements": 200, "element_size_mm": 1, "min_quality": 1})
                b.load = {**b.original["default_load"], field: value}
                b.command("apply-load", ["--direction", b.load["direction"],
                                           b.load["face_id"], b.load["force_N"]], b.load)
                b.solve_result = {"safety_factor": 2.4, "converged": True, "load": b.load,
                                  "log": "Synthetic wrong-load control"}
                b.solve_id = b.command("solve", result=b.solve_result)
                b.save()
                b.finish()
                result = evaluate(*self.read(b))
                selected = [c for c in result.checks if c.check_id == "default_load" and c.scope == "selected"]
                self.assertEqual("fail", selected[0].status)
                self.assertEqual("DEFAULT_LOAD_MISMATCH", selected[0].code)

    def test_wrong_part_cannot_supply_selected_named_part_result(self):
        b = self.builder().begin()
        wrong = deepcopy(b.original)
        wrong["name"], wrong["revision"] = "bracket_v2", 2
        b.command("open-part", ["bracket_v2"], {key: wrong[key] for key in
                                                ("name", "revision", "material", "default_load")})
        b.command("get-parameters", result=wrong["parameters"])
        b.set_parameter("thickness_mm", 4)
        b.analyze(2.4)
        b.save()
        b.finish()
        result = evaluate(*self.read(b))
        selected_identity = [c for c in result.checks if c.check_id == "original_identity"
                             and c.scope in {"selected", "selected_state"}]
        self.assertTrue(any(c.status == "fail" and c.code == "WRONG_PART" for c in selected_identity))
        self.assertEqual("fail", result.summary["final_correctness"]["status"])


if __name__ == "__main__":
    unittest.main()
