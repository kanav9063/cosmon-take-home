# Executed evaluation coverage

This maps the 43 scenario rows in [EVAL_TEST_MATRIX.md](EVAL_TEST_MATRIX.md) to
concrete automated assertions. The matrix retains the original requirements;
this file records the implementation evidence. A covered row means its named
predicate and relevant control are exercised, not that every conceivable input
variant has been enumerated.

Run the complete suite with:

```bash
python3 -m unittest discover -s tests -v
```

The tests use temporary local bundles and no paid/model API. Synthetic solver
numbers establish test inputs, not measured engineering performance. Actual
scripted CLI captures are separately identified by `evidence_kind` in
`fixtures/examples/scripted_bracket_v3` and `scripted_flange_v1`. No synthetic or
scripted capture is relabeled as a real model-agent run.

## Test references

The prefixes in the tables expand to these classes. Every name after the prefix
is an exact method name, so a row can be located without interpreting prose.

| Prefix | Class and source | Test level |
| --- | --- | --- |
| `A` | `AdapterReviewTests` in [test_adapter_review.py](../tests/test_adapter_review.py) | Raw bundle and batch boundary |
| `W` | `WireCoverageTests` in [test_wire_coverage.py](../tests/test_wire_coverage.py) | Adversarial raw bytes, events and references |
| `S` | `StateTests` in [test_state.py](../tests/test_state.py) | Typed execution history reduction |
| `C` | `CheckTests` in [test_checks.py](../tests/test_checks.py) | Independent predicates and dimensions |
| `R` | `StateReviewTests` in [test_state_review.py](../tests/test_state_review.py) | Independent review regressions through adapter/reducer/checks |
| `P` | `PipelineTests` in [test_pipeline.py](../tests/test_pipeline.py) | Complete local evaluation and command contract |

## Capture and normalization: I01–I12

| Row | Status | Exact automated assertions | Established behavior / scope |
| --- | --- | --- | --- |
| I01 | Covered | `P.test_valid_full_bundle_all_required_dimensions_pass`; `A.test_simulated_live_profile_with_raw_boundaries_is_complete` | Complete supported raw evidence passes. The latter tests the live-profile wire shape with explicitly simulated API payloads; it is not evidence of a live API call. |
| I02 | Covered | `W.test_malformed_json_tail_preserves_known_prefix_and_reports_incomplete`; `W.test_nonfinite_and_duplicate_key_raw_json_is_rejected`; `A.test_malformed_event_kind_yields_issue_not_exception` | Malformed JSON/records produce issues, preserve usable prefix evidence and do not become successful capture. |
| I03 | Covered | `W.test_missing_completion_never_certifies_capture`; `W.test_malformed_json_tail_preserves_known_prefix_and_reports_incomplete`; `C.test_incomplete_capture_cannot_establish_final_delivery` | EOF or a plausible successful prefix cannot replace terminal evidence; final delivery remains unestablished. |
| I04 | Covered | `W.test_missing_terminal_cli_result_retains_unknown_attempt` | A requested mutating CLI attempt without its terminal record remains unknown, retains a `CALL_RESULT_MISSING` finding and invalidates dependent geometry. |
| I05 | Covered | `W.test_terminal_result_without_request_is_not_admitted_as_execution`; `R.test_already_safe_does_not_ignore_an_unresolvable_explicit_solve_reference`; `A.test_malformed_direct_artifact_solve_id_not_certified` | Orphan/malformed/unresolvable links cannot supply a valid solve. The adapter calls an orphan CLI group `EXECUTION_AMBIGUOUS`; malformed individual references may be `CALL_LINK_INVALID`. |
| I06 | Covered | `W.test_duplicate_conflicting_terminal_results_are_rejected`; `W.test_overlapping_mutating_attempts_do_not_get_a_favorable_order`; `S.test_uncertain_order_still_retains_proved_accepted_value` | Conflicting results and ambiguous overlaps cannot acquire invented order; an independently observed illegal value is still available to constraint checks. |
| I07 | Covered | `W.test_exit_envelope_contradiction_cannot_certify_transition`; `W.test_producer_parse_cannot_override_raw_cli_result` | Raw process/envelope contradictions make transitions unestablished. A conflicting producer parse does not replace the raw result. |
| I08 | Covered | `W.test_unsupported_schema_never_certifies_capture`; `W.test_unsupported_command_never_becomes_an_ignored_readonly_action`; `A.test_unknown_capture_profile_not_certified` | Unsupported versions/actions are explicit evidence issues, not assumed compatible semantics. |
| I09 | Covered | `C.test_blocked_proposal_is_diagnostic`; `P.test_guard_and_recovery_are_diagnostics` | A blocked undispatched proposal is diagnostic and does not become an executed mutation. |
| I10 | Covered | `C.test_blocked_dispatched_action_is_failure` | Linked actual dispatch contradicting a block produces `GUARD_EXECUTION_CONTRADICTION`. The test distinguishes dispatch from a mere proposed command. |
| I11 | Covered | `W.test_nonfinite_and_duplicate_key_raw_json_is_rejected`; `W.test_boolean_and_unit_strings_do_not_become_numeric_safety_factors`; `C.test_boolean_never_counts_as_number` | Nonfinite wire numbers are parse errors; booleans, numeric strings and unit-bearing strings do not supply a finite numerical SF. |
| I12 | Covered | `A.test_malformed_bundle_does_not_abort_other_inputs`; `P.test_200_mixed_inputs_preserve_denominator_and_exact_permutation_results` | Malformed inputs remain in batch accounting, valid neighbors are evaluated, and every requested entry is evaluated or explicitly rejected. |

## Workflow and saved output: C01–C24

| Row | Status | Exact automated assertions | Established behavior / scope |
| --- | --- | --- | --- |
| C01 | Covered | `C.test_already_safe_requires_no_save`; `C.test_saved_optional_already_safe_baseline_is_not_a_repair`; `R.test_already_safe_baseline_survives_closed_session_cleanup` | A valid safe original requires neither mutation nor save; optional baseline saves do not become claimed repairs; cleanup does not rewrite the historical original analysis. |
| C02 | Covered | `P.test_valid_full_bundle_all_required_dimensions_pass`; `C.test_valid_repair_and_exact_allowed_boundaries` | Complete verified one-parameter repair, saved projection and final publication pass their separate dimensions. |
| C03 | Covered | `R.test_wrong_part_cannot_supply_selected_named_part_result`; `C.test_wrong_part_exploration_is_not_erased_by_valid_final` | Wrong part/revision cannot supply the selected result; an earlier wrong-part process violation survives a later valid result. |
| C04 | Covered | `C.test_two_final_parameters_fail` | The selected full parameter map must differ from original in exactly one value. |
| C05 | Covered | `S.test_repeated_assignments_to_one_parameter_are_allowed`; `S.test_equal_value_set_invalidates_live_but_not_saved_certificate`; `C.test_stale_save_fails_even_when_geometry_values_restore` | Number of set calls is not number of final parameter differences. Equal-value assignments still invalidate analysis. |
| C06 | Covered | `R.test_independent_parameter_families_restore_and_final_uses_only_last` | Different parameter families can be explored across observed original restorations; the final selected repair is checked independently of the union of explored parameter names. |
| C07 | Covered | `S.test_switching_parameter_or_trial_requires_new_restore`; `C.test_two_final_parameters_fail` | A new family or explicit trial without restoration is rejected; accumulated final changes separately fail the final parameter predicate. |
| C08 | Covered | `R.test_flange_constraint_boundaries_accept_equality_and_reject_each_outside`; `P.test_old_violation_does_not_disappear_or_corrupt_final_artifact`; `C.test_partial_mutation_can_prove_violation` | Both manufacturing limits accept equality and reject the immediately tested outside values; prior violations survive recovery; partial evidence can prove a violation. |
| C09 | Covered | `C.test_blocked_proposal_is_diagnostic`; `P.test_guard_and_recovery_are_diagnostics` | A proposed illegal value that is safely blocked does not contaminate actual geometry or manufacturing compliance. |
| C10 | Covered | `R.test_each_default_load_component_is_checked_against_original`; `C.test_wrong_default_load` | Face, force and direction are each independently compared with the trusted original default. |
| C11 | Covered | `C.test_missing_direction_is_unknown`; `S.test_explicit_load_direction_flag_before_positionals` | Missing effective direction remains unknown. Correct explicit direction flags work even before positional arguments. |
| C12 | Covered | `P.test_semantic_stale_detected_with_raw_evidence`; `C.test_stale_save_fails_even_when_geometry_values_restore` | A schema-valid, hash-valid stale trace produces `STALE_SOLVE` with raw references; restoring numbers cannot revive a certificate. |
| C13 | Covered | `P.test_valid_full_bundle_all_required_dimensions_pass`; `S.test_readback_proves_effect_of_failed_set_and_recovers_current_geometry` | A new mesh/load/converged solve can certify the selected changed state after complete current geometry is established. |
| C14 | Covered | `R.test_new_save_after_reset_cannot_reuse_old_solve`; `S.test_gap_invalidates_current_but_retains_historical_saved_artifact` | A newly saved state cannot cite a pre-reset solve. The independent historical-artifact control remains valid. |
| C15 | Covered | `S.test_failed_set_does_not_guess_effects_and_later_open_recovers`; `S.test_readback_proves_effect_of_failed_set_and_recovers_current_geometry`; `C.test_unknown_failed_mutation_cannot_pass_process_after_reset`; `R.test_successful_unreadable_set_effects_do_not_pass_process_after_restore` | A failed or unreadable mutating attempt is neither automatically atomic nor automatically illegal; raw post-state can establish effects, while restoration alone cannot erase unknown earlier effects. |
| C16 | Covered | `C.test_below_target_is_not_rounded_up` | A claimed result below the exact SF target fails target achievement and cannot become a successful repair. |
| C17 | Covered | `C.test_below_target_is_not_rounded_up` | The tested `1.9996`-style boundary does not pass by display rounding; there is no numerical epsilon on the task target. |
| C18 | Covered | `C.test_explicit_estimate_substitution_fails_but_missing_solve_is_unknown`; `S.test_documented_readonly_commands_accept_list_string_and_empty_payloads` | An explicit handbook/estimate substitution fails FEA-source requirements; merely calling a supported read-only estimate helper does not invalidate a real solve. |
| C19 | Covered | `C.test_complete_omitted_save_is_separate_from_missing_artifact`; `R.test_complete_failed_save_establishes_not_delivered_not_unknown` | Known missing/failed required save is distinguished from missing artifact bytes and from unknown delivery after interruption. |
| C20 | Covered | `W.test_artifact_hash_mismatch_remains_an_integrity_failure` | Changed bytes cannot pass the original event hash or completion inventory; the artifact mismatch remains a failure. |
| C21 | Covered | `W.test_hash_valid_artifact_with_wrong_geometry_fails_content_check`; `C.test_artifact_projection_rejects_wrong_content_not_key_order` | A valid hash is not semantic correctness; saved geometry and solve projection must agree while incidental JSON key order is ignored. |
| C22 | Covered | `C.test_wrong_publication_path_and_overwrite`; `W.test_equivalent_platform_separators_preserve_logical_publication` | Wrong destination and overwritten selected output fail; supported equivalent logical platform separators do not cause a false failure. |
| C23 | Covered | `C.test_explicit_unapproved_material_edit_fails`; `S.test_first_readback_must_match_the_opened_original` | Explicit forbidden source fields and unexpected original parameter state are not hidden by a valid final parameter count. |
| C24 | Covered | `C.test_nonconverged_success_cannot_certify_result`; `S.test_nonconverged_solve_is_not_a_valid_certificate` | Exit success plus finite SF does not replace explicit convergence. |

## Outcomes and claims: O01–O07

| Row | Status | Exact automated assertions | Established behavior / scope |
| --- | --- | --- | --- |
| O01 | Covered | `C.test_visible_claim_is_independent`; `C.test_honest_exhaustion_still_checks_reported_sf`; `R.test_exhaustion_still_rejects_a_false_structured_parameter_claim`; `R.test_already_safe_does_not_ignore_an_unresolvable_explicit_solve_reference` | Claims remain assertions on every outcome branch, including unsuccessful runs; explicit links cannot be silently ignored. |
| O02 | Covered | `P.test_exhaustion_reporting_separate_from_achievement`; `C.test_honest_exhaustion_separates_reporting` | Honest completed bounded exhaustion has reporting pass, repair not achieved and feasibility unknown. |
| O03 | Covered | `C.test_infeasibility_requires_implemented_proof_verifier` | A finite search or assertion cannot establish global impossibility. |
| O04 | Intentionally unsupported in v1 | `C.test_infeasibility_requires_implemented_proof_verifier` verifies rejection, not proof acceptance | No independent complete-domain proof verifier is implemented. This was explicitly excluded from the approved first evaluator. An accepted infeasibility proof remains a future capability, not an untested positive claim. |
| O05 | Covered | `P.test_guard_and_recovery_are_diagnostics`; `C.test_recovered_cli_error_does_not_fail_valid_final` | A recovered CLI error remains diagnostic when the final independent evidence is valid. |
| O06 | Covered | `C.test_honest_execution_failure_without_baseline_can_report_correctly`; `R.test_complete_failed_save_establishes_not_delivered_not_unknown`; `C.test_old_recovered_error_does_not_certify_failure_termination` | Honest observed execution failure can be reported accurately. Known failed delivery and unestablished repair are distinguished; an old recovered error does not prove failure termination. |
| O07 | Covered | `C.test_visible_claim_is_independent`; `C.test_malformed_claim_fields_never_raise` | Structured and supported visible claims are checked independently. Malformed/unsupported visible claims remain unknown rather than being inferred with an API call. |

## Additional accepted requirements and controls

- **Reset between runs:** `R.test_complete_run_missing_required_reset_does_not_pass_process`.
- **Data-driven extra case and correct default face:**
  `P.test_added_case_uses_data_including_non_mounting_default` evaluates
  `housing_v1` using `face_lid`, without inheriting flange constraints.
- **Alternate API/harness boundary:** `P.test_explicit_api_adapter_seam_preserves_grade`
  exercises the adapter registration seam and equivalent semantic grade. It
  does not establish compatibility with an API that has not been connected.
- **Offline operation:** `P.test_evaluation_has_no_process_or_network_dependency`
  makes process creation and socket construction raise if attempted during grading.
- **Repeatability and batch order:** `A.test_batch_permutation_does_not_change_reports`
  and `P.test_200_mixed_inputs_preserve_denominator_and_exact_permutation_results`
  compare deterministic report bytes across permutations.
- **Duplicate identities and output isolation:**
  `A.test_duplicate_run_rejection_does_not_depend_on_order`,
  `A.test_summary_input_id_does_not_overwrite_batch_metadata` and
  `P.test_reports_cannot_overwrite_evidence_or_existing_runs`.
- **Tunable diagnostic budgets:**
  `C.test_efficiency_warning_does_not_change_engineering` and
  `P.test_warning_budgets_are_explicit_and_do_not_change_correctness`.
- **Explicit resource limits:** `P.test_resource_limits_are_explicit_unknown_not_pass`.
- **Operational versus semantic success:**
  `P.test_cli_success_is_report_execution_not_engineering_verdict` and
  `P.test_internal_error_is_not_reported_as_bad_agent_evidence`.
- **Capture causality:** the seven raw-bundle controls in
  [test_capture_links.py](../tests/test_capture_links.py) require non-null CLI
  and guard references to resolve to tool boundaries in the correct order,
  while retaining valid harness-only calls and enclosed tool executions.
- **Trusted configuration validation:**
  `P.test_custom_case_rejects_missing_identity_fields_before_grading` rejects
  incomplete original revision/material metadata before grading begins.

## Reference-audit additions in 1.1.0

- [18 readiness regressions](../tests/test_readiness_review.py) cover artifact
  causal ordering, later writes to the publication destination, separate private
  save locations, known/unknown effects, same-byte rewrites, re-publication and
  complete versus incomplete failure evidence. Exact decisions and test names
  are in [READINESS_REVIEW.md](READINESS_REVIEW.md).
- [Four Tau²-inspired regressions](../tests/test_tau2_review.py) require summary
  membership for adverse checks, accept alternate valid trajectories, reject
  unchanged unsafe no-op repairs, and retain proved violations in partial traces.
- `P.test_report_pins_effective_case_and_installed_code` checks effective-policy
  and source provenance. The existing 200-input test now also requires every
  dimension's denominator to remain 200, including all three rejected entries.
- [verify.py](../scripts/verify.py) asserts 19 bundled outcomes, including two
  actual live producer captures and a scripted producer guard check, with
  unchanged raw bytes and independent source-kind assertions.
- [Optional Scout contract tests](../scout_setup/test_bridge.py) validate the
  separate viewer import. Its persisted scan and reference parity are recorded
  in [SCOUT_AUDIT.md](SCOUT_AUDIT.md); these tests do not require adding Scout to
  the standard-library grader's runtime.

## Direct rubric portability proof

The later [five-requirement rubric check](EVAL_RUBRIC.md) adds two explicit
portability regressions in [test_rubric.py](../tests/test_rubric.py):
`test_unseen_case_uses_trusted_data_for_load_target_and_parameter_bounds` and
`test_foreign_harness_layout_preserves_grading_and_stale_solve_detection`.
These strengthen the earlier housing-case and adapter-registration evidence.
Eight focused checks, including these two, passed on the host and offline Docker;
the original full-suite execution record is preserved unchanged.

## Remaining boundaries

1. A new provider must supply real raw model/tool/CLI captures through the
   documented adapter seam. The existing SDK's two live bundles and scripted
   guard capture are now included and checked; they do not certify a different
   future provider before its own integration test.
2. General free-form prose interpretation is deliberately unsupported. The
   deterministic `json/1` visible-claim contract is implemented; other formats
   receive an explicit unknown result.
3. O04 positive infeasibility proof acceptance is deliberately unavailable.
   The implemented correct behavior is to refuse an unsupported proof claim.
4. The reducer supports the pinned PartLab binary/profile, not arbitrary future
   binaries with different atomicity, save formats or command semantics.
5. These tests cover the specified predicates and adversarial controls. They do
   not claim exhaustive formal verification, capture authenticity, physical FEA
   validity, or production-scale infrastructure calibration.
