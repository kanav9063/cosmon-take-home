# Run the offline evaluator

Python 3.12; standard library only. No API key, package install, network,
PartLab process, or model call is needed to evaluate persisted evidence.

```sh
cd /home/ubuntu/work/cosmon-eval
python3 scripts/verify.py --output-dir /tmp/partlab-eval-verification
```

Choose a **new** output directory on every invocation. This runs the regression
suite, including a 200-input batch in both orders, then generates and asserts
all 19 checked-in example and producer reports. Read its `REPORTS.md`, `verification.json`,
`summary.json`, and individual `report-<input-id>.json` files.

To evaluate all checked-in evidence, including the two existing live SDK runs:

```sh
python3 evaluate.py --inputs fixtures/all-inputs.json --output-dir /tmp/partlab-eval-reports
```

For new captures, create a JSON input manifest:

```json
{"inputs": [{"id": "bracket-run-001", "path": "captures/bracket-run-001", "case": "bracket_v3"}]}
```

Paths resolve relative to this manifest. Run the same command with its path.
Cases are independently pinned in `eval_cases.json`; use `--cases` for a trusted
additional case configuration. Producer policy never overrides those constraints.
Input IDs and run IDs must be unique within a batch. Duplicate run IDs receive
explicit rejected reports. Missing/malformed evidence cannot silently disappear.

Exit **0** means the batch reports were written, including reports of failed
repairs. Exit **2** means invalid invocation/configuration, output failure, or an
evaluator failure. Inspect each report's separate capture, process, final result,
delivery, reporting, and repair dimensions. There is no averaged success score.

Optional `--policy` accepts, for example,
`{"warning_budgets":{"raw_bytes":1000000,"model_visible_tool_bytes":100000}}`.
These are user-selected diagnostic budgets, not recommended universal thresholds.
Optional `--limits` accepts positive integer overrides for `max_file_bytes`,
`max_total_bytes`, `max_record_bytes`, `max_files`, and `max_events`.
Applied policy and limits are preserved in reports with a configuration digest.
Reports also identify the effective case policy, evaluator source hashes and
Python version. Rejected inputs remain unknown in every dimension so no
per-dimension denominator silently shrinks.

Generate fresh examples, including actual scripted PartLab captures:

```sh
python3 scripts/build_examples.py --output /tmp/partlab-fresh-examples --real
```

This command uses the pinned local binary in temporary isolated working
directories. It calls no model. The checked-in bracket capture repairs SF
1.428 to 3.072 by changing thickness to 5; the flange capture reports a bounded
one-candidate search without a repair (SF 0.212 to 0.839). Synthetic examples
are labeled and contain invented solver values solely for testing.

Run the complete verification in the already cached Docker image, with network
access disabled and source mounted read-only:

```sh
docker run --rm --pull=never --network none --read-only --tmpfs /tmp \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v /home/ubuntu/work/cosmon-eval:/app:ro -w /app \
  python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 \
  python3 scripts/verify.py --output-dir /tmp/eval-verification
```

On the prepared host an old shell may require `sg docker -c 'COMMAND'` to pick
up its existing group membership. The separate Harbor infrastructure task and
its checked oracle/no-op results remain documented in `docs/HARBOR_SETUP.md`.

Integration instructions: [API_INTEGRATION.md](docs/API_INTEGRATION.md).
Detailed rationale: [EVAL_DECISIONS.md](docs/EVAL_DECISIONS.md).
Executed coverage and limits: [EVAL_TEST_MATRIX.md](docs/EVAL_TEST_MATRIX.md).
Current checked results: [REPORTS.md](reports/reference-audit/REPORTS.md).
Original 1.0.0 results: [REPORTS.md](reports/eval-verification/REPORTS.md).
Current reference audit and acceptance: [REFERENCE_ACCEPTANCE.md](docs/REFERENCE_ACCEPTANCE.md).

The actual SDK producer connection is now tested using two completed live traces
copied unchanged from the sibling SDK workspace, plus its scripted guard check.
See [capture provenance](fixtures/producer-provenance.json). This evaluator made
no new model calls. A different API must provide the same required evidence;
the existing CLI handles those bundles. The original `RUN.md` remains the
assignment template owned by the agent exercise, including its recording.
