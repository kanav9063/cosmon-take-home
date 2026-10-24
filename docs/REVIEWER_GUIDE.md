# Reviewer walkthrough

Start with the results, follow one repair through its evidence, then inspect
the code that enforces the workflow. Supporting files are retained for
reproduction; you do not need to read every raw payload to review the design.

## Suggested reading order

1. [TASK.md](../TASK.md) is the original assignment, unchanged. It defines the
   required load, SF target, single-parameter repair and flange constraints.
2. [REPORT.md](../REPORT.md) records what worked, what failed, the verification
   performed and the remaining limitations.
3. [DECISIONS.md](../DECISIONS.md) explains 19 implementation choices and their
   tradeoffs. [ARCHITECTURE.md](ARCHITECTURE.md) shows how the pieces fit together.
4. Follow the bracket trace below to inspect a delivered repair; then inspect
   the flange and deliberately flawed traces to see how failure is handled.
5. Read the three core agent files and the independent evaluator files listed
   below. [RUN.md](../RUN.md) provides the exact reproduction commands.
6. For the experiments, read the [five-model findings](../reports/model-benchmark-20261024/FINDINGS.md)
   and [second-harness demonstration](HARNESS_PORTABILITY.md). These are
   separate experiments with different conclusions.

## Follow one result to the underlying evidence

Use the original bracket run as a small, complete example:

1. Open its [outcome](../reports/e2e-20261023/bracket/outcome.json). It identifies
   the baseline, selected solve, changed parameter and saved artifact. Treat
   this as the producer's account, not independent proof.
2. Inspect the [independent bracket report](../reports/main-integration-20261024/agent-evaluation/reports/report-bracket.json).
   Its summary separates capture, process, correctness, delivery, reporting
   and repair. Individual checks contain evidence references and reasons.
3. Follow those references into [events.jsonl](../reports/e2e-20261023/bracket/events.jsonl).
   Link a model proposal to its guard decision, CLI execution, returned result,
   solve, save and publication using their IDs. A proposal alone is not an
   executed action.
4. Open only the referenced payloads under [raw/](../reports/e2e-20261023/bracket/raw/):
   `model/` contains SDK requests, responses and final text; `tools/` contains
   exact model-facing observations; `cli/` contains full stdout and stderr.
   This also makes the difference between compact observations and full solver
   logs visible.
5. Compare the [published bracket](../outputs/bracket_v3.json) with the run's
   [saved artifact](../reports/e2e-20261023/bracket/outputs/bracket_v3.json).
   [completion.json](../reports/e2e-20261023/bracket/completion.json) inventories
   the captured files and their hashes. The [manifest](../reports/e2e-20261023/bracket/manifest.json)
   records the original, policy, binary identity and capture profile.

Next, inspect the [flange report](../reports/main-integration-20261024/agent-evaluation/reports/report-flange.json):
valid process and honest reporting do not imply a successful repair. The
[stale-solve report](../reports/main-integration-20261024/agent-evaluation/reports/report-synthetic-stale.json)
shows a specific semantic failure; the
[interrupted report](../reports/main-integration-20261024/agent-evaluation/reports/report-synthetic-interrupted.json)
shows what remains unknown when evidence is incomplete. Both derivatives are
explicitly synthetic.

## Important implementation files

| File | What to look for |
| --- | --- |
| [cosmon_agent/agent.py](../cosmon_agent/agent.py) | System instructions, seven tool schemas, strict arguments, Agents SDK loop, model capture, budgets and final-claim validation. Start here to understand what the model can do. |
| [cosmon_agent/engine.py](../cosmon_agent/engine.py) | Isolated PartLab session, subprocess I/O, serialized guards, trial restoration, state invalidation, compact results and verified publication. This is the execution boundary. |
| [cosmon_agent/trace.py](../cosmon_agent/trace.py) | Exclusive bundle creation, raw payload files, linked events and completion inventory. This is how execution becomes inspectable evidence. |
| [cosmon_agent/config.json](../cosmon_agent/config.json) | Search ranges and run/model/tool/time budgets. Exploration ranges are not the complete feasible domain. |
| [cosmon_agent/__main__.py](../cosmon_agent/__main__.py) | CLI arguments, configuration loading, output locations and exit handling. |
| [cosmon_agent/anthropic_runner.py](../cosmon_agent/anthropic_runner.py) | Optional native ToolRunner adapter and HTTP capture. Read after the core runner to see which pieces a different SDK changes. |
| [evaluation/trace_adapter.py](../evaluation/trace_adapter.py) | Capture resource limits, bounded loading, reference validation and normalization of evidence. |
| [evaluation/eval_state.py](../evaluation/eval_state.py) | Independent reconstruction of CLI state and evidence freshness. |
| [evaluation/eval_checks.py](../evaluation/eval_checks.py) | Engineering predicates, separate result dimensions, finding codes and remediation. |
| [evaluation/evaluate.py](../evaluation/evaluate.py) | Case/policy loading, batch isolation and structured report generation. Exit 0 means reports were written, not that every repair passed. |
| [evaluation/eval_types.py](../evaluation/eval_types.py) | Evaluator records, strict numeric parsing and version/profile constants. |
| [evaluation/eval_cases.json](../evaluation/eval_cases.json) | Trusted originals, expected outputs, SF targets and manufacturing constraints, independent of producer claims. |

The [trace contract](../evaluation/docs/EVAL_IMPLEMENTATION_CONTRACT.md) defines
the persisted interface. [Evaluator provenance](../evaluation/PROVENANCE.json)
records the source files and relocation changes. The supplied [partlab](../partlab)
binary and shared [parts/](../parts/) are the task inputs; the evaluator's case
configuration pins those originals independently by hash.

## Checks worth reading or running

| File | What it proves or measures |
| --- | --- |
| [tests/test_agent_engine.py](../tests/test_agent_engine.py) | Guards, single-parameter trials, concurrency, state freshness, publication failure and cancelled CLI evidence. |
| [tests/test_agent_sdk.py](../tests/test_agent_sdk.py) | SDK capture, invalid arguments, recovery, configuration extensibility, budgets and final claims. |
| [tests/test_anthropic_runner.py](../tests/test_anthropic_runner.py) | Actual native ToolRunner with mocked HTTP and real PartLab; forbidden flange mutation blocked before dispatch. Optional SDK dependency required. |
| [evaluation/tests/](../evaluation/tests/) | Independent evaluator regression suite, including incomplete evidence and causal artifact checks. |
| [evaluation/tests/test_rubric.py](../evaluation/tests/test_rubric.py) | Synthetic unseen-case and foreign-capture-layout tests, beyond the agent's renamed-part checks. |
| [evaluation/scripts/verify.py](../evaluation/scripts/verify.py) | Runs the evaluator suite and asserts the expected outcomes of 19 example bundles. |
| [scripts/check_agent_guard.py](../scripts/check_agent_guard.py) | Small repeatable constraint-rejection demonstration without a model or API key. |
| [scripts/check_e2e_evaluation.py](../scripts/check_e2e_evaluation.py) | Labeled stale-solve/interrupted derivatives and report stability across batch ordering. |
| [scripts/verify_live_capture.py](../scripts/verify_live_capture.py) and [verify_anthropic_capture.py](../scripts/verify_anthropic_capture.py) | Byte inventories, model/tool continuity, compact context and artifact checks for the two capture formats. |
| [scripts/benchmark_models.py](../scripts/benchmark_models.py) | Paid model comparison using the same harness, policy and isolated runs. |
| [scripts/summarize_model_benchmark.py](../scripts/summarize_model_benchmark.py) | Offline evaluation and comparison of captured runs, including failures. |

The [run guide](../RUN.md) separates paid agent calls from offline checks.
[requirements.lock](../requirements.lock) pins the baseline environment;
[requirements-anthropic.txt](../requirements-anthropic.txt) adds the optional
SDK. [pyproject.toml](../pyproject.toml) records project metadata and direct
dependencies. [.env.example](../.env.example) lists supported local settings
without credentials.

## Supporting files retained for reproduction

| Location | Why it stays, and when to read it |
| --- | --- |
| [reports/main-integration-20261024/README.md](../reports/main-integration-20261024/README.md) | Current combined-layout verification: 22 agent tests, 156 evaluator tests, 19 expected cases, replay parity and optional integration checks. Start here for the latest receipt. |
| [reports/e2e-20261023/](../reports/e2e-20261023/) | Original live captures; start with an outcome and follow references instead of reading every payload. |
| [reports/evaluator-sync-20261023/](../reports/evaluator-sync-20261023/) | Earlier evaluator 1.1.0 reevaluation, negative derivatives, capture audits and source-sync receipt, retained with its original paths and test counts. |
| [reports/guard-check-20261023-201100/](../reports/guard-check-20261023-201100/) | Original real constraint-check evidence. |
| [reports/model-benchmark-20261024/INDEX.md](../reports/model-benchmark-20261024/INDEX.md) | Navigable index to all ten model runs, reports and artifacts. |
| [reports/anthropic-harness-20261024/](../reports/anthropic-harness-20261024/) | Two native SDK captures, evaluations, audits and test logs; separate from the five-model pilot. |
| [reports/submission-check-20261023/](../reports/submission-check-20261023/) | Submission checks and relocation replay evidence. Test counts reflect the checks performed at that stage. |
| [docs/assets/](assets/) | Rendered Archify diagrams and editable JSON sources. The images are review aids; code and evidence establish behavior. |
| [evaluation/docs/](../evaluation/docs/) | Detailed component decisions, acceptance criteria, audits and clearly labeled historical plans. Start with the [rubric](../evaluation/docs/EVAL_RUBRIC.md); use the [decision index](../DECISIONS.md#detailed-decision-records) for deeper rationale. |
| [evaluation/fixtures/](../evaluation/fixtures/) and [evaluation/reports/](../evaluation/reports/) | Preserved example captures, deliberate defects and source-pinned historical evaluation results. |
| [evaluation/scout_setup/](../evaluation/scout_setup/) | Optional findings viewer: [bridge.py](../evaluation/scout_setup/bridge.py) and [scanners.py](../evaluation/scout_setup/scanners.py) project existing verdicts into Scout. No additional engineering judge. |
| [evaluation/harbor_setup/](../evaluation/harbor_setup/) | Optional Docker task: [check.py](../evaluation/harbor_setup/check.py) runs controls; [task/](../evaluation/harbor_setup/task/) contains environment, verifier and oracle source. See the [setup guide](../evaluation/docs/HARBOR_SETUP.md). |
| [scripts/check_setup.py](../scripts/check_setup.py), [inspect_partlab_io.py](../scripts/inspect_partlab_io.py), [check_openrouter.py](../scripts/check_openrouter.py) and [test_check_openrouter.py](../scripts/test_check_openrouter.py) | Optional setup, CLI probing and provider smoke-test utilities. Not required to evaluate existing traces; the provider smoke test makes paid calls. |

Historical reports remain intact so their provenance can be inspected; they
do not replace the current evaluator reports linked above. Local `.env`, virtual
environments, session state, caches and new `runs/` directories are ignored by
Git. Raw traces and saved outputs are retained because they are submission
evidence, even though they account for most of the file count.

The [integration decisions](INTEGRATION_DECISIONS.md) explain the cleanup:
shared root parts, one current evaluator, original evidence preserved, and the
superseded preparation prototype retained only in Git history.
