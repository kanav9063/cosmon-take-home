# Concrete integration profile for evaluator v1

Implementation contract for this repository's adapter and test fixtures. The
SDK proposal remains owned by its producer. This profile fills its unspecified
field spellings explicitly; it does not claim bilateral producer agreement.
The user approved implementation on the existing design. Missing optional
extensions remain unknown, never fabricated. A new API maps to `EvidenceRun`
or emits this documented profile; engineering rules do not depend on provider.

Schema is `partlab.trace/0.1-proposal`; manifest `capture_profile` is
`cosmon-eval/1`. The binary profile is `partlab-cli/9b202e1b`. All numbers in raw
input are JSON numbers. Output reports serialize Decimal quantities as strings.

Required files: `manifest.json`, `events.jsonl`, `outcome.json`,
`completion.json`; incomplete bundles may lack any and must receive a report.
References are `{path, sha256, bytes}`, with relative in-bundle paths. Inventory
does not include `completion.json` itself (no self-hash).

Manifest fields:

- `schema_version`, `capture_profile`, `run_id`, `evidence_kind`:
  `live_agent`, `synthetic_fixture`, or `preparation_check`.
- `producer.binary_sha256`; `original.part_ref` references original raw part.
- `case.part_name`; evaluator caller independently selects its trusted case.
- Optional original summaries must not contradict original raw bytes.
- `task_ref` and `policy_ref` retain captured task/policy. Their verified raw
  references are required for complete capture in this local profile.

Event envelope: `event_id`, integer `seq` starting at 1, `kind`, `run_id`,
`actor`, `trial_id`, `call_id`, `cli_id`, `data`. Model boundaries and live
proposals also use `model_call_id`. Optional `session_id` defaults
to `main`. Raw schema version/time can be retained as metadata.

- `cli_requested`: data `{argv: [binary, command, ...], cwd, attempt, purpose}`.
- `cli_started`: references its request through the same `cli_id`.
- `cli_finished`: data `{stdout_ref, stderr_ref, exit_code, termination}`.
  Normal termination is `exit`; alternatives timeout/signal/spawn_error. A spawn
  error may lack a start. Each request has a unique CLI attempt ID.
- `trial_started`: data `{restoration_cli_id, parameter}`. Restoration points
  at an actual preceding original open. Labels alone do not restore state.
- `tool_proposed`: raw argument string, tool name and provider IDs; call ID links
  guard, execution and tool return.
- `guard_decision`: data `{decision: allow|block|error, reason_code, ...}`.
  `error` explicitly extends the proposal; it never counts as safe rejection.
- `model_requested` requires verified `data.request_ref`; `model_returned`
  requires `data.response_ref`. Each `model_call_id` has exactly one request
  and later return or failure. `model_failed` is terminal failure evidence,
  never a successful proposal source. Record error information in its data.
- `tool_returned` requires `data.result_ref` and the same `call_id` as an earlier
  proposal. In live captures each proposal links to an earlier successful raw
  model response using `model_call_id`. Producer snapshots are cross-checks only.
  Non-null CLI `call_id` values must resolve to those tool boundaries, and all
  linked CLI execution must occur between proposal and return. Harness-only
  actions may use null `call_id`. Every guard resolves to a proposal and return,
  occurs between them, and precedes any linked CLI dispatch.
- `artifact_saved`: data `{artifact_id, artifact_ref, save_cli_id,
  solve_cli_id}`. Also support proposed `solve_event_id` by resolving it through
  `solve_observed.data.solve_cli_id`.
- `artifact_published` (optional extension): data `{artifact_id, path,
  published_ref, status}`. `path` is logical `outputs/<part>.json`; the referenced
  captured bytes establish the observed final destination. `status` is ok/failed.
  Later publication events supersede earlier ones for the same destination.
  Optional `destination` records the absolute physical handoff file; combined
  with CLI request `cwd`, it distinguishes a later private-workdir save from
  a write to that handoff destination. Without it, matching logical output
  paths share the local profile's output namespace. Paths are compared from
  captured evidence, not opened on the current host.
  An `ok` publication requires `published_ref`. A `failed` publication may omit
  that reference when no destination bytes were captured, and must retain a
  nonempty `error_type`, `error`, or `reason_code`. Any supplied reference is
  verified even on failure. A fully captured failed publication does not make
  the capture incomplete; it is execution-failure evidence and a diagnostic
  if a later publication succeeds.
- `run_finished`: `data.outcome_ref` points to the verified `outcome.json` loaded
  by the evaluator. It occurs exactly once as the last event; completion
  inventory closes capture.

Outcome: `status`, `initial_sf`, `final_sf`, `initial_solve_cli_id`,
`solve_cli_id`, `artifact_id`, `changed_parameter` (null or `{name, from, to}`),
`reason_code`, optional `search` with scope/budget/termination, and
`final_message_ref`. `final_message_format: json/1` means visible final content
is a JSON object containing `status`, `initial_sf`, `final_sf`,
`changed_parameter`, `artifact_id`; extra visible claims are not silently ignored.
Unsupported prose yields unknown visible-claim consistency. Recognized status
aliases are specified in EVAL_DESIGN.md.

Completion: `{run_id, status, event_count, last_seq, files}`; `files` is a map
from every captured relative file path except completion itself to its
`{sha256, bytes}`. Completed and honestly failed-but-fully-captured runs can have
complete execution coverage; interrupted/missing tails cannot. Every started or
requested CLI attempt must have a terminal record to establish execution coverage.

The internal dataclasses are in `eval_types.py`. `Action.name` is the hyphenated
CLI command; `Action.result` is independently parsed raw envelope `result`.
Reducer entrypoint: `reconstruct(run: EvidenceRun, case: Case) -> History`.
Checks entrypoint: `evaluate(run, history, case, policy=None) -> Evaluation`.
Do not read expected outcomes from fixtures in either entrypoint.

Evaluator 1.1 also checks causal artifact provenance: solve before save in the
same session, captured snapshot after its producing save, and publication after
its referenced snapshot. A later write to the delivered destination invalidates
an earlier destination observation unless later verified bytes re-establish
the selected artifact. A confirmed same-byte save or actual re-publication is
sufficient; failed/uncaptured writes leave delivery unknown. Historical saved
artifacts remain eligible when these final-destination requirements are met.
