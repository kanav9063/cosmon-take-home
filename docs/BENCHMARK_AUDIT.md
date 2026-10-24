# Benchmark reference and requirement coverage

Reviewed October 23, 2026 (ET). The unchanged [assignment](../README.md) is the
authority. This audit distinguishes preparation from implemented evidence; it
does not declare the take-home complete. The evaluator is now implemented;
the [test matrix](EVAL_TEST_MATRIX.md) links executed coverage and the
[runbook](../EVAL_RUN.md) provides reproducible commands. Reference research
below is retained from the earlier audit; it was not refreshed during offline implementation.

## Reference checked

The latest official release checked was **Terminal-Bench 4.0.0**, commit
`452bf305c6daa62fc59061d22133a7cbc7c1572e`. Use this immutable revision for task
examples; current authoring documentation on `main` can change.
[Release](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0)
and [official announcement](https://www.tbench.ai/news/terminal-bench-4-0).

Two relevant released tasks were inspected:

| Task | What it checks | Lesson for PartLab |
| --- | --- | --- |
| [cad-model](https://github.com/harbor-framework/terminal-bench/tree/452bf305c6daa62fc59061d22133a7cbc7c1572e/tasks/cad-model) | Explicit STEP artifact export; separate verifier checks geometry, topology and physical properties, with justified numerical tolerances | Inspect the saved part's actual bytes and solve evidence, not only the agent's assertion. A tolerance justified for tessellation does not justify relaxing our exact SF or manufacturing limits. |
| [batched-eval-parity](https://github.com/harbor-framework/terminal-bench/tree/452bf305c6daa62fc59061d22133a7cbc7c1572e/tasks/batched-eval-parity) | Independent reference results, deterministic repeat/order checks, separate correctness and runtime tests | Keep evaluator logic independent; require stable findings when unrelated input bundles are reordered; separate efficiency from engineering correctness. |

## Relevant lessons and current disposition

| Check | Disposition here |
| --- | --- |
| Requirement-to-check mapping in both directions | The matrix below maps every assignment requirement to evidence. Every hard finding must cite the assignment or an explicitly accepted policy, rather than an unstated benchmark preference. [Current TB rubric](https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-implementation.toml) |
| Independent verifier and trusted original inputs | Harbor smoke uses an explicit separate verifier with pristine references in its own image. The implemented offline evaluator parses raw evidence and uses independent trusted cases; it imports no producer decisions. [Harbor isolation](https://docs.harborframework.com/tasks/separate-verifier) |
| Explicit artifact transfer and completeness | Smoke declares `/logs/artifacts`, checks collection manifests and required files, and checks hashes. Future real tasks must export the complete raw bundle, final response and saved parts; `/logs/agent` is not automatically transferred to a separate verifier. [Artifact declaration](https://docs.harborframework.com/tasks/artifacts), [collection](https://docs.harborframework.com/jobs/artifact-collection) |
| Positive and negative controls | Two scripted smoke trials and one no-op test infrastructure. The evaluator now detects stale solve, wrong load, forbidden mutation, missing evidence and overwritten publication against passing controls. Actual model behavior still needs its own runs. [TB review workflow](https://github.com/harbor-framework/terminal-bench/blob/main/docs/REVIEWING.md) |
| Explicit resources and errors | Smoke pins CPU, memory, network and timeouts and disables retrying failed trials. Core runs must record search/CLI/model budgets, and distinguish exhaustion from infrastructure or capture failure. TB's much larger time limits do not override the one-hour assignment. [Release resource changes](https://www.tbench.ai/news/terminal-bench-4-0), [Harbor error classification](https://docs.harborframework.com/jobs/error-classification) |
| Reproducible re-evaluation | Preserve raw inputs, schema/config/binary versions, digests and evaluator version. The standalone offline command remains required even if Harbor is used. Harbor regrade additionally requires its results and artifact inventory. [Regrade requirements](https://docs.harborframework.com/jobs/regrade) |
| Version-specific runtime truth | Installed Harbor is **0.24.0**, task schema **1.4**. Explicitly set separate mode; current docs describe defaults introduced in 0.25. Check installed source and resolved task config rather than assuming the live docs match. |

Full Terminal-Bench execution, leaderboard publication, canaries, large-scale
parallelism, paid adversarial runs, CI and production packaging are not needed
for this assignment. Reference benchmark conventions cannot replace PartLab's
explicit process, trace and tool-use requirements with an outcome-only reward.
The smoke's binary reward means only that its infrastructure contract passed.

## Assignment coverage and evidence still needed

The table distinguishes implemented evaluator evidence from the remaining
producer/model exercise. “Smoke” refers only to the infrastructure task. The
two actual scripted captures test PartLab behavior but are not live model runs.

| Assignment requirement | Planned implementation/check | Current evidence and completion gate |
| --- | --- | --- |
| One hour total, approximately 30 minutes per part | Timed sequence and preparation disclosure in EVAL_PLAN | Recording pending; disclose pre-existing setup and preserve the time-box. |
| State plan/assumptions; build runnable slice; narrate diagnosis and correction | Show commands, inspect output, explain failed checks and fixes | Pending recorded exercise; verify AI-generated work visibly. |
| Clean agent loop, sensible prompt/tool surface; explain choices | Separate named SDK actions; CLI, decisions and capture boundaries | Design only; inspect actual source and one end-to-end run. |
| Run at least `bracket_v3` and `flange_v1` | Two real run bundles with distinct IDs and part metadata | Neither live run exists in this eval workspace. Scripted bracket smoke does not count. |
| Reset between runs | Logged reset/private per-run session; I01/C06 | Required baseline reset predicate and negative regression; actual scripted captures reset in isolated directories. |
| Named part, original default load, correct FEA workflow and reported SF | C01–C03, C10–C14; raw solve and effective-load evidence | Implemented, including housing's face_lid control; real scripted bracket/flange traces parsed. Live agent traces pending. |
| When SF <2, propose one parameter change; achieve SF >=2, rerun and save `outputs/<part>.json` | C02, C04–C07, C12–C24; compare original/final full maps, fresh converged solve and saved bytes | Real scripted bracket repair: SF 1.428 to 3.072, thickness 5, saved bytes checked. Model-directed repair not claimed. |
| Flange thickness <=5; hole diameter >=4 | C08/C09 plus exact boundary tests | Implemented exact limits, blocked/actual mutation distinction, and restored-violation history tests. |
| Report no possible fix clearly instead of forcing a change | O02–O04; distinguish exhaustion, proof and execution failure | Separate outcome/reporting predicates; scripted flange one-candidate exhaustion. Independent global proof verification explicitly unsupported. |
| SDK preconditions, ordering, recovery | State reconstruction; C12–C15, O05/O06 | Implemented generation transitions, missing/overlapping execution, failed-effects readback, recovery regressions. |
| Avoid unnecessary fetches and large context blobs | Model-visible versus raw byte counts; repeated-read metrics | Implemented measurements and explicit optional diagnostic budgets. Actual provider token usage remains unmapped/null. |
| Separate CLI/decisions/capture; add a part without rewriting; no hardcoded solve answers | Case-driven policy and adapter/state/check modules; use raw PartLab results | Five independent evaluator modules, trusted case data, housing portability and registered adapter tests. Expected fixture numbers stay outside grading code. |
| Persist raw messages, tool calls and results for each run | Versioned bundle, execution ledger, raw SDK objects and CLI bytes | Contract reviewed but unagreed. Smoke CLI logs and synthetic fixtures are not raw live-agent traces. |
| Small repeatable non-happy-path check, with explanation | Blocked flange mutation or recovered CLI failure with linked raw evidence | Pending agent check. Harbor no-op tests missing output, not agent recovery or constraint handling. |
| Eval consumes Part 1 raw traces and emits structured reports | Offline adapter -> reconstruction -> predicates -> JSON report | Implemented and run on 16 bundled examples, including two real scripted captures. Connect real model/SDK exporter using API_INTEGRATION.md. |
| General schema; support a fourth case or another harness | Versioned adapter; data-driven cases; portability checks | Implemented; housing default-face and explicit custom-adapter tests; six trusted cases configured. |
| Principled tunable heuristics; readable actionable report; defend scoring | Named config, exact hard limits, evidence-linked findings, separate outcome dimensions | Implemented JSON reports plus readable REPORTS.md index, explicit resource/warning configuration, detailed decision records. |
| Deliberately flawed trace; demonstrate its specific detection | C12 synthetic stale solve; valid IDs/hashes; assert `STALE_SOLVE` and evidence links | Implemented and asserted against valid control with raw references and no unrelated manufacturing or single-parameter defect. |
| Show checks for outcomes, saved parts and eval | Independently parse raw results and artifact content; positive/negative controls | Actual scripted capture -> report -> saved-part chain checked. Live model chain remains producer integration work. |
| Concise RUN.md: clean reset, agent/check/eval commands, dependencies, parts, passes, main limitation | Fill unchanged starter template with commands actually run | Template remains TODO until actual exercise results exist. |
| Submit source, checks, >=2 raw traces, eval output and any saved parts | Final inventory with readable paths and hashes | Incomplete. Put submission evidence outside ignored `.harbor-jobs/`; include or explicitly package it. |
| No production packaging or CI expected | Prioritize runnable core; name uncovered cases | Preserve this scope; an extensive planned matrix is not a requirement to implement every edge case in one hour. |

Accepted policies beyond the README's literal wording are recorded in
[EVAL_PLAN.md](EVAL_PLAN.md): restore original state for independent parameter
trials, keep forbidden executed mutations as compliance failures, treat safely
blocked/recovered incidents as diagnostics, and separate repair achievement from
reporting accuracy. The SDK's proposed stricter one-mutation-per-trial rule is
**not yet accepted**; see the [contract review](EVAL_TRACE_REQUIREMENTS.md).

## Minimum remaining task set

1. **Contract checkpoint:** agree a single producer revision and adapter mapping;
   parse complete, blocked, stale and partial examples on both sides. Resolve
   trial policy, outcome aliases and final artifact publication evidence.
2. **Two real agent runs:** bracket and flange, with reset, raw capture, default
   loads, constraint checks, verified outputs or honest bounded no-repair reports.
   Include one repeatable agent non-happy-path demonstration.
3. **Use the completed evaluator:** run the existing command on the new live
   bundles. Stale-solve detection, separate repair/reporting results, recovered
   error diagnostics, added-case support and deterministic mixed-batch tests are
   already implemented. No additional evaluator feature is required to connect
   a producer that conforms to the supported profile.
4. **Exercise handoff:** inspect actual live artifact inventory, complete the
   original RUN.md with agent commands and results, and make the narrated
   recording. EVAL_RUN.md already documents the finished evaluator command.

Docker/Harbor readiness is tracked separately in [HARBOR_SETUP.md](HARBOR_SETUP.md)
and [verification.json](../harbor_setup/verification.json). It must never be used
as a substitute for one of these completion gates.
