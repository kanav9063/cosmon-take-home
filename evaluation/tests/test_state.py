"""Semantic state controls independent of the expected-outcome fixture table."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import unittest

from eval_state import reconstruct
from eval_types import Action, Case, Event, EvidenceRun, digest, strict_json


class StateTests(unittest.TestCase):
    def setUp(self):
        raw = (Path(__file__).resolve().parents[1] / "parts" / "bracket_v3.json").read_bytes()
        self.case = Case("bracket_v3", strict_json(raw), digest(raw))
        self.run = EvidenceRun(Path("unused"), profile_supported=True, original_matches=True,
                               complete=True, execution_complete=True)
        self.seq = 0

    def action(self, name, result, args=(), **kwargs):
        self.seq += 1
        cli_id = f"c{self.seq}"
        self.run.actions.append(Action(cli_id, name, ["partlab", name, *map(str, args)],
                                       self.seq, self.seq, result, **{
                                           "success": True, "termination": "exit", "exit_code": 0,
                                           **kwargs}))
        return cli_id

    def original(self, *, readback=True):
        self.action("reset", {"state_path": "/tmp/state"})
        self.open_original(readback=readback)

    def open_original(self, *, readback=True):
        original = self.case.original
        self.action("open-part", {"name": original["name"], "revision": original["revision"],
                                 "material": original["material"], "default_load": original["default_load"]},
                    (original["name"],))
        if readback:
            self.action("get-parameters", deepcopy(original["parameters"]))

    def analyze(self, *, load=None, sf="1.4", converged=True):
        actual = deepcopy(self.case.default_load if load is None else load)
        self.action("mesh", {"elements": 42, "element_size_mm": 1, "min_quality": Decimal("0.5")})
        self.action("apply-load", actual, (actual["face_id"], actual["force_N"]))
        return self.action("solve", {"safety_factor": Decimal(sf), "converged": converged, "load": actual})

    def set_value(self, value, previous=3, parameter="thickness_mm", **kwargs):
        return self.action("set-parameter", {"name": parameter, "previous_value": previous,
                                            "new_value": value, "downstream_invalidated": True},
                           (parameter, value), **kwargs)

    def save(self, name="a"):
        return self.action("save-part", {"saved_to": f"outputs/{name}.json"}, (f"outputs/{name}.json",))

    def reduce(self):
        return reconstruct(self.run, self.case)

    def test_original_requires_raw_complete_readback(self):
        self.original(readback=False)
        solve = self.analyze()
        h = self.reduce()
        self.assertIsNone(h.baseline)
        self.assertIn("GEOMETRY_UNKNOWN", h.solves[solve].problems)
        self.assertEqual([solve], [c.cli_id for c in h.baseline_candidates])

    def test_baseline_requires_original_default_but_wrong_load_solve_is_retained(self):
        self.original()
        wrong = {**self.case.default_load, "force_N": 100}
        bad, good = self.analyze(load=wrong), self.analyze()
        h = self.reduce()
        self.assertTrue(h.solves[bad].valid)
        self.assertEqual(good, h.baseline.cli_id)
        self.assertEqual([bad, good], [c.cli_id for c in h.baseline_candidates])

    def test_equal_value_set_invalidates_live_but_not_saved_certificate(self):
        self.original()
        solve = self.analyze()
        saved = self.save()
        same = self.set_value(3)
        stale_save = self.save("b")
        h = self.reduce()
        self.assertEqual(solve, h.saves[saved].certificate_id)
        self.assertIsNone(h.saves[stale_save].certificate_id)
        self.assertGreater(h.states[same].generation, h.solves[solve].state.generation)
        self.assertEqual(solve, h.solves[solve].state.live_solve_id)

    def test_equal_value_set_before_baseline_is_not_effective_candidate(self):
        self.original()
        self.set_value(3)
        solve = self.analyze()
        self.assertEqual(solve, self.reduce().baseline.cli_id)

    def test_repeated_assignments_to_one_parameter_are_allowed(self):
        self.original()
        self.analyze()
        self.set_value(4, trial_id="t1")
        self.set_value(5, previous=4, trial_id="t1")
        self.assertEqual([True, True], [m.restored for m in self.reduce().mutations])

    def test_switching_parameter_or_trial_requires_new_restore(self):
        self.original()
        self.set_value(4, trial_id="t1")
        self.set_value(5, previous=4, trial_id="t2")
        self.set_value(6, previous=8, parameter="hole_diameter_mm", trial_id="t2")
        self.open_original()
        self.set_value(6, previous=8, parameter="hole_diameter_mm", trial_id="t3")
        self.assertEqual([True, False, False, True], [m.restored for m in self.reduce().mutations])

    def test_restored_original_does_not_retroactively_supply_initial_baseline(self):
        self.original()
        self.set_value(4)
        self.open_original()
        self.analyze()
        self.assertIsNone(self.reduce().baseline)

    def test_failed_and_malformed_readonly_results_preserve_live_analysis(self):
        self.original()
        solve = self.analyze()
        self.action("get-safety-factor", None, success=False, exit_code=1)
        self.action("get-parameters", None)
        save = self.save()
        h = self.reduce()
        self.assertEqual(solve, h.saves[save].certificate_id)
        self.assertEqual(self.case.parameters, h.saves[save].state.parameters)

    def test_failed_solve_clears_live_result_but_not_prior_saved_proof(self):
        self.original()
        solve = self.analyze()
        old_save = self.save()
        failed = self.action("solve", None, success=False, exit_code=1)
        new_save = self.save("b")
        h = self.reduce()
        self.assertFalse(h.solves[failed].valid)
        self.assertEqual(solve, h.saves[old_save].certificate_id)
        self.assertIsNone(h.saves[new_save].certificate_id)
        self.assertEqual(self.case.parameters, h.states[failed].parameters)

    def test_readback_proves_effect_of_failed_set_and_recovers_current_geometry(self):
        self.original()
        self.analyze()
        bad = self.action("set-parameter", None, ("thickness_mm", 7), success=False,
                          exit_code=None, termination="timeout")
        self.action("get-parameters", {**self.case.parameters, "thickness_mm": 7})
        solve = self.analyze(sf="2.4")
        h = self.reduce()
        self.assertTrue(h.solves[solve].valid)
        self.assertEqual(1, len(h.mutations))
        mutation = h.mutations[0]
        self.assertEqual(bad, mutation.cli_id)
        self.assertEqual(7, mutation.parameters["thickness_mm"])
        self.assertTrue(mutation.observed_after_failure)
        self.assertTrue(mutation.restored)

    def test_failed_set_does_not_guess_effects_and_later_open_recovers(self):
        self.original()
        self.analyze()
        bad = self.action("set-parameter", None, ("thickness_mm", 7), success=False, exit_code=1)
        self.open_original()
        solve = self.analyze()
        h = self.reduce()
        self.assertIsNone(h.states[bad].parameters)
        self.assertTrue(h.solves[solve].valid)
        self.assertEqual([], h.mutations)

    def test_gap_invalidates_current_but_retains_historical_saved_artifact(self):
        self.original()
        solve = self.analyze()
        saved = self.save()
        self.seq += 1
        self.run.events.append(Event("gap", self.seq, "evidence_gap", {"scope": "all"}))
        unknown = self.save("b")
        self.open_original()
        fresh = self.analyze()
        h = self.reduce()
        self.assertEqual(solve, h.saves[saved].certificate_id)
        self.assertIsNone(h.saves[unknown].certificate_id)
        self.assertTrue(h.solves[fresh].valid)
        self.assertEqual(solve, h.baseline.cli_id)

    def test_unknown_prebaseline_history_cannot_prove_initial_baseline(self):
        self.seq += 1
        self.run.events.append(Event("gap", self.seq, "evidence_gap", {"scope": "all"}))
        self.original()
        solve = self.analyze()
        h = self.reduce()
        self.assertTrue(h.solves[solve].valid)
        self.assertIsNone(h.baseline)

    def test_uncertain_order_still_retains_proved_accepted_value(self):
        self.original()
        bad = self.set_value(7, uncertain_order=True)
        h = self.reduce()
        self.assertIsNone(h.states[bad].parameters)
        self.assertEqual({"thickness_mm": 7}, h.mutations[0].parameters)
        self.assertIsNone(h.mutations[0].restored)

    def test_nonconverged_solve_is_not_a_valid_certificate(self):
        self.original()
        solve = self.analyze(converged=False)
        h = self.reduce()
        self.assertFalse(h.solves[solve].valid)
        self.assertIn("ANALYSIS_NOT_CONVERGED", h.solves[solve].problems)
        self.assertIsNone(h.baseline)

    def test_mesh_rerun_invalidates_load_and_solve(self):
        self.original()
        self.analyze()
        mesh = self.action("mesh", {"elements": 20, "element_size_mm": 2, "min_quality": 1})
        h = self.reduce()
        self.assertIsNone(h.states[mesh].load)
        self.assertIsNone(h.states[mesh].live_solve_id)
        self.assertEqual(self.case.parameters, h.states[mesh].parameters)

    def test_load_failure_preserves_geometry_and_mesh(self):
        self.original()
        solve = self.analyze()
        load = self.action("apply-load", None, ("bad_face", 42), success=False, exit_code=1)
        h = self.reduce()
        self.assertEqual(h.solves[solve].state.mesh_id, h.states[load].mesh_id)
        self.assertEqual(self.case.parameters, h.states[load].parameters)
        self.assertIsNone(h.states[load].load)

    def test_unsupported_profile_cannot_certify_solve(self):
        self.run.profile_supported = False
        self.original()
        solve = self.analyze()
        self.assertFalse(self.reduce().solves[solve].valid)

    def test_explicit_load_direction_flag_before_positionals(self):
        self.original()
        self.action("mesh", {"elements": 20, "element_size_mm": 2, "min_quality": 1},
                    ("--element-size", "2"))
        load = self.case.default_load
        self.action("apply-load", load, ("--direction", load["direction"],
                                         load["face_id"], load["force_N"]))
        solve = self.action("solve", {"safety_factor": 2, "converged": True, "load": load})
        h = self.reduce()
        self.assertTrue(h.solves[solve].valid)
        self.assertFalse(h.issues)

    def test_explicit_direction_disagreement_retains_actual_result_and_issue(self):
        self.original()
        self.action("apply-load", self.case.default_load,
                    ("--direction=+X", self.case.default_load["face_id"],
                     self.case.default_load["force_N"]))
        h = self.reduce()
        self.assertTrue(any(issue.code == "EVIDENCE_CONTRADICTION" for issue in h.issues))
        self.assertEqual("-Z", h.final_states["main"].load["direction"])

    def test_documented_readonly_commands_accept_list_string_and_empty_payloads(self):
        self.original()
        solve = self.analyze()
        for name, payload in (("get-feature", [1]), ("get-solve-log", "log"),
                              ("get-max-stress", {}), ("state-dir", "/tmp/state"),
                              ("compute-stress-from-handbook", 42), ("--help", None)):
            self.action(name, payload)
        saved = self.save()
        h = self.reduce()
        self.assertEqual(solve, h.saves[saved].certificate_id)
        self.assertFalse(h.issues)

    def test_first_readback_must_match_the_opened_original(self):
        self.original(readback=False)
        self.action("get-parameters", {**self.case.parameters, "thickness_mm": 7})
        self.analyze(sf="3")
        h = self.reduce()
        self.assertIsNone(h.baseline)
        self.assertEqual(7, h.mutations[0].parameters["thickness_mm"])
        self.assertTrue(any(issue.code == "UNAPPROVED_PART_MUTATION" for issue in h.issues))

    def test_active_part_phase_contradiction_invalidates_live_solve(self):
        self.original()
        self.analyze()
        readback = self.action("get-active-part", {"active_part": "bracket_v3", "phase": "open"})
        self.assertIsNone(self.reduce().states[readback].live_solve_id)

    def test_active_part_overrides_retain_proved_illegal_value(self):
        self.original()
        self.analyze()
        readback = self.action("get-active-part", {"active_part": "bracket_v3", "phase": "open",
                                                   "parameter_overrides": {"thickness_mm": 7}})
        h = self.reduce()
        self.assertIsNone(h.states[readback].parameters)
        self.assertEqual({"thickness_mm": 7}, h.mutations[0].parameters)

    def test_active_part_closed_readback_cannot_leave_live_certificate(self):
        self.original()
        self.analyze()
        readback = self.action("get-active-part", {"active_part": None, "phase": "closed"})
        h = self.reduce()
        self.assertIsNone(h.states[readback].live_solve_id)
        self.assertEqual("closed", h.states[readback].phase)


if __name__ == "__main__":
    unittest.main()
