# Optional Inspect Scout report viewer

The evaluator remains Python standard-library only. This separate integration
imports completed evaluator reports into Inspect Scout and executes a deterministic
scanner so each independent dimension and its supporting references can be reviewed.
It does not call a model or re-grade the evidence.

The imported messages are explicitly labeled **derived evaluator reports**, not
original agent conversation turns. The original report bytes are copied unchanged
into the output's `reports/` directory, and their hashes are retained. Real source
labels (`live_agent`, `preparation_check`, `synthetic_fixture`) remain in metadata.

Prepare the optional environment (package download requires network):

```sh
python3 -m venv .venv-scout
.venv-scout/bin/python -m pip install -r scout_setup/requirements.lock
.venv-scout/bin/python -m pip check
```

Run from the repository root with a **new** output directory:

```sh
.venv-scout/bin/python -m unittest scout_setup.test_bridge -v
.venv-scout/bin/python -m scout_setup.bridge \
  --reports reports/reference-audit \
  --output-dir scout_setup/results/review
```

The bridge blocks Python network connection and DNS calls during import and scan.
It reads every manifest entry, including explicitly rejected evaluations, and fails
on incomplete batches, missing reports, inconsistent counts, duplicate identities,
unsafe filenames, unsupported dimensions, or unresolved check references. Scout
scans every imported transcript. The bridge then reads the **persisted** scan output
and verifies all `(transcript, dimension, status)` tuples and raw evidence references.

`verification.json` records acceptance, input hashes and every resulting dimension.
Database and scan file names contain Scout-generated identifiers; semantic output
is repeatable, while arbitrary Parquet/container bytes are not promised identical.
Exit 0 means the import and projection checks passed; it does not mean the evaluated
agent passed. Exit 2 means projection/validation failed. A partial output directory
from a failed command must not be reused; choose a new one after fixing its cause.

To inspect locally after that command:

```sh
.venv-scout/bin/scout view --transcripts scout_setup/results/review/transcripts \
  --scans scout_setup/results/review/scans
```

The projection does not contain the original model conversation. Raw trace files
remain in the source evidence bundles referenced
by each evaluator report. Source audit and executed checks:
[SCOUT_AUDIT.md](../docs/SCOUT_AUDIT.md).
