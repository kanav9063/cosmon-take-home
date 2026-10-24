# Sierra Tau² reference audit

This audit compares the implemented PartLab evaluator with the official
`sierra-research/tau2-bench` grading and run-accounting code. It uses Tau² as a
review reference; it does not claim that PartLab implements or ran the Tau²
benchmark. The comparison found no additional required grading component for
the supported PartLab task. Four additional cross-cutting regression tests were
added and executed successfully.

The supported boundary remains important: this evaluator grades persisted
PartLab evidence without executing an agent, asking a judge model, or repeating
a physical analysis. A producer must supply authentic, complete observations.
Each producer/API integration must pass the local capture contract. During this
audit the existing SDK's completed live captures became available and were
checked; see [REFERENCE_ACCEPTANCE.md](REFERENCE_ACCEPTANCE.md). A different
future exporter still requires its own conformance run.

## Reference and reproducibility

The reviewed official revision is
[`cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2`](https://github.com/sierra-research/tau2-bench/commit/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2),
whose commit timestamp is `2026-10-22T22:21:28Z`. The GitHub connector resolved
`main` once, and subsequent source reads used this commit ID. The current
reference has evolved beyond the original Tau² release, including text/voice
benchmark frames and semantic communication grading. This audit therefore
does not treat a historical description of substring grading as current policy.

Source inventory:

| Reviewed source at the pinned revision | Purpose | Git blob SHA |
| --- | --- | --- |
| [Task schema and evaluation](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/docs/evaluation.md) | Explain reference trajectories and explicit reward basis | `ae42a6df5db0fc312364c855e8ac8ab0a7bbfcf2` |
| [Evaluator dispatch](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/evaluator/evaluator.py) | Applicability, termination and component combination | `782b294cc7bfe90460dd227dda25def03fddc14f` |
| [Environment evaluator](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/evaluator/evaluator_env.py) | Predicted/gold environments, DB hashes and assertions | `12482cf3eb74e61e1987165351e1628c207e309b` |
| [Environment replay](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/environment/environment.py) | Pairing, rejected versus executed calls, strict replay | `dcb6b5a6a62190b77b7e2504d72eccd91fa113be` |
| [Action evaluator](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/evaluator/evaluator_action.py) | Reference tool-call matching | `861784876aab7f0f2bf16685b8607b50f9873fd5` |
| [Communication evaluator](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/evaluator/evaluator_communicate.py) | Semantic judge and legacy substring route | `5be74fbf0c65c9c469035ddfa34e35394eb0ccc7` |
| [Agent metrics](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/metrics/agent_metrics.py) | Repeated-trial estimator and error accounting | `f6959b005e9653f1858f463d4c73c321d6d26eef` |
| [Benchmark metrics](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/src/tau2/metrics/benchmark.py) | Pinned conditions, authoritative artifacts and complete frames | `6654008f2606f20f1f88d349d5a52ca1ec63d7f9` |
| [Plan integrity tests](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/tests/test_benchmark/test_plan_integrity.py) | Prevent duplicate/mismatched execution plans | `eae4db84889ca7965b3c09a76019da0f7d6b83fc` |

Also reviewed: the pinned
[running guide](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/docs/running-the-benchmark.md)
and
[submission guide](https://github.com/sierra-research/tau2-bench/blob/cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2/docs/leaderboard-submission.md).
No Tau² model simulation, judge request, leaderboard submission, dependency
installation or source modification was performed.

## Decisions and mapped evidence

### T01: Make required verdict membership explicit

Tau² distinguishes a computed component from one selected by `reward_basis` to
affect the final reward. Its combined evaluator rejects a required basis that
was not evaluated. This is a useful warning against calculating a failure and
then accidentally omitting it from the reported result.

PartLab retains separate `capture_integrity`, `process_compliance`,
`final_correctness`, `delivery`, `reporting_accuracy` and `repair_achievement`
dimensions. Each declares its contributing check-instance IDs. No arithmetic
average can make a forbidden mutation disappear behind a correct final part.
This preserves the user's explicit choice to separate repair and reporting.

Mapping: [eval_checks.py](../eval_checks.py), `_dimension` and the final summary
construction; [test_tau2_review.py](../tests/test_tau2_review.py),
`test_all_adverse_checks_have_an_explicit_summary_dimension`. The new test runs
all 14 synthetic scenario families and requires every failed or unknown check
to appear in a summary dimension. Diagnostics intentionally remain separate.

### T02: Accept valid alternative solutions

The reference action evaluator matches proposed tool calls against a reference
list. It is suitable only when that path is a task requirement. Our repair
problem admits multiple parameter families, candidate values and read patterns;
requiring one scripted sequence would reject valid repairs.

The local policy checks actual state and the explicitly required dependencies:
reset/original baseline, independent trial restoration, legal mutation, fresh
analysis and delivery. It does not require matching the demonstration's number
of reads, candidate values or thickness choice.

Mapping: [eval_state.py](../eval_state.py), `reconstruct`;
[test_state.py](../tests/test_state.py),
`test_repeated_assignments_to_one_parameter_are_allowed`;
[test_state_review.py](../tests/test_state_review.py),
`test_independent_parameter_families_restore_and_final_uses_only_last`;
new `test_alternative_valid_trajectories_do_not_require_a_reference_script`.
The new integration test independently accepts thickness and fillet repairs
with repeated assignments and extra read-only calls. Its SF values are
deliberately synthetic and make no claim about those real geometries.

### T03: Distinguish absent requirements from missing observations

The reference can return neutral reward for absent evaluation criteria. In our
task, absence of a required solve, raw result, saved byte snapshot or completion
record is missing evidence, not permission to pass. The trusted case defines
the requirements independently of the capture.

Local `not_applicable` therefore depends on the branch: a verified already-safe
original does not require a repair file. Required but unestablished evidence
becomes `unknown`; an observed contradiction becomes `fail`.

Mapping: [eval_checks.py](../eval_checks.py), baseline, repair/save applicability
and reporting checks; [test_checks.py](../tests/test_checks.py),
`test_already_safe_requires_no_save`,
`test_complete_omitted_save_is_separate_from_missing_artifact` and
`test_incomplete_capture_cannot_establish_final_delivery`.

### T04: An unchanged state can be correct only for the right task branch

Tau²'s gold-environment approach can intentionally accept an unchanged database
when refusing a request is correct. PartLab similarly accepts an unchanged
original when a verified baseline already meets SF 2. An unchanged unsafe
original does not satisfy a repair claim merely because its trace is complete.

Mapping: the new
`test_complete_capture_and_unchanged_unsafe_state_do_not_pass_repair` establishes
capture `pass` while repair achievement and reporting both `fail`. Existing
already-safe tests exercise the opposite, legitimate branch. No artificial
mutation or save is demanded to create visible activity.

### T05: Separate rejected proposals from executed failures

The pinned environment replay explicitly skips a pre-execution rejection. It
still replays a failed executed call because the call may have mutated state
before failing. This is directly applicable to our capture contract.

A blocked proposal is a diagnostic when no dispatch occurred. An executed
forbidden mutation fails compliance permanently, including after a restore.
A failed mutating command with unknown effects cannot establish clean process
history just because a later result is valid. An authoritative intervening
readback can resolve its effects.

Mapping: [trace_adapter.py](../trace_adapter.py), distinct event and action
records; [eval_state.py](../eval_state.py), failed actions and readback;
[test_checks.py](../tests/test_checks.py),
`test_blocked_dispatched_action_is_failure`,
`test_unknown_failed_mutation_cannot_pass_process_after_reset`, and
`test_readback_can_resolve_failed_set_effects`. The existing recovered-error
tests preserve the user's diagnostic policy without erasing real violations.

### T06: Interrupted evidence must not erase observed failures

Tau² applies a zero reward on premature termination before its component
evaluators. We retain finer information because the approved PartLab result is
a vector of evidence-backed findings. A missing tail prevents claims about
complete delivery or absence of further violations. It cannot negate a
manufacturing violation already recorded in the intact prefix.

Mapping: new
`test_interruption_preserves_an_observed_forbidden_mutation` appends an invalid
tail to an otherwise complete illegal-then-restored trace. Capture is not
passed, while process compliance remains `fail` with referenced
`MANUFACTURING_VIOLATION` evidence. This is a deliberate local policy difference,
not an attempt to reproduce Tau²'s scalar termination score.

### T07: Ground communication in supported claims

The current communication evaluator supports a semantic model judge; its
legacy substring route remains available. Neither route is necessary for our
machine-readable final statement. PartLab checks exact finite numeric claims,
the selected solve/artifact, parameter change and branch; it also compares the
persisted visible `json/1` result to the structured outcome.

A free-text statement containing a correct number is not sufficient evidence
that its meaning is correct. Unsupported prose or extra claims remain
unverified rather than receiving a substring-based pass. A hypothetical
general prose judge would add cost, nondeterminism and another API dependency
without being required by the approved scope.

Mapping: [eval_checks.py](../eval_checks.py), structured and visible
`claim_consistency`; [test_checks.py](../tests/test_checks.py),
`test_visible_claim_is_independent`, `test_below_target_is_not_rounded_up`, and
`test_honest_exhaustion_still_checks_reported_sf`.

### T08: Be explicit about replay and trust

Tau² builds predicted and gold simulator states and compares environment
hashes. Strict replay also checks replayed mutating outputs against the
recorded outputs. The local evaluator instead reconstructs state from verified
raw bytes under the pinned PartLab action semantics. It checks saved content
against save-time state and the selected solve, then checks final publication.

The source bytes' SHA/length checks establish that the evaluated bytes agree
with the bundle references; they are not a signature proving an authentic
execution occurred. The original part and local policy are separately trusted.
No producer-written `verified` or success field substitutes for raw evidence.
Independent live re-execution of an arbitrary trace is not silently introduced
as a grading dependency.

Mapping: [trace_adapter.py](../trace_adapter.py), `Reader`, action admission and
artifact extraction; [eval_checks.py](../eval_checks.py), artifact-state and
publication checks; [test_wire_coverage.py](../tests/test_wire_coverage.py),
`test_producer_parse_cannot_override_raw_cli_result` and
`test_hash_valid_artifact_with_wrong_geometry_fails_content_check`;
[test_pipeline.py](../tests/test_pipeline.py),
`test_evaluation_has_no_process_or_network_dependency`.

### T09: Freeze interpretation and independently selected task data

The reference benchmark reader validates effective run settings, task frames,
condition fingerprints and authoritative task assets instead of authenticating
assets solely from saved metadata. The equivalent local controls are the
trusted original digest, case policy, pinned binary/action profile, explicit
capture-profile version, configuration digest and versioned adapter name.

Mapping: [evaluate.py](../evaluate.py), `load_cases`, `report_run` and
`evaluate_one`; [eval_cases.json](../eval_cases.json);
[test_adapter_review.py](../tests/test_adapter_review.py),
`test_unknown_capture_profile_not_certified` and
`test_manifest_context_reference_is_validated`;
[test_pipeline.py](../tests/test_pipeline.py),
`test_custom_case_rejects_missing_identity_fields_before_grading` and
`test_warning_budgets_are_explicit_and_do_not_change_correctness`.

The producer must preserve the actual model request/settings, tool schema and
task/policy bytes. The evaluator preserves and references those bytes; it does
not invent a model seed, temperature or token count if the provider did not
expose one. A model API change does not require changing engineering policy.

### T10: Keep batch denominators and trial meanings honest

The reference repeated-trial metric is `C(successes,k) / C(trials,k)`, an
estimate of success on all k trials. It is different from best-of-k success.
Its newer benchmark summaries also distinguish expected, missing, unscored
and infrastructure-error trials and apply a documented aggregation policy.

Our batch is an explicit collection of requested captures. It preserves every
requested input as evaluated or explicitly rejected, including duplicate run
IDs and malformed bundles. It reports dimension counts; it does not label
synthetic examples as model success rates, treat parameter-search candidates
as independent model rollouts, or invent a pass^k statistic.

Mapping: [evaluate.py](../evaluate.py), `evaluate_batch`;
[test_pipeline.py](../tests/test_pipeline.py),
`test_200_mixed_inputs_preserve_denominator_and_exact_permutation_results`;
[test_adapter_review.py](../tests/test_adapter_review.py),
`test_duplicate_run_rejection_does_not_depend_on_order`.

Scheduling repeated independent model runs, recording provider configuration,
selecting a study population and preserving retry provenance are producer/study
responsibilities. When reporting model-level rates, the caller must provide the
complete intended input manifest, including failed captures. A directory with
only selected successes is not evidence of study completeness. No current
PartLab requirement asks for a Tau² leaderboard or its error-exclusion policy.

### T11: Preserve errors and diagnostics without hiding evaluator failure

The comparison reinforces the distinction between task failure, incomplete
observations and machinery failure. Local malformed evidence produces an
explicit issue/rejected input. A programming or output-writing failure aborts
the batch with an abnormal exit and best-effort `aborted.json`; it is not
turned into a bad agent score. A successful CLI exit means reports were written,
not that the agent repaired a part.

Mapping: [test_pipeline.py](../tests/test_pipeline.py),
`test_internal_error_is_not_reported_as_bad_agent_evidence` and
`test_cli_success_is_report_execution_not_engineering_verdict`;
[test_adapter_review.py](../tests/test_adapter_review.py),
`test_malformed_bundle_does_not_abort_other_inputs`.

## Execution recorded for this audit

Command, from the repository root:

```bash
python3 -m unittest discover -s tests -p test_tau2_review.py -v
```

Result: **4 tests passed**, including the 14-scenario dimension-membership
subtests and both alternative-trajectory controls. The command uses only local
synthetic temporary bundles and deletes them on completion. It neither writes
the SDK checkout nor calls PartLab, a model endpoint, or the internet.

The full test suite, offline Docker checks and saved example reports are
covered by the repository's release verification, not represented as having
been rerun by this four-test audit command. See [EVAL_RUN.md](../EVAL_RUN.md),
[EVAL_COVERAGE.md](EVAL_COVERAGE.md) and the release verification record for the
combined results.

## Applicability and remaining integration boundary

No Tau² user simulator, dual-control telecom environment, audio transport,
multilingual pack, semantic judge, golden-action database or leaderboard
submission is needed for the PartLab assignment. Copying them would change the
task and create dependencies unrelated to the requested evaluator.

Within the supported PartLab scope, this review leaves no new grading-backend
implementation item. The future SDK/API connection must still produce a real
capture and pass [API_INTEGRATION.md](API_INTEGRATION.md), including paired raw
model/tool/CLI records, exact final visible output, immutable saved bytes and
completion publication. That is an acceptance condition on the integration,
not a claim that synthetic tests certify an unseen exporter. A different
CAD/CAE tool would additionally need its own validated state/action profile.
