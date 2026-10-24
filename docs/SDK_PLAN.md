# Agents SDK design and verification plan

For the short build sequence and proposed tool signatures, start with
[AGENT_BUILD_PLAN.md](AGENT_BUILD_PLAN.md).

This is **preparation**, not a completed agent, evaluation, or recorded exercise.
The unchanged root [README](../README.md) is the assignment. No repair search or
model run was performed to write this plan. See [SDK setup](SDK_SETUP.md) for
the installed environment and checks actually run, and the
[trace contract proposal](TRACE_CONTRACT_PROPOSAL.md) for the proposed producer
interface. That interface requires a checkpoint with the evaluation track;
this document does not claim agreement.

## Accepted scope and remaining decisions

Kanav has accepted these decisions:

1. Finish the core agent, persisted traces, offline eval, and demonstrations
   first. Docker, Harbor, ATIF, and Inspect Scout are conditional follow-on work.
2. Expose separate named SDK actions. Do not replace the workflow with one
   combined analysis tool.
3. Restore the original baseline between candidate trials. A saved repair must
   differ from the original in exactly one parameter, even if different trials
   investigate different parameters.
4. Distinguish demonstrated infeasibility, finite search with no repair found,
   and execution failure. Exhausting a finite search does not prove impossibility.
5. Stop at the first verified valid fix; further optimization is unnecessary.
6. Use configurable exploration ranges without claiming that the search is
   complete. The actual numerical ranges remain to be chosen.

Everything below is an implementation recommendation unless it follows directly
from those decisions or the README. Resolve these choices before live runs:

| Decision | Recommendation, not an accepted final choice |
| --- | --- |
| Model and provider | Choose an explicit available model after checking credentials without printing secrets; record provider/model in each run. No silent SDK default. |
| Candidate selection/order | Start with bounded model-proposed single-parameter trials. The first verified valid fix is the accepted stopping rule; the candidate proposal/order method remains open. |
| Numerical candidate ranges | Choose the actual finite, positive exploration bounds for each parameter and label their source. Configurability and the absence of a completeness claim are accepted; the numeric bounds are not yet set. |
| Budget | Set maximum candidate trials, model turns, output tokens, wall time, and any monetary cap before a paid run. Record the effective values. |
| Mesh settings | Use the starter's default mesh initially; if exposing element size, pin it across baseline and trials and record it. Changing mesh is not a repair parameter. |
| Numeric comparisons | Compare the CLI-reported SF directly with 2.0; never round it upward or substitute a handbook/recomputed estimate. Compare parameter values numerically so 3 and 3.0 are equal; do not introduce a broad tolerance that hides a second change. |
| Infeasibility proof | Disable that outcome for ordinary bounded exploration. Enable it only when an independently checkable proof and its actual constraint scope exist. No such proof method is currently implemented. |
| Error policy | Recover from expected invalid proposals; stop on uncertain mutation state, broken evidence capture, or unrecoverable execution errors. |

Use the shared `grill-me` decision workflow for genuinely unresolved choices;
do not reopen the accepted decisions. All live-run prerequisites, including
the producer/evaluator interface checkpoint, remain visible rather than being
silently chosen by a default.

## Small implementation boundary

Recommended package layout (not implemented by this plan):

```text
cosmon_agent/
  cli.py       one subprocess runner and envelope parsing
  policy.py    typed inputs, constraints, state and save guards
  trace.py     raw evidence persistence and normalized event writer
  agent.py     named tools, instructions, SDK orchestration
  __main__.py  configuration, isolated run lifecycle, final report
tests/         focused offline behavioral checks
```

The evaluator reads files from the trace bundle. It must not import `policy.py`,
the tool implementations, or agent decisions to decide whether they were
correct. A small documented data contract is sufficient; a shared framework,
service, database, CI system, and production packaging are out of scope.

### Verified SDK integration points

The setup environment resolves `openai-agents==0.24.0`, `openai==3.37.0`, and
`pydantic==2.14.1`; imports and `pip check` passed. Direct pins and the complete
transitive lock are owned by the setup files. The installed SDK exposes these
integration points; the future agent has not yet exercised them in a model run:

- Import `ToolContext` from `agents.tool_context`, not top-level `agents`.
  It carries `tool_call_id`, `tool_name`, and original `tool_arguments` for
  linking the wrapper's evidence to the model call.
- `RunHooks.on_llm_start(context, agent, system_prompt, input_items)` and
  `on_llm_end(context, agent, response)` provide model-boundary capture points;
  tool start/end hooks receive tool context. Snapshot serializable data at the
  boundary rather than retaining references to subsequently mutable objects.
- Preserve `RunResult.raw_responses` and `RunResult.new_items` as a final
  cross-check/SDK artifact. `to_input_list()` can filter history and is not a
  complete raw archive on its own. Hooks must preserve partial evidence even
  when the run never reaches a successful `RunResult`.
- `RunConfig(tracing_disabled=True)` and
  `ModelSettings(parallel_tool_calls=False, store=False, timeout=...,
  max_tokens=...)` are available. Recommended initial configuration is local
  journaling with hosted tracing disabled, explicit model limits, and a
  non-streaming run to keep implementation small. Set actual timeout/token
  values only after the budget decision; disabling parallel calls also needs
  the runner's serialization guard.

SDK tracing settings and response-storage settings do not replace the local
evidence writer or imply that a provider receives no request data. Do not claim
transport-level wire capture from these SDK hooks: persist the raw SDK-visible
messages, call arguments, results, and responses actually available to the app.

### One CLI runner

All PartLab invocations go through one runner using an argument list with
`shell=False`, a fixed executable, a run-specific working directory, captured
stdout/stderr, and a bounded timeout. Record command arguments, timing, return
code, and exact output bytes before exposing a compact result. Parse ordinary
commands as JSON envelopes and validate the required fields, including numeric
finiteness and expected result types. Preserve unknown extra fields in raw data.

Do not conflate transport/process success with `ok: true`. Classify nonzero
exit plus a valid error envelope as a CLI error; missing/malformed JSON,
contradictory return code/envelope, or an invalid result shape as protocol errors.
Top-level `--help` is a setup-only exception: it returns exit 0 with text on
stderr and empty stdout. Unknown commands return exit 2 with textual stderr.
Never discover command syntax by adding `--help` to arbitrary commands:
`save-part --help` writes a file named `--help`.

One run executes at most one PartLab command at a time. Disable parallel model
tool calls where the selected SDK/model supports that setting and also serialize
the runner; the runner is the actual protection against state races.

### Named tool surface

Keep each action independently visible in the model trace. Suggested names and
responsibilities follow; signatures and schemas must be finalized with the
trace contract. Context supplies the allowed part, sandbox path, original
snapshot, policy, budget, and evidence writer rather than accepting them as
model-controlled arguments.

| Tool | CLI operation and code responsibility |
| --- | --- |
| `open_part` | `open-part <assigned_part>`; require the assigned identity. Initial open establishes the original baseline. A later reopen begins a fresh candidate trial from that same original. |
| `get_parameters` | `get-parameters`; return effective values and compare them with expected state. Capture original values on the first open before any mutation. |
| `get_active_part` | `get-active-part`; expose compact phase/load/override evidence when necessary, especially after errors. There is no `get-state` command. |
| `set_parameter` | `set-parameter <name> <value>`; record proposal, validate type, allowed parameter, finite positive value, manufacturing constraints, trial rules, and budget before any CLI call. |
| `mesh` | `mesh` (or a pinned `--element-size <value>`); invalidate previous load/solve evidence when successful. |
| `apply_load` | `apply-load --direction <direction> <face_id> <force_N>`; require the original part's complete default-load tuple. Flags must precede positional arguments. |
| `solve` | `solve`; require the current mesh and default load. Return SF/stress/convergence with evidence IDs; preserve the full solve output separately. |
| `get_safety_factor` | `get-safety-factor`; permit only when the tracked solve is still fresh. This is a read of the preceding solve, not new verification. |
| `save_part` | `save-part <code-derived_path>`; enforce final repair conditions and verify the saved file. The model cannot supply arbitrary filesystem paths. |

Reset is a run-lifecycle operation recorded as code execution, not a model
proposal. No generic shell, arbitrary-file access, alternate-part substitution,
or handbook estimate tool is needed to complete this task. Add feature lookup
only if an actual failure requires it; default load is already returned by open.

### Model versus code

The model reads compact observations, follows the separate FEA actions, proposes
one candidate with a brief rationale, interprets failures, selects the next
trial within the configured range/budget, and explains the final outcome.
Instructions require the named part and its default load, source-of-truth solves,
baseline restoration, one-parameter repairs, and honest uncertainty.

Python controls the executable, files, allowed tools, original snapshot,
constraints, trial lifecycle, freshness, resource budgets, trace durability,
and save verification. It refuses invalid operations regardless of the model's
explanation. The final structured result is validated against evidence; fluent
model prose cannot turn a failed verification into success. A refusal by the
model itself is not a safety factor or an infeasibility proof.

## State, trials, and constraint policy

Snapshot the assigned starter's exact bytes/hash, identity, original parameters,
and default load before mutation. Confirm the CLI-opened identity, parameters,
and load agree. Do not replace the original snapshot with a previous candidate
or saved output. Keep starter files unchanged.

Recommended normal sequence:

```text
isolated reset -> open original -> read original parameters
  -> mesh -> apply original default load -> solve -> read/report baseline SF
  -> if SF < 2: reopen original -> confirm baseline -> set one parameter
       -> mesh -> apply original default load -> solve
       -> if failed/insufficient: record trial and reopen original for next trial
       -> if verified SF >= 2: save -> verify artifact -> report repaired
```

The model performs the named actions. Code checks this sequence; it does not
hide a mesh/load/solve sequence inside `set_parameter` or `open_part`. Recommended
trial rule: one successful parameter mutation per trial. A rejected proposal
does not execute or consume that mutation slot, but still counts against a
configured proposal/model budget. A changed value needs a new trial even when
trying the same parameter again. Treat these accounting rules as decisions to
confirm, not previously agreed requirements.

Before allowing a trial mutation, verify restoration with effective parameters
and phase `open`. The observed CLI `open-part <same_name>` clears overrides and
load. Track a monotonically increasing state generation and explicit latest
mutation, mesh, load, and solve event references. Successful open/reset/close,
parameter change, mesh, and load operations invalidate downstream evidence as
appropriate. A same-value `set-parameter` also invalidates the CLI's downstream
state. Reapplying the same load invalidates the solve. Remeshing clears the load.
Do not infer freshness from identical numeric inputs or a cached SF.

Attach every successful solve to the current trial, effective parameters,
state generation, mesh event, and applied-load event. A save requires that same
fresh solve after the latest invalidating action. Metadata references supplement
raw CLI evidence; the evaluator checks ordering and values independently.

Input validation should reject booleans masquerading as numbers, nonnumeric
strings, NaN/infinity, unknown parameter names, and nonpositive values for these
dimensional parameters. The observed CLI accepts a NaN parse then fails while
saving state, so CLI errors alone are not an adequate numeric validator.

Constraint policy is an explicit, versioned mapping from the README:

```text
flange_v1: thickness_mm <= 5.0; hole_diameter_mm >= 4.0
```

Check the full resulting parameter state, not just a verbal rationale or the
edited field. Enforce the original load tuple including direction. A proposal
rejected by Python gets a guard-decision event and a compact actionable message,
with **no CLI execution record** pretending it ran. Evidence distinguishes model
proposal, guard decision, attempted command, observed result, and resulting
state. Search-range rejections are distinct from manufacturing violations.

The final parameter difference set is computed against the original values:
exactly one name with a different numeric value, not one key in the CLI's
override map. For example, setting an original value creates an override but
does not create a repair. Require all other parameters and the part identity
to match the original, all manufacturing constraints to hold, the fresh solve
to converge with finite SF >= 2.0, and the original default load to match.

## Raw evidence, compact observations, and saved files

Use the [trace contract proposal](TRACE_CONTRACT_PROPOSAL.md) as the producer's
draft, with stable run/call identifiers and ordering. Persist raw model messages,
tool calls (including original argument strings), tool results, and full CLI
stdout/stderr. Store available provider response/usage identifiers as evidence;
do not claim to capture unavailable private model reasoning. Record code-driven
setup/recovery commands distinctly from model-generated calls.

The CLI `solve` response itself contains a large convergence log. Preserve it
in raw evidence but send only summary fields and an evidence reference to the
model. Avoid fetching `get-solve-log` on every solve. Never overwrite full raw
data with the compact projection. Finish each raw event before returning the
corresponding tool observation; capture interrupted and failed runs too. If
evidence persistence fails, stop instead of creating untraceable successes.

Record guard decisions whether allowed or rejected, originals/default load,
trial restores, successful state changes, current solve references, and final
outcome separately from immutable raw data. New normalization or eval output
must not rewrite raw events. Integrity hashes detect later modification; they
are not proof that events came from a real model. Mark synthetic fixtures and
edited flawed traces explicitly and preserve their source relationships.

PartLab permits save before solve, even with null solve result. The save guard
therefore runs before execution. Save into the isolated run's output directory,
then parse the file and compare identity, revision, effective parameters,
applied load, and solve summary with the current evidence. The observed file
shape is `{name, revision, parameters, applied_load, solve_result}`; the saved
solve result omits the verbose log. Persist its bytes/hash and reference the
successful save plus the supporting solve. Do not validate it by assuming
`open-part outputs/name.json` works: that path is not an accepted named part.

Publish the verified deliverable at `outputs/<part_name>.json` for the README,
keeping a per-run copy to avoid losing earlier evidence. Fail rather than
silently overwrite a conflicting run bundle. Failed/insufficient trials do not
leave a file labeled as the final repaired part.

## Isolation, configuration, errors, and outcomes

Each run gets its own working directory with copied starter parts and executable,
and thus its own `.partlab/`. Record executable/starter hashes. A run-specific
working directory is essential: changing the executable path alone does not
isolate the SDK state. Reset inside that directory before starting; never reset
another run or the source checkout. Clean up transient state while retaining
the raw bundle, run metadata, final report, and any saved artifact.

The observed `reset` returns the intended `state_path` but deletes the state
file. A subsequent `get-active-part` returns `closed` and creates a new closed
state file. Health checks must not require that `reset` itself leave a file.
This behavior was also confirmed with only `PATH`, `LANG`, and `TMPDIR` in the
subprocess environment; state remained under the process working directory.

Require explicit provider/model selection and validated budgets before a live
call. Check credential presence without reading it into logs, printing values,
or embedding environment dumps. Missing credentials/configuration should fail
early with a clear local error and no paid request. Do not mistake Codex/Claude
CLI availability for provider API access. Keep SDK telemetry configuration
explicit and retain local raw evidence independently of hosted SDK tracing.

Expected state/constraint/geometry errors produce compact typed observations
and may permit a corrected next action. An identical rejected proposal is not
retried automatically. A subprocess timeout or kill can leave uncertain state;
record it and stop the trial/run unless a documented reset/replay recovery
establishes a new state. Do not blindly retry mutation or save operations.
Permit only configured bounded retries for known transient provider/read-only
failures, with every attempt recorded and counted. A CLI error, process timeout,
protocol error, provider error, exhausted budget, and interrupted run need
distinct reasons, even when they share an unsuccessful top-level status.

For the initial version, recommend disabling both hidden transport retries
(`AsyncOpenAI(max_retries=0)`) and SDK retries
(`ModelSettings(retry=ModelRetrySettings(max_retries=0))`, importing the latter
from `agents.retry`). Installed code shows model start/end hooks surround the
SDK retry block; they do not record every physical request automatically.
Any later retries must be explicit at the recorded attempt boundary and consume
the same run budget. Do not restart a whole workflow after partial mutations.
Track model turns, CLI calls, candidate proposals and wall time separately:
`max_turns` alone does not cap every tool invocation. Resolve model pricing and
a conservative token allowance before promising a monetary spending cap.

Recommended final outcome vocabulary (exact serialized fields await agreement):

| Outcome | Required meaning |
| --- | --- |
| `already_safe` | Original part was solved under its original default load and SF >= 2.0; no repair claimed. |
| `repaired` | Exactly one original parameter differs; constraints hold; a fresh converged solve has SF >= 2.0; the verified saved artifact is referenced. |
| `no_repair_found` | A valid baseline and bounded search exist, but no verified feasible candidate was found before the configured search limit. Report what was tried and why search stopped; make no impossibility claim. |
| `demonstrated_infeasible` | An independently checkable argument covers the stated legal change domain and constraints. Ordinary finite sampling does not qualify. Disabled until a proof procedure is agreed. |
| `execution_failure` | Configuration, provider, CLI, timeout, persistence, or verification failure prevents a trustworthy result. Include last confirmed phase and evidence references. |

An interrupted/incomplete bundle remains evaluable as incomplete. Decide at the
interface checkpoint whether interruption is a distinct outcome or an execution
failure reason. Likewise distinguish orderly search-budget exhaustion from
failure to complete a baseline or current verification. Never report a repair
merely because the model's final message says it succeeded.

## Recorded exercise implementation sequence

Preparation includes installing dependencies, this plan, the proposed interface,
and starter health checks. It does **not** count as the required implemented
agent, raw model runs, eval, or deliberately flawed-trace demonstration. Start
the one-hour recording and narrate this distinction before exercise work.

| Recording time | Smallest useful deliverable |
| --- | --- |
| 0–5 min | State accepted assumptions and unresolved choices already resolved for the run; implement runner, isolated lifecycle, and append-only raw capture. |
| 5–12 min | Add separate typed tools, original snapshot, default-load/state/constraint guards, and SDK loop. Run the focused offline checks as each behavior exists. |
| 12–20 min | Connect current SDK message/tool capture to the agreed contract; run one baseline-to-save vertical slice, inspecting evidence rather than trusting prose. |
| 20–27 min | Run both required parts with the chosen model/budgets; keep every failed attempt and diagnose via raw events. Repeat the non-happy-path guard/state check. |
| 27–30 min | Verify saved output/evidence, document any unsuccessful outcomes honestly, and freeze the producer bundle for eval. |
| 30–50 min | Evaluation track normalizes persisted traces and checks ordering, defaults, constraints, single-parameter change, outcome truthfulness, and artifacts offline. |
| 50–57 min | Evaluate both real traces and an explicitly edited/synthetic flawed trace; demonstrate the specific detected fault and repeatable command. |
| 57–60 min | Run the submission commands, inspect reports/artifacts, and finish concise RUN.md with actual results and the main limitation. |

Keep conditional integrations out of this schedule. If a live run fails, show
the failure and diagnose the smallest issue; do not replace it with a fixture
labeled as a real trace. Submission still requires the actual implemented
agent/eval and runs, not this timetable.

## Executable verification plan

### Setup check and observations actually obtained

The reusable preparation command is:

```bash
.venv/bin/python scripts/check_setup.py
```

Its current implementation, environment requirements, and recorded pass/fail
results belong in [SDK_SETUP.md](SDK_SETUP.md). Do not read the command's presence
here as proof that future agent checks pass.

Temporary-directory exploratory probes performed while preparing this plan
confirmed: help/list/open/parameter/mesh/load/solve/SF behavior; the original
`bracket_v3` SF of 1.428 under its 5000 N default load; original `flange_v1`
metadata/default load; invalid-state and invalid-argument errors; downstream
invalidation; baseline reopening; and the saved JSON shape. These were direct
CLI checks, with no model, no repair search, no changed-parameter solve, and no
persisted agent demonstration. Exploratory temporary files were deleted.

### Proposed offline test targets — not implemented yet

The following are exact **proposed future** unittest targets. Their commands
become runnable only after implementing the corresponding package/tests. Keep
tests behavioral: expected decisions, state changes, and evidence relationships,
not copies of the implementation.

The future commands below assume this checkout is the working directory and
the pinned environment has been activated with `source .venv/bin/activate`.

| Proposed command | What it must establish |
| --- | --- |
| `python -m unittest tests.test_policy` | Reject NaN/infinity/bool/unknown parameters; flange thickness 5.0 and hole diameter 4.0 boundaries allowed, violations rejected without subprocess execution; wrong force/face/direction rejected; search limits distinguished from manufacturing constraints. |
| `python -m unittest tests.test_state` | A second trial restores all original values; parameter/mesh/load mutations invalidate SF; a same-value set invalidates too; different trials may vary different parameters without accumulating a two-parameter repair; error paths do not invent successful state changes. |
| `python -m unittest tests.test_evidence` | Stable unique IDs and causal ordering; raw arguments/full solve log survive compact projection; guard rejection has no CLI execution; latest mutation → mesh → original load → fresh solve → save links validate; file content/hash match evidence; malformed/truncated evidence is not a success. |
| `python -m unittest tests.test_agent_offline` | Inject a deterministic model stub to emit separate tool calls and final output; preserve SDK raw call/results; a false final success claim fails validation; serialized tool execution prevents state races; label these traces synthetic. |
| `python -m unittest tests.test_config` | Missing model/credential or invalid budgets fail before provider requests; provider error/timeout/interrupt preserve failure evidence; bounded retries count attempts; isolated runs leave source checkout and each other's state unchanged. |
| `python -m unittest tests.test_save` | Unsolved/stale SF, wrong load, SF < 2, no changed parameter, two changed parameters, constraint violation, missing artifact, and artifact mismatch cannot produce `repaired`; baseline sufficient requires no fake repair. |

Use temporary copies of the real CLI for state behavior and focused stubs for
timeout, malformed output, provider failure, and attempted-call counting. Do not
need a paid model to check these behaviors. The repeatable non-happy-path demo
can select one focused test from this suite and explain exactly what it proves.

### Proposed live commands — not implemented or executed

The CLI spelling below is a recommendation for the future implementation.
Configure `COSMON_MODEL` and an approved run-budget config before using it;
do not put secret values in commands or RUN.md. Exact configuration options
must be implemented and documented rather than silently ignored.

```bash
python -m cosmon_agent run --part bracket_v3 --model "$COSMON_MODEL" --run-id 11111111-1111-4111-8111-111111111111 --config run-config.json
python -m cosmon_agent run --part flange_v1 --model "$COSMON_MODEL" --run-id 22222222-2222-4222-8222-222222222222 --config run-config.json
```

Use new UUIDs for subsequent runs; existing run directories must not be reused.
For each run, inspect the immutable raw trace, original snapshot/default load,
baseline solve, candidate restores and guards, final solve freshness, terminal
reason, and any saved `outputs/<part_name>.json`. A flange run may honestly end
without a repair; that outcome still needs evidence and precise scope. Do not
claim infeasibility from a bounded set of trials. Use the evaluation track's
agreed executable command to consume the resulting bundle **offline**; its CLI
is not invented here. Include a labeled flawed copy and demonstrate that eval
flags the chosen specific defect, while the untouched source trace remains intact.

### Required interface checkpoint

Before full implementation, the producer and eval track must explicitly confirm
schema/version, event and call identity, raw artifact encoding, tool-name and
argument mapping, proposal/guard/execution separation, original/default-load
representation, state/solve/save references, outcome semantics, interruption
and missing-data handling, and one compatible fixture for success plus rejection
or failure. Eval validates those fixtures without importing agent logic. Record
agreement and any revisions in the contract document. Until then the contract
and all example fields are proposals, not a completed integration.
