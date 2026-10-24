# Design decisions

This is the central record of what we chose, why, and the resulting limits.
It describes the submitted implementation, including the five-model comparison
and second-harness demonstration. It also links the detailed evaluator records
preserved during consolidation. The [architecture](docs/ARCHITECTURE.md)
explains the workflow; the [report](REPORT.md) contains measured results;
[RUN.md](RUN.md) contains reproduction commands.

## Agent and tool boundary

### 1. One model-driven agent, with Python enforcing the workflow

The model chooses a candidate parameter and value. A shared executor validates
the proposal, runs PartLab, verifies effective state and captures evidence.
Prompt instructions explain the task, order, constraints, recovery, budgets
and final format, but do not carry sole responsibility for enforcing them.

This keeps candidate selection flexible while making mandatory rules testable.
A planner/worker hierarchy would add coordination without helping this small,
sequential task. The separation also lets another SDK reuse the same executor.
See [agent.py](cosmon_agent/agent.py) and [engine.py](cosmon_agent/engine.py).

### 2. Seven named tools, backed by one serialized executor

Expose `open_part`, `get_parameters`, `set_parameter`, `mesh`, `apply_load`,
`solve` and `save_part`. Each has a narrow argument schema and an explicit
purpose. The model does not receive a generic shell, arbitrary CLI command,
part-selection argument or output-path argument.

Compared with one tool accepting an action string, separate schemas make legal
arguments and ordering easier to explain and validate. Keeping the executor
shared avoids seven separate implementations of state and trace handling.
The prompt requests one tool call per response; SDK concurrency settings and
the executor lock serialize execution even if the model emits multiple calls.
The tradeoff is more model turns than an opaque all-in-one repair tool.
See [tool definitions and SDK configuration](cosmon_agent/agent.py).

### 3. Use the supplied CLI through explicit subprocess arguments

PartLab remains the engineering interface and its solve remains the source of
truth. Commands run with argument arrays, a controlled working directory and
timeouts. The executor checks both the process exit status and JSON envelope;
an inconsistent or malformed response cannot establish valid state.

This respects the actual task interface and preserves errors for diagnosis.
We do not reproduce simulator formulas or embed successful answers for named
parts. An adapter for another CAD interface would need different CLI handling;
it could still preserve the decision and evidence boundaries.
See [CLI handling](cosmon_agent/engine.py) and [original assignment](TASK.md).

## Search and state correctness

### 4. Stop at the first verified repair

The objective is the first legal single-parameter change with a fresh,
converged SF ≥ 2, followed immediately by a verified save. We do not optimize
for minimum material or smallest parameter change. If the unchanged original
already passes, report `already_safe` without manufacturing a repair artifact.

First-fix stopping was an explicit project choice: it matches the required
feasibility task and keeps search practical within the time limit. A larger
passing SF is not automatically a better result. In the benchmark, Luna's
12 mm bracket and the other models' 5 mm brackets satisfy the same objective.
See [instructions](cosmon_agent/agent.py) and [findings](reports/model-benchmark-20261024/FINDINGS.md).

### 5. Model-proposed candidates within configurable exploration bounds

The model chooses values based on observed solves; Python checks the ranges
and rejects duplicate candidates. We encourage informative changes and
exploration of another parameter family when one is unpromising. There is no
fixed answer table, exhaustive grid or assumed closed-form relationship.

The starter does not define a complete feasible domain, so the ranges in
[config.json](cosmon_agent/config.json) are explicit exploration choices.
They are not a completeness claim. The model can stop before consuming every
trial; a no-repair result reports only what this bounded search established.
Global infeasibility would require a separate, justified proof procedure.

### 6. Manufacturing constraints are independent of search ranges

Every executed flange candidate must respect thickness ≤ 5 mm and hole
diameter ≥ 4 mm, even if exploration bounds are widened. Those assignment
rules are checked before dispatch, separately from range checks. The evaluator
has its own trusted case rules.

This prevents changing a search setting from silently relaxing the task.
The implementation deliberately contains the named flange constraints, but
no named-part repair answers. New manufacturing rules currently require an
executor guard, matching prompt guidance and evaluator case rules.
See [executor setup and validation](cosmon_agent/engine.py) and [trusted cases](evaluation/eval_cases.json).

### 7. Isolate runs and restore the original for every candidate

Each run uses a temporary directory containing the supplied binary and assigned
original, records a reset, and leaves source part files untouched. Within a
run, every candidate reopens the original before one successful parameter
assignment. Readbacks check restoration and the effective mutation.

PartLab is stateful. Isolation makes concurrent benchmark runs independent;
restoration prevents separate one-parameter trials from accumulating into a
multi-parameter design. Extra reads and temporary files are accepted costs
for knowing which geometry was actually tested.
See [session and trial handling](cosmon_agent/engine.py).

### 8. Require a baseline and fresh evidence under the exact default load

Analyze the original before editing. For every candidate, mesh, explicitly
apply the original face/force/direction tuple, then solve. Load metadata alone
does not count as an applied load. Mutations invalidate mesh, load and solve;
remeshing or reloading invalidates dependent evidence.

This prevents a convincing SF from a different load or an earlier geometry
from being used to justify the current part. Save requires a current,
converged solve and exactly one changed parameter. Reusing a stale result is
not an optimization. See [state guards](cosmon_agent/engine.py) and the
[stale-solve check](scripts/check_e2e_evaluation.py).

### 9. Bound execution and recover only when state is understood

Default limits are six candidates, 48 model turns, 64 completed tool calls,
300 seconds per run, 40 seconds per model request, 15 seconds per CLI command
and 2,048 output tokens. These are practical, configurable limits, not
experimentally optimal values. Rejected proposals consume tool calls;
accepted candidates whose meshing fails still consume trials.

Invalid proposals return compact, actionable errors so the model can correct
them. A known mesh error permits recovery by restoring the original. Ambiguous
process failures stop execution with unknown state. Automatic client and SDK
model retries are disabled, making attempts and costs easier to account for.
This trades some transient-error resilience for explicit behavior. Exhausting
a runner budget without a valid final response is an execution failure.
See [policy](cosmon_agent/config.json), [runner](cosmon_agent/agent.py) and [executor](cosmon_agent/engine.py).

## Context, evidence and output

### 10. Compact model observations, complete local evidence

Return selected engineering fields and progress: effective changes, default
load, SF, convergence, state revision, remaining trials and evidence IDs.
Do not send the original part's private physics fields or verbose solver logs
to the model. Open and mutation already perform necessary readbacks;
`get_parameters` remains available for uncertainty. Solve already supplies
SF and stress, so there are no redundant follow-up tools for those fields.

The original live solve observations were 334–379 bytes, versus roughly
6.3 KiB of retained stdout. This reduces unnecessary context without discarding
debugging evidence. `routine_result_bytes` flags oversized responses; it is
not a hard truncation limit. Full messages still accumulate in the bounded
conversation, so this is not a constant-context-memory design.
See [capture audit](reports/evaluator-sync-20261023/capture-audit.json) and [result projection](cosmon_agent/engine.py).

### 11. Preserve raw payloads alongside a common trace contract

The bundle uses ordered JSONL events with run, model, tool, CLI and trial IDs,
plus file references carrying lengths and SHA-256 hashes. It distinguishes
proposals, guard decisions, executed commands, returned observations, solves
and artifacts. A completion inventory records the files present at finish.

This supports both readable diagnosis and deterministic offline evaluation.
Raw data preserves details normalization might lose, including malformed
arguments. Interrupted captures remain inspectable but cannot claim complete
execution coverage. Hashes establish consistency within the bundle, not
independent proof of authenticity; these are local files, not signed evidence
or a transactional, crash-durable database.
See [trace writer](cosmon_agent/trace.py) and [wire contract](evaluation/docs/EVAL_IMPLEMENTATION_CONTRACT.md).

### 12. Verify delivery and final reporting separately from solving

Save through PartLab, compare the saved JSON with the verified geometry/load/
solve, preserve its bytes, and publish identical bytes to the required output.
Publication uses an atomic no-overwrite operation; an existing identical file
is acceptable, while different contents require a new publication directory.

Require the model's final response to be one JSON object with the five defined
fields, then compare it with the executor's observed outcome. A passing solve
without a verified save is not a delivered repair. We preserve malformed final
text and report failure rather than silently rewriting it into a successful
claim. This stricter interface exposed two flange reporting failures in the
benchmark. See [save and outcome handling](cosmon_agent/engine.py),
[final validation](cosmon_agent/agent.py) and [benchmark findings](reports/model-benchmark-20261024/FINDINGS.md).

## Evaluation and experiments

### 13. Grade persisted evidence independently, with separate dimensions

The standard-library evaluator does not import agent policy, call a model or
rerun PartLab. It reconstructs execution from retained CLI evidence against
trusted original files, binary identity and case constraints. This makes
reevaluation repeatable, offline and independent of the producer's success flag.

Reports separate capture integrity, process compliance, final correctness,
delivery, reporting accuracy and repair achievement. Checks use `pass`, `fail`,
`unknown` and `not_applicable`, with evidence and remediation. Missing evidence
cannot become a pass. We avoid a weighted aggregate that could hide a hard
constraint violation behind good formatting or low cost. Decimal parsing and
exact task thresholds avoid a tolerance silently admitting SF below 2;
configurable diagnostic budgets never relax engineering rules.

An honest unsuccessful flange search can pass process/reporting and fail
repair achievement. A byte audit can pass even when malformed final JSON
prevents the evaluator from admitting a run. Evaluator 1.1.0 has source
provenance: the consolidated import is based on `cadf11e`, with unchanged
grading modules and explicit part-path and launcher relocations. Earlier
`b60473c` receipts retain their original case digest and test counts; new
verification records the combined layout.
See [evaluation guide](evaluation/README.md), [checks](evaluation/eval_checks.py)
and [provenance](evaluation/PROVENANCE.json).

### 14. Test semantic failures as well as the successful path

The repeatable guard check proposes flange thickness 5.5 mm after a real
baseline and confirms rejection before any mutation command or state change.
The deliberately flawed trace inserts a state-invalidating assignment before
save and refreshes hashes, so the evaluator must detect `STALE_SOLVE`, not
merely broken file integrity. An interrupted derivative checks incomplete
coverage; reversed batch order checks for cross-run state leakage.

Synthetic derivatives and mocked HTTP tests are labeled and kept separate
from live runs. They establish specific guarantees, not universal fault
tolerance. The [guard check](scripts/check_agent_guard.py),
[evaluation integration check](scripts/check_e2e_evaluation.py) and
[native runner regression](tests/test_anthropic_runner.py) document those guarantees.

### 15. Compare five models with the harness held constant

Use OpenAI Agents SDK through OpenRouter for two OpenAI models, two Anthropic
models and one DeepSeek model. Keep the prompt per part, tools, policy and
requested medium reasoning setting fixed. The default Sol/medium choice
follows the selected starting configuration; the pilot does not establish it
as the optimal model. OpenRouter allows model substitution with the existing
credentials and runner.

Run both required parts once per model, preserving failures, usage and raw
traces. Concurrent isolated runs fit the short experiment window. The cost
setting is an observed-spend target, not a hard cap: in-flight calls and delayed
usage reporting can exceed it. Identical requested reasoning levels also do
not guarantee identical provider behavior. With ten runs total, the result is
a functional comparison, not a statistical reliability ranking.
See [benchmark runner](scripts/benchmark_models.py), [all runs](reports/model-benchmark-20261024/INDEX.md)
and [interpretation](reports/model-benchmark-20261024/FINDINGS.md).

### 16. Demonstrate a second SDK without changing the task or grader

The additional harness is Anthropic Python SDK's ToolRunner, not Claude Agent
SDK, Claude Code or OpenCode. It is a small adapter around the same instructions,
seven tools, executor, trace writer and final validator, with optional pinned
dependencies. It exercises a real alternative SDK tool loop without introducing
an unrelated coding-agent environment.

OpenAI captures SDK-exposed objects; the native adapter captures Anthropic HTTP
bodies, excluding headers. Native tool-input objects are preserved and their
normalized argument strings are explicitly labeled canonical JSON. Runtime
checks and capture audits verify continuity between tool returns and SDK messages.
The two native live cases use the unchanged evaluator. They prove this adapter
works, not that every harness is compatible or that changing SDK improves
performance. See [portability design and evidence](docs/HARNESS_PORTABILITY.md).

## Extension and handoff

### 17. Extend through explicit contracts, with limits stated

A new part using the existing CLI needs original data, exploration ranges and
a trusted evaluator case. New manufacturing rules also need the changes
described above. Another harness needs a capture adapter that emits the common
contract and retains native evidence; a different CAD interface needs a new
execution adapter.

This is enough separation to add cases without rewriting the workflow, while
keeping the take-home implementation small. The agent's extra-part checks used
renamed synthetic fixtures. The evaluator also tests an unseen parameter/load/
constraint combination and a foreign capture layout through a test adapter.
Those are synthetic contract checks, not new live CAD runs. We therefore claim
the demonstrated extensions, not arbitrary CAD support.
See [architecture extension notes](docs/ARCHITECTURE.md#extending-the-system).

### 18. Keep the submission reproducible and its evidence reviewable

Commit source, dependency pins, raw traces, evaluations, outputs, diagrams and
their editable sources. Keep credentials in the ignored local `.env`; parse
only supported literal settings and never execute that file. Disable hosted
SDK tracing. The configured provider still receives the model conversation;
local capture does not mean model inference is offline.

Keep the original assignment unchanged as [TASK.md](TASK.md), put reviewer
navigation and Archify images in [README.md](README.md), and centralize commands
in [RUN.md](RUN.md). Retaining raw evidence makes the repository larger but
lets reviewers trace a claim to actual bytes. Live results, synthetic checks
and known limits stay distinguishable. The human recording link remains a
separate submission item; the repository does not claim that a recorded
one-hour session exists.

### 19. Keep optional viewers and execution checks outside the grading core

Scout displays the existing evaluator's findings; it does not independently
judge engineering correctness. Harbor checks a separate container execution
and verification environment using successful oracle and failing no-op controls.
Neither integration is required to evaluate the captured PartLab traces.

Harbor's separate verifier uses pristine references and receives only explicitly
exported artifacts. This checks isolation and delivery rather than allowing
the agent's working copy to define correctness. Two scripted oracle runs scored
1; a no-op scored 0. They are infrastructure controls, not live model repairs.
See the [Harbor decisions](evaluation/docs/HARBOR_SETUP.md#what-the-smoke-check-proves).

Docker repeats the evaluator checks in a pinned environment with networking
disabled and source mounted read-only. The combined 156-test suite and 19
expected outcomes passed there as well as on the host. The
[recorded command](reports/main-integration-20261024/docker-execution.json)
defines the tested boundary; this does not claim a general security audit.

Scout preserves separate verdicts and evidence references instead of reducing
them to one success flag. Its import follows the full batch manifest, including
rejected inputs, and verifies persisted results against source reports. This
makes browsing useful without quietly losing failed cases or changing grades.
See the [Scout decisions](evaluation/docs/SCOUT_AUDIT.md#decisions-and-requirements)
and [17-test, 19-transcript verification](reports/main-integration-20261024/README.md).

This permits richer inspection and environment checks without changing the
core verdicts or requiring their dependencies for a basic replay. Docker build
source is tracked; image layers, local databases and job directories are not.
Initial setup needs downloaded or cached dependencies even though the verified
runtime is offline. The consolidated verification preserves original receipts
and adds fresh checks for the final layout rather than relabeling old results.
See [integration decisions](docs/INTEGRATION_DECISIONS.md) and
[combined verification](reports/main-integration-20261024/README.md).

### 20. Use Sierra Tau² as a design reference, with local task semantics

The evaluator audit reviewed Sierra's Tau² grading and run-accounting code at
pinned revision `cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2`. It checked whether
every adverse finding reaches a verdict, valid alternative repair paths remain
valid, blocked proposals differ from executed mutations, and incomplete runs
retain both uncertainty and observed failures. Complete batch accounting keeps
rejected inputs visible rather than reporting only selected successes.

The reason is to test our evaluator design against concrete reference behavior
while retaining PartLab's requirements. We use separate evidence-based verdicts,
exact structured claims and recorded-state reconstruction. We do not copy a
scalar reward, require one reference trajectory, add an LLM judge or invent
repeated-trial statistics. Four focused regression tests were added by the
audit. Tau² itself was not run, and no Tau² score or leaderboard result is claimed.
See the [mapped decisions](evaluation/docs/TAU2_REFERENCE_AUDIT.md#decisions-and-mapped-evidence),
[regressions](evaluation/tests/test_tau2_review.py) and
[reference acceptance](evaluation/docs/REFERENCE_ACCEPTANCE.md).

## Detailed decision records

These retained records explain component-level choices and rejected alternatives.
Development-time references describe the original workstreams; the
[reviewer guide](docs/REVIEWER_GUIDE.md) and integration decisions describe the
current combined layout.

| Topic | Detailed rationale |
| --- | --- |
| Evaluator boundaries, authority and normalization | [Evaluator decisions](evaluation/docs/EVAL_DECISIONS.md) |
| State reconstruction, invalidation and evidence gaps | [State decisions](evaluation/docs/EVAL_STATE_DECISIONS.md) |
| Predicates, separate verdicts and scoring alternatives | [Check and scoring decisions](evaluation/docs/EVAL_CHECK_DECISIONS.md) |
| Synthetic fixtures, adversarial examples and raw capture | [Fixture decisions](evaluation/docs/EVAL_FIXTURE_DECISIONS.md) |
| Acceptance criteria and demonstrated portability | [Evaluation rubric](evaluation/docs/EVAL_RUBRIC.md) |
| Second live SDK and native message mapping | [Harness portability](docs/HARNESS_PORTABILITY.md) |
| Harbor verifier isolation and artifact transfer | [Harbor rationale and controls](evaluation/docs/HARBOR_SETUP.md#what-the-smoke-check-proves) |
| Docker environment and offline verification | [Recorded invocation](reports/main-integration-20261024/docker-execution.json), [combined verification](reports/main-integration-20261024/README.md) |
| Scout projection, complete imports and persisted evidence | [Scout decisions](evaluation/docs/SCOUT_AUDIT.md) |
| Sierra Tau² lessons and deliberate local differences | [Reference audit](evaluation/docs/TAU2_REFERENCE_AUDIT.md) |
| Layout, source history, cleanup and optional integrations | [Consolidation decisions](docs/INTEGRATION_DECISIONS.md) |
