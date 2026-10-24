# Benchmark reference and requirement coverage

Reviewed October 23, 2026 (ET). The unchanged [assignment](../README.md) is the
authority. This audit distinguishes preparation from implemented evidence; it
does not declare the take-home complete. The [eval plan](EVAL_PLAN.md) and
[test matrix](EVAL_TEST_MATRIX.md) remain implementation plans.

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
| Independent verifier and trusted original inputs | Harbor smoke uses an explicit separate verifier with pristine references in its own image. The future offline evaluator must also avoid importing producer decisions or trusting producer verdicts. [Harbor isolation](https://docs.harborframework.com/tasks/separate-verifier) |
| Explicit artifact transfer and completeness | Smoke declares `/logs/artifacts`, checks collection manifests and required files, and checks hashes. Future real tasks must export the complete raw bundle, final response and saved parts; `/logs/agent` is not automatically transferred to a separate verifier. [Artifact declaration](https://docs.harborframework.com/tasks/artifacts), [collection](https://docs.harborframework.com/jobs/artifact-collection) |
| Positive and negative controls | Two scripted smoke trials and one no-op test infrastructure. Actual agent behavior and deliberately flawed-trace detection still need their own checks. If real tasks are wrapped in Harbor, repeat oracle/no-op controls against those tasks too. [TB review workflow](https://github.com/harbor-framework/terminal-bench/blob/main/docs/REVIEWING.md) |
| Explicit resources and errors | Smoke pins CPU, memory, network and timeouts and disables retrying failed trials. Core runs must record search/CLI/model budgets, and distinguish exhaustion from infrastructure or capture failure. TB's much larger time limits do not override the one-hour assignment. [Release resource changes](https://www.tbench.ai/news/terminal-bench-4-0), [Harbor error classification](https://docs.harborframework.com/jobs/error-classification) |
| Reproducible re-evaluation | Preserve raw inputs, schema/config/binary versions, digests and evaluator version. The standalone offline command remains required even if Harbor is used. Harbor regrade additionally requires its results and artifact inventory. [Regrade requirements](https://docs.harborframework.com/jobs/regrade) |
| Version-specific runtime truth | Installed Harbor is **0.24.0**, task schema **1.4**. Explicitly set separate mode; current docs describe defaults introduced in 0.25. Check installed source and resolved task config rather than assuming the live docs match. |

Full Terminal-Bench execution, leaderboard publication, canaries, large-scale
parallelism, paid adversarial runs, CI and production packaging are not needed
for this assignment. Reference benchmark conventions cannot replace PartLab's
explicit process, trace and tool-use requirements with an outcome-only reward.
The smoke's binary reward means only that its infrastructure contract passed.

## Assignment coverage and evidence still needed

“Planned” means a design/check exists, not an executed pass. “Smoke” refers only
to the scripted infrastructure task. It is not a live model run or a repair.

| Assignment requirement | Planned implementation/check | Current evidence and completion gate |
| --- | --- | --- |
| One hour total, approximately 30 minutes per part | Timed sequence and preparation disclosure in EVAL_PLAN | Recording pending; disclose pre-existing setup and preserve the time-box. |
| State plan/assumptions; build runnable slice; narrate diagnosis and correction | Show commands, inspect output, explain failed checks and fixes | Pending recorded exercise; verify AI-generated work visibly. |
| Clean agent loop, sensible prompt/tool surface; explain choices | Separate named SDK actions; CLI, decisions and capture boundaries | Design only; inspect actual source and one end-to-end run. |
| Run at least `bracket_v3` and `flange_v1` | Two real run bundles with distinct IDs and part metadata | Neither live run exists in this eval workspace. Scripted bracket smoke does not count. |
| Reset between runs | Logged reset/private per-run session; I01/C06 | Verified for smoke; demonstrate in actual raw traces. |
| Named part, original default load, correct FEA workflow and reported SF | C01–C03, C10–C14; raw solve and effective-load evidence | Smoke verifies unchanged bracket baseline SF 1.428. Actual agent traces pending. |
| When SF <2, propose one parameter change; achieve SF >=2, rerun and save `outputs/<part>.json` | C02, C04–C07, C12–C24; compare original/final full maps, fresh converged solve and saved bytes | No actual repair demonstrated. Require a valid repair or an honestly supported no-repair outcome. |
| Flange thickness <=5; hole diameter >=4 | C08/C09 plus exact boundary tests | Synthetic blocked-proposal example only; check actual mutations and saved result. |
| Report no possible fix clearly instead of forcing a change | O02–O04; distinguish exhaustion, proof and execution failure | Planned. A finite unsuccessful search supports “no repair found,” not global impossibility. |
| SDK preconditions, ordering, recovery | State reconstruction; C12–C15, O05/O06 | Happy-path smoke only; actual recovery check pending. |
| Avoid unnecessary fetches and large context blobs | Model-visible versus raw byte counts; repeated-read metrics | Planned; inspect actual model inputs, explain budgets, report measurements before tuning warnings. |
| Separate CLI/decisions/capture; add a part without rewriting; no hardcoded solve answers | Case-driven policy and adapter/state/check modules; use raw PartLab results | Source and additional-case check pending. Fixture numbers must not become agent answers. |
| Persist raw messages, tool calls and results for each run | Versioned bundle, execution ledger, raw SDK objects and CLI bytes | Contract reviewed but unagreed. Smoke CLI logs and synthetic fixtures are not raw live-agent traces. |
| Small repeatable non-happy-path check, with explanation | Blocked flange mutation or recovered CLI failure with linked raw evidence | Pending agent check. Harbor no-op tests missing output, not agent recovery or constraint handling. |
| Eval consumes Part 1 raw traces and emits structured reports | Offline adapter -> reconstruction -> predicates -> JSON/JSONL report | Not implemented. Run on both actual bundles without model/CLI calls. |
| General schema; support a fourth case or another harness | Versioned adapter; data-driven cases; portability checks | Design only. Demonstrate an added case without changing checks; avoid requiring a second harness in the time-box. |
| Principled tunable heuristics; readable actionable report; defend scoring | Named config, exact hard limits, evidence-linked findings, separate outcome dimensions | Planned. Show generated reports and explain unknown versus fail. |
| Deliberately flawed trace; demonstrate its specific detection | C12 synthetic stale solve; valid IDs/hashes; assert `STALE_SOLVE` and evidence links | Fixture exists; packaging checker does **not** detect its semantics. Working assertion still required. |
| Show checks for outcomes, saved parts and eval | Independently parse raw results and artifact content; positive/negative controls | Smoke baseline checked. Actual complete agent -> trace -> report -> saved-part chain pending. |
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
3. **Offline evaluator:** generate evidence-linked reports for those runs; prove
   stale-solve detection with a schema-valid flawed trace and a valid control.
   Preserve separate repair/reporting outcomes and recovered-error diagnostics.
4. **Repeatability and handoff:** re-evaluate saved inputs with identical semantic
   findings, check independent run ordering and an added case, inspect the final
   artifact inventory, complete RUN.md and the narrated recording.

Docker/Harbor readiness is tracked separately in [HARBOR_SETUP.md](HARBOR_SETUP.md)
and [verification.json](../harbor_setup/verification.json). It must never be used
as a substitute for one of these completion gates.
