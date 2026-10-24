# Synthetic evaluation preparation

These fixtures are **preparation only**. They are **not actual raw model runs**, **not ATIF**, **not an agreed SDK producer schema**, and **not proof that an evaluator works**. All safety factors, CLI executions/results, state observations, and saved artifacts are invented. Baseline part snapshots were copied from the original starter files; their inclusion does not turn the invented analysis into a real run.

The package expresses proposed **consumer evidence semantics**. The SDK producer contract and its eventual normalizer must be reviewed separately before implementation. Do not make a producer emit this format merely because the fixtures exist.

Run the zero-dependency packaging check from the repository root:

```sh
.venv/bin/python eval_preparation/check_fixtures.py
```

System `python3` also works. Optional file arguments select fixtures. Output is one JSON object per file; exit status is nonzero for packaging errors. The checker reads only supplied fixture JSON and writes nothing. It checks synthetic labels, duplicate keys/IDs, contiguous event order, run/call links, reference existence, numeric finiteness, snapshot digests, artifact byte digests, and required proposal/result linkage. It **does not** evaluate manufacturing constraints, state transitions, solve freshness, target safety factors, parameter changes, or final claims. In particular, `stale_solve.json` must pass this packaging check.

## Inventory

| Fixture | Intended future semantic result | Events | Calls |
| --- | --- | ---: | ---: |
| `fixtures/repaired.json` | Valid one-parameter synthetic repair | 25 | 11 |
| `fixtures/already_safe.json` | Already safe; save/repair checks not applicable | 11 | 5 |
| `fixtures/guard_rejected.json` | Rejected flange thickness proposal is not executed; truthful search exhaustion | 13 | 5 |
| `fixtures/stale_solve.json` | Deliberate semantic flaw: `STALE_SOLVE` | 29 | 12 |

`expected.json` records anticipated future evaluator findings. It is **expectation data**, not produced evaluation output. These are semantic-unit examples: they lack complete raw-capture evidence and cannot establish an end-to-end integrity pass. The search-exhausted fixture has no fabricated compliance failure, but repair achievement is `fail` (not achieved) and feasibility remains `unknown`. The stale fixture changes thickness again after the last solve, then saves the new snapshot and claims the old SF; the final snapshot and parameter claim agree, isolating freshness as the intended flaw. Required/forbidden finding codes identify the specific assertion without suppressing related final/artifact explanations. All synthetic files remain independent of live PartLab session state.

The simplified examples also omit raw solver-convergence evidence. Their
`fresh_solve` expectations test state/solve linkage only. Full baseline/repair
validation must additionally check convergence from the agreed raw producer
format; do not infer it from a `solved` phase or finite SF.

## Proposed package fields

- `schema_version: eval-fixture-proposal/0`, `source_kind: synthetic`, `fixture_id`, `run_id`, and `provenance` label the package and invented values.
- `baseline` references an original full part snapshot and its default load; `task` supplies the named part, SF target, and manufacturing constraints.
- `snapshots` contains `snapshot_id`, full `part` objects, and SHA-256 digests of canonical JSON (UTF-8, sorted keys, no whitespace, no NaN/Infinity).
- `states` contains `state_id`, `snapshot_id`, phase, and effective load. Phases describe the fictional observed session, not evaluator conclusions.
- `events` contains `event_id`, contiguous one-based `seq`, `kind`, `run_id`, optional `call_id`, and `data`. CLI execution and result are separate records sharing a call ID; results reference execution event IDs. These are logical invented CLI facts, **not raw stdout/stderr or SDK envelopes**.
- `guard_proposal` and `guard_decision` events are separate from `cli_execution`. Proposal/decision references permit distinguishing a suggestion from an actual state change.
- `solves` contains stable `solve_id`, `solved_state_id`, `result_event_id`, and invented `safety_factor`. A reference to a solve is not evidence that it remains fresh.
- `artifacts` embeds exact synthetic saved JSON bytes as `content_utf8`, their SHA-256, path, saved-state reference, save-result reference, and most recent solve reference. No real `outputs/` artifact is claimed. Digests protect internal consistency only; no authenticity or independent SDK replay is implied.
- The final `final_claim` event records outcome, SF and solve references, current state, original/final parameters, effective load, and optional saved-artifact reference. A claim is deliberately distinct from reconstructed verification.

Actual producer evidence will additionally need immutable raw messages, model/tool request/result envelopes, observed exit codes and raw stdout/stderr, complete run boundaries/status, provenance/version identity, and reliable artifact capture. How those raw records map to these consumer concepts is the required integration checkpoint.
