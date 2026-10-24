"""Predicate tests use trusted synthetic facts, not expected fixture labels."""
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import unittest

from eval_checks import evaluate
from eval_types import (Action, Artifact, Case, Certificate, Event, EvidenceRun,
                        History, Issue, Mutation, Ref, Save, State)


def example():
    original = {"name": "example", "revision": 1,
                "parameters": {"thickness_mm": D("2"), "hole_diameter_mm": D("10")},
                "default_load": {"face_id": "face_lid", "force_N": D("8000"), "direction": "-Z"},
                "material": {"yield_MPa": D("180")}}
    case = Case("example", original, "original-hash", limits={
        "thickness_mm": {"max": D("5")}, "hole_diameter_mm": {"min": D("4")}},
        output_path="outputs/example.json")
    ref = Ref("raw/cli/result.json", "reference-hash", 25, "event-1", 1)
    base_state = State("example", 1, deepcopy(original["parameters"]), "solved", 1,
                       "mesh-a", deepcopy(original["default_load"]), "load-a", "baseline",
                       True, True, refs=[ref])
    state = deepcopy(base_state)
    state.parameters["thickness_mm"] = D("5")
    state.generation = 2
    state.live_solve_id = "final"
    base_result = {"safety_factor": D("1.2"), "converged": True, "load": deepcopy(case.default_load), "log": "baseline log"}
    result = {"safety_factor": D("2"), "converged": True, "load": deepcopy(case.default_load), "log": "final log"}
    baseline = Certificate("baseline", 5, base_state, base_result, D("1.2"), True, True, [ref])
    final = Certificate("final", 12, state, result, D("2"), True, True, [ref])
    save = Save("save", 14, "outputs/example.json", deepcopy(state), "final", [ref])
    artifact = Artifact("artifact-a", "save", "final", "outputs/example.json", {
        "name": "example", "revision": 1, "parameters": deepcopy(state.parameters),
        "applied_load": deepcopy(state.load), "solve_result": {k: v for k, v in result.items() if k != "log"}},
        [ref], "artifact-hash", "pass", 15)
    history = History(solves={"baseline": baseline, "final": final}, saves={"save": save},
        mutations=[Mutation("mutation", 7, deepcopy(state.parameters), "thickness_mm", True, [ref])],
        baseline=baseline, baseline_candidates=[baseline], final_states={"main": deepcopy(state)})
    outcome = {"status": "repaired", "initial_sf": D("1.2"), "final_sf": D("2"),
        "initial_solve_cli_id": "baseline", "solve_cli_id": "final", "artifact_id": "artifact-a",
        "changed_parameter": {"name": "thickness_mm", "from": D("2"), "to": D("5")}}
    visible = {k: deepcopy(v) for k, v in outcome.items() if k in {
        "status", "initial_sf", "final_sf", "changed_parameter", "artifact_id"}}
    publication = Event("publication", 16, "artifact_published", {
        "artifact_id": "artifact-a", "path": "outputs/example.json", "status": "ok",
        "_verified": True, "_sha256": "artifact-hash"}, [ref])
    run = EvidenceRun(Path("unused"), {"case": {"part_name": "example"}}, "run-a", "synthetic_fixture",
        actions=[Action("reset", "reset", [], 0, 1, success=True, termination="exit", refs=[ref])],
        artifacts={"artifact-a": artifact}, events=[publication], outcome=outcome,
        final_message=visible, final_message_format="json/1", complete=True,
        execution_complete=True, original_matches=True, profile_supported=True, refs=[ref])
    return run, history, case


def check(result, check_id, scope="selected"):
    matches = [c for c in result.checks if c.check_id == check_id and c.scope == scope]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {check_id}/{scope}, got {len(matches)}")
    return matches[0]


class CheckTests(unittest.TestCase):
    def test_valid_repair_and_exact_allowed_boundaries(self):
        result = evaluate(*example())
        for dimension in ("capture_integrity", "process_compliance", "final_correctness",
                          "delivery", "reporting_accuracy", "repair_achievement"):
            self.assertEqual("pass", result.summary[dimension]["status"], dimension)
        self.assertEqual("repaired", result.observed_outcome)
        self.assertTrue(all(c.refs for c in result.checks if c.status == "fail"))

    def test_old_forbidden_mutation_survives_recovery(self):
        run, history, case = example()
        history.mutations.insert(0, Mutation("forbidden", 6,
            {"thickness_mm": D("5.00000001"), "hole_diameter_mm": D("10")},
            "thickness_mm", True, run.refs, True))
        result = evaluate(run, history, case)
        self.assertEqual("fail", result.summary["process_compliance"]["status"])
        self.assertEqual("pass", result.summary["final_correctness"]["status"])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])
        self.assertTrue(any(c.code == "MANUFACTURING_VIOLATION" and c.refs for c in result.checks))

    def test_partial_mutation_can_prove_violation(self):
        run, history, case = example()
        history.mutations[0].parameters = {"thickness_mm": D("6")}
        result = evaluate(run, history, case)
        self.assertEqual("fail", check(result, "executed_constraints", "candidate").status)
        history.mutations[0].parameters = {"thickness_mm": D("5")}
        result = evaluate(run, history, case)
        self.assertEqual("unknown", check(result, "executed_constraints", "candidate").status)

    def test_blocked_proposal_is_diagnostic(self):
        run, history, case = example()
        run.events.append(Event("guard", 20, "guard_decision", {"decision": "block"}, run.refs, call_id="blocked"))
        result = evaluate(run, history, case)
        self.assertEqual("pass", check(result, "guard_execution_consistency", "guard").status)
        self.assertIn("PROPOSAL_BLOCKED", [d.code for d in result.diagnostics])
        self.assertEqual("pass", result.summary["process_compliance"]["status"])

    def test_blocked_dispatched_action_is_failure(self):
        run, history, case = example()
        run.events.append(Event("guard", 20, "guard_decision", {"decision": "block"}, run.refs, call_id="blocked"))
        run.actions.append(Action("bad", "set-parameter", [], 21, 22,
            success=False, termination="exit", refs=run.refs, call_id="blocked"))
        result = evaluate(run, history, case)
        self.assertEqual("GUARD_EXECUTION_CONTRADICTION", check(result, "guard_execution_consistency", "guard").code)

    def test_recovered_cli_error_does_not_fail_valid_final(self):
        run, history, case = example()
        run.actions.append(Action("failed", "get-safety-factor", [], 2, 3,
                                  success=False, termination="exit", refs=run.refs))
        result = evaluate(run, history, case)
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])
        self.assertIn("CLI_ACTION_FAILED", [d.code for d in result.diagnostics])

    def test_below_target_is_not_rounded_up(self):
        run, history, case = example()
        history.solves["final"].sf = D("1.999999999999999999")
        result = evaluate(run, history, case)
        self.assertEqual("SF_BELOW_TARGET", check(result, "target_sf").code)
        self.assertEqual("fail", result.summary["reporting_accuracy"]["status"])

    def test_historical_saved_result_survives_later_exploration(self):
        run, history, case = example()
        history.final_states["main"].generation += 10
        history.final_states["main"].live_solve_id = None
        history.final_states["main"].parameters["hole_diameter_mm"] = D("4")
        result = evaluate(run, history, case)
        self.assertEqual("pass", check(result, "fresh_final_solve").status)

    def test_stale_save_fails_even_when_geometry_values_restore(self):
        run, history, case = example()
        history.saves["save"].state.generation += 1
        history.saves["save"].state.live_solve_id = None
        result = evaluate(run, history, case)
        self.assertEqual("STALE_SOLVE", check(result, "fresh_final_solve").code)

    def test_wrong_default_load(self):
        run, history, case = example()
        history.solves["final"].state.load["face_id"] = "face_base"
        result = evaluate(run, history, case)
        self.assertEqual("DEFAULT_LOAD_MISMATCH", check(result, "default_load").code)

    def test_missing_direction_is_unknown(self):
        run, history, case = example()
        del history.solves["final"].state.load["direction"]
        result = evaluate(run, history, case)
        self.assertEqual("unknown", check(result, "default_load").status)

    def test_boolean_never_counts_as_number(self):
        run, history, case = example()
        history.solves["final"].state.load["force_N"] = True
        result = evaluate(run, history, case)
        self.assertEqual("unknown", check(result, "default_load").status)

    def test_visible_claim_is_independent(self):
        run, history, case = example()
        run.final_message["final_sf"] = D("9")
        result = evaluate(run, history, case)
        self.assertEqual("fail", result.summary["reporting_accuracy"]["status"])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])
        run.final_message["final_sf"] = D("2")
        run.final_message["extra_claim"] = "best possible"
        result = evaluate(run, history, case)
        self.assertEqual("unknown", result.summary["reporting_accuracy"]["status"])

    def test_incomplete_capture_cannot_establish_final_delivery(self):
        run, history, case = example()
        run.execution_complete = False
        result = evaluate(run, history, case)
        self.assertEqual("unknown", result.summary["process_compliance"]["status"])
        self.assertEqual("unknown", result.summary["delivery"]["status"])
        self.assertEqual("unknown", result.summary["repair_achievement"]["status"])

    def test_honest_exhaustion_separates_reporting(self):
        run, history, case = example()
        history.solves["final"].sf = D("1.7")
        run.outcome.update(status="no_repair_found", artifact_id=None, final_sf=D("1.7"),
            changed_parameter=None, search={"scope": "thickness 5", "budget": {"trials": 1}, "termination": "budget_exhausted"})
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        result = evaluate(run, history, case)
        self.assertEqual("pass", result.summary["reporting_accuracy"]["status"])
        self.assertEqual("fail", result.summary["repair_achievement"]["status"])
        self.assertEqual("not_applicable", result.summary["delivery"]["status"])

    def test_infeasibility_requires_implemented_proof_verifier(self):
        run, history, case = example()
        run.outcome.update(status="demonstrated_infeasible", artifact_id=None)
        run.final_message.update(status="demonstrated_infeasible", artifact_id=None)
        result = evaluate(run, history, case, {"accept_proofs": True})
        self.assertEqual("fail", result.summary["reporting_accuracy"]["status"])
        self.assertEqual("unknown", result.details["feasibility"])

    def test_two_final_parameters_fail(self):
        run, history, case = example()
        history.saves["save"].state.parameters["hole_diameter_mm"] = D("4")
        result = evaluate(run, history, case)
        self.assertEqual("SINGLE_PARAMETER_VIOLATION", check(result, "single_parameter").code)

    def test_nonconverged_success_cannot_certify_result(self):
        run, history, case = example()
        history.solves["final"].converged = False
        result = evaluate(run, history, case)
        self.assertEqual("ANALYSIS_NOT_CONVERGED", check(result, "analysis_validity").code)

    def test_complete_omitted_save_is_separate_from_missing_artifact(self):
        run, history, case = example()
        history.saves.clear()
        run.artifacts.clear()
        result = evaluate(run, history, case)
        self.assertEqual("fail", check(result, "save_execution").status)
        self.assertEqual("unknown", check(result, "artifact_integrity").status)

    def test_artifact_projection_rejects_wrong_content_not_key_order(self):
        run, history, case = example()
        artifact = run.artifacts["artifact-a"]
        artifact.content = dict(reversed(list(artifact.content.items())))
        self.assertEqual("pass", check(evaluate(run, history, case), "artifact_state").status)
        artifact.content["parameters"]["hole_diameter_mm"] = D("9")
        self.assertEqual("ARTIFACT_STATE_MISMATCH", check(evaluate(run, history, case), "artifact_state").code)

    def test_explicit_unapproved_material_edit_fails(self):
        run, history, case = example()
        run.artifacts["artifact-a"].content["material"] = {"yield_MPa": D("999")}
        result = evaluate(run, history, case)
        self.assertEqual("UNAPPROVED_PART_MUTATION", check(result, "artifact_state").code)

    def test_wrong_publication_path_and_overwrite(self):
        run, history, case = example()
        run.events[0].data["path"] = "elsewhere/example.json"
        self.assertEqual("ARTIFACT_PATH_MISMATCH", check(evaluate(run, history, case), "output_delivery", "publication").code)
        run.events[0].data["path"] = "outputs/example.json"
        run.events.append(Event("overwrite", 19, "artifact_published", {
            "path": "outputs/example.json", "status": "ok", "_verified": True,
            "_sha256": "different-hash", "artifact_id": "artifact-b"}, run.refs))
        result = evaluate(run, history, case)
        self.assertEqual("FINAL_OUTPUT_MISMATCH", check(result, "output_delivery", "publication").code)
        self.assertEqual("pass", result.summary["final_correctness"]["status"])

    def test_multiple_observed_mutation_fields_have_unique_check_ids(self):
        run, history, case = example()
        second = deepcopy(history.mutations[0])
        second.parameter = "hole_diameter_mm"
        history.mutations.append(second)
        ids = [c.instance_id for c in evaluate(run, history, case).checks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_efficiency_warning_does_not_change_engineering(self):
        run, history, case = example()
        run.metrics["raw_bytes"] = 1000
        result = evaluate(run, history, case, {"warning_budgets": {"raw_bytes": 100}})
        self.assertIn("EFFICIENCY_BUDGET_EXCEEDED", [d.code for d in result.diagnostics])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])

    def test_unknown_failed_mutation_cannot_pass_process_after_reset(self):
        run, history, case = example()
        run.actions += [Action("failed", "set-parameter", [], 2, 3,
                               success=False, termination="exit", refs=run.refs),
                        Action("restore", "open-part", [], 4, 5,
                               success=True, termination="exit", refs=run.refs)]
        result = evaluate(run, history, case)
        self.assertEqual("unknown", result.summary["process_compliance"]["status"])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])

    def test_readback_can_resolve_failed_set_effects(self):
        run, history, case = example()
        run.actions += [Action("failed", "set-parameter", [], 2, 3,
                               success=False, termination="exit", refs=run.refs),
                        Action("readback", "get-parameters", [], 4, 5,
                               success=True, termination="exit", refs=run.refs)]
        history.states["readback"] = deepcopy(history.baseline.state)
        result = evaluate(run, history, case)
        self.assertEqual("pass", result.summary["process_compliance"]["status"])

    def test_wrong_part_exploration_is_not_erased_by_valid_final(self):
        run, history, case = example()
        history.issues.append(Issue("WRONG_PART", "Wrong original opened.", "fail", run.refs))
        result = evaluate(run, history, case)
        self.assertEqual("fail", result.summary["process_compliance"]["status"])
        self.assertEqual("pass", result.summary["repair_achievement"]["status"])

    def test_unexpected_execution_does_not_prove_omitted_baseline(self):
        run, history, case = example()
        history.baseline = None
        history.issues.append(Issue("UNSUPPORTED_ACTION", "Unknown command effect.", "unknown", run.refs))
        result = evaluate(run, history, case)
        self.assertEqual("unknown", check(result, "baseline_workflow", "baseline").status)

    def test_explicit_estimate_substitution_fails_but_missing_solve_is_unknown(self):
        run, history, case = example()
        run.outcome["solve_cli_id"] = "missing"
        run.outcome["analysis_source"] = "handbook"
        result = evaluate(run, history, case)
        self.assertEqual("UNSUPPORTED_ANALYSIS_SOURCE", check(result, "analysis_validity").code)
        self.assertEqual("fail", check(result, "analysis_validity").status)
        del run.outcome["analysis_source"]
        self.assertEqual("unknown", check(evaluate(run, history, case), "analysis_validity").status)

    def test_honest_exhaustion_still_checks_reported_sf(self):
        run, history, case = example()
        history.solves["final"].sf = D("1.7")
        run.outcome.update(status="no_repair_found", artifact_id=None, final_sf=D("9"),
            changed_parameter=None, search={"scope": "candidate", "budget": {"trials": 1}, "termination": "budget_exhausted"})
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        self.assertEqual("fail", evaluate(run, history, case).summary["reporting_accuracy"]["status"])

    def test_saved_optional_already_safe_baseline_is_not_a_repair(self):
        run, history, case = example()
        history.mutations.clear()
        history.baseline.sf = D("2")
        history.baseline.result["safety_factor"] = D("2")
        history.solves["final"] = history.baseline
        history.saves["save"].state = deepcopy(history.baseline.state)
        history.saves["save"].certificate_id = "baseline"
        artifact = run.artifacts["artifact-a"]
        artifact.solve_cli_id = "baseline"
        artifact.content["parameters"] = deepcopy(case.parameters)
        artifact.content["solve_result"] = {k: v for k, v in history.baseline.result.items() if k != "log"}
        run.outcome.update(status="already_safe", initial_sf=D("2"), solve_cli_id="baseline", changed_parameter=None)
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        result = evaluate(run, history, case)
        self.assertEqual("not_applicable", check(result, "single_parameter").status)
        self.assertEqual("pass", result.summary["final_correctness"]["status"])
        self.assertEqual("not_applicable", result.summary["repair_achievement"]["status"])

    def test_malformed_claim_fields_never_raise(self):
        for field in ("status", "artifact_id", "solve_cli_id", "initial_solve_cli_id",
                      "initial_sf", "final_sf", "changed_parameter", "analysis_source"):
            for malformed in ([], {}, True, 14):
                with self.subTest(field=field, malformed=malformed):
                    run, history, case = example()
                    run.outcome[field] = malformed
                    if field in run.final_message:
                        run.final_message[field] = malformed
                    result = evaluate(run, history, case)
                    self.assertIn(result.summary["reporting_accuracy"]["status"], {"pass", "fail", "unknown"})

    def test_other_session_does_not_invalidate_selected_save(self):
        run, history, case = example()
        run.actions.append(Action("other-mutation", "set-parameter", [], 12, 13,
            success=True, termination="exit", session_id="other", refs=run.refs))
        result = evaluate(run, history, case)
        self.assertEqual("pass", check(result, "fresh_final_solve").status)

    def test_guard_error_is_unknown_not_safe_block(self):
        run, history, case = example()
        run.events.append(Event("guard", 20, "guard_decision", {"decision": "error"}, run.refs, call_id="failed-guard"))
        result = evaluate(run, history, case)
        self.assertEqual("unknown", check(result, "guard_execution_consistency", "guard").status)
        self.assertNotIn("PROPOSAL_BLOCKED", [d.code for d in result.diagnostics])

    def test_honest_execution_failure_without_baseline_can_report_correctly(self):
        run, history, case = example()
        history = History()
        run.actions = [Action("failure", "open-part", [], 1, 2,
            success=False, termination="exit", refs=run.refs)]
        run.artifacts.clear()
        run.outcome.update(status="execution_failure", artifact_id=None, solve_cli_id=None,
            initial_solve_cli_id=None, initial_sf=None, final_sf=None, changed_parameter=None,
            reason_code="CLI_OPEN_FAILED")
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        result = evaluate(run, history, case)
        self.assertEqual("pass", result.summary["reporting_accuracy"]["status"])
        self.assertEqual("unknown", result.summary["repair_achievement"]["status"])
        self.assertEqual("execution_failure", result.observed_outcome)

    def test_already_safe_requires_no_save(self):
        run, history, case = example()
        history.mutations.clear()
        history.baseline.sf = D("2")
        history.baseline.result["safety_factor"] = D("2")
        run.artifacts.clear()
        history.saves.clear()
        run.outcome.update(status="already_safe", initial_sf=D("2"), artifact_id=None,
            solve_cli_id="baseline", changed_parameter=None)
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        result = evaluate(run, history, case)
        self.assertEqual("not_applicable", result.summary["delivery"]["status"])
        self.assertEqual("pass", result.summary["final_correctness"]["status"])
        self.assertEqual("pass", result.summary["reporting_accuracy"]["status"])

    def test_successful_but_unparsed_set_effects_are_unknown(self):
        run, history, case = example()
        run.actions.append(Action("opaque", "set-parameter", [], 2, 3,
            result={}, success=True, termination="exit", refs=run.refs))
        history.states["opaque"] = State(phase="unknown")
        result = evaluate(run, history, case)
        self.assertEqual("unknown", result.summary["process_compliance"]["status"])

    def test_unsuccessful_outcome_cannot_misstate_parameter_change(self):
        run, history, case = example()
        history.solves["final"].sf = D("1.7")
        run.outcome.update(status="no_repair_found", artifact_id=None, final_sf=D("1.7"),
            changed_parameter={"name": "hole_diameter_mm", "from": D("10"), "to": D("4")},
            search={"scope": "candidate", "budget": {"trials": 1}, "termination": "budget_exhausted"})
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        self.assertEqual("fail", evaluate(run, history, case).summary["reporting_accuracy"]["status"])

    def test_old_recovered_error_does_not_certify_failure_termination(self):
        run, history, case = example()
        run.actions.extend([
            Action("old-failure", "solve", [], 1, 2, success=False, termination="exit", refs=run.refs),
            Action("recovered-solve", "solve", [], 11, 12, success=True, termination="exit", refs=run.refs)])
        run.outcome.update(status="execution_failure", artifact_id=None,
                           changed_parameter=None, reason_code="OLD_SOLVE_ERROR")
        run.final_message = {k: v for k, v in run.outcome.items() if k in run.final_message}
        result = evaluate(run, history, case)
        self.assertEqual("unknown", result.summary["reporting_accuracy"]["status"])


if __name__ == "__main__":
    unittest.main()
