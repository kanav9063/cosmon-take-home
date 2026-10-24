# Offline evaluation

This directory contains independent evaluator **1.1.0**, copied verbatim from
evaluation-workstream commit `b60473ca172a2fad33c377e96c212f2adb6aa84f`.
Its five production modules, case configuration, trusted parts, tests, and
integration contracts match that committed snapshot. `PROVENANCE.json` records
each file's Git blob identity, SHA-256 and size. No local source or test patches
are applied to this version.

The evaluator uses only the Python standard library. It does not import agent
policy, call a model, run PartLab, or trust a producer's success flag. Optional
Scout and Harbor environments are not included in this standalone snapshot.

Version 1.1 adds causal artifact and publication checks, detects later writes
that invalidate a destination snapshot, handles failed publications explicitly,
and records evaluator source and effective policy identity in reports. The
supported bundle remains `partlab.trace/0.1-proposal` with capture profile
`cosmon-eval/1`; no new model runs are needed to evaluate existing captures.

The earlier 1.0.0 import came from an uncommitted working tree and included one
test-only Decimal serialization correction. Its original provenance and patch
hash are preserved in `provenance/1.0.0.json`. The committed 1.1.0 test suite
supersedes that local correction. Previously saved reports remain evidence of
the evaluator version that produced them.

From the repository root, create an input manifest with one entry per capture:

```json
{"inputs":[{"id":"bracket","path":"captures/bracket-run","case":"bracket_v3"}]}
```

Paths resolve relative to the input manifest. Use a new report directory:

```sh
python3 evaluation/evaluate.py --inputs inputs.json --output-dir reports/evaluation-001
```

Exit 0 means reports were written. A failed repair can still produce exit 0.
Inspect the report's separate `capture_integrity`, `process_compliance`,
`final_correctness`, `delivery`, `reporting_accuracy`, and `repair_achievement`
dimensions. Honest bounded search exhaustion is distinct from a successful
repair and from a proof of infeasibility.

`eval_cases.json` pins trusted original part bytes and task constraints
independently of the producer. `--cases` supplies a different trusted case file.
`--policy` supplies diagnostic warning budgets, for example:

```json
{"warning_budgets":{"model_visible_tool_bytes":100000,"model_calls":48}}
```

These warning budgets never relax engineering checks. `--limits` controls
bounded parsing of input files. Run `--help` for the exact CLI options.

Run the imported regression suite without network access or an API key:

```sh
cd evaluation
python3 -m unittest discover -s tests -v
```

From the repository root, capture and evaluate a real guard regression without
a model or API key:

```sh
python3 scripts/check_agent_guard.py --output reports/guard-check-001
```

This solves the original flange under its default load, restores it, and proposes
thickness 5.5 mm. It checks that the manufacturing guard blocks the proposal
without dispatching a CLI command or changing state. The resulting
`preparation_check` bundle and its independent report are saved together; the
blocked proposal must be a diagnostic, not an executed constraint violation.

After producing real captures, evaluate them and demonstrate stale-solve and
interrupted-trace handling with:

```sh
python3 scripts/check_e2e_evaluation.py --inputs inputs.json --output reports/e2e-evaluation-001
```

The integration check requires one input reporting a completed repair. It
preserves all input captures and creates explicitly labelled synthetic
derivatives. The stale-solve derivative inserts a successful same-value
parameter assignment before saving, which invalidates the prior solve. Its
hashes are refreshed so the expected failure is semantic `STALE_SOLVE` rather
than an integrity mismatch. The interrupted derivative stops at a CLI start,
omits future evidence, and is explicitly incomplete. Neither derivative is a
claim that those events happened in the live run. The script evaluates the
combined batch twice in different orders and checks byte-identical reports.

The concrete wire contract is documented in
[EVAL_IMPLEMENTATION_CONTRACT.md](docs/EVAL_IMPLEMENTATION_CONTRACT.md).
The general integration notes are preserved in
[API_INTEGRATION.md](docs/API_INTEGRATION.md); references there to the source
repository's examples and additional design documents are historical and are
not part of this minimal import.
