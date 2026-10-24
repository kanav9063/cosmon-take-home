# Reproduce the submission

Run commands from the repository root. Python 3.12 is required; the bundled
PartLab binary targets Linux AMD64. Dependencies are pinned in `requirements.lock`.
The independent evaluator uses only the Python standard library. The bundled
version is **1.1.0**, pinned to source commit
`b60473ca172a2fad33c377e96c212f2adb6aa84f`.

## Setup

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip check
test -f .env || cp .env.example .env
chmod 600 .env
```

Set `OPENROUTER_API_KEY` locally in `.env`. The selected model and reasoning
settings are `openai/gpt-6.1-sol` and `medium`. Credentials are never required
for the offline checks and are not part of the committed evidence.

## Run both parts

```sh
.venv/bin/python -m cosmon_agent --part bracket_v3 --output runs/replay-001/bracket --publish-dir runs/replay-001/outputs
.venv/bin/python -m cosmon_agent --part flange_v1 --output runs/replay-001/flange --publish-dir runs/replay-001/outputs
```

Each invocation records a reset in a new private PartLab session. The original
parts and checkout session are untouched. Use fresh trace directories for
subsequent runs. Replay outputs are isolated above; omit `--publish-dir` to
publish to the assignment's `outputs/<part>.json` location. A different existing
file is never overwritten. The submitted live runs used the default location.

`--policy PATH` selects a JSON policy with configurable exploration ranges and
budgets. Defaults are six candidates, 48 model turns, 64 completed tool calls
and 300 seconds per run. The agent stops after its first verified repair.

## Offline verification

```sh
.venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=evaluation .venv/bin/python -m unittest discover -s evaluation/tests -v
.venv/bin/python scripts/check_agent_guard.py --output reports/guard-replay-001
.venv/bin/python evaluation/evaluate.py --inputs reports/e2e-20261023/inputs.json --output-dir reports/eval-replay-001
.venv/bin/python scripts/check_e2e_evaluation.py --inputs reports/e2e-20261023/inputs.json --output reports/e2e-replay-001
.venv/bin/python scripts/verify_live_capture.py reports/e2e-20261023/bracket reports/e2e-20261023/flange --publication-dir outputs --output reports/capture-replay-001.json
```

Use a new output directory or filename for each check. The guard check proves
that forbidden flange thickness is rejected with no CLI mutation or state
change. The end-to-end evaluation check creates labelled synthetic stale-solve
and interrupted derivatives and verifies their expected findings; it never
modifies the original captures. The capture audit verifies actual SDK/tool
continuity, compact context, original parts and the published artifact bytes.

The evaluator exits 0 when it writes reports, even when a repair fails. Read
the separate report dimensions, particularly `repair_achievement`. The
`--publication-dir` audit argument permits checking included artifacts after
relocating the repository; for new replays, use their output directory.

For new agent runs, save an input manifest in `runs/replay-001/inputs.json`:

```json
{"inputs":[{"id":"bracket","path":"bracket","case":"bracket_v3"},{"id":"flange","path":"flange","case":"flange_v1"}]}
```

Pass it with `--inputs` to the evaluator. Paths are relative to the manifest.
The derivative check needs at least one verified repair as its source.

The current verification recorded **21 passing agent tests and 154 passing
evaluator tests**. The [synchronization receipt](reports/evaluator-sync-20261023/sync-receipt.json)
pins the evaluator's source bytes; the
[latest offline replay](reports/evaluator-sync-20261023/evaluation-check/verification.json)
checks the original captures and negative cases with version 1.1.0.

## Model comparison

The completed comparison ran the same harness on five models and both parts
(ten runs), preserving separate captures and reports. To run a new comparison:

```sh
.venv/bin/python scripts/benchmark_models.py --output reports/benchmark-001
.venv/bin/python scripts/summarize_model_benchmark.py --input reports/benchmark-001
```

The first command makes paid model calls; the summary command evaluates saved
evidence without additional model calls. To reevaluate the included benchmark:

```sh
.venv/bin/python evaluation/evaluate.py --inputs reports/model-benchmark-20261024/inputs.portable.json --output-dir reports/benchmark-replay-001
```

The [comparison](reports/model-benchmark-20261024/comparison.md) records five
verified bracket repairs, three valid bounded flange outcomes, and two flange
reporting failures. The batch took about 66.6 seconds with provider-reported
cost **$0.371235631**. See [REPORT.md](REPORT.md) for interpretation and limits.

## Evidence and limits

The [submission report](REPORT.md) records the actual outcomes, test counts,
constraint check and known limits. The [architecture](docs/ARCHITECTURE.md)
explains the implementation. The original task remains in [TASK.md](TASK.md).

Optional development utilities are retained in `scripts/`: `check_setup.py`
checks local dependencies and PartLab, `inspect_partlab_io.py` probes isolated
CLI behavior, and `check_openrouter.py` makes a small **paid** provider/tool
smoke test. They are not needed to evaluate the included evidence.

The human recording link still needs to be added for submission. A bounded
search result is not a proof of infeasibility, and interrupted/ambiguous state
is reported conservatively rather than presented as a verified repair.
