# Executed Scout checks

These are observed results from the isolated Scout 0.6.1 environment. They refer
to `reports/reference-audit` and its manifest of 19 evaluator reports. The scanner
projects stored grades; it does not independently judge engineering correctness.

- `installation.json`: installed versions and verification of 10,345 hashed
  installed files, with zero missing/mismatched files. `pip check` also passed.
- `tests.txt`: all 17 bridge tests passed, including missing/duplicate/partial
  batches, unknown statuses, malformed JSON, unsafe paths, rejected inputs,
  preserved raw references and distinct content-based identities.
- `acceptance.json`: 19 inputs -> 19 transcripts -> 133 dimension results, with
  4,507 raw reference occurrences checked against their source reports.
- `repeat.json`: second independent local import/scan.
- `docker.json`: same import/scan in the pinned cached Python image, no network.
- `repeatability.json`: exact semantic equality among those three runs, excluding
  only their generated scan locations.
- `rejected.json`: three-input control with two explicit duplicate-run rejections;
  all three inputs and all 21 dimension results remained present.
- `rejected-inputs.json`: reproducible source manifest for that control.
- `database-validation.txt`: the official Scout database schema validator passed.
- `view-help.txt`: the installed viewer entrypoint and its supported options; this
  proves CLI availability, not a claimed manual browser/UI review.

The three accepted run records include hashes of the exact bridge, scanner and
dependency lock used. `network_attempts=0` refers to the Python network audit hook;
the Docker run additionally enforced `--network none`. `model_calls=0` is backed
by empty persisted scanner model usage and zero tokens, together with a scanner
that contains no model calls. Existing live traces were read, never re-executed.

Commands executed from `/home/ubuntu/work/cosmon-eval`:

```sh
.venv-scout/bin/python -m pip install inspect-scout==0.6.1
.venv-scout/bin/python -m pip check
.venv-scout/bin/python -m unittest scout_setup.test_bridge -v
.venv-scout/bin/python -m scout_setup.bridge \
  --reports reports/reference-audit --output-dir scout_setup/results/acceptance
.venv-scout/bin/python -m scout_setup.bridge \
  --reports reports/reference-audit --output-dir scout_setup/results/repeat
python3 evaluate.py --inputs scout_setup/verification/rejected-inputs.json \
  --output-dir scout_setup/results/rejected-reports
.venv-scout/bin/python -m scout_setup.bridge \
  --reports scout_setup/results/rejected-reports --output-dir scout_setup/results/rejected-scan
.venv-scout/bin/scout db validate scout_setup/results/acceptance/transcripts
.venv-scout/bin/scout view --help
```

Docker command executed through `sg docker -c` to use the host's configured group:

```sh
docker run --rm --pull=never --network none --read-only --tmpfs /tmp \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e XDG_DATA_HOME=/tmp/scout-data -e XDG_CACHE_HOME=/tmp/scout-cache \
  -e PYTHONPATH=/app/.venv-scout/lib/python3.12/site-packages:/app \
  -v /home/ubuntu/work/cosmon-eval:/app:ro \
  -v /home/ubuntu/work/cosmon-eval/scout_setup/results/docker-audit:/audit \
  -w /app \
  python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 \
  python3 -m scout_setup.bridge --reports /app/reports/reference-audit \
    --output-dir /audit/projection
```

The host `docker-audit` directory was created first; its `projection` subdirectory
did not exist. Choose new output paths for reruns. Original acceptance directories
remain in the ignored `scout_setup/results/` directory on the prepared host.
Failed exploratory runs are not counted as accepted checks. In particular, the
first scanner-reference spelling probe and expanded-metadata read exposed errors;
both were fixed before the recorded runs. See decision SC13 in `SCOUT_AUDIT.md`.
