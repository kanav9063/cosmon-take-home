"""Reconstruct only state established by recorded PartLab CLI observations.

This module does not execute the CLI or consume producer verdicts.  A live
analysis is deliberately more fragile than an immutable saved certificate.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from eval_types import (
    Action, Case, Certificate, EvidenceRun, History, Issue, Mutation, State,
    Save, number,
)


READ_ONLY = frozenset({
    "list-parts", "get-parameters", "get-active-part", "list-features",
    "get-safety-factor", "get-max-stress", "get-solve-log", "get-feature",
    "state-dir", "compute-stress-from-handbook", "--help", "help",
})
STATE_READBACKS = frozenset({"get-parameters", "get-active-part", "get-safety-factor"})
KNOWN = READ_ONLY | {"reset", "close-part", "open-part", "set-parameter",
                     "mesh", "apply-load", "solve", "save-part"}


@dataclass
class _Session:
    state: State = field(default_factory=State)
    # An original open is not a proved restoration until a raw parameter
    # readback confirms it.  IDs, rather than values alone, identify restores.
    open_id: str | None = None
    open_seq: int | None = None
    restore_id: str | None = None
    restore_known: bool = False
    used_restore: str | None = None
    trial_label: str | None = None
    last_parameters: dict | None = None
    pending: list[tuple[Action, State, bool, str | None]] = field(default_factory=list)
    candidate_since_open: bool = False


def _parameters(value: Any, case: Case) -> dict | None:
    if not isinstance(value, dict) or set(value) != set(case.parameters):
        return None
    parsed = {key: number(item) for key, item in value.items()}
    return None if any(item is None for item in parsed.values()) else parsed


def _load(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    force = number(value.get("force_N"))
    face, direction = value.get("face_id"), value.get("direction")
    if force is None or not isinstance(face, str) or not face or not isinstance(direction, str) or not direction:
        return None
    return {"face_id": face, "force_N": force, "direction": direction}


def _arg_number(value: str) -> Decimal | None:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _arguments(argv: list[str], options: frozenset[str]) -> tuple[list[str], dict[str, str], bool]:
    """Separate known value options from positionals without invoking a shell.

    The recorded result remains authoritative.  This only checks consistency
    with explicit requested settings; omission never invents an accepted value.
    """
    positional, settings = [], {}
    args = iter(argv[2:])
    for argument in args:
        option, equals, value = argument.partition("=")
        if option in options:
            if option in settings:
                return positional, settings, False
            if not equals:
                value = next(args, None)
            if value is None:
                return positional, settings, False
            settings[option] = value
        elif argument.startswith("--"):
            return positional, settings, False
        else:
            positional.append(argument)
    return positional, settings, True


def reconstruct(run: EvidenceRun, case: Case) -> History:
    """Reduce ordered raw actions, keeping uncertainty and historical evidence.

    ``states`` and ``before`` contain independent snapshots keyed by CLI ID.
    ``baseline_candidates`` includes invalid original analysis attempts, but
    ``baseline`` requires a valid, original/default solve before any effective
    candidate mutation or unaccounted-for preceding execution.
    """
    history = History()
    sessions: dict[str, _Session] = {}
    first_effective_mutation = False
    baseline_history_known = True

    def issue(code, message, action=None, status="unknown", refs=None, seq=None):
        history.issues.append(Issue(
            code, message, status,
            list(action.refs if action is not None else (refs or [])),
            action.end_seq if action is not None else seq,
        ))

    def session(name):
        if name not in sessions:
            sessions[name] = _Session()
        return sessions[name]

    def invalidate(ctx, scope, refs=()):
        state = ctx.state
        state.live_solve_id = None
        if scope == "solve":
            if state.phase == "solved":
                state.phase = "loaded" if state.load is not None else "unknown"
            return
        state.generation += 1
        state.load = None
        state.load_id = None
        if scope in {"mesh", "geometry", "all"}:
            state.mesh_id = None
        if scope in {"geometry", "all"}:
            state.parameters = None
            state.restored = False
            ctx.restore_known = False
            ctx.restore_id = None
            ctx.open_id = None
        if scope == "all":
            state.part_name = None
            state.revision = None
            state.original_verified = False
            state.trial_parameter = None
            ctx.last_parameters = None
        state.phase = "unknown"
        state.refs = list(refs)

    def record_mutation(ctx, action, parameter, params, previous, *, failed=False,
                        restored_override=None):
        nonlocal first_effective_mutation
        state = ctx.state
        label = action.trial_id or ctx.trial_label
        new_trial = label is not None and state.trial_id is not None and label != state.trial_id
        new_family = state.trial_parameter is not None and parameter != state.trial_parameter
        if restored_override is not None:
            restored = restored_override
        elif not ctx.restore_known:
            restored = None
        elif new_trial or new_family:
            restored = ctx.restore_id is not None and ctx.restore_id != ctx.used_restore
        else:
            restored = state.restored and ctx.restore_id is not None
        history.mutations.append(Mutation(
            action.cli_id, action.end_seq, deepcopy(params), parameter,
            restored, list(action.refs), failed,
        ))
        if restored is False:
            issue("TRIAL_BASELINE_NOT_RESTORED",
                  "A parameter family or independent trial began without a new original restoration.",
                  action, "fail")
        effective = (previous is None or parameter not in previous or
                     params is None or previous.get(parameter) != params.get(parameter))
        if effective:
            first_effective_mutation = True
        ctx.candidate_since_open = True
        state.trial_id = label
        state.trial_parameter = parameter
        state.restored = restored is True
        if ctx.restore_id is not None:
            ctx.used_restore = ctx.restore_id

    def malformed(ctx, action, message, scope):
        issue("CLI_RESULT_INVALID", message, action)
        invalidate(ctx, scope, action.refs)

    # Events that do not carry raw execution never mutate state.  In particular,
    # tool proposals, guards, observed summaries and artifact claims are not CLI
    # observations.  Explicit gaps are reducer barriers supplied by the adapter.
    stream = [(a.end_seq, 1, i, "action", a) for i, a in enumerate(run.actions)]
    stream += [(e.seq, 0, i, "event", e) for i, e in enumerate(run.events)
               if e.kind in {"evidence_gap", "trial_started"}]
    for _, _, _, kind, item in sorted(stream, key=lambda row: row[:3]):
        ctx = session(item.session_id)
        state = ctx.state
        if kind == "event":
            if item.kind == "evidence_gap":
                baseline_history_known = False
                scope = item.data.get("scope", "all")
                if scope not in {"all", "geometry", "mesh", "load", "solve"}:
                    scope = "all"
                invalidate(ctx, scope, item.refs)
                issue("STATE_EVIDENCE_GAP", item.data.get("reason", "Execution history has a gap."),
                      refs=item.refs, seq=item.seq)
            else:
                ctx.trial_label = item.trial_id
                restoration = item.data.get("restoration_cli_id")
                if restoration is not None and restoration != ctx.restore_id:
                    issue("TRIAL_RESTORATION_UNVERIFIED",
                          "Trial restoration does not reference the currently observed original open and readback.",
                          refs=item.refs, seq=item.seq)
                # The label records intent; the next actual set proves whether
                # a new restoration was performed.  Do not clear the old label.
            continue

        action = item
        before = deepcopy(state)
        history.before[action.cli_id] = before
        result = action.result
        name = action.name
        scope = ("geometry" if name == "set-parameter" else
                 "mesh" if name == "mesh" else
                 "load" if name == "apply-load" else
                 "solve" if name == "solve" else "all")

        if name not in KNOWN:
            baseline_history_known = False
            invalidate(ctx, "all", action.refs)
            issue("UNSUPPORTED_ACTION", f"Unsupported CLI command {name!r}; its effects are unknown.", action)
        elif action.uncertain_order:
            if name == "set-parameter" and action.success is True and isinstance(result, dict):
                param, value = result.get("name"), number(result.get("new_value"))
                if isinstance(param, str) and value is not None:
                    history.mutations.append(Mutation(action.cli_id, action.end_seq,
                                                     {param: value}, param, None, list(action.refs)))
                    first_effective_mutation = True
            baseline_history_known = False
            invalidate(ctx, "all", action.refs)
            issue("AMBIGUOUS_EXECUTION_ORDER", "Overlapping execution cannot establish an ordered state transition.", action)
        elif action.success is not True:
            issue("CLI_ACTION_FAILED", action.error or f"{name} did not establish a successful result.",
                  action, "diagnostic")
            if name not in READ_ONLY and name != "save-part" and action.termination != "spawn_error":
                if name == "set-parameter":
                    ctx.pending.append((action, before, ctx.restore_known, ctx.restore_id))
                    baseline_history_known = False
                invalidate(ctx, scope, action.refs)
            if name == "solve":
                history.solves[action.cli_id] = Certificate(
                    action.cli_id, action.end_seq, deepcopy(state),
                    deepcopy(result) if isinstance(result, dict) else {},
                    number(result.get("safety_factor")) if isinstance(result, dict) else None,
                    result.get("converged") if isinstance(result, dict) and type(result.get("converged")) is bool else None,
                    False, list(action.refs), ["CLI_ACTION_FAILED"],
                )
                cert = history.solves[action.cli_id]
                if not first_effective_mutation and state.part_name == case.original["name"]:
                    history.baseline_candidates.append(cert)
        elif name in READ_ONLY - STATE_READBACKS:
            # Lists, strings and empty help output are legitimate.  None of
            # these commands establishes or invalidates solver input state.
            pass
        elif not isinstance(result, dict):
            if name in STATE_READBACKS or name == "save-part":
                issue("CLI_RESULT_INVALID", "A successful CLI result must be an object.", action)
            else:
                malformed(ctx, action, "A successful CLI result must be an object.", scope)
        elif name in {"reset", "close-part"}:
            generation = state.generation + 1
            ctx = _Session(state=State(phase="closed", generation=generation, refs=list(action.refs)),
                           restore_known=True)
            sessions[action.session_id] = ctx
            state = ctx.state
        elif name == "open-part":
            generation = state.generation + 1
            part, revision = result.get("name"), result.get("revision")
            valid_identity = (isinstance(part, str) and bool(part) and
                              type(revision) is int and
                              isinstance(result.get("material"), dict) and
                              _load(result.get("default_load")) is not None)
            matching = (valid_identity and part == case.original["name"] and
                        revision == case.original["revision"] and
                        result["material"] == case.original["material"] and
                        _load(result["default_load"]) == _load(case.default_load))
            argument_matches = len(action.argv) >= 3 and action.argv[2] == part
            ctx = _Session(state=State(
                part_name=part if isinstance(part, str) else None,
                revision=revision, phase="open" if valid_identity else "unknown",
                generation=generation,
                original_verified=bool(matching and argument_matches and
                                       run.original_matches is True and run.profile_supported),
                refs=list(action.refs),
            ), open_id=action.cli_id, open_seq=action.end_seq,
                restore_known=False)
            sessions[action.session_id] = ctx
            state = ctx.state
            if not valid_identity:
                issue("CLI_RESULT_INVALID", "Open result lacks required identity, material or default-load fields.", action)
            elif not matching:
                issue("WRONG_PART" if part != case.original["name"] else "UNAPPROVED_PART_MUTATION",
                      "Opened part metadata does not match the independently trusted original.", action, "fail")
            if valid_identity and not argument_matches:
                issue("EVIDENCE_CONTRADICTION", "Open result identity differs from the requested part.", action, "fail")
        elif name == "get-parameters":
            params = _parameters(result, case)
            if params is None:
                issue("CLI_RESULT_INVALID", "Parameter readback must contain the complete finite original parameter schema.", action)
            elif state.part_name is None:
                issue("STATE_UNKNOWN", "A parameter readback without a known active part cannot bind geometry.", action)
            else:
                previous = deepcopy(state.parameters if state.parameters is not None else ctx.last_parameters)
                if (previous is None and state.original_verified and
                        ((ctx.open_id is not None and not ctx.candidate_since_open) or ctx.pending)):
                    expected = _parameters(case.parameters, case)
                    if params != expected:
                        previous = expected
                        if not ctx.pending:
                            issue("UNAPPROVED_PART_MUTATION",
                                  "First parameter readback contradicts the freshly opened trusted original.",
                                  action, "fail")
                changed = [] if previous is None else [key for key in params if params[key] != previous.get(key)]
                if changed:
                    pending = ctx.pending[-1] if len(ctx.pending) == 1 else None
                    cause = pending[0] if pending else action
                    restored = None
                    # Attribute the cause to the failed command, but retain the
                    # later raw readback that establishes its actual effect.
                    if pending:
                        cause = deepcopy(cause)
                        cause.refs.extend(action.refs)
                    saved_restore_id = pending[3] if pending else ctx.restore_id
                    prior_family = pending[1].trial_parameter if pending else None
                    all_restored = bool(pending and pending[2] and pending[1].restored)
                    for param in changed:
                        if pending and pending[2]:
                            prior_trial = pending[1].trial_id
                            new_trial = bool(cause.trial_id is not None and prior_trial is not None
                                             and cause.trial_id != prior_trial)
                            restored = bool(pending[1].restored and not new_trial
                                            and prior_family in {None, param})
                        record_mutation(ctx, cause, param, params, previous,
                                        failed=bool(ctx.pending), restored_override=restored)
                        prior_family = param
                        all_restored = all_restored and restored is True
                    if not ctx.pending:
                        issue("EVIDENCE_CONTRADICTION", "Parameter readback differs from the preceding established geometry.", action, "fail")
                    invalidate(ctx, "geometry", action.refs)
                    if pending and all_restored:
                        # Recovery repairs current knowledge.  It does not
                        # erase the historical failed call or its mutation.
                        state.restored = True
                        ctx.restore_known = True
                        ctx.restore_id = saved_restore_id
                        ctx.used_restore = ctx.restore_id
                state.parameters = params
                ctx.last_parameters = deepcopy(params)
                if (state.original_verified and ctx.open_id is not None and
                        not ctx.candidate_since_open and params == _parameters(case.parameters, case)):
                    state.restored = True
                    ctx.restore_known = True
                    ctx.restore_id = ctx.open_id
                state.refs = list(action.refs)
                ctx.pending.clear()
        elif name == "set-parameter":
            param = result.get("name")
            value, previous_value = number(result.get("new_value")), number(result.get("previous_value"))
            if not isinstance(param, str) or not param or value is None or previous_value is None:
                baseline_history_known = False
                ctx.pending.append((action, before, ctx.restore_known, ctx.restore_id))
                malformed(ctx, action, "Set result lacks a parameter and finite previous/accepted values.", "geometry")
            else:
                params = deepcopy(state.parameters) if state.parameters is not None else {}
                previous = deepcopy(state.parameters)
                consistent = previous is None or previous.get(param) == previous_value
                if not consistent:
                    issue("EVIDENCE_CONTRADICTION", "Accepted set previous_value conflicts with established parameters.", action, "fail")
                if (len(action.argv) < 4 or action.argv[2] != param or
                        _arg_number(action.argv[3]) != value):
                    issue("EVIDENCE_CONTRADICTION", "Accepted set result differs from its requested name or value.", action, "fail")
                params[param] = value
                record_mutation(ctx, action, param, params,
                                previous if previous is not None else {param: previous_value})
                state.generation += 1
                state.parameters = params if previous is not None and consistent else None
                state.mesh_id = state.load = state.load_id = state.live_solve_id = None
                state.phase = "open"
                state.refs = list(action.refs)
                if state.parameters is not None:
                    ctx.last_parameters = deepcopy(state.parameters)
                elif ctx.last_parameters is not None:
                    # A later readback must not mistake this already-observed
                    # accepted value for a new, unrecorded mutation.
                    ctx.last_parameters[param] = value
                if result.get("downstream_invalidated") is not True:
                    issue("CLI_RESULT_INVALID", "Set result does not confirm the pinned downstream-invalidation contract.", action)
                if param not in case.parameters:
                    issue("UNAPPROVED_PART_MUTATION", "Executed set changed a parameter outside the trusted original schema.", action, "fail")
                ctx.pending.clear()
        elif name == "mesh":
            size, quality = number(result.get("element_size_mm")), number(result.get("min_quality"))
            count = result.get("elements")
            if size is None or size <= 0 or quality is None or type(count) is not int or count <= 0:
                malformed(ctx, action, "Mesh result lacks finite settings and a positive element count.", "mesh")
            else:
                state.generation += 1
                state.mesh_id = action.cli_id
                state.load = state.load_id = state.live_solve_id = None
                state.phase = "meshed"
                state.refs = list(action.refs)
                positional, options, recognized = _arguments(action.argv, frozenset({"--element-size"}))
                if (not recognized or positional or
                        ("--element-size" in options and _arg_number(options["--element-size"]) != size)):
                    issue("EVIDENCE_CONTRADICTION", "Mesh result settings differ from the supported explicit request.", action, "fail")
        elif name == "apply-load":
            load = _load(result)
            if load is None:
                malformed(ctx, action, "Load result lacks the complete finite actual load.", "load")
            else:
                state.generation += 1
                state.load = load
                state.load_id = action.cli_id
                state.live_solve_id = None
                state.phase = "loaded"
                state.refs = list(action.refs)
                positional, options, recognized = _arguments(action.argv, frozenset({"--direction"}))
                if (not recognized or len(positional) != 2 or positional[0] != load["face_id"] or
                        _arg_number(positional[1]) != load["force_N"] or
                        ("--direction" in options and options["--direction"] != load["direction"])):
                    issue("EVIDENCE_CONTRADICTION", "Actual load result differs from requested face, force or explicit direction.", action, "fail")
        elif name == "solve":
            sf = number(result.get("safety_factor"))
            converged = result.get("converged") if type(result.get("converged")) is bool else None
            problems = []
            if not state.original_verified:
                problems.append("ORIGINAL_IDENTITY_UNVERIFIED")
            if state.parameters is None:
                problems.append("GEOMETRY_UNKNOWN")
            if state.mesh_id is None:
                problems.append("MESH_UNKNOWN")
            if state.load is None or state.load_id is None:
                problems.append("LOAD_UNKNOWN")
            if _load(result.get("load")) is None:
                problems.append("SOLVE_LOAD_UNKNOWN")
            elif _load(result["load"]) != state.load:
                problems.append("SOLVE_LOAD_MISMATCH")
                issue("EVIDENCE_CONTRADICTION", "Solve load differs from the established actual load.", action, "fail")
            if sf is None:
                problems.append("SF_NOT_FINITE")
            if converged is not True:
                problems.append("ANALYSIS_NOT_CONVERGED" if converged is False else "CONVERGENCE_UNKNOWN")
            valid = not problems
            state.live_solve_id = action.cli_id if valid else None
            state.phase = "solved" if valid else "loaded" if state.load is not None else "unknown"
            state.refs = list(action.refs)
            cert = Certificate(action.cli_id, action.end_seq, deepcopy(state),
                               deepcopy(result), sf, converged, valid, list(action.refs), problems)
            history.solves[action.cli_id] = cert
            if not first_effective_mutation and state.part_name == case.original["name"]:
                history.baseline_candidates.append(cert)
                if (history.baseline is None and baseline_history_known and valid and
                        state.parameters == _parameters(case.parameters, case) and
                        state.load == _load(case.default_load)):
                    history.baseline = cert
        elif name == "save-part":
            path = result.get("saved_to")
            if not isinstance(path, str) or not path:
                issue("CLI_RESULT_INVALID", "Save result lacks an observed saved_to destination.", action)
            else:
                history.saves[action.cli_id] = Save(action.cli_id, action.end_seq, path,
                                                   deepcopy(state), state.live_solve_id, list(action.refs))
                if len(action.argv) < 3 or action.argv[2] != path:
                    issue("EVIDENCE_CONTRADICTION", "Save result destination differs from requested path.", action, "fail")
        elif name == "get-safety-factor":
            if state.live_solve_id is not None and result.get("region", "all") == "all":
                sf = number(result.get("safety_factor"))
                if sf is None:
                    issue("CLI_RESULT_INVALID", "Safety factor query lacks a finite value.", action)
                elif sf != history.solves[state.live_solve_id].sf:
                    issue("EVIDENCE_CONTRADICTION", "Safety factor query conflicts with its live raw solve.", action, "fail")
                    invalidate(ctx, "solve", action.refs)
        elif name == "get-active-part":
            part = result.get("active_part")
            if "active_part" in result and part is None:
                if state.part_name is not None:
                    issue("EVIDENCE_CONTRADICTION", "Active-part readback reports no part in a previously open session.", action, "fail")
                invalidate(ctx, "all", action.refs)
                if result.get("phase") == "closed":
                    state.phase = "closed"
            elif state.part_name is not None and isinstance(part, str) and part != state.part_name:
                issue("EVIDENCE_CONTRADICTION", "Active-part readback conflicts with established part identity.", action, "fail")
                invalidate(ctx, "all", action.refs)
            elif (state.revision is not None and "revision" in result and result["revision"] != state.revision):
                issue("EVIDENCE_CONTRADICTION", "Active-part readback conflicts with established revision.", action, "fail")
                invalidate(ctx, "all", action.refs)
            elif (state.load is not None and "applied_load" in result and _load(result["applied_load"]) != state.load):
                issue("EVIDENCE_CONTRADICTION", "Active-part readback conflicts with established load.", action, "fail")
                invalidate(ctx, "load", action.refs)
            else:
                overrides = result.get("parameter_overrides")
                if isinstance(overrides, dict) and state.parameters is not None:
                    observed = {key: number(value) for key, value in overrides.items()}
                    changed = [key for key, value in observed.items()
                               if value is not None and state.parameters.get(key) != value]
                    if changed:
                        previous = deepcopy(state.parameters)
                        for parameter in changed:
                            record_mutation(ctx, action, parameter,
                                            {parameter: observed[parameter]}, previous)
                            if ctx.last_parameters is not None:
                                ctx.last_parameters[parameter] = observed[parameter]
                        issue("EVIDENCE_CONTRADICTION", "Active-part override readback conflicts with established parameters.", action, "fail")
                        invalidate(ctx, "geometry", action.refs)
                phase = result.get("phase")
                if (phase in {"closed", "open", "meshed", "loaded", "solved"}
                        and state.phase != "unknown" and phase != state.phase):
                    issue("EVIDENCE_CONTRADICTION", "Active-part phase readback conflicts with established workflow state.", action, "fail")
                    # A phase downgrade can conceal an unobserved mutation;
                    # the readback cannot invent the missing transition.
                    invalidate(ctx, "geometry", action.refs)
        history.states[action.cli_id] = deepcopy(ctx.state)

    history.final_states = {name: deepcopy(ctx.state) for name, ctx in sessions.items()}
    return history
