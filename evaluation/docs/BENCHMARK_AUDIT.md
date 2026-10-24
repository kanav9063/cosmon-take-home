# Benchmark reference and requirement coverage

Reviewed October 23, 2026 (ET). The unchanged [assignment](../../TASK.md) is the
authority. This audit distinguishes preparation from implemented evidence; it
does not declare the take-home complete. The evaluator is now implemented;
the [test matrix](EVAL_TEST_MATRIX.md) links executed coverage and the
[runbook](../EVAL_RUN.md) provides reproducible commands. Reference research
below is retained from the earlier audit. The subsequent
[Tau²/Scout acceptance audit](REFERENCE_ACCEPTANCE.md) records the new reference
review, actual SDK captures, corrections and final executed checks.

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
two original scripted captures test PartLab behavior but are not live model runs.
The current 19-input set additionally includes two completed live SDK captures
and its scripted guard check, copied unchanged with
[source provenance](../fixtures/producer-provenance.json).

| Assignment requirement | Planned implementation/check | Current evidence and completion gate |
| --- | --- | --- |
| One hour total, approximately 30 minutes per part | Timed sequence and preparation disclosure in EVAL_PLAN | Recording pending; disclose pre-existing setup and preserve the time-box. |
| State plan/assumptions; build runnable slice; narrate diagnosis and correction | Show commands, inspect output, explain failed checks and fixes | Pending recorded exercise; verify AI-generated work visibly. |
| Clean agent loop, sensible prompt/tool surface; explain choices | Separate named SDK actions; CLI, decisions and capture boundaries | Existing SDK boundaries inspected and its complete raw captures parsed. Agent implementation and its presentation remain owned by the SDK exercise. |
| Run at least `bracket_v3` and `flange_v1` | Two real run bundles with distinct IDs and part metadata | Both existing live captures are included under `fixtures/producer/` and evaluated. No new model calls were made by this audit. |
| Reset between runs | Logged reset/private per-run session; I01/C06 | Required baseline reset predicate and negative regression; actual scripted captures reset in isolated directories. |
| Named part, original default load, correct FEA workflow and reported SF | C01–C03, C10–C14; raw solve and effective-load evidence | Implemented, including housing's face_lid control; scripted and live bracket/flange traces parsed. |
| When SF <2, propose one parameter change; achieve SF >=2, rerun and save `outputs/<part>.json` | C02, C04–C07, C12–C24; compare original/final full maps, fresh converged solve and saved bytes | Scripted and existing live bracket repairs verify SF 1.428 to 3.072, thickness 5, saved bytes and final publication. Live flange honestly exhausted its bounded search without a repair. |
| Flange thickness <=5; hole diameter >=4 | C08/C09 plus exact boundary tests | Implemented exact limits, blocked/actual mutation distinction, and restored-violation history tests. |
| Report no possible fix clearly instead of forcing a change | O02–O04; distinguish exhaustion, proof and execution failure | Separate outcome/reporting predicates; scripted flange one-candidate exhaustion. Independent global proof verification explicitly unsupported. |
| SDK preconditions, ordering, recovery | State reconstruction; C12–C15, O05/O06 | Implemented generation transitions, missing/overlapping execution, failed-effects readback, recovery regressions. |
| Avoid unnecessary fetches and large context blobs | Model-visible versus raw byte counts; repeated-read metrics | Implemented measurements and explicit optional diagnostic budgets. Actual provider token usage remains unmapped/null. |
| Separate CLI/decisions/capture; add a part without rewriting; no hardcoded solve answers | Case-driven policy and adapter/state/check modules; use raw PartLab results | Five independent evaluator modules, trusted case data, housing portability and registered adapter tests. Expected fixture numbers stay outside grading code. |
| Persist raw messages, tool calls and results for each run | Versioned bundle, execution ledger, raw SDK objects and CLI bytes | Existing live SDK bundles pass raw model/tool/CLI boundary and completion validation. Future exporters must pass the documented local contract too. |
| Small repeatable non-happy-path check, with explanation | Blocked flange mutation or recovered CLI failure with linked raw evidence | Actual producer guard-check capture is included and evaluated; synthetic blocked/recovered controls separately assert grading semantics. Harbor no-op remains only an infrastructure control. |
| Eval consumes Part 1 raw traces and emits structured reports | Offline adapter -> reconstruction -> predicates -> JSON report | Implemented and run on 19 bundles: 14 synthetic, three scripted, two existing live. See current acceptance records and API_INTEGRATION.md for a different exporter. |
| General schema; support a fourth case or another harness | Versioned adapter; data-driven cases; portability checks | Implemented; housing default-face and explicit custom-adapter tests; six trusted cases configured. |
| Principled tunable heuristics; readable actionable report; defend scoring | Named config, exact hard limits, evidence-linked findings, separate outcome dimensions | Implemented JSON reports plus readable REPORTS.md index, explicit resource/warning configuration, detailed decision records. |
| Deliberately flawed trace; demonstrate its specific detection | C12 synthetic stale solve; valid IDs/hashes; assert `STALE_SOLVE` and evidence links | Implemented and asserted against valid control with raw references and no unrelated manufacturing or single-parameter defect. |
| Show checks for outcomes, saved parts and eval | Independently parse raw results and artifact content; positive/negative controls | Scripted and live capture -> report -> saved-part chains are checked; current acceptance records include independent negative controls. |
| Concise RUN.md: clean reset, agent/check/eval commands, dependencies, parts, passes, main limitation | Fill unchanged starter template with commands actually run | EVAL_RUN.md is complete for this evaluator. The original RUN.md is preserved; the SDK exercise owns the combined handoff and recording. |
| Submit source, checks, >=2 raw traces, eval output and any saved parts | Final inventory with readable paths and hashes | Evaluator source, checks, live raw bundles, captured saved/published bytes and reports are retained outside ignored directories. Combined packaging and recording remain the agent exercise's handoff. |
| No production packaging or CI expected | Prioritize runnable core; name uncovered cases | Preserve this scope; an extensive planned matrix is not a requirement to implement every edge case in one hour. |

Accepted policies beyond the README's literal wording are recorded in
[EVAL_PLAN.md](EVAL_PLAN.md): restore original state for independent parameter
trials, keep forbidden executed mutations as compliance failures, treat safely
blocked/recovered incidents as diagnostics, and separate repair achievement from
reporting accuracy. The SDK's proposed stricter one-mutation-per-trial rule is
**not yet accepted**; see the [contract review](EVAL_TRACE_REQUIREMENTS.md).

## Current completion and integration handoff

The prior evaluator gates are closed: complete/blocked/stale/partial controls
are implemented; two live producer captures and a producer guard check are
included; the 19-input acceptance run checks their independent outcomes. The
[current acceptance record](REFERENCE_ACCEPTANCE.md) links source-pinned host,
offline Docker, Harbor and Scout evidence.

A different model API or SDK must produce the documented capture or register
its trusted adapter, then run the existing conformance command. The existing
SDK also needs to select this 1.1.0 evaluator release if it continues using a
vendored copy; this audit does not silently change sibling source. No further
evaluator feature is required for that supported integration.

The human recording, combined agent/eval RUN.md and final exercise submission
are separate handoff responsibilities. This preparation cannot retroactively
establish the requested one-hour recorded workflow.

Docker/Harbor readiness is tracked separately in [HARBOR_SETUP.md](HARBOR_SETUP.md)
and [verification.json](../harbor_setup/verification.json). It must never be used
as a substitute for one of these completion gates.
