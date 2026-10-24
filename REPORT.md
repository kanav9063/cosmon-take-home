# Submission report

The agent completed live runs for both required parts using OpenRouter
`openai/gpt-6.1-sol` with medium reasoning. PartLab supplied every reported
safety factor. Independent evaluator **1.1.0**, pinned to source commit
`b60473ca172a2fad33c377e96c212f2adb6aa84f`, replayed the saved evidence and
verified the execution and reporting. That offline reevaluation made no
additional model calls and preserved the original captures and earlier reports.

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

## Acceptance criteria

| Assignment criterion | Implemented behavior and evidence |
| --- | --- |
| Clean agent loop and sensible tools | Agents SDK loop, explicit system instructions, seven narrow named tools; model chooses candidates and executor enforces rules |
| Correct SDK use and recovery | Guards enforce ordering and exact default load; each trial restores the original; malformed proposals can be corrected; ambiguous execution failures stop |
| Avoid over-fetching | Actual SDK inputs contain the exact compact tool returns and no verbose solver log or private physics fields; no redundant SF/stress/log calls |
| Separate decisions, CLI and traces | Agent, execution engine and trace writer have separate responsibilities; evaluator reconstructs evidence independently; additional part names/configurations work without rewriting the workflow |
| Repeatable unhappy path | A real flange baseline followed by a 5.5 mm thickness proposal: rejected before CLI dispatch, with state bytes, parameters and revision unchanged |
| Explain design choices | [Architecture](docs/ARCHITECTURE.md) explains first-fix stopping, isolated trials, serialized guards, compact observations and independent evaluation |

Model-facing solve observations were **334–379 bytes**, versus roughly 6.3 KiB
of full stdout retained for each solve. The largest tool response was 674
bytes. These are observed byte counts, not claims about total token savings.

## Verification and evidence

- [Bracket raw trace](reports/e2e-20261023/bracket/) and [flange raw trace](reports/e2e-20261023/flange/).
- [Verified bracket output](outputs/bracket_v3.json).
- [Current independent evaluation summary](reports/evaluator-sync-20261023/evaluation-check/verification.json).
- [Evaluator source and regression receipt](reports/evaluator-sync-20261023/sync-receipt.json).
- [Model/tool continuity and context audit](reports/evaluator-sync-20261023/capture-audit.json).
- [Original trace inventory check](reports/evaluator-sync-20261023/trace-inventory.json).
- [Final verification receipt](reports/submission-check-20261023/verification.json), including tests and replay from a relocated checkout.
- [Agent test transcript](reports/submission-check-20261023/agent-tests.log) and [evaluator test transcript](reports/submission-check-20261023/evaluator-tests.log).
- [Real constraint-rejection check](reports/guard-check-20261023-201100/verification.json).

The bracket passes capture, process, correctness, delivery, reporting and repair
achievement. Flange capture, process and reporting pass; repair achievement
correctly fails. The evaluator does not turn honest failure into success.

**21 agent tests and 154 evaluator tests passed.** Tests include state
invalidation, concurrent proposals, malformed arguments, publication failure,
subprocess cancellation and tool budgets. A deliberately edited trace preserves
valid hashes but invalidates the cited solve; the evaluator flags `STALE_SOLVE`.
An interrupted derivative remains incomplete and unverified. All five evaluation
reports were identical when the batch order was reversed.

Version 1.1 additionally checks that artifact snapshots follow their producing
saves and solves, detects later writes that make publication evidence stale,
and distinguishes a fully captured publication failure from missing evidence.
Reports include the evaluator's source hashes and effective case policy.

See [RUN.md](RUN.md) for reproducible agent, negative-check and evaluation commands.

## Limits and reviewer checks

- Search is bounded and stochastic; it does not prove that all legal flange
  designs are infeasible.
- Raw model capture preserves SDK-exposed objects, not original HTTP bytes or
  hidden reasoning. Hosted tracing is disabled.
- Generic part-name handling and the final tool-call budget stop were verified
  offline after the two live captures. Additional synthetic parts use the same
  CLI schema; new manufacturing constraints need explicit policy.
- The recording link still needs to be supplied. This report does not claim a
  recorded one-hour session.

The original assignment is retained unchanged in [TASK.md](TASK.md).
