# Trace contract proposal — SDK producer

**Status: proposal v0.1, not agreed with the evaluation chat.** This is a
design artifact from setup, not a captured agent run. Before implementation,
reconcile it with the eval track's `docs/EVAL_TRACE_REQUIREMENTS.md`, record the
accepted version in both plans, and run the same example bundle through both
sides. Neither side should infer agreement from the existence of this file.

The root [README](../README.md) is authoritative. The
[shared planning page](https://app.notion.com/p/4026333fbd2f807badd4d8f1d1c6fe6f)
supplies context; the subsequently approved core-first scope applies. ATIF is
an optional derived export, not the evidence source or a prerequisite.

## Boundary and authority

The producer writes plain JSON/JSONL and referenced files. The evaluator reads
them offline without importing `cosmon_agent`, invoking a model or PartLab,
or trusting the producer's verdict. A future adapter can translate another
harness into the same event vocabulary while retaining its raw source.

Keep three kinds of statement distinct:

1. **Proposal:** what the model requested, including malformed arguments and
   prohibited changes.
2. **Execution:** what the runner actually launched and the unmodified stdout,
   stderr and process result it observed.
3. **Interpretation:** guards, state summaries and final outcomes computed or
   claimed from that evidence. Evaluators independently check these claims.

Never derive execution solely from a model's tool call or a guard's `allow`.
Never treat a producer's `repaired` label as the success criterion. Evaluation
policy has its own version, thresholds and trusted constraints. In particular,
the evaluator must not accept relaxed manufacturing limits merely because a
run manifest records them.

## Small on-disk bundle

```text
runs/<run_id>/
  manifest.json                # immutable starting inputs and configuration
  events.jsonl                 # ordered append-only evidence references
  raw/model/m0001.request.json  # system prompt and exact SDK input items
  raw/model/m0001.response.json # full SDK ModelResponse serialization
  raw/tools/c0001.result.txt    # exact string returned to the SDK/model
  raw/cli/x0001.stdout          # exact subprocess bytes; never compacted
  raw/cli/x0001.stderr
  inputs/part.json              # original starter file bytes
  inputs/task.md                # original assignment README bytes
  inputs/policy.json            # run's policy configuration, independently checked
  outputs/<part_name>.json      # actual saved part bytes
  outcome.json                  # producer claim and evidence references
  completion.json              # completed/interrupted/failed, file sizes/hashes
```

Run directories are created exclusively and are never reused. Keep `.partlab`
in a separate private working directory with copied inputs; it is not a source
of offline evaluation evidence. Publish the selected verified artifact to the
submission's root `outputs/<part_name>.json` with the same hash and record that
publication separately. Do not overwrite an existing selected artifact silently.

Flush each event and its raw payload before returning control to the model.
Write new raw files exclusively, then append the reference. Serialize SDK
objects immediately at capture time, before later mutation. Finalize files
atomically; a partial run still has a readable manifest and completed event
lines. A truncated last line, missing completion marker or missing referenced
payload is incomplete evidence, not an empty successful run. No elaborate
distributed event store is needed for this exercise.

All paths are bundle-relative POSIX paths, resolved strictly inside the bundle;
reject absolute paths, `..`, and escaping symlinks. Each reference is
`{"path": "...", "sha256": "<64 lowercase hex>", "bytes": 123}`. Validate the
hash and length before reading evidence. These hashes detect accidental changes;
they do not authenticate a maliciously rewritten bundle. Sealing is an application
invariant, not a claim that local files are cryptographically immutable.

## Manifest fields

| Field | Type / requirement |
| --- | --- |
| `schema_version` | Literal `partlab.trace/0.1-proposal` until agreed |
| `run_id` | UUID string, stable for the entire run |
| `evidence_kind` | `live_agent`, `synthetic_fixture`, or `preparation_check` |
| `created_at` | RFC 3339 UTC timestamp |
| `case` | Part name/revision, target SF `2.0`, required output name |
| `original` | Input file reference, complete original parameters, default load including face, force in N, direction, material and revision |
| `task_ref`, `policy_ref` | Assignment and configured constraints references |
| `producer` | Harness/version, Python/dependency versions, source git SHA and dirty flag, binary SHA-256, prompt/tool-schema hashes |
| `config` | Provider/model identifier, explicit model settings, search domain/provenance and objective, budgets, timeout/retry settings, mesh settings |
| `capture` | `sdk_objects` model capture, subprocess `bytes`, whether provider HTTP transport is captured (`false` initially), hosted tracing setting |

No credentials, environment dumps, authentication headers or provider client
object reprs belong in the manifest. The exact model and numerical search/budget
settings must be resolved before a live run, not filled with implicit defaults.
The manifest's default load comes from the original file and must agree with
the CLI `open-part` response. Missing original data is a capture failure.

## Common event envelope and identity

Every JSONL line has the following fields (explicit `null` when not applicable):

```json
{
  "schema_version": "partlab.trace/0.1-proposal",
  "run_id": "11111111-1111-4111-8111-111111111111",
  "event_id": "e000012",
  "seq": 12,
  "time": "2026-10-24T01:00:00.000Z",
  "kind": "guard_decision",
  "actor": "guard",
  "trial_id": "t0001",
  "model_call_id": "m0002",
  "call_id": "c0003",
  "cli_id": null,
  "data": {
    "decision": "block",
    "reason_code": "manufacturing.maximum",
    "parameter": "thickness_mm",
    "proposed_value": 5.5,
    "limit": 5.0,
    "rule_id": "flange_v1.thickness_max",
    "proposal_event_id": "e000011"
  }
}
```

This is an **illustrative synthetic fragment**, not a real blocked model call.
All examples in this document have this status. The UUID is an example only.

`seq` starts at 1 and strictly increases without duplicates or gaps within a
bundle; it defines ordering, not wall-clock time. Local IDs (`e`, `m`, `c`, `x`,
`t` plus counters) are unique within a run; references use `(run_id, local_id)`
when crossing bundle boundaries. The independent `call_id` identifies one tool
invocation. Preserve the provider's native tool call ID and response item ID as
separate fields in `tool_proposed`; do not replace either with a tool name.
One tool call may cause several CLI invocations (e.g. readback verification),
each with its own `cli_id` and `purpose`. `actor` is one of `model`, `guard`,
`runner`, `harness`. Harness-initiated reset/readback calls have `call_id: null`
unless they are a documented child of a model tool call; they are still logged.

## Event vocabulary and required data

| `kind` | Required `data` fields and meaning |
| --- | --- |
| `model_requested` | `request_ref`, requested model/settings; exact prompt/input snapshot including prior tool results |
| `model_returned` | `response_ref`, native response/request IDs if supplied, usage as reported or `null`; full returned messages, reasoning items if exposed, function calls and original argument strings |
| `model_failed` | Error category, safe message, attempt number, retry eligibility, any available response evidence; not a fabricated response |
| `tool_proposed` | Name, `native_call_id`, native item ID, **raw arguments string**, source response/event; parsed args if valid or parse error |
| `guard_decision` | `allow` / `block`, stable reason/rule code, proposal reference, full proposed effective parameters and checked state revision where relevant |
| `cli_requested` | Ordered `argv` array, sanitized cwd label, timeout, `purpose`, `attempt`, parent guard/event; durable intent before spawn |
| `cli_started` | Spawn succeeded; PID and requested event reference. Not proof of completion or success |
| `cli_finished` | stdout/stderr references, `exit_code` or `null`, `termination` (`exit`, `timeout`, `signal`, `spawn_error`), duration, parsed envelope or parse error, requested/start references |
| `state_observed` | Current state summary, evidence CLI IDs for get-active-part/get-parameters and related successful actions, previous state revision, invalidated evidence IDs |
| `trial_started` | New trial ID, `baseline`/`candidate`, original input reference, restoration/open CLI ID, selected parameter or `null` |
| `solve_observed` | Successful solve CLI ID, state revision, mesh/load CLI IDs, effective parameters, complete applied load, SF and convergence exactly as returned |
| `artifact_saved` | Save CLI ID, artifact reference, solve event ID, state revision, observed parameters/load/solve summary from saved bytes |
| `tool_returned` | Exact model-facing result reference, source proposal/guard/executions; native call ID |
| `run_finished` | Final outcome reference and completion status; no implied success if absent |

JSON uses finite numbers only; do not serialize NaN or infinity. Retain unit
names (`force_N`, `thickness_mm`, `max_stress_MPa`) and do not round SF. A
malformed CLI stdout remains intact in its raw file even if parsed evidence is
unavailable. A malformed tool argument string stays intact even if the SDK
rejects it before entering the Python function.

No `cli_requested`/`cli_started` is permitted as a child of a blocked proposal.
Read-only inspection of the prior state after rejection is a separate harness
action, not an execution of the rejected change. Distinguish guard coverage
from actual violations: a blocked illegal proposal is useful negative-path
evidence, while the attempted proposal may still affect agent-quality scoring.

## State and freshness semantics

Maintain a monotone integer `state_revision` independent of the part's design
`revision`. It begins at zero for a closed workspace. Increment after every
successful state-changing CLI command, including reset, open, close, parameter
set (even a no-op numeric value), mesh and load. `solve` does not change this
analysis-input revision; every invocation still receives a fresh `cli_id`.
On an ambiguous failed mutation, mark state unknown and invalidate the solve;
do not certify recovery solely by incrementing a counter.

A state summary contains `known`, `phase`, original part identity, effective
parameters, active trial ID, applied load or `null`, current mesh CLI ID or
`null`, last successful solve event ID or `null`, and the current state revision.
It is a convenience index that the evaluator verifies from the raw commands
and responses. No hidden Python-state object is necessary to evaluate a run.

At the start of each candidate trial, reopen the original named part from the
private **unchanged starter copy**, then read effective parameters. Record the
open and readback evidence and require equality with the manifest original.
Clear old mesh/load/solve references. Try a single selected parameter in this
trial; selecting a different parameter requires another baseline restoration.
Proposed rule: one successful parameter mutation per trial, including a new
baseline restoration when trying a second value of the same parameter. Each
mutation requires a new mesh → default load → solve. This mutation-accounting
rule still needs confirmation. A final parameter difference is the numeric
comparison of all effective parameters against the original, not the number
of entries in the CLI override dictionary.

Before accepting `repaired`, the offline evaluator must be able to reconstruct:

1. Original identity, parameters, required constraints and default load.
2. Initial mesh/load/solve giving a finite original SF under the default load,
   with convergence confirmed.
3. Successful baseline restoration before the candidate sequence.
4. Exactly one final parameter differs; all final constraints hold.
5. Latest successful parameter/open/reset/mesh/load actions precede a successful,
   converged solve of that exact state, with SF ≥ 2.0 and the part's default load.
6. No intervening invalidating action before save; save's file bytes agree with
   parameters, load, part identity and that solve's result.
7. The final model claim and producer outcome cite this evidence accurately.

Check constraints on every successfully executed candidate mutation as well,
not only on the final saved parameters. An intermediate illegal change remains
an execution violation even if later reverted. Keep blocked proposals separate.

The strongest references point to actual CLI invocations and saved bytes, not
just matching counters. An unknown or missing reference yields unverified
evidence. An observed contradictory reference is a failure. Suggested evaluator
labels are `pass`, `fail`, `unknown`, `not_applicable`; scoring remains eval-owned.

## Examples of linked data (synthetic fragments)

The following describes links to be present in a **future fixture**, not a
complete valid fixture and not measured values from a repair:

```json
{
  "kind": "solve_observed",
  "data": {
    "solve_cli_id": "x0015",
    "state_revision": 8,
    "mesh_cli_id": "x0013",
    "load_cli_id": "x0014",
    "parameters": {"thickness_mm": 4.0, "hole_diameter_mm": 8.0, "fillet_radius_mm": 2.0},
    "applied_load": {"face_id": "face_mounting", "force_N": 5000.0, "direction": "-Z"},
    "safety_factor": 2.1,
    "converged": true
  }
}
```

```json
{
  "kind": "artifact_saved",
  "data": {
    "save_cli_id": "x0016",
    "state_revision": 8,
    "solve_event_id": "e000031",
    "artifact_ref": {"path": "outputs/bracket_v3.json", "sha256": "<computed from fixture bytes>", "bytes": 432},
    "observed_part_name": "bracket_v3",
    "observed_parameters": {"thickness_mm": 4.0, "hole_diameter_mm": 8.0, "fillet_radius_mm": 2.0},
    "observed_load": {"face_id": "face_mounting", "force_N": 5000.0, "direction": "-Z"},
    "observed_solve_summary": {"safety_factor": 2.1, "converged": true}
  }
}
```

The full fixture must also contain the common envelope, matching raw execution
files and complete actual-shaped solve summary. Placeholder hashes above are
intentionally invalid and must never pass fixture validation. Prefer an
invented part for full synthetic fixtures to avoid suggesting that illustrative
repair values are known PartLab answers.

For a **stale-solve** fixture, start with a valid synthetic bundle, insert an
executed parameter mutation between `e000031` and the save, and retain the old
solve reference in the claimed outcome. Update the fixture inventory/hashes so
the semantic checker, not only integrity validation, detects it. Preserve the
parent fixture and label the derived manifest `synthetic_fixture`, with a
`derived_from` reference and explicit edit description. The eval should name the
mutation and stale solve, not merely assign a lower aggregate score.

For a **blocked constraint** fixture, propose flange thickness 5.5, record
`guard_decision:block`, no mutation execution, and an exact model-facing error
with rule code and limit. This is a different check from stale-solve detection.

## Outcome contract

`outcome.json` contains `run_id`, `status`, `reason_code`, initial/final SF or
`null`, changed parameter or `null`, evidence event IDs, artifact reference or
`null`, configured search domain and attempted-candidate references, and the
model's final message reference. Status proposals:

| Status | Evidence required / limitation |
| --- | --- |
| `already_safe` | Fresh converged baseline solve with finite SF ≥ 2.0 at default load; no repair or saved part required by the task |
| `repaired` | Full seven-step evidence chain above and saved output |
| `no_repair_found` | Converged baseline with finite SF; finite completed trials/search budget and best verified result. Never claims global impossibility |
| `demonstrated_infeasible` | An explicit exhaustive finite feasible domain or a separately justified proof covering all allowed parameters/values. Solver failures, arbitrary range limits and finite unsuccessful sampling are insufficient |
| `execution_failure` | Configuration/provider/CLI/capture/artifact failure; stage, error, and last verified state. Not an engineering conclusion |

Early budget/turn/deadline stops may be `no_repair_found` only when baseline
analysis exists and the record supports that statement. Otherwise use
`execution_failure` with a budget-specific reason. An incomplete process has no
certified outcome even if an earlier message claimed success. Invalid model
success claims are retained verbatim and rejected by finalization; the producer
must not silently rewrite the message into a successful corrected history.

The configured exploration ranges approved for this exercise are not known to
cover the physical domain. Therefore `demonstrated_infeasible` is normally
unavailable; keep its evidentiary requirement rather than manufacturing proof.

## Capture implementation checkpoint

Installed SDK 0.24.0 exposes `RunHooks.on_llm_start` with system prompt/input
items and `on_llm_end` with `ModelResponse`. Snapshot these plus explicit
configuration/tool schemas. The function-tool context (`agents.tool_context`)
provides the native call ID and raw arguments. Persist proposals from every
returned response before tool parsing; wrap tool invocation to record validation
errors and results even when the function body never runs. Each wrapper returns
an explicit JSON string and records those exact bytes.

`RunResult.raw_responses` and `new_items` can provide a final completeness
cross-check; `to_input_list()` alone is not an immutable raw archive. Hooks and
SDK objects do not promise original provider HTTP bytes or inaccessible model
reasoning. Label capture fidelity honestly. Start with non-streaming calls; if
streaming is added, persist deltas and incomplete-response markers explicitly.
Disable hosted SDK tracing for the initial local capture path; a dashboard is
not the offline evaluator's input.

Also disable hidden SDK and provider-client retries initially. Hooks bracket
the SDK retry loop and cannot prove every physical provider request was logged.
If retries are later enabled, record them at the actual attempt boundary,
including failures; do not call a logical model invocation a complete physical
request log. Persist exact configured retry limits either way.

Before declaring compatibility, both tracks must check a minimal valid bundle,
a guard-blocked bundle, a stale-solve bundle and a partial-failure bundle; agree
on units/numeric equality, unknown-field/version handling, identity mapping,
failure semantics, and final output publication. Hashes, parsed observations
and raw records must agree. Record any departures here and in the eval plan.

No full schema validator, fixture bundle or producer is implemented by this
proposal. That is the next implementation checkpoint, not completed setup.
