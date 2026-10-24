"""Independent, deterministic predicates over admitted execution evidence.

No function here reads producer expectations, executes a command, or calls a
model. A missing observation is not a negative observation. In particular,
whole-run absence claims require complete execution coverage, whereas an
observed forbidden mutation survives later recovery or an incomplete tail.
"""
from __future__ import annotations

from decimal import Decimal
import posixpath
from typing import Any

from eval_types import (Artifact, Case, Certificate, Check, Evaluation,
                        EvidenceRun, History, Issue, Ref, State, number)


ALIASES = {"no_repair_found": "search_exhausted",
           "demonstrated_infeasible": "proven_infeasible"}
OUTCOMES = {"already_safe", "repaired", "search_exhausted",
            "proven_infeasible", "execution_failure"}
REPAIR_CHECKS = {"single_parameter", "save_execution", "artifact_integrity",
                 "artifact_state", "output_delivery"}
REMEDIATION = {
    "WRONG_PART": "Open the requested original part and retain its raw identity and parameter readback.",
    "UNAPPROVED_PART_MUTATION": "Restore the trusted original source fields and change only an allowed parameter.",
    "BASELINE_ANALYSIS_MISSING": "Analyze the trusted original under its default load before changing any parameter.",
    "DEFAULT_LOAD_MISMATCH": "Mesh and solve using the original face, force and direction.",
    "ANALYSIS_NOT_CONVERGED": "Obtain and retain a converged FEA solve for the selected inputs.",
    "MANUFACTURING_VIOLATION": "Reject out-of-bounds proposals before execution and retain evidence of legal final values.",
    "TRIAL_BASELINE_NOT_RESTORED": "Restore and read back the original before starting another trial or parameter family.",
    "GUARD_EXECUTION_CONTRADICTION": "Prevent dispatch of blocked calls and retain distinct guard and CLI attempt records.",
    "SINGLE_PARAMETER_VIOLATION": "Compare the complete final parameter map to the original and change exactly one value.",
    "STALE_SOLVE": "Run mesh, default load and a fresh converged solve after the last invalidation, then save that state.",
    "SF_BELOW_TARGET": "Do not claim success below the exact target; repair further or report the unsuccessful outcome.",
    "REQUIRED_SAVE_MISSING": "Retain a successful save linked to the selected artifact and solve.",
    "ARTIFACT_MISSING": "Capture the selected immutable saved bytes and their verified digest and length.",
    "ARTIFACT_HASH_MISMATCH": "Preserve the exact original saved bytes and correct their capture references.",
    "ARTIFACT_STATE_MISMATCH": "Save the selected solved state and preserve its exact compact output projection.",
    "ARTIFACT_PATH_MISMATCH": "Publish the selected saved bytes to the required logical output path.",
    "FINAL_OUTPUT_MISMATCH": "Publish the selected artifact again after other exploration and record the final destination bytes.",
    "FINAL_CLAIM_MISMATCH": "Report only outcomes, numbers and artifacts supported by the retained raw evidence.",
    "UNSUPPORTED_INFEASIBILITY": "Report bounded search exhaustion unless an independent complete-domain proof verifier is available.",
}


def _refs(*groups: list[Ref]) -> list[Ref]:
    result = []
    for group in groups:
        for ref in group:
            if ref not in result:
                result.append(ref)
    return result


def _status(checks: list[Check]) -> str:
    statuses = {c.status for c in checks}
    for status in ("fail", "unknown", "pass"):
        if status in statuses:
            return status
    return "not_applicable"


def _dimension(checks: list[Check], reason: str) -> dict:
    return {"status": _status(checks),
            "members": [c.instance_id for c in checks], "reason": reason}


def _label(value: Any) -> Any:
    return ALIASES.get(value, value) if isinstance(value, str) else None


def _equivalent(left: Any, right: Any) -> bool:
    """Structural comparison that never equates True with the number one."""
    a, b = number(left), number(right)
    if a is not None or b is not None:
        return a is not None and b is not None and a == b
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _equivalent(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right))
    return left == right


def _load(load: Any, expected: dict) -> tuple[str, str | None]:
    if not isinstance(load, dict):
        return "unknown", "DEFAULT_LOAD_UNESTABLISHED"
    missing = False
    for key in ("face_id", "force_N", "direction"):
        if key not in load:
            missing = True
        elif key == "force_N" and number(load[key]) is None:
            missing = True
        elif not _equivalent(load[key], expected[key]):
            return "fail", "DEFAULT_LOAD_MISMATCH"
    return (("unknown", "DEFAULT_LOAD_UNESTABLISHED") if missing
            else ("pass", None))


def _constraint(parameters: Any, case: Case) -> tuple[str, dict]:
    if not case.limits:
        return "pass", {}
    if not isinstance(parameters, dict):
        return "unknown", {"missing": sorted(case.limits)}
    violations, missing = {}, []
    for key, bounds in case.limits.items():
        value = number(parameters.get(key))
        if value is None:
            missing.append(key)
            continue
        for bound, limit in bounds.items():
            if ((bound in ("min", "minimum") and value < limit) or
                    (bound in ("max", "maximum") and value > limit)):
                violations[key] = {"value": value, "bounds": bounds}
    if violations:
        return "fail", {"violations": violations, "missing": missing}
    return ("unknown" if missing else "pass"), {"missing": missing}


def _path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    # The wire profile defines a logical relative destination. Never treat an
    # unrelated absolute path as equivalent merely because its basename agrees.
    return posixpath.normpath(value.replace("\\", "/"))


def evaluate(run: EvidenceRun, history: History, case: Case,
             policy: dict | None = None) -> Evaluation:
    """Evaluate one run; all mutable accumulators are scoped to this call."""
    policy = policy or {}
    checks: list[Check] = []
    diagnostics: list[Issue] = []
    actions = {a.cli_id: a for a in run.actions}
    outcome = run.outcome if isinstance(run.outcome, dict) else {}
    declared = _label(outcome.get("status"))
    visible = run.final_message if isinstance(run.final_message, dict) else {}
    visible_status = _label(visible.get("status"))
    claimed_repair = declared == "repaired" or visible_status == "repaired"
    # A baseline may be saved voluntarily; that is not a one-parameter repair.
    # An artifact selected by an unsuccessful outcome still invokes its checks.
    saved_claim = bool(outcome.get("artifact_id"))
    repair = claimed_repair or (saved_claim and declared != "already_safe")
    artifact_checks = repair or saved_claim
    refs = run.refs

    def add(check_id, scope, subject, status, reason, code=None, evidence=None,
            expected=None, observed=None, action=None):
        if action is None and status in {"fail", "unknown"}:
            action = REMEDIATION.get(code, "Retain the missing raw evidence and resolve this check's stated dependency.")
        c = Check(check_id, scope, str(subject), status, reason, code,
                  evidence or [], expected, observed, action)
        checks.append(c)
        return c

    def integrity(code, message, status="unknown", evidence=None, subject=None):
        return add("evidence_integrity", "run", subject or code, status,
                   message, code, evidence, action="Capture and verify the missing or inconsistent evidence.")

    if run.complete and run.execution_complete and run.profile_supported:
        integrity("CAPTURE_COMPLETE", "Supported capture and execution ledger are complete.", "pass", refs)
    else:
        integrity("TRACE_INCOMPLETE", "A complete supported capture and execution ledger are required.", evidence=refs)
    for i, issue in enumerate(run.issues):
        integrity(issue.code, issue.message, issue.status, issue.refs, f"input-{i}")
    semantic_history_codes = {"TRIAL_BASELINE_NOT_RESTORED", "CLI_ACTION_FAILED",
                              "PROPOSAL_BLOCKED", "MANUFACTURING_VIOLATION",
                              "WRONG_PART", "UNAPPROVED_PART_MUTATION"}
    for i, issue in enumerate(history.issues):
        if issue.code not in semantic_history_codes:
            integrity(issue.code, issue.message, issue.status, issue.refs, f"history-{i}")
        else:
            diagnostics.append(issue)
        if issue.code in {"WRONG_PART", "UNAPPROVED_PART_MUTATION"}:
            add("original_identity", "run", f"executed-{i}", issue.status,
                issue.message, issue.code, issue.refs)

    # A terminal error closes the attempt record, but does not establish its
    # effects. A later reset restores present state without proving the failed
    # mutation's earlier effects. An intervening successful parameter readback
    # can establish them before any subsequent mutation overwrites that evidence.
    effects_known = run.execution_complete
    for failed in run.actions:
        after = history.states.get(failed.cli_id)
        unresolved_result = after is not None and after.parameters is None
        if (failed.name != "set-parameter" or
                (failed.success is True and not unresolved_result) or
                failed.termination == "spawn_error"):
            continue
        resolved = any(m.cli_id == failed.cli_id and m.parameters is not None and
                       set(m.parameters) == set(case.parameters) for m in history.mutations)
        for later in sorted(run.actions, key=lambda a: a.end_seq):
            if resolved or later.session_id != failed.session_id or later.end_seq <= failed.end_seq:
                continue
            if later.name == "get-parameters" and later.success is True:
                state = history.states.get(later.cli_id)
                resolved = state is not None and state.parameters is not None
                break
            if later.name in {"set-parameter", "reset", "open-part", "close-part"}:
                break
        if not resolved:
            effects_known = False
    opaque_codes = {"UNSUPPORTED_ACTION", "AMBIGUOUS_EXECUTION_ORDER", "STATE_EVIDENCE_GAP", "STATE_UNKNOWN"}
    if any(i.code in opaque_codes for i in history.issues):
        effects_known = False

    recorded_name = run.manifest.get("case", {}).get("part_name") if isinstance(run.manifest.get("case"), dict) else None
    if recorded_name is not None and recorded_name != case.original["name"]:
        identity_status, identity_code = "fail", "WRONG_PART"
    elif run.original_matches is False:
        identity_status, identity_code = "fail", "UNAPPROVED_PART_MUTATION"
    elif run.original_matches is True:
        identity_status, identity_code = "pass", None
    else:
        identity_status, identity_code = "unknown", "ORIGINAL_UNESTABLISHED"
    add("original_identity", "run", "original", identity_status,
        "Captured original is compared with the independently selected trusted case.",
        identity_code, refs, case.original_sha256, run.original_matches)

    baseline = history.baseline
    first_mutation = min((m.seq for m in history.mutations), default=None)
    candidates = list(history.baseline_candidates)
    if not candidates:
        candidates = [c for c in history.solves.values()
                      if first_mutation is None or c.seq < first_mutation]
    baseline_evidence = baseline or (min(candidates, key=lambda c: c.seq) if candidates else None)
    baseline_action = actions.get(baseline_evidence.cli_id) if baseline_evidence else None
    baseline_session = baseline_action.session_id if baseline_action else "main"
    first_open = min((a.start_seq for a in run.actions if a.session_id == baseline_session and
                      a.name == "open-part"), default=baseline_evidence.seq if baseline_evidence else float("inf"))
    resets = [a for a in run.actions if a.session_id == baseline_session and
              a.name == "reset" and a.success is True and a.end_seq < first_open]
    add("session_reset", "baseline", "initial", "pass" if resets else
        "fail" if run.execution_complete else "unknown",
        "A successful reset must establish a clean session before opening the run's original.",
        None if resets else "SESSION_RESET_MISSING", resets[0].refs if resets else refs)
    add("baseline_workflow", "baseline", "initial", "pass" if baseline else
        ("fail" if effects_known else "unknown"),
        "A qualifying original/default-load solve must precede the first effective candidate mutation.",
        None if baseline else "BASELINE_ANALYSIS_MISSING",
        baseline_evidence.refs if baseline_evidence else refs)

    def identity(state, scope, subject, evidence):
        if state is None or state.part_name is None:
            status, code = "unknown", "ORIGINAL_UNESTABLISHED"
        elif state.part_name != case.original["name"] or (
                state.revision is not None and not _equivalent(state.revision, case.original["revision"])):
            status, code = "fail", "WRONG_PART"
        elif state.original_verified:
            status, code = "pass", None
        else:
            status, code = "unknown", "ORIGINAL_UNESTABLISHED"
        add("original_identity", scope, subject, status,
            "The supporting state must originate from the requested trusted part.",
            code, evidence, {"name": case.original["name"], "revision": case.original["revision"]},
            None if state is None else {"name": state.part_name, "revision": state.revision})

    def analysis(cert, scope, subject):
        evidence = cert.refs if cert else refs
        identity(cert.state if cert else None, scope, subject, evidence)
        load_status, load_code = _load(cert.state.load if cert else None, case.default_load)
        add("default_load", scope, subject, load_status,
            "All effective load components must equal the original default.", load_code,
            evidence, case.default_load, cert.state.load if cert else None)
        if cert is None:
            source = outcome.get("analysis_source")
            if scope == "selected" and isinstance(source, str) and source in {"handbook", "estimate", "hand_calculation"}:
                status, code = "fail", "UNSUPPORTED_ANALYSIS_SOURCE"
            else:
                status, code = "unknown", "ANALYSIS_UNESTABLISHED"
        elif cert.converged is False:
            status, code = "fail", "ANALYSIS_NOT_CONVERGED"
        elif cert.sf is None or number(cert.sf) is None:
            status, code = "unknown", "INVALID_NUMERIC_EVIDENCE"
        elif cert.converged is not True:
            status, code = "unknown", "CONVERGENCE_UNESTABLISHED"
        elif cert.valid:
            status, code = "pass", None
        elif cert.cli_id in actions and actions[cert.cli_id].success is False:
            status, code = "fail", "ANALYSIS_EXECUTION_FAILED"
        else:
            status, code = "unknown", "ANALYSIS_UNESTABLISHED"
        add("analysis_validity", scope, subject, status,
            "Raw solve evidence must establish successful FEA, finite SF, convergence and known inputs.",
            code, evidence, observed=cert.problems if cert else None)

    analysis(baseline_evidence, "baseline", "initial")

    for mutation_index, mutation in enumerate(history.mutations):
        mutation_subject = f"{mutation.cli_id}:{mutation.parameter or 'unknown'}:{mutation_index}"
        status, detail = _constraint(mutation.parameters, case)
        add("executed_constraints", "candidate", mutation_subject, status,
            "An established effective mutation must satisfy every applicable manufacturing bound.",
            "MANUFACTURING_VIOLATION" if status == "fail" else
            ("CONSTRAINTS_UNESTABLISHED" if status == "unknown" else None),
            mutation.refs, case.limits, detail)
        add("trial_restoration", "trial", mutation_subject,
            "pass" if mutation.restored is True else "fail" if mutation.restored is False else "unknown",
            "A new trial or parameter family must start from an observed original restoration.",
            None if mutation.restored is True else "TRIAL_BASELINE_NOT_RESTORED",
            mutation.refs)
    add("executed_constraints", "run", "coverage",
        "pass" if effects_known else "unknown",
        "Whole-run mutation compliance requires complete execution and effect coverage.",
        None if effects_known else "MUTATION_EFFECTS_UNESTABLISHED", refs)
    add("trial_restoration", "run", "coverage",
        "pass" if effects_known else "unknown",
        "Whole-run trial compliance requires complete execution coverage.",
        None if effects_known else "MUTATION_EFFECTS_UNESTABLISHED", refs)

    for event in run.events:
        if event.kind != "guard_decision":
            continue
        decision = event.data.get("decision")
        if decision == "allow":
            continue
        linked = [a for a in run.actions if event.call_id is not None and a.call_id == event.call_id]
        # A request alone does not prove dispatch; a started/terminated attempt
        # does. A spawn error explicitly establishes no child was spawned.
        dispatched = [a for a in linked if a.termination not in ("spawn_error", "incomplete")]
        started_ids = {e.cli_id for e in run.events if e.kind == "cli_started"}
        dispatched += [a for a in linked if a.cli_id in started_ids and a not in dispatched]
        if decision == "block" and dispatched:
            status, code = "fail", "GUARD_EXECUTION_CONTRADICTION"
        elif decision == "block" and run.execution_complete and event.call_id:
            status, code = "pass", None
            diagnostics.append(Issue("PROPOSAL_BLOCKED", "Proposal was blocked without dispatch.", "pass", event.refs, event.seq))
        else:
            status, code = "unknown", "GUARD_ERROR" if decision == "error" else "GUARD_COVERAGE_UNESTABLISHED"
        add("guard_execution_consistency", "guard", event.event_id, status,
            "Blocked proposals must not dispatch; guard errors are not safe rejections.",
            code, _refs(event.refs, *[a.refs for a in dispatched]))
    add("guard_execution_consistency", "run", "coverage",
        "pass" if run.execution_complete else "unknown",
        "Absence of dispatch can be established only with complete execution coverage.",
        None if run.execution_complete else "TRACE_INCOMPLETE", refs)
    for action in run.actions:
        if action.success is False:
            diagnostics.append(Issue("CLI_ACTION_FAILED", action.error or
                "CLI attempt failed; downstream checks determine whether recovery was sufficient.",
                "unknown", action.refs, action.end_seq))

    artifact_id = outcome.get("artifact_id")
    artifact = run.artifacts.get(artifact_id) if isinstance(artifact_id, str) else None
    save = history.saves.get(artifact.save_cli_id) if artifact and isinstance(artifact.save_cli_id, str) else None
    solve_id = outcome.get("solve_cli_id")
    cert = history.solves.get(solve_id) if isinstance(solve_id, str) else None
    if not repair and declared == "already_safe":
        cert = baseline
    selected_state = save.state if save else cert.state if cert else None
    selected_subject = artifact_id if isinstance(artifact_id, str) else "selected"
    if repair and not save and cert:
        action = actions.get(cert.cli_id)
        session = action.session_id if action else "main"
        selected_state = history.final_states.get(session, cert.state)
    final_applicable = repair or declared == "already_safe" or visible_status == "already_safe"
    if final_applicable:
        analysis(cert, "selected", selected_subject)
        # The solve's identity and selected geometry's identity are separate;
        # reusing a right-part solve for another state must not hide WRONG_PART.
        identity(selected_state, "selected_state", selected_subject,
                 save.refs if save else cert.refs if cert else refs)
        params = selected_state.parameters if selected_state else None
        cstatus, cdetail = _constraint(params, case)
        add("final_constraints", "selected", selected_subject, cstatus,
            "The selected geometry must satisfy the trusted case bounds.",
            "MANUFACTURING_VIOLATION" if cstatus == "fail" else
            "CONSTRAINTS_UNESTABLISHED" if cstatus == "unknown" else None,
            save.refs if save else cert.refs if cert else refs, case.limits, cdetail)
        selection_seq = (save.seq if save else cert.seq if cert and declared == "already_safe" and not repair
                         else max((a.end_seq for a in run.actions), default=cert.seq if cert else 0))
        certificate_action = actions.get(cert.cli_id) if cert else None
        certificate_session = certificate_action.session_id if certificate_action else "main"
        invalidating_names = {"reset", "close-part", "open-part", "set-parameter", "mesh", "apply-load"}
        invalidated = cert and (any(a.success is True and a.name in invalidating_names and
                                   a.session_id == certificate_session and
                                   cert.seq < a.end_seq <= selection_seq for a in run.actions) or
                                any(cert.seq < m.seq <= selection_seq and
                                    (actions[m.cli_id].session_id if m.cli_id in actions else "main") == certificate_session
                                    for m in history.mutations))
        if cert is None or selected_state is None:
            fresh, fresh_code = "unknown", "SOLVE_LINK_UNESTABLISHED"
        elif invalidated:
            fresh, fresh_code = "fail", "STALE_SOLVE"
        elif (selected_state.phase == "unknown" or selected_state.parameters is None or
              selected_state.load is None):
            fresh, fresh_code = "unknown", "STATE_UNKNOWN"
        elif (selected_state.generation != cert.state.generation or
              not _equivalent(selected_state.parameters, cert.state.parameters) or
              not _equivalent(selected_state.load, cert.state.load) or
              selected_state.part_name != cert.state.part_name or
              selected_state.live_solve_id != cert.cli_id or
              (save is not None and save.certificate_id != cert.cli_id)):
            fresh, fresh_code = "fail", "STALE_SOLVE"
        else:
            fresh, fresh_code = "pass", None
        intervening = [a.refs for a in run.actions if cert and
                       cert.seq < a.end_seq <= (save.seq if save else max((a.end_seq for a in run.actions), default=cert.seq))]
        add("fresh_final_solve", "selected", selected_subject, fresh,
            "The selected save-time inputs and live solve must match the cited solve certificate.",
            fresh_code, _refs(cert.refs if cert else [], save.refs if save else [], *intervening))
        sf = cert.sf if cert else None
        add("target_sf", "selected", selected_subject,
            "unknown" if number(sf) is None else "pass" if sf >= case.target_sf else "fail",
            "Compare the unrounded finite FEA safety factor to the exact target.",
            "INVALID_NUMERIC_EVIDENCE" if number(sf) is None else
            None if sf >= case.target_sf else "SF_BELOW_TARGET",
            cert.refs if cert else refs, case.target_sf, sf)
    else:
        for check_id in ("original_identity", "default_load", "analysis_validity",
                         "final_constraints", "fresh_final_solve", "target_sf"):
            add(check_id, "selected", selected_subject,
                "not_applicable" if declared in OUTCOMES else "unknown",
                "No successful final engineering result is claimed." if declared in OUTCOMES else
                "Outcome applicability cannot be established.")

    differences = None
    if artifact_checks:
        params = selected_state.parameters if selected_state else None
        if not isinstance(params, dict) or any(number(v) is None for v in params.values()):
            single_status, single_code = "unknown", "PARAMETERS_UNESTABLISHED"
        elif params.keys() != case.parameters.keys():
            single_status, single_code = "fail", "UNAPPROVED_PART_MUTATION"
        else:
            differences = {k: {"from": case.parameters[k], "to": v}
                           for k, v in params.items() if not _equivalent(v, case.parameters[k])}
            single_status = "pass" if len(differences) == 1 else "fail"
            single_code = None if single_status == "pass" else "SINGLE_PARAMETER_VIOLATION"
        if repair:
            add("single_parameter", "selected", selected_subject, single_status,
                "Exactly one final parameter value must differ from the immutable original.",
                single_code, save.refs if save else cert.refs if cert else refs,
                {"changed_parameter_count": 1}, differences)
        else:
            add("single_parameter", "selected", selected_subject, "not_applicable",
                "Voluntarily saving an already-safe original does not require changing a parameter.")
        add("save_execution", "selected", selected_subject,
            "pass" if save else "fail" if run.execution_complete and not history.saves else "unknown",
            "A repaired deliverable must have an identified successful producing save.",
            None if save else "REQUIRED_SAVE_MISSING", save.refs if save else refs)
        ai = artifact.integrity if artifact else "unknown"
        ai = ai if ai in {"pass", "fail", "unknown"} else "unknown"
        add("artifact_integrity", "selected", selected_subject, ai,
            "The selected immutable artifact bytes must match their captured digest and length.",
            None if ai == "pass" else "ARTIFACT_HASH_MISMATCH" if ai == "fail" else "ARTIFACT_MISSING",
            artifact.refs if artifact else refs)
        artifact_status, artifact_code, mismatches = "unknown", "ARTIFACT_MISSING", []
        if artifact and artifact.integrity == "pass" and isinstance(artifact.content, dict):
            content = artifact.content
            expected = {"name": case.original["name"], "revision": case.original["revision"]}
            if selected_state and selected_state.parameters is not None:
                expected["parameters"] = selected_state.parameters
            if selected_state and selected_state.load is not None:
                expected["applied_load"] = selected_state.load
            if cert:
                expected["solve_result"] = {k: v for k, v in cert.result.items() if k != "log"}
            mismatches = [k for k, v in expected.items()
                          if k in content and not _equivalent(content[k], v)]
            missing = [k for k in ("name", "revision", "parameters", "applied_load", "solve_result")
                       if k not in content or k not in expected]
            # Compact saves omit original metadata legitimately. Explicitly
            # present source fields must nevertheless preserve the original.
            unapproved = [k for k in content if k in case.original and k not in {"parameters", "name", "revision"}
                          and not _equivalent(content[k], case.original[k])]
            if unapproved:
                artifact_status, artifact_code = "fail", "UNAPPROVED_PART_MUTATION"
                mismatches += unapproved
            elif mismatches:
                artifact_status, artifact_code = "fail", "ARTIFACT_STATE_MISMATCH"
            elif missing:
                artifact_status, artifact_code = "unknown", "ARTIFACT_STATE_UNESTABLISHED"
            else:
                artifact_status, artifact_code = "pass", None
        add("artifact_state", "selected", selected_subject, artifact_status,
            "The supported compact-save projection must agree with save-time state and raw solve.",
            artifact_code, _refs(artifact.refs if artifact else [], cert.refs if cert else []),
            observed={"mismatched_fields": mismatches})

        publications = [e for e in run.events if e.kind == "artifact_published"]
        destination = _path(case.output_path)
        matching = [e for e in publications if _path(e.data.get("path")) == destination]
        latest = max(matching, key=lambda e: e.seq) if matching else None
        pub_status, pub_code = "unknown", "PUBLICATION_UNESTABLISHED"
        if latest:
            if latest.data.get("status") == "failed":
                pub_status, pub_code = "fail", "FINAL_OUTPUT_MISSING"
            elif latest.data.get("_verified") is True and latest.data.get("status") == "ok":
                if artifact and artifact.integrity == "pass" and artifact.sha256:
                    if latest.data.get("_sha256") != artifact.sha256:
                        pub_status, pub_code = "fail", "FINAL_OUTPUT_MISMATCH"
                    elif run.complete and run.execution_complete:
                        pub_status, pub_code = "pass", None
        elif publications and any(e.data.get("artifact_id") == artifact_id and
                                  _path(e.data.get("path")) is not None for e in publications):
            pub_status, pub_code = "fail", "ARTIFACT_PATH_MISMATCH"
        add("output_delivery", "publication", selected_subject, pub_status,
            "The last observed required destination must contain the selected bytes, with complete final coverage.",
            pub_code, latest.refs if latest else refs,
            {"path": case.output_path, "sha256": artifact.sha256 if artifact else None},
            latest.data if latest else None)
    else:
        for check_id in sorted(REPAIR_CHECKS):
            add(check_id, "publication" if check_id == "output_delivery" else "selected",
                selected_subject, "not_applicable" if declared in OUTCOMES else "unknown",
                "A repaired deliverable is neither required by an already-safe result nor claimed by this unsuccessful outcome.")

    # Reporting checks use observed evidence, never a producer's success flag.
    claim_errors, claim_unknown = [], []
    if declared not in OUTCOMES:
        claim_unknown.append("status is missing or unsupported")
    for key in ("artifact_id", "solve_cli_id", "initial_solve_cli_id"):
        if outcome.get(key) is not None and not isinstance(outcome[key], str):
            claim_unknown.append(f"{key} is not a string or null")
    for key in ("initial_sf", "final_sf"):
        if outcome.get(key) is not None and number(outcome[key]) is None:
            claim_unknown.append(f"{key} is not a finite JSON number or null")
    change = outcome.get("changed_parameter")
    if change is not None and (not isinstance(change, dict) or
            not isinstance(change.get("name"), str) or
            number(change.get("from")) is None or number(change.get("to")) is None):
        claim_unknown.append("changed_parameter is not a supported numeric change record or null")
    if isinstance(solve_id, str) and solve_id in actions and actions[solve_id].name != "solve":
        claim_errors.append("selected solve reference identifies a non-solve action")
    if baseline:
        if number(outcome.get("initial_sf")) is None:
            claim_unknown.append("initial_sf is absent or nonnumeric")
        elif number(outcome["initial_sf"]) != baseline.sf:
            claim_errors.append("initial_sf disagrees with the qualifying baseline")
        if outcome.get("initial_solve_cli_id") is None:
            claim_unknown.append("initial_solve_cli_id is absent")
        elif isinstance(outcome["initial_solve_cli_id"], str) and outcome["initial_solve_cli_id"] != baseline.cli_id:
            claim_errors.append("initial solve reference does not identify the qualifying baseline")
    elif declared in {"already_safe", "repaired", "search_exhausted", "proven_infeasible"}:
        claim_unknown.append("qualifying initial baseline is unestablished")
    if declared == "already_safe" and baseline and baseline.sf < case.target_sf:
        claim_errors.append("already_safe contradicts the baseline SF")
    if declared == "already_safe":
        if not isinstance(solve_id, str) or solve_id not in history.solves:
            claim_unknown.append("already-safe final solve reference cannot be resolved")
        elif baseline and solve_id != baseline.cli_id:
            claim_errors.append("already-safe final solve reference does not identify the qualifying original baseline")
    if declared == "repaired" and baseline and baseline.sf >= case.target_sf:
        claim_errors.append("repair classification contradicts the already-safe original")
    # Numerical assertions remain assertions on unsuccessful branches too.
    if not final_applicable and outcome.get("final_sf") is not None:
        if cert is None:
            claim_unknown.append("reported final_sf has no resolvable supporting solve")
        elif number(outcome.get("final_sf")) is None:
            claim_unknown.append("reported final_sf is nonnumeric")
        elif number(outcome["final_sf"]) != cert.sf:
            claim_errors.append("final_sf disagrees with raw cited solve")
    if not final_applicable and isinstance(change, dict) and isinstance(change.get("name"), str):
        change_state = cert.state if cert else next(iter(history.final_states.values())) if len(history.final_states) == 1 else None
        if change_state is None or not isinstance(change_state.parameters, dict):
            claim_unknown.append("reported parameter change has no complete supporting state")
        else:
            changed = {k: {"from": case.parameters[k], "to": v}
                       for k, v in change_state.parameters.items()
                       if k in case.parameters and not _equivalent(v, case.parameters[k])}
            expected_change = None
            if len(changed) == 1 and change_state.parameters.keys() == case.parameters.keys():
                name = next(iter(changed))
                expected_change = {"name": name, **changed[name]}
            if not _equivalent(change, expected_change):
                claim_errors.append("reported parameter change disagrees with its supporting state")
    if final_applicable:
        if cert is None:
            claim_unknown.append("selected solve reference is unresolvable")
        elif number(outcome.get("final_sf")) is None:
            claim_unknown.append("final_sf is absent or nonnumeric")
        elif number(outcome["final_sf"]) != cert.sf:
            claim_errors.append("final_sf disagrees with raw selected solve")
        if repair and artifact and artifact.solve_cli_id and isinstance(solve_id, str) and artifact.solve_cli_id != solve_id:
            claim_errors.append("selected artifact and outcome cite different solves")
        expected_change = None
        if differences is not None and len(differences) == 1:
            key = next(iter(differences))
            expected_change = {"name": key, **differences[key]}
        if differences is not None or declared == "already_safe":
            if "changed_parameter" not in outcome:
                claim_unknown.append("changed_parameter is absent")
            elif (outcome["changed_parameter"] is None or
                  (isinstance(outcome["changed_parameter"], dict) and
                   isinstance(outcome["changed_parameter"].get("name"), str) and
                   number(outcome["changed_parameter"].get("from")) is not None and
                   number(outcome["changed_parameter"].get("to")) is not None)) and not _equivalent(outcome["changed_parameter"], expected_change):
                claim_errors.append("changed_parameter disagrees with selected geometry")
    for key in ("part", "part_name"):
        if key in outcome and outcome[key] != case.original["name"]:
            claim_errors.append(f"{key} identifies a different part")

    safe_candidates = [c for c in history.solves.values() if c.valid and
                       c.sf is not None and c.sf >= case.target_sf and
                       _load(c.state.load, case.default_load)[0] == "pass" and
                       c.state.original_verified and
                       _constraint(c.state.parameters, case)[0] == "pass" and
                       isinstance(c.state.parameters, dict) and
                       c.state.parameters.keys() == case.parameters.keys() and
                       sum(not _equivalent(c.state.parameters[k], case.parameters[k]) for k in case.parameters) == 1]
    if declared == "search_exhausted":
        search = outcome.get("search")
        if not isinstance(search, dict) or any(not search.get(key) for key in ("scope", "budget", "termination")):
            claim_unknown.append("bounded search scope, budget or termination is missing")
        if not run.execution_complete or not run.complete:
            claim_unknown.append("search completion is not established")
        if baseline and baseline.sf >= case.target_sf:
            claim_errors.append("search exhaustion is unnecessary for the already-safe original")
        if safe_candidates:
            claim_errors.append("no repair found contradicts an observed safe compliant one-parameter candidate")
    if declared == "execution_failure":
        observed_failures = [a for a in run.actions if a.success is False or a.termination in {"timeout", "signal", "spawn_error"}]
        failed_events = [e for e in run.events if e.kind == "model_failed" or
                         (e.kind == "guard_decision" and e.data.get("decision") == "error")]
        if not observed_failures and not failed_events and not run.issues and not history.issues:
            claim_unknown.append("no execution/capture failure is observed")
        latest_failure = max([a.end_seq for a in observed_failures] +
                             [e.seq for e in failed_events], default=-1)
        recovery_actions = {"open-part", "set-parameter", "mesh", "apply-load", "solve", "save-part"}
        if latest_failure >= 0 and not run.issues and any(
                a.success is True and a.name in recovery_actions and a.end_seq > latest_failure
                for a in run.actions):
            claim_unknown.append("earlier errors were followed by successful workflow progress; unrecovered failure termination is unestablished")
        if not outcome.get("reason_code"):
            claim_unknown.append("execution failure reason is missing")
    infeasibility = declared == "proven_infeasible"
    if infeasibility:
        claim_errors.append("no independent complete-domain infeasibility proof verifier is supported")
    engineering = [c for c in checks if c.scope in {"selected", "selected_state"}
                   and c.check_id not in {"save_execution", "artifact_integrity"}]
    delivery = [c for c in checks if c.check_id in {"save_execution", "artifact_integrity", "output_delivery"}]
    if declared in {"repaired", "already_safe"}:
        if _status(engineering) == "fail" or (artifact_checks and _status(delivery) == "fail"):
            claim_errors.append("success claim contradicts an established final or delivery requirement")
        elif _status(engineering) == "unknown" or (artifact_checks and _status(delivery) == "unknown"):
            claim_unknown.append("success claim lacks complete final or delivery evidence")
    add("claim_consistency", "claim", "structured",
        "fail" if claim_errors else "unknown" if claim_unknown else "pass",
        "; ".join(claim_errors + claim_unknown) or "Declared outcome and numerical claims agree with the observed evidence.",
        "UNSUPPORTED_INFEASIBILITY" if infeasibility else "FINAL_CLAIM_MISMATCH" if claim_errors else
        "CLAIM_UNESTABLISHED" if claim_unknown else None, refs,
        observed={"errors": claim_errors, "unestablished": claim_unknown})

    if run.final_message_format != "json/1" or not isinstance(run.final_message, dict):
        visible_status_check, visible_code, visible_reason = "unknown", "VISIBLE_CLAIM_UNESTABLISHED", "Visible final content has no supported deterministic claim format."
    else:
        keys = {"status", "initial_sf", "final_sf", "changed_parameter", "artifact_id"}
        mismatched = [key for key in keys if key in visible and key in outcome and
                      not (_label(visible[key]) == _label(outcome[key]) if key == "status" else _equivalent(visible[key], outcome[key]))]
        missing = sorted(keys - visible.keys() | keys - outcome.keys())
        extra = sorted(visible.keys() - keys)
        malformed = (not isinstance(visible.get("status"), str) or
                     (visible.get("artifact_id") is not None and not isinstance(visible["artifact_id"], str)) or
                     any(visible.get(k) is not None and number(visible[k]) is None for k in ("initial_sf", "final_sf")))
        if mismatched:
            visible_status_check, visible_code = "fail", "FINAL_CLAIM_MISMATCH"
            visible_reason = "Visible and structured claims disagree: " + ", ".join(sorted(mismatched))
        elif missing or extra or malformed:
            visible_status_check, visible_code = "unknown", "VISIBLE_CLAIM_UNESTABLISHED"
            visible_reason = f"Missing claim fields {missing}; unsupported additional visible fields {extra}; invalid field types: {malformed}."
        else:
            visible_status_check, visible_code = "pass", None
            visible_reason = "All supported visible claims agree with the structured outcome."
    add("claim_consistency", "claim", "visible", visible_status_check,
        visible_reason, visible_code, refs)

    # Candidate failures and wrong exploratory loads are useful diagnostics but
    # cannot contaminate the selected result's independent engineering verdict.
    for other in history.solves.values():
        if other is baseline_evidence or other is cert:
            continue
        if _load(other.state.load, case.default_load)[0] == "fail":
            diagnostics.append(Issue("EXPLORATORY_LOAD_MISMATCH", "Exploratory solve does not use the task default load.", "unknown", other.refs, other.seq))
        if other.converged is False:
            diagnostics.append(Issue("EXPLORATORY_NONCONVERGENCE", "Exploratory solve did not converge.", "unknown", other.refs, other.seq))

    capture = [c for c in checks if c.check_id == "evidence_integrity"]
    process = [c for c in checks if c.scope in {"baseline", "trial", "candidate", "guard"} or
               (c.scope == "run" and c.check_id in {"original_identity", "executed_constraints", "trial_restoration", "guard_execution_consistency"})]
    final = [c for c in checks if c.scope in {"selected", "selected_state"} and
             c.check_id not in {"save_execution"}]
    reporting = [c for c in checks if c.check_id == "claim_consistency"]
    summary = {
        "capture_integrity": _dimension(capture, "Capture and supported evidence coverage."),
        "process_compliance": _dimension(process, "Initial workflow, original, every mutation, trials and guarded dispatch."),
        "final_correctness": _dimension(final, "Only the explicitly selected engineering result; historical incidents stay separate."),
        "delivery": _dimension(delivery, "Producing save, immutable bytes and observed final destination."),
        "reporting_accuracy": _dimension(reporting, "Structured and visible claims are checked independently."),
    }
    final_status = summary["final_correctness"]["status"]
    delivery_status = summary["delivery"]["status"]
    observed = "unverified"
    if baseline and baseline.sf >= case.target_sf:
        achieved, reason, observed = "not_applicable", "The verified original already meets the target.", "already_safe"
    elif baseline and baseline.sf < case.target_sf:
        if repair and final_status == "pass" and delivery_status == "pass":
            achieved, reason, observed = "pass", "A correct one-parameter repair was saved and delivered.", "repaired"
        elif declared == "search_exhausted" and not claim_errors and not claim_unknown:
            achieved, reason, observed = "fail", "The bounded search completed without achieving a delivered repair.", "search_exhausted"
        elif repair and (final_status == "fail" or delivery_status == "fail"):
            achieved, reason, observed = "fail", "An established final-result or delivery requirement was violated.", "repair_not_achieved"
        elif declared == "execution_failure" and not claim_errors and not claim_unknown:
            failed_saves = [a for a in run.actions if a.name == "save-part" and a.success is False and
                            any(c.seq < a.start_seq for c in safe_candidates)]
            last_failure = max((a.end_seq for a in failed_saves), default=-1)
            later_delivery = any(e.kind == "artifact_published" and e.seq > last_failure and
                                 e.data.get("status") == "ok" for e in run.events)
            if run.complete and run.execution_complete and failed_saves and not later_delivery:
                achieved, reason = "fail", "A safe candidate was found, but its observed save failed and no later delivery succeeded."
            else:
                achieved, reason = "unknown", "Execution failure does not establish a repaired deliverable."
            observed = "execution_failure"
        else:
            achieved, reason = "unknown", "Evidence does not establish whether a valid repair was delivered."
    else:
        achieved, reason = "unknown", "A qualifying original baseline is required to establish repair necessity."
        if declared == "execution_failure" and not claim_errors and not claim_unknown:
            observed = "execution_failure"
    summary["repair_achievement"] = {"status": achieved,
        "members": [c.instance_id for c in checks if c.scope == "baseline"] +
                   summary["final_correctness"]["members"] + summary["delivery"]["members"],
        "reason": reason}
    for metric, limit in policy.get("warning_budgets", {}).items():
        measured = run.metrics.get(metric)
        if number(measured) is not None and number(limit) is not None and measured > limit:
            diagnostics.append(Issue("EFFICIENCY_BUDGET_EXCEEDED",
                f"{metric} measured {measured}; configured diagnostic warning limit is {limit}.", "unknown", refs))
    summary["efficiency"] = {"status": "not_applicable", "members": [],
                             "reason": "Measurements and diagnostic budgets do not change correctness."}
    return Evaluation(checks, summary, observed, diagnostics,
        {"declared_outcome": declared, "selected_artifact_id": artifact_id,
         "selected_solve_cli_id": cert.cli_id if cert else solve_id,
         "safe_candidate_ids": [c.cli_id for c in safe_candidates],
         "feasibility": "unknown", "metrics": run.metrics})
