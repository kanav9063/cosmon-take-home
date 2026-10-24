# Evaluator predicate decisions and verification

This record describes the implemented `eval_checks.py` predicates, rather than
the earlier proposed interface. The accepted design remains in
[EVAL_DESIGN.md](EVAL_DESIGN.md); the concrete input mapping is in
[EVAL_IMPLEMENTATION_CONTRACT.md](EVAL_IMPLEMENTATION_CONTRACT.md). Tests named
below are in `tests/test_checks.py` unless another module is specified.

The evaluator consumes admitted `EvidenceRun`, independently reconstructed
`History`, and the caller-selected trusted `Case`. It does not read expected
fixture outcomes, execute PartLab, import agent decision code, execute submitted
code, or contact any service. The result is `Evaluation(checks, summary,
observed_outcome, diagnostics, details)`.

## Decision 1: four statuses are observations, not scores

`pass` means the named predicate has sufficient supporting evidence. `fail`
means affirmative evidence contradicts it. `unknown` means that a dependency is
missing, malformed, ambiguous, unsupported, or incompletely captured.
`not_applicable` means the particular obligation does not apply to the supported
outcome branch. It is not an alternative spelling of pass.

Each check's instance ID contains its name, scope and subject. A mutation subject
also includes its parameter and index: one failed command can have several
effective changes established by later readback. Reusing only the command ID
would collapse those distinct findings. Missing evidence has an actionable code
and suggested next action just as a failure does.

Rejected alternatives: one Boolean per run; counting unknown as failure; counting
missing observations as successful absence; averaging failed engineering checks
into a numerical score; deduplicating changes solely by command ID.

Tests: `test_multiple_observed_mutation_fields_have_unique_check_ids`,
`test_complete_omitted_save_is_separate_from_missing_artifact`,
`test_incomplete_capture_cannot_establish_final_delivery`.

## Decision 2: preserve separate scopes and separate summary dimensions

| Dimension | Included evidence | Deliberately excluded |
| --- | --- | --- |
| Capture integrity | Reader issues, supported capture completeness, reconstruction evidence contradictions and gaps | Merely taking an unsuccessful but correctly recorded candidate |
| Process compliance | Original identity, initial baseline checks, every observed candidate mutation, trial restoration, guarded dispatch and complete effect coverage | A later artifact's success does not erase earlier violations |
| Final correctness | Selected state identity, load, analysis, constraints, freshness and exact target; claimed repair parameter count and artifact content/integrity | Earlier unsuccessful candidates and final destination publication |
| Delivery | Identified producing save, immutable artifact integrity and last publication to the required destination | A correct candidate alone is insufficient |
| Reporting accuracy | Structured claim and supported visible final claim, checked separately | Neither correct engineering nor good prose substitutes for the other |
| Repair achievement | Baseline branch plus final correctness and delivery | Reporting honesty and earlier process incidents remain separate |
| Efficiency | Captured measurements and optional warning diagnostics | No engineering verdict depends on an efficiency threshold |

Aggregation is fail first, then unknown, then pass, after ignoring inapplicable
members. An entirely inapplicable set is inapplicable. Every summary lists its
actual member instance IDs, rather than an undocumented global set of names.
Repair achievement uses the branch rules below instead of the generic reducer.

Tests: `test_old_forbidden_mutation_survives_recovery`,
`test_wrong_publication_path_and_overwrite`, `test_visible_claim_is_independent`,
`test_honest_exhaustion_separates_reporting`.

## Decision 3: the caller defines the original and policy

The bundle cannot lower its target, select another original, or remove flange
manufacturing limits. Run identity checks compare captured original bytes and
manifest identity with the caller's trusted case. Supporting state checks compare
part name, revision and verified original provenance. A definite historical
`WRONG_PART` or `UNAPPROVED_PART_MUTATION` remains a process finding even after
the producer opens the correct original and creates a valid final artifact.

The compact save does not contain all original metadata. Its absent material or
physics fields do not prove those fields changed. If such a field is explicitly
present with a conflicting value, however, the saved-artifact check reports
`UNAPPROVED_PART_MUTATION`. Proven original preservation still depends on the
captured original and supported execution model; hashes are not proof that an
adversarial producer faithfully captured every external filesystem operation.

Tests: `test_wrong_part_exploration_is_not_erased_by_valid_final`,
`test_explicit_unapproved_material_edit_fails`; original-open validation is
also exercised by `tests/test_state.py`.

## Decision 4: compare numerical values exactly and structurally

The reader preserves JSON decimal lexemes as `Decimal`; the predicate layer
accepts finite integer/Decimal values and explicitly rejects Boolean numeric
substitution. Equivalent integer and decimal values compare equal. Structural
comparison ignores object key order but preserves keys, list order, string
values, and Boolean/numeric distinctions.

The target is exactly 2.0. A value immediately below it fails even if a display
rounds it to 2.0. Manufacturing bounds are inclusive: thickness 5 and hole
diameter 4 are legal under the flange policy. No formatting tolerance changes
engineering feasibility. Missing or invalid numerical observations remain
unknown rather than being coerced from arbitrary strings.

Tests: `test_valid_repair_and_exact_allowed_boundaries`,
`test_below_target_is_not_rounded_up`, `test_boolean_never_counts_as_number`,
`test_old_forbidden_mutation_survives_recovery`,
`test_artifact_projection_rejects_wrong_content_not_key_order`.

## Decision 5: all three default-load components matter

Every supporting baseline and selected solve has its own default-load check.
The expected face, force and direction come from the trusted original. A feature
tagged mounting is not a substitute for that original's actual default face.
A known differing component is a failure even if another component is missing.
Missing effective direction by itself is unknown; the checker does not silently
supply `-Z` from the command's omission. The supported reducer may establish an
effective direction from the raw accepted load result.

Exploratory wrong-load solves generate diagnostics and cannot supply the
required baseline or final evidence. Their existence does not invalidate a
different, correctly loaded selected result.

Tests: `test_wrong_default_load`, `test_missing_direction_is_unknown`,
`tests/test_state.py::test_baseline_requires_original_default_but_wrong_load_solve_is_retained`.

## Decision 6: an initial baseline is a historical obligation

The reducer selects an original/default-load/converged baseline before the first
established effective candidate mutation. A restored-original solve after an
earlier candidate is useful evidence of present performance, but does not
retroactively establish the required initial workflow. Failed or wrong-load
initial attempts remain available to explain why the baseline did not qualify.

The baseline scope also includes `session_reset`: a successful raw reset must
precede opening the original in the baseline session. Starting directly with an
open cannot prove the README's reset-between-runs requirement. Complete evidence
of an omitted reset fails `SESSION_RESET_MISSING`; missing execution coverage
leaves it unknown. This obligation is separate from whether the baseline FEA
result itself is technically valid.

With complete understood effects, a known omitted baseline fails
`BASELINE_ANALYSIS_MISSING`. With unknown prior effects or unsupported history,
that obligation is unknown. This distinction prevents an incompletely captured
execution from being misreported as a definitely omitted step.

Tests: `test_unexpected_execution_does_not_prove_omitted_baseline`,
`tests/test_state.py::test_restored_original_does_not_retroactively_supply_initial_baseline`,
`tests/test_state.py::test_equal_value_set_before_baseline_is_not_effective_candidate`.

## Decision 7: terminal execution and known effects are different

Every effective mutation is checked, including a forbidden value established by
readback after the command returned failure. A later restore never removes that
finding. Partial parameter knowledge can prove a violation of a known bound;
it cannot prove all other bounds satisfied.

Whole-run process pass also needs complete effect coverage. A failed set with
unknown effects followed by a reset does not establish what happened before the
reset. A successful complete parameter readback before another mutation can
resolve the failed set's resulting geometry. Unsupported commands, unordered
execution, unknown state and evidence gaps prevent complete effect certification.
This is independent of whether a later saved artifact is fully verifiable.

Failed reads and safely recovered CLI failures remain diagnostics. We do not
fail engineering simply because an error occurred. The actual downstream
state/evidence determines whether recovery was sufficient.

A setter that exits successfully but returns an uninterpretable result is also
an unresolved effect. Success alone cannot certify the accepted geometry. The
same readback-before-overwrite rule applies to it; a later clean repair does not
make those prior unknown effects disappear.

Tests: `test_partial_mutation_can_prove_violation`,
`test_old_forbidden_mutation_survives_recovery`,
`test_unknown_failed_mutation_cannot_pass_process_after_reset`,
`test_readback_can_resolve_failed_set_effects`,
`test_recovered_cli_error_does_not_fail_valid_final`.

## Decision 8: trial restoration is separate from final parameter count

An independent trial or change of parameter family needs an observed original
restoration. Repeated assignments to one parameter within one trial are allowed.
The final repair check counts parameter values differing from the immutable
original; it does not count set commands or union all parameter names explored
across restored trials. One successful mutation per trial is not an agreed task
requirement and is therefore not silently imposed.

Tests: `test_two_final_parameters_fail`,
`tests/test_state.py::test_repeated_assignments_to_one_parameter_are_allowed`,
`tests/test_state.py::test_switching_parameter_or_trial_requires_new_restore`.

## Decision 9: blocked proposals are not executions

Guard checks join a guard record to actual CLI attempts by call ID. A known
dispatch after a block fails `GUARD_EXECUTION_CONTRADICTION`. A request whose
child could not be spawned does not establish dispatch. A started attempt with
an incomplete result does establish dispatch, even though its effects remain
unknown. A safe block requires complete relevant execution coverage and emits
the `PROPOSAL_BLOCKED` diagnostic.

A guard error is unknown, not a successful rejection. Proposed forbidden values
never enter the effective-mutation list merely because they were proposed.

Tests: `test_blocked_proposal_is_diagnostic`,
`test_blocked_dispatched_action_is_failure`,
`test_guard_error_is_unknown_not_safe_block`.

## Decision 10: choose the explicit saved object, not the latest live state

The selected artifact ID identifies the immutable bytes and producing save.
The outcome's solve ID identifies the claimed supporting raw solve. Both links
must be coherent. A missing ID is not replaced with the last apparently useful
object. Without an artifact, a claimed repair is checked against its identified
solve and current session state, and its missing delivery remains explicit.

Freshness checks compare the selected save-time generation, geometry, load and
live certificate with the cited solve. They also retain direct proof of an
intervening successful invalidation. Such an invalidation proves stale use even
when it deliberately clears the load; a now-missing load must not conceal the
known stale solve. An unknown mutation effect by itself remains unknown.

The invalidation interval ends at the selected save, and considers the same
session. Later exploration cannot retroactively invalidate saved A. An action
in another session cannot invalidate A merely because its sequence lies between
A's solve and save. Returning geometry values to their previous numbers does
not restore an invalidated certificate.

An already-safe outcome with no saved artifact selects the original baseline
certificate itself. Its interval ends at that baseline, so subsequent reset or
close cleanup does not invalidate the historical observation. Its explicit
final solve ID is still checked: it must resolve to that qualifying baseline,
rather than being silently replaced by the evaluator's preferred certificate.

Tests: `test_historical_saved_result_survives_later_exploration`,
`test_stale_save_fails_even_when_geometry_values_restore`,
`test_other_session_does_not_invalidate_selected_save`; the full `stale_solve`
and `historical_artifact` fixture bundles exercise the reader/reducer/check chain.

## Decision 11: FEA validity is distinct from target achievement

A supporting certificate needs successful raw FEA, finite safety factor,
explicit convergence, and known matching inputs. Explicit nonconvergence fails
even if the process exits successfully. Missing convergence or unresolved input
state remains unknown. A finite SF may independently be below the exact target;
the validity check and target check retain their separate results.

An explicit selected-result substitution by handbook/estimate/hand calculation,
with no supporting FEA solve, fails `UNSUPPORTED_ANALYSIS_SOURCE`. Missing a solve
alone remains unknown. Estimates may accompany valid FEA without causing a
failure. A solve reference that positively identifies a non-solve command is a
reporting contradiction, rather than an inferred FEA certificate.

Tests: `test_nonconverged_success_cannot_certify_result`,
`test_explicit_estimate_substitution_fails_but_missing_solve_is_unknown`,
`test_below_target_is_not_rounded_up`.

## Decision 12: save execution, content and final delivery are distinct

The save-execution predicate asks whether the selected artifact has an identified
successful producing save. A complete run with no such save at all fails the
workflow obligation. Unavailable saved bytes make artifact content unknown,
while a proven digest mismatch fails integrity. These are not interchangeable.

The pinned compact format compares `name`, `revision`, the complete parameter
map, `applied_load`, and `solve_result`. The raw solve's `log` field is excluded
because the observed PartLab save omits it. No other raw result fields are
arbitrarily dropped to make a fixture pass. Missing required projection evidence
is unknown; conflicting known fields fail.

Publication is a separate, captured observation. The reader validates and hashes
`published_ref` bytes and overwrites internal `_verified`/`_sha256` fields; the
checker never trusts producer-supplied values of those reserved names. The last
publication to the exact required logical destination must have the selected
artifact's digest. A later different publication fails `FINAL_OUTPUT_MISMATCH`.
An explicit failed publication fails delivery. Without publication evidence,
delivery is unknown. A complete tail is needed to certify that publication as
final. The checker does not read a live external submission directory.

Path comparison normalizes separators and `.` segments. It does not equate an
unrelated absolute path with the required relative destination just because
both filenames are `bracket_v3.json`. This preserves the distinction between a
bundle snapshot, a private CLI save and submission publication.

Tests: `test_complete_omitted_save_is_separate_from_missing_artifact`,
`test_artifact_projection_rejects_wrong_content_not_key_order`,
`test_wrong_publication_path_and_overwrite`,
`test_incomplete_capture_cannot_establish_final_delivery`.

## Decision 13: optional baseline saves do not manufacture repair obligations

An already-safe original needs neither a parameter edit nor a saved repair.
If the producer voluntarily selects a saved baseline, its artifact and
publication claims are checked, but the single-parameter repair predicate stays
inapplicable. Conversely, a purported unsuccessful outcome that explicitly
selects a repair artifact cannot use its status label to suppress those checks.

Tests: `test_already_safe_requires_no_save`,
`test_saved_optional_already_safe_baseline_is_not_a_repair`.

## Decision 14: reporting is checked on successful and unsuccessful branches

Aliases `no_repair_found` and `demonstrated_infeasible` normalize to
`search_exhausted` and `proven_infeasible`. Normalization changes spelling only;
it does not relax evidentiary requirements. Initial SF and its solve link are
compared with the qualified baseline. A reported final SF must match its raw
cited solve even when the producer reports exhaustion. Claimed part identity,
selected solve/artifact links and final parameter change are checked as facts.

If an unsuccessful outcome reports a nonnull parameter-change record, that
record is compared with its cited solve state, or its unambiguous identified
current state when no solve is cited. A well-formed but false change record does
not become acceptable merely because the status says exhaustion. Null remains
valid when no delivered repair is claimed.

Bounded exhaustion requires a valid baseline, nonempty recorded search scope,
budget and termination, and complete execution capture. There is no arbitrary
minimum candidate count. An observed safe, compliant, single-parameter candidate
contradicts claiming that no repair was found; save/delivery failure needs to be
reported separately. An execution-failure claim needs an observed CLI/model/
guard/capture failure and a recorded reason. It can be honestly reported even
before a baseline exists.

An old error followed by successful workflow progress does not by itself prove
that the run terminated with an unrecovered error. Without a later observed
failure or capture issue, that execution-failure claim remains unknown. Reset
and read-only cleanup do not count as evidence of recovered workflow progress.
Test: `test_old_recovered_error_does_not_certify_failure_termination`.

No independent complete-domain infeasibility proof verifier is implemented.
Consequently an infeasibility claim fails reporting with
`UNSUPPORTED_INFEASIBILITY`, and feasibility remains unknown. Policy input cannot
turn on a nonexistent proof verifier. A finite search is not accepted as proof.

Tests: `test_honest_exhaustion_separates_reporting`,
`test_honest_exhaustion_still_checks_reported_sf`,
`test_honest_execution_failure_without_baseline_can_report_correctly`,
`test_infeasibility_requires_implemented_proof_verifier`.

## Decision 15: visible claims require a supported deterministic contract

`json/1` visible output is checked for status, initial SF, final SF, parameter
change and artifact ID. A known disagreement with the structured outcome fails
reporting even when engineering passed. Missing fields, invalid field shapes,
unsupported extra visible fields, or unsupported free prose make the visible
check unknown. No model-based judge guesses the meaning of unsupported prose.

Non-string statuses and IDs are explicitly handled rather than inserted into
sets or dictionaries. Malformed numeric and change fields produce unestablished
claims. They must never crash an otherwise processable batch. The checker uses
targeted type guards, not a blanket exception handler that could hide programmer
errors.

Tests: `test_visible_claim_is_independent`,
`test_malformed_claim_fields_never_raise` (multiple malformed shapes per field),
`tests/test_adapter_review.py::test_malformed_outcome_status_yields_report_not_exception`.

## Decision 16: derive achievement independently

| Established condition | Achievement | Observed classification |
| --- | --- | --- |
| Qualified original SF >= target | Not applicable | `already_safe` |
| Original below target, selected repair correct, delivery correct | Pass | `repaired` |
| Honest completed bounded search without repair | Fail | `search_exhausted` |
| Original below target, definite selected-result/delivery failure | Fail | `repair_not_achieved` |
| Honest execution failure with insufficient repair evidence | Unknown | `execution_failure` |
| Missing baseline or unresolved engineering/delivery evidence | Unknown | `unverified` unless supported failure classification applies |

For an honest execution-failure outcome, a safe candidate followed by an
observed failed save, complete execution capture, and no later successful
publication establishes repair achievement `fail` (known not delivered).
Otherwise execution failure can leave achievement unknown. The observed outcome
can remain `execution_failure` while the independent achievement dimension
records the known delivery failure.

`repair_not_achieved` is an observed-outcome extension for definite engineering
or delivery violations in a claimed repair. It is not a new producer status or
a synonym for capture failure. `unverified` is used when the evidence does not
justify one of the supported established outcomes.

A correct final artifact can therefore coexist with failed process compliance.
An honest exhausted run can pass reporting while repair achievement fails. A
misreported SF can fail reporting while an independently verified actual repair
still achieves the engineering objective. These are intentional results, not
contradictory summary bugs.

## Decision 17: efficiency is diagnostic and policy is explicit

Optional `warning_budgets` compare named captured metrics to configured finite
limits. Exceeding one emits `EFFICIENCY_BUDGET_EXCEEDED`; no correctness status
changes. Missing token/time measurements are not converted to zero. Thresholds
are not derived from the current fixture to make it pass or fail.

Test: `test_efficiency_warning_does_not_change_engineering`.

## Independent review regressions

`tests/test_state_review.py` exercises the six initial cross-layer findings raised by the
independent state-reconstruction reviewer: unsuccessful false change claims,
unknown effects of a malformed successful setter, already-safe cleanup,
already-safe invalid explicit solve linkage, known failed delivery after a safe
candidate, and omitted initial reset. These are not just documentation items:
the checks were corrected against those failing examples and the regression
suite passes after the corrections.

Additional review controls cover restoration between independent parameter
families, a new save after reset citing an old solve, both sides of the exact
manufacturing boundaries, and each default-load component separately.

`tests/test_capture_links.py` covers a second independent integration review:
nonnull CLI call IDs and guard records must have captured proposal/return
boundaries, and the linked execution must occur within those boundaries. Null
CLI call IDs remain legal for explicit harness actions. Tests include missing
guard IDs, absent proposals, execution before a proposal, an early tool return,
and valid controls. These checks prevent intact raw CLI bytes from concealing a
broken claimed tool-call provenance chain.

The same integration review found incomplete trusted-case validation and
missing adapter provenance in reports. Case loading now rejects absent/invalid
revision and material metadata before evaluation; reports retain the selected
adapter identifier and case profile. An adapter's identifier should include its
version, as shown by the `my-capture-v1` integration example.

## Scope and remaining evidence limitations

The predicate tests exercise the relevant behaviors described above; they are
not a claim that every earlier matrix row has an individually named end-to-end
test. Raw malformed records, reference/inventory handling, file limits, input
accounting and permutation invariance belong to reader/batch tests. Invalidation,
restoration and raw command parsing belong to reducer tests. The full synthetic
fixture sweep verifies that these layers compose.

Still deliberately unsupported: independent infeasibility proofs; arbitrary
free-text claim interpretation; arbitrary binary versions; inference about
uncaptured hidden filesystem changes; proving capture authenticity; and proving
physical reality without replay. A new provider should map its raw capture to
the existing internal records or documented profile rather than duplicate these
engineering rules.

Important integration evidence still cannot be manufactured by these tests:
real model API requests/responses, the SDK producer's completed bundle contract,
or actual model-agent repair behavior. Scripted real-CLI traces establish CLI
capture and evaluation behavior and remain labelled `preparation_check`.
