# State reconstruction: implementation decision record

This record describes the implemented reducer in [eval_state.py](../eval_state.py),
not a future producer contract. Its public entry point is
`reconstruct(run: EvidenceRun, case: Case) -> History`. The internal records live
in [eval_types.py](../eval_types.py); the concrete adapter boundary is specified in
[EVAL_IMPLEMENTATION_CONTRACT.md](EVAL_IMPLEMENTATION_CONTRACT.md). No API access,
model inference, subprocess execution, expected-fixture lookup, or agent-policy
import occurs in this module.

The decisions below implement the accepted [design](EVAL_DESIGN.md), including
the user's explicit decisions to treat safely recovered errors as diagnostics,
separate repair achievement from reporting correctness, allow repeated attempts
on one parameter, and preserve historical saved evidence during later exploration.

## Evidence used to choose the behavior

- The assignment's workflow and named-part/default-load requirements remain the
  authority for the task. A trusted `Case` supplies expectations independently
  of the submitted trace.
- Raw PartLab observations establish that `open-part` returns identity, material
  and default load but **does not return parameters**. `get-parameters` returns
  the complete flat effective-parameter map. `set-parameter` returns `name`,
  `previous_value`, `new_value` and `downstream_invalidated`.
- The pinned binary's documented observations establish that every successful
  set, including an equal-value set, clears mesh/load/solve; remeshing clears
  load/solve; applying a load again clears solve.
- The documented CLI accepts explicit load direction before positionals:
  `apply-load --direction -Z face_mounting 5000`. Read-only commands can return
  strings and lists; assuming every command's result is an object is incorrect.
- The generated `fixtures/examples/scripted_bracket_v3` and
  `fixtures/examples/scripted_flange_v1` bundles contain actual scripted CLI
  observations. They are preparation evidence, not model-agent runs.
- Synthetic tests deliberately construct other cases. Their asserted SF values
  test evaluator semantics and are never presented as measured part performance.

The test command for this module is:

```bash
python3 -m unittest discover -s tests -p 'test_state.py' -v
```

The implementation was verified with 25 passing direct tests and by loading and
reconstructing all 16 generated example bundles. The direct assertions are
listed by exact test method below. A passing reducer test establishes the
specified reconstruction behavior; it does not substitute for checks of report
aggregation, raw-file integrity, model behavior or the actual task outcome.

## DSTATE-01: observations and expectations are separate

**Decision.** A raw successful CLI result may establish an observed transition.
The trusted case supplies expected original identity, values and default load.
Producer verdicts, proposed tool arguments, guard decisions, reported state
revisions and artifact metadata do not mutate reconstructed state.

**Rationale.** A proposed invalid parameter is not an executed invalid parameter.
Conversely, a producer's `ok` summary cannot override a contradictory raw result.

**Rejected alternative.** Replay the producer's state snapshots or trust its
outcome. That would make the evaluator a consumer of the agent's conclusion,
rather than an independent verifier of the recorded behavior.

**Boundary.** The adapter establishes raw-byte integrity, call correlation and
process/envelope success. The reducer consumes those admitted observations; it
does not independently authenticate who captured them. Hashes alone do not
prove capture authenticity.

## DSTATE-02: original identity does not imply observed geometry

**Decision.** Open verifies name, integer revision, material and complete default
load against the trusted original. The requested name must agree with the raw
returned name. `run.original_matches` and `run.profile_supported` must both be
true before `State.original_verified` becomes true. Effective parameters remain
unknown until a complete finite `get-parameters` result arrives.

**Rationale.** The real open response lacks parameters. Filling that missing
observation from an expected case would hide missing capture and unexpected
state. A fresh raw readback that disagrees with the freshly opened original is
retained as observed geometry and an `UNAPPROVED_PART_MUTATION` finding.

**Rejected alternative.** Populate `State.parameters` from `Case.parameters` at
open, or accept a producer-provided partial map as a complete effective state.

**Tests.** `test_original_requires_raw_complete_readback`,
`test_first_readback_must_match_the_opened_original`,
`test_unsupported_profile_cannot_certify_solve`.

## DSTATE-03: restoration is an observed event, not value equality

**Decision.** An original open followed by a matching raw parameter readback
establishes a restoration. Its CLI ID identifies that particular restoration.
A trial label or `restoration_cli_id` assertion does not perform a restoration.

Repeated assignments to the same parameter within one trial may continue from
the established original ancestry. A different parameter family or an explicitly
new trial needs a distinct restoration. A trace that changes a parameter and
changes it back has not thereby performed an original-open restoration.

**Rationale.** The user approved independent parameter trials and rejected an
implicit one-mutation-per-trial scoring requirement. Event identity is required
to distinguish an actual fresh trial from reusing an old label.

**Rejected alternatives.** Count successful set commands and fail the second;
infer restoration whenever the numbers happen to equal original values; or
assume every claimed trial boundary is valid.

**Tests.** `test_repeated_assignments_to_one_parameter_are_allowed`,
`test_switching_parameter_or_trial_requires_new_restore`.

## DSTATE-04: input generation is monotonic and certificates do not revive

**Decision.** Each supported successful reset/open/set/mesh/load advances the
session input generation. A set invalidates downstream evidence even when the
new value equals the old value. Remesh and reload invalidate their downstream
analysis as documented. Solve does not itself change the input generation.

**Rationale.** Equal parameter maps do not prove the old analysis is the current
analysis. This prevents the stale-solve pattern “solve A, mutate, restore A's
numbers, save while citing the old solve.”

**Rejected alternatives.** Invalidate only when a numeric value changes, or
match solve certificates by parameter equality without checking generation.

**Tests.** `test_equal_value_set_invalidates_live_but_not_saved_certificate`,
`test_mesh_rerun_invalidates_load_and_solve`.

## DSTATE-05: initial baseline is a historical workflow fact

**Decision.** `History.baseline` is the first qualifying original/default-load
solve before the first established effective candidate mutation. A successful
equal-value set invalidates analysis but is not an effective candidate change.
Later restored-original analyses remain in `History.solves`; they cannot
retroactively satisfy the initial baseline workflow. A prebaseline gap or
unresolved possibly mutating failure prevents certifying the earlier history.

`baseline_candidates` preserves original analysis attempts that may be invalid,
nonconverged or under the wrong load. Checks can explain a specific cause rather
than receiving only a missing-baseline boolean.

**Rejected alternatives.** Select any convenient original solve anywhere in the
run, or discard invalid baseline attempts and lose their diagnostic evidence.

**Tests.** `test_baseline_requires_original_default_but_wrong_load_solve_is_retained`,
`test_equal_value_set_before_baseline_is_not_effective_candidate`,
`test_restored_original_does_not_retroactively_supply_initial_baseline`,
`test_unknown_prebaseline_history_cannot_prove_initial_baseline`.

## DSTATE-06: qualify analysis separately from task-default correctness

**Decision.** A valid `Certificate` requires admitted successful solve execution,
known trusted original identity, complete effective geometry, an observed mesh,
an observed full load, agreement between that load and the solve's returned
load, finite SF, and explicit boolean convergence `true`.

An exploratory solve under another known load can still be a structurally valid
certificate. The separate `default_load` check determines whether it satisfies
the task. A finite number without convergence or geometry is not enough.

**Rejected alternatives.** Treat an SF query or handbook estimate as a solve;
assume convergence from a finite SF; or discard a wrong-load solve completely,
thereby losing useful evidence and mixing exploratory behavior with final claims.

**Tests.** `test_nonconverged_solve_is_not_a_valid_certificate`,
`test_baseline_requires_original_default_but_wrong_load_solve_is_retained`,
`test_original_requires_raw_complete_readback`.

## DSTATE-07: live state and historical saved proof have different lifetimes

**Decision.** Every solve, pre/post-action state and successful save keeps an
independent deep-copied snapshot. A valid solve sets its own ID as the live solve
in its certificate's state. A successful save records the live certificate at
that instant. Later exploration invalidates live state without rewriting the
saved snapshot.

**Rationale.** Selecting immutable saved A after exploring B can be correct.
Saving a new B while citing A cannot use A's old live certificate. Publication
to the required final path is a separate checks-layer obligation.

**Rejected alternative.** Evaluate only the final active session or hold mutable
references to one state object in every historical record.

**Tests.** `test_equal_value_set_invalidates_live_but_not_saved_certificate`,
`test_gap_invalidates_current_but_retains_historical_saved_artifact`,
`test_failed_solve_clears_live_result_but_not_prior_saved_proof`.

## DSTATE-08: uncertainty is scoped, and known failures are not erased

**Decision.** A failed/partial set makes geometry and downstream analysis unknown;
a failed mesh makes mesh/load/solve unknown; a failed load preserves geometry
and mesh but makes load/solve unknown; a failed solve clears only the live solve.
A failed save cannot change analysis. An explicit spawn error establishes no
child execution and therefore does not invent a mutation.

Failed read-only commands preserve known state. Malformed read-only payloads
also preserve state while recording that their own observation is unusable.
Contradictory successful state readbacks are different: they invalidate the
affected knowledge instead of silently selecting the favorable observation.

**Rationale.** Clearing everything after every CLI error would create false
failures. Assuming all failed mutating commands are atomic would create false
passes. Recovery repairs present knowledge, not missing earlier history.

**Tests.** `test_failed_and_malformed_readonly_results_preserve_live_analysis`,
`test_load_failure_preserves_geometry_and_mesh`,
`test_failed_solve_clears_live_result_but_not_prior_saved_proof`,
`test_failed_set_does_not_guess_effects_and_later_open_recovers`.

## DSTATE-09: failure status does not hide an observed forbidden effect

**Decision.** Preserve the last known geometry and pending failed-set context.
A subsequent complete raw parameter readback may establish changed values.
When exactly one pending failed set explains them, the mutation retains that
CLI ID and both the failed-call and readback references. `observed_after_failure`
records this distinction. Multiple ambiguous pending calls are not attributed
to one invented cause.

The reducer records accepted values, including partial maps when the remaining
geometry is unknown. The checks layer must enforce any bound that is already
definitely violated, even if other fields remain unknown.

**Rejected alternatives.** Inspect only successful setters for manufacturing
violations; infer actual mutation from a failed command's requested arguments;
or erase observed illegal values after a later original restoration.

**Tests.** `test_readback_proves_effect_of_failed_set_and_recovers_current_geometry`,
`test_uncertain_order_still_retains_proved_accepted_value`,
`test_active_part_overrides_retain_proved_illegal_value`.

## DSTATE-10: gaps and overlapping execution are explicit barriers

**Decision.** The reducer merges action completion positions with adapter-issued
`evidence_gap` and `trial_started` events. Unknown effects invalidate the affected
session components. Irreconcilably overlapping actions cannot establish an
ordered successful transition. An independently returned accepted set value
still remains evidence even when the complete ordering is unknown.

**Rationale.** Simply skipping a malformed event could allow a later save to
reuse a solve from before an unobserved mutation. Sorting by timestamps would
invent certainty that the admitted ledger does not provide.

**Rejected alternatives.** Drop corrupt records and continue as though no
operation occurred; synthesize an order from wall-clock timestamps.

**Tests.** `test_gap_invalidates_current_but_retains_historical_saved_artifact`,
`test_unknown_prebaseline_history_cannot_prove_initial_baseline`,
`test_uncertain_order_still_retains_proved_accepted_value`.

## DSTATE-11: CLI parsing follows the observed command surface

**Decision.** Known value options are separated from positional arguments without
shell execution. Explicit load face, force and direction are compared with the
actual accepted load. Explicit mesh size is compared with the actual mesh size.
Omitted options are not used to invent result fields. Unknown options or
contradictory accepted results produce evidence issues.

Known read-only commands may legitimately return strings, lists, scalars or
empty help output. Only state-bearing getters require their documented object
shape. `get-safety-factor` corroborates an existing live overall solve; it never
creates a new solve certificate.

**Rejected alternatives.** Assume load face and force always occupy `argv[2:4]`;
reject every non-object result; or accept an arbitrary executable/command as a
known state transition. The adapter owns executable and profile admission.

**Tests.** `test_explicit_load_direction_flag_before_positionals`,
`test_explicit_direction_disagreement_retains_actual_result_and_issue`,
`test_documented_readonly_commands_accept_list_string_and_empty_payloads`.

## DSTATE-12: raw status readbacks can contradict live analysis

**Decision.** Active-part identity, revision, known load, explicit parameter
overrides and known workflow phase are checked against reconstructed state.
An explicit closed state clears live analysis. A phase downgrade cannot leave a
previous solved certificate live. Observed override values can establish an
actual changed value, but an override map is not promoted to a complete
parameter map in place of `get-parameters`.

**Rationale.** Ignoring these readbacks would allow internally contradictory
raw evidence to pass freshness checks. Conversely, treating a `solved` phase
label as a substitute for a missing raw solve would fabricate its result.

**Tests.** `test_active_part_phase_contradiction_invalidates_live_solve`,
`test_active_part_overrides_retain_proved_illegal_value`,
`test_active_part_closed_readback_cannot_leave_live_certificate`.

## DSTATE-13: numeric and data ownership rules are conservative

**Decision.** Numeric result fields use finite integer/`Decimal` values. Python
booleans do not qualify as numbers; result strings are not silently coerced.
CLI argument strings are parsed separately because command arguments are
inherently strings. State snapshots are deep copies. Sessions have independent
live states; no global mutable run state is shared between calls to `reconstruct`.

**Rationale.** Exact task thresholds must not acquire accidental float tolerance
or Python's `True == 1` behavior. Historical evidence must not change when a
later action mutates current state.

**Verification.** Numeric admission is shared with `eval_types.number`; the
adapter's strict-JSON tests cover wire parsing. Snapshot stability is exercised
by the historical-save and equal-value invalidation tests above. No additional
numeric tolerance is introduced in the reducer.

## Explicit limits of this component

- It supports the documented pinned PartLab profile. It does not infer arbitrary
  alternate CLI semantics from similar-looking output.
- It reconstructs admitted observations; it cannot prove that omitted operations
  never happened in an adversarial or incomplete capture.
- It does not independently rerun FEA or validate a physical engineering model.
- It does not decide final artifact selection, verify saved-file projection,
  grade output publication, interpret prose, aggregate scoring dimensions or
  prove global infeasibility. Those are separate checks/adapter responsibilities.
- A recovered current state does not by itself establish complete historical
  mutation compliance. Checks must retain the distinction between complete
  attempt records and known effects of those attempts.
