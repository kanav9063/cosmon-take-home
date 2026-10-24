# Architecture

![PartLab agent architecture](assets/architecture.png)

[Editable diagram source](assets/architecture.json), with code references pinned
to the implemented source revision.

The system has one model-driven agent and one local execution boundary. The
model chooses a parameter and value. The executor decides whether the action
is permitted and uses the PartLab solver as the source of truth. Evaluation is
a separate offline process.

## Code map

| Module | Responsibility |
| --- | --- |
| `cosmon_agent/agent.py` | System instructions, seven tool schemas, Agents SDK loop, model capture and final-claim validation |
| `cosmon_agent/engine.py` | Serialized guards, CLI subprocesses, state transitions, baseline restoration and verified saves |
| `cosmon_agent/trace.py` | Exclusive bundle creation, raw payloads, ordered events and final inventory |
| `cosmon_agent/config.json` | Exploration ranges, budgets and timeouts |
| `cosmon_agent/__main__.py` | Part selection, local configuration and CLI entry point |
| `evaluation/trace_adapter.py` | Bounded evidence loading, reference integrity and trace normalization |
| `evaluation/eval_state.py` | Independent reconstruction of executed PartLab state |
| `evaluation/eval_checks.py` | Engineering, process, delivery and reporting checks |
| `evaluation/evaluate.py` | Offline batch evaluation and structured reports |

## Workflow and tool contracts

First, `open_part()` returns the assigned original's identity, effective
parameters and default load. `mesh()`, `apply_load(face_id, force_N, direction)`
and `solve()` establish its baseline. Default-load metadata is not an applied
load; the tool call must apply the complete original tuple explicitly.

If the baseline is unsafe, every candidate follows:

```text
open original → set one parameter → mesh → apply default load → solve
                                                        SF ≥ 2 → save and verify
                                                        SF < 2 → next trial
```

`get_parameters()` is available when inspection is necessary. Open and mutation
already perform the specific readbacks needed to verify effective values, so
normal use does not need extra parameter queries.

All seven tools share a lock around validation, execution, readback and trace
capture. Parameter changes invalidate mesh, load and solve evidence; remeshing
and reloading also invalidate downstream results. `save_part()` accepts only a
fresh converged result with SF ≥ 2, exactly one changed parameter and legal
constraints. It validates the saved JSON against the solve, then publishes
identical bytes to the chosen output directory without overwriting a different
existing artifact.

Expected invalid proposals return actionable errors without dispatching the
change. A failed mesh requires restoration before another candidate. Ambiguous
process failures stop with unknown state. There is no claim of universal error
recovery, and no hidden provider or SDK retry.

## Search policy

| Parameter, mm | bracket_v3 | flange_v1 |
| --- | --- | --- |
| thickness_mm | 3–12 | 2–5 |
| hole_diameter_mm | 2–8 | 4–10 |
| fillet_radius_mm | 2–10 | 1.5–10 |

These editable exploration bounds are not a complete feasible domain. The
assignment's flange limits—thickness ≤ 5 and hole diameter ≥ 4—are enforced
independently of them. Defaults are six candidates, 48 model turns, 64 completed
tool calls including rejected proposals, 300 seconds per run, 40 seconds per
model request, 15 seconds per CLI invocation and 2,048 maximum response tokens.
A budget stop without a final model message is an execution failure.

First-valid-fix stopping keeps the goal achievable within the exercise's time
limit. The prompt encourages informative candidates rather than a long series
of tiny changes. No successful parameter value, safety-factor answer or
simulator formula is embedded in the runtime.

## Evidence and context

Each bundle preserves original part bytes, the unchanged task, policy, SDK
request/response snapshots, raw function arguments, exact tool return strings,
full CLI stdout/stderr, immutable artifact snapshots, an outcome and a completion
inventory. Full logs remain local; tools return compact engineering observations.
A trace reference is useful for diagnosis without placing its whole payload in
model context.

The evaluator does not import agent policy or invoke PartLab or a model. It
checks independent trusted originals and reconstructs actions from raw command
results. Its report separates capture integrity, process compliance, final
correctness, delivery, reporting accuracy and repair achievement. A trustworthy
report of search exhaustion is different from a successful repair.

## Extending the system

A part using the existing CLI contract needs source data, exploration ranges
and a trusted evaluator case. New manufacturing rules need a guard in
`Engine.setup`, corresponding prompt guidance and evaluator case rules; the workflow stays the same. Two
additional renamed synthetic parts were checked offline. This establishes
name/configuration extensibility, not compatibility with an arbitrary CAD API.

The [report](../REPORT.md) links the measured outcomes and checks. The
[trace contract](../evaluation/docs/EVAL_IMPLEMENTATION_CONTRACT.md) specifies
the persisted format; its existing version is retained for compatibility with
the captured runs.
