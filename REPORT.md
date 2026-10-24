# Submission report

The agent completed live runs for both required parts using OpenRouter
`openai/gpt-6.1-sol` with medium reasoning. PartLab supplied every reported
safety factor. Independent evaluator **1.1.0** replayed the saved evidence and
verified the execution and reporting. The consolidated evaluator comes from
`cadf11e`, retaining the `b60473c` grading core with documented path relocations
and additional tests. [Provenance](evaluation/PROVENANCE.json) records those
changes. Offline reevaluation made no additional model calls and preserved the
original captures and earlier reports.

## Original two-part run

| Part | Baseline SF | Best verified SF | Result |
| --- | --- | --- | --- |
| `bracket_v3` | 1.428 | **3.072** | Thickness 3 → 5 mm; exactly one parameter changed; fresh solve; verified save |
| `flange_v1` | 0.212 | **0.839** | Six legal independent trials; no repair found within configured bounds |

The bracket used 11 model requests, 10 tools and two solves. The flange used
35 model requests, 34 tools and seven solves. Its trials changed thickness to
5 and 3.5 mm, fillet radius to 10 and 5.75 mm, and hole diameter to 4 and 7 mm,
each starting from the original. No candidate reached SF ≥ 2; no unsafe part
was saved. This is not an infeasibility proof.

The provider reported **$0.0469329** for these two runs, excluding earlier setup
checks. Both runs used zero automatic retries.

## Five-model comparison

Ten additional live runs used the same harness, prompt per part, tool schema,
policy, and requested medium reasoning setting. The concurrent batch took about
**66.6 seconds** and cost **$0.371235631** in provider-reported usage.

| Model | Bracket verified SF | Flange outcome |
| --- | --- | --- |
| `openai/gpt-6.1-sol` | 3.072 | Valid bounded search; no repair |
| `openai/gpt-6-luna` | 11.421 | Valid bounded search; no repair |
| `anthropic/claude-sonnet-5.5` | 3.072 | Valid bounded search; no repair |
| `anthropic/claude-haiku-5.5` | 3.072 | Reporting failure |
| `deepseek/deepseek-v4.1-flash-1017` | 3.072 | Reporting failure |

All five bracket repairs passed independent evaluation. The three valid flange
outcomes reported best SF 0.839 without claiming a repair. Haiku and DeepSeek
returned prose or code fences instead of the required final JSON; the evaluator
reported `TRACE_PARSE_ERROR` and left capture, process, reporting and repair
dimensions unknown for those flange runs. They are not counted as compliant
bounded outcomes.

The separate byte and SDK-continuity audit passed for all ten captures; that
does not establish task success or repair a malformed final response. See the
[full comparison](reports/model-benchmark-20261024/comparison.md),
[machine-readable results](reports/model-benchmark-20261024/comparison.json),
[capture audit](reports/model-benchmark-20261024/capture-audit.json), and
[raw runs](reports/model-benchmark-20261024/runs/). One run per model and part
does not establish a reliability ranking; provider routing and caching also
affect observed cost and latency.

## Second harness and trace portability

Two additional live runs use Anthropic Python SDK ToolRunner 2.3.0 with
`anthropic/claude-sonnet-5.5`. The runner preserves native HTTP message bodies
and maps tool-use events into the existing trace contract. The shared PartLab
executor, prompt, tools and evaluator are unchanged. Bracket was repaired at
SF 3.072; flange returned a valid bounded no-repair report with best SF 0.839.
Both passed the native capture audit and expected independent evaluation
checks. Provider-reported cost was $0.298670 for these two runs.

The [portability design and evidence](docs/HARNESS_PORTABILITY.md) explain what
the adapter changes and how it preserves native arguments and exact tool
returns. This demonstrates a real harness substitution. It does not establish
arbitrary-harness compatibility or a controlled performance advantage.

Model choice and harness choice are separate. The five-model comparison kept
OpenAI Agents SDK fixed, including for Anthropic model IDs. The two additional
runs actually use Anthropic Python SDK ToolRunner. Both harnesses execute the
same seven tools, guarded executor and task, and emit evidence accepted by the
same evaluator. The native adapter preserves HTTP bodies; the original runner
preserves SDK-exposed objects. This is the live demonstration of the assignment's
requirement to support a different harness without rewriting the grader.

## Acceptance criteria

The tables map the [original assignment](TASK.md) to implemented behavior and
inspectable evidence. A demonstrated check is not a claim that every search
succeeds or every possible failure mode is handled.

### Required task and captures

| Requirement | How it is addressed | Evidence |
| --- | --- | --- |
| Run both required parts and persist messages, calls and results | Original live runs cover `bracket_v3` and `flange_v1`; bundles retain model messages, tool proposals/returns and raw CLI output. | [Bracket trace](reports/e2e-20261023/bracket/), [flange trace](reports/e2e-20261023/flange/), [capture audit](reports/main-integration-20261024/capture-audit.json) |
| Reset between runs; apply the default load and run the FEA workflow | Each run uses an isolated session and records reset. The executor requires open → mesh → explicit original face/force/direction → solve. | [Executor](cosmon_agent/engine.py), [bracket events](reports/e2e-20261023/bracket/events.jsonl) |
| Verify one changed parameter and save a passing repair | Bracket thickness changed 3 → 5 mm, then a fresh converged solve reached SF 3.072. Saved and published bytes were verified. | [Saved part](outputs/bracket_v3.json), [independent bracket report](reports/main-integration-20261024/agent-evaluation/reports/report-bracket.json) |
| Respect flange manufacturing constraints and report unsuccessful search honestly | Every executed trial is guarded by thickness ≤ 5 mm and hole diameter ≥ 4 mm. Best observed SF was 0.839; no unsafe artifact was saved. The bounded search does not prove that no legal fix exists. | [Independent flange report](reports/main-integration-20261024/agent-evaluation/reports/report-flange.json), [search policy and rationale](DECISIONS.md#5-model-proposed-candidates-within-configurable-exploration-bounds) |

### Part 1: agent requirements

| Requirement | How it is addressed | Evidence |
| --- | --- | --- |
| Clean agent loop, sensible prompt and tool surface | One model-driven loop, explicit task/order/recovery/final-format instructions and seven narrow tools. The model proposes; Python enforces. | [Agent implementation](cosmon_agent/agent.py), [tool-boundary decisions](DECISIONS.md#agent-and-tool-boundary) |
| Correct SDK use: preconditions, ordering and error recovery | Serialized guards enforce state and exact default load. Each trial restores the original. Correctable proposals return errors; known mesh failures permit restoration; ambiguous execution failures stop. | [Executor](cosmon_agent/engine.py), [engine regressions](tests/test_agent_engine.py), [SDK regressions](tests/test_agent_sdk.py) |
| Avoid over-fetching and large context blobs | Selected solve fields and necessary parameter readbacks supply observations. Full logs remain in local evidence; no redundant SF/stress/log fetches follow a solve. | [Context and continuity audit](reports/main-integration-20261024/capture-audit.json), [context decision](DECISIONS.md#10-compact-model-observations-complete-local-evidence) |
| Separate CLI interaction, decisions and capture; use the solver, not hard-coded answers | `agent.py`, `engine.py` and `trace.py` have distinct responsibilities. SF comes from PartLab. Configured new names reuse the workflow; new manufacturing rules still require explicit guards and case policy. | [Architecture code map](docs/ARCHITECTURE.md#code-map), [extension limits](DECISIONS.md#17-extend-through-explicit-contracts-with-limits-stated), [configuration and new-part tests](tests/test_agent_sdk.py) |
| One small, repeatable non-happy-path check, with its meaning explained | After a real flange baseline, a 5.5 mm thickness proposal is rejected before CLI dispatch. Ten assertions verify no forbidden mutation or state change; this proves guard behavior for that case. | [Runnable guard check](scripts/check_agent_guard.py), [verification](reports/main-integration-20261024/guard/verification.json) |
| Explain the design choices | Central decision record explains choices, reasons, alternatives and limits, with deeper component records linked. | [DECISIONS.md](DECISIONS.md), [architecture](docs/ARCHITECTURE.md) |

Model-facing solve observations were **334–379 bytes**, versus roughly 6.3 KiB
of full stdout retained for each solve. The largest tool response was 674
bytes. These are observed byte counts, not claims about total token savings.

### Part 2: evaluation requirements

| Requirement | How it is addressed | Evidence |
| --- | --- | --- |
| Generalize to another case or harness | Two real SDK loops emit the same contract and use unchanged grading logic: OpenAI Agents SDK and Anthropic Python SDK ToolRunner. Separate synthetic tests cover an unseen parameter/load/constraint case and a differently structured capture adapter. | [Live two-harness proof](docs/HARNESS_PORTABILITY.md), [unchanged-source receipt](reports/anthropic-harness-20261024/verification.json), [unseen-case and adapter tests](evaluation/tests/test_rubric.py) |
| Principled, tunable heuristics | Trusted cases define targets and manufacturing bounds; configurable warning budgets cover efficiency, while read limits bound parsing. Reports retain effective policy and its digest. Efficiency settings cannot weaken correctness. | [Case policy](evaluation/eval_cases.json), [configuration runbook](evaluation/EVAL_RUN.md), [detailed rubric](evaluation/docs/EVAL_RUBRIC.md) |
| Structured reports an engineer can read and act on | Each report separates outcome dimensions and provides check IDs, reasons, raw evidence references and corrective actions. A readable index summarizes runs; Scout optionally displays the same findings. | [Current report index](reports/main-integration-20261024/evaluator/REPORTS.md), [specific findings](reports/main-integration-20261024/agent-evaluation/reports/report-synthetic-stale.json), [Scout guide](evaluation/scout_setup/README.md) |
| Defensible scoring | Capture, compliance, correctness, delivery, reporting and repair achievement remain separate. Missing evidence is unknown; observed violations fail; recovered errors remain diagnostic. An honest failed search does not earn a successful-repair verdict. | [Scoring decisions](evaluation/docs/EVAL_CHECK_DECISIONS.md), [flange verdict](reports/main-integration-20261024/agent-evaluation/reports/report-flange.json) |
| Deliberately flawed trace that triggers the specific expected finding | A labeled synthetic derivative invalidates a cited solve before save while preserving valid hashes. Evaluation flags `STALE_SOLVE`; a separate interrupted derivative remains incomplete. | [Reproducible check](scripts/check_e2e_evaluation.py), [stale-solve report](reports/main-integration-20261024/agent-evaluation/reports/report-synthetic-stale.json), [verification](reports/main-integration-20261024/agent-evaluation/verification.json) |

The evaluator processes batches with bounded input reads and independent case
state. The current check covers 19 expected example outcomes and verifies
order-independent reports; it is not a measured throughput benchmark over
hundreds of production traces. Two-harness compatibility is demonstrated for
the included adapters, not promised for an arbitrary SDK with no adapter.

### Engineering process and handoff

[RUN.md](RUN.md) supplies setup, pinned dependencies, isolated-reset agent runs,
checks and offline evaluation commands. Source, tests, at least two live traces,
evaluation output and the saved bracket are committed; the
[reviewer walkthrough](docs/REVIEWER_GUIDE.md) identifies the important files.
[Combined verification](reports/main-integration-20261024/README.md) records
22 agent tests, 156 evaluator tests and 19 expected cases, including an offline
Docker run. Additional model tests retain their failures and limitations.

The recording is still outstanding. The repository demonstrates implementation
and verification, but does not establish the required recorded narration or
compliance with a one-hour session. No global flange infeasibility proof is
claimed, and the remaining failure-handling limits are documented below.

## Verification and evidence

- [Bracket raw trace](reports/e2e-20261023/bracket/) and [flange raw trace](reports/e2e-20261023/flange/).
- [Verified bracket output](outputs/bracket_v3.json).
- [Current independent evaluation summary](reports/main-integration-20261024/agent-evaluation/verification.json).
- [Consolidated verification and Docker/Scout/Harbor checks](reports/main-integration-20261024/README.md).
- [Evaluator rubric and portability proofs](evaluation/docs/EVAL_RUBRIC.md).
- [Evaluator source and regression receipt](reports/evaluator-sync-20261023/sync-receipt.json).
- [Model/tool continuity and context audit](reports/evaluator-sync-20261023/capture-audit.json).
- [Original trace inventory check](reports/evaluator-sync-20261023/trace-inventory.json).
- [Earlier submission verification](reports/submission-check-20261023/verification.json), retained with its original test counts.
- [Agent test transcript](reports/submission-check-20261023/agent-tests.log) and [evaluator test transcript](reports/submission-check-20261023/evaluator-tests.log).
- [Real constraint-rejection check](reports/guard-check-20261023-201100/verification.json).

The bracket passes capture, process, correctness, delivery, reporting and repair
achievement. Flange capture, process and reporting pass; repair achievement
correctly fails. The evaluator does not turn honest failure into success.

**22 agent tests (including the optional native harness) and 156 evaluator tests
passed in the combined checkout.** The evaluator suite and 19 expected report
cases also passed in Docker with networking disabled. The [latest agent test log](reports/main-integration-20261024/agent-tests.log)
includes a real ToolRunner/CLI check with mocked HTTP: flange thickness 5.5 mm
is rejected without CLI dispatch and native capture remains intact. Tests include state
invalidation, concurrent proposals, malformed arguments, publication failure,
subprocess cancellation and tool budgets. A deliberately edited trace preserves
valid hashes but invalidates the cited solve; the evaluator flags `STALE_SOLVE`.
An interrupted derivative remains incomplete and unverified. All five evaluation
reports were identical when the batch order was reversed.

Version 1.1 additionally checks that artifact snapshots follow their producing
saves and solves, detects later writes that make publication evidence stale,
and distinguishes a fully captured publication failure from missing evidence.
Reports include the evaluator's source hashes and effective case policy.

The additional evaluator tests demonstrate an unseen case with different parameters,
load and limits, and an adapter for a different persisted harness layout. Scout
passes 17 contract tests and displays all 133 dimensions from 19 reports. It is a
projection of the independent evaluator, not another judge.

See [RUN.md](RUN.md) for reproducible agent, negative-check and evaluation commands,
and [the integration decisions](docs/INTEGRATION_DECISIONS.md) for source preservation
and the final repository layout.

## Limits and reviewer checks

- Search is bounded and stochastic; it does not prove that all legal flange
  designs are infeasible.
- The OpenAI harness preserves SDK-exposed objects; the Anthropic harness
  preserves native HTTP request/response bodies. Neither claims access to
  unexposed model internals. Hosted tracing is disabled.
- Generic part-name handling and the final tool-call budget stop were verified
  offline after the two live captures. Additional synthetic parts use the same
  CLI schema; new manufacturing constraints need explicit policy.
- The recording link still needs to be supplied. This report does not claim a
  recorded one-hour session.

The original assignment is retained unchanged in [TASK.md](TASK.md).
