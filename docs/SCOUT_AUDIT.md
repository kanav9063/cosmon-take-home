# Inspect Scout audit and integration

Audit date: 2026-10-23. Scope: evaluator-side integration, without a model/API
request. The core evaluator does not depend on Scout.

## Reference and version

The inspected release is **inspect-scout 0.6.1**, tag `0.6.1`, commit
`9db31e47de985a0f8098f326184efe0a41d5c3a5` (released 2026-10-21).
The tag was resolved from the official repository; execution uses the released
PyPI package in `.venv-scout`. Exact installed dependency versions are recorded in
`scout_setup/requirements.lock`.

Primary references:

- [Official 0.6.1 release](https://github.com/meridianlabs-ai/inspect_scout/releases/tag/0.6.1).
- [Transcript API and imports](https://meridianlabs-ai.github.io/inspect_scout/db_importing.html).
- [Custom scanners](https://meridianlabs-ai.github.io/inspect_scout/custom_scanner.html).
- [Transcript fields](https://meridianlabs-ai.github.io/inspect_scout/transcripts.html).
- [Pinned scanner/result source](https://github.com/meridianlabs-ai/inspect_scout/blob/9db31e47de985a0f8098f326184efe0a41d5c3a5/src/inspect_scout/_scanner/result.py).
- [Pinned scan source](https://github.com/meridianlabs-ai/inspect_scout/blob/9db31e47de985a0f8098f326184efe0a41d5c3a5/src/inspect_scout/_scan.py).
- [Pinned results reader](https://github.com/meridianlabs-ai/inspect_scout/blob/9db31e47de985a0f8098f326184efe0a41d5c3a5/src/inspect_scout/_scanresults.py).

## Decisions and requirements

**SC01 — Keep grading and browsing separate.** Scout supports custom transcript
imports and deterministic custom scanners. We use that facility to browse the
existing grades with their evidence. Scout does not replace the state reducer or
produce another conflicting engineering score. This integration verifies projection
fidelity; it is not independent validation that the original grade is correct.

**SC02 — Explicitly identify derived content.** One evaluator input becomes one
Scout `Transcript` with `source_type=cosmon_evaluator_report`. Each displayed check
is a derived message with a custom role label. No CLI command, observation, or
assistant conversation turn is invented. Metadata preserves the original `source_kind`
and evaluation status, including failed and rejected inputs. Real model captures
remain real captures; their report projections remain derived reports.

**SC03 — Preserve seven dimensions.** The transcript score is a dictionary. Its
`success` is null: this integration never reduces repair, reporting, compliance,
delivery, capture, final correctness and efficiency into one success Boolean.
The scanner emits one named result for each dimension, including `unknown` and
`not_applicable`. A safely recovered CLI error can remain diagnostic; a truthful
exhaustion report can remain accurate while repair achievement fails.

**SC04 — Require explicit content loading.** The official scanner documentation
notes that a scanner without active content filters may never be called. The
scanner therefore declares `messages="all"`. Every projection has an overview
message even when a rejected input contains no checks. The bridge verifies exactly
seven resulting rows per input; a silently skipped transcript cannot pass.
The configured `max_transcripts=1` is a concurrency limit, as confirmed in the
pinned `_scan.py` source. The separate `limit` parameter remains unset.

**SC05 — Preserve references twice.** Check messages contain the exact structured
check records, including raw file hashes, sizes, event IDs, line numbers and JSON
pointers. Dimension results link to these displayed messages and carry the raw
references of their member checks in metadata. The bridge reopens persisted Scout
results and compares that metadata to the original report. Repeated references
remain repeated because they belong to distinct check instances.

**SC06 — Use the batch manifest as the denominator.** The bridge never imports
`report-*.json` with a glob or filters only successful repairs. It loads the complete
`summary.json`, verifies requested/evaluated/rejected counts, and reads every listed
report once. Missing files, duplicate IDs, report/entry disagreement, incomplete
batch status, unresolved members and missing dimensions cause a visible failure.

**SC07 — Bound and constrain import.** Reports must have the precise local filename
`report-<input-id>.json`, be regular files, and not be symlinks. Duplicate JSON keys
and non-finite constants are rejected. Limits are 16 MiB per report, 256 MiB per
batch and 10,000 reports. These bounds protect the optional viewer import; they do
not alter the core raw-evidence limits or convert rejected evidence into passes.

**SC08 — Stable identity, fresh outputs.** Transcript identity hashes the projection
version, batch-summary bytes, input ID and report bytes. Changing the evidence
report or batch changes its identity. Scout imports are idempotent by transcript
ID, so this avoids accidentally retaining an old report after its content changes.
Each run requires a fresh output directory and preserves report bytes beside the
database. It does not overwrite prior audit output.

**SC09 — Verify persistence, not just function returns.** Acceptance reads Scout's
saved results with the official results API, requires a completed error-free scan,
compares every `(transcript_id, dimension, value)`, and compares every result's raw
reference metadata. Scan IDs, timestamps and Parquet organization can vary across
runs. Repeatability concerns the deterministic projection, identity, grades and
references, not byte-identical Scout storage files.

**SC10 — No runtime network or model judge.** No `llm_scanner`, model client or
provider credential is used. The executable installs a Python audit hook that
raises on connection, DNS and datagram send attempts. Package installation is a
separate network-enabled setup step. The integration stays outside core imports
and therefore adds no dependency to offline grading.

**SC11 — Do not assume native Harbor import proves our contract.** Scout has an
ATIF importer requiring Harbor >=0.6.0. Its documented file-time and subagent
handling are relevant to future trajectory browsing, but ATIF alone does not prove
our original-part identity, CLI raw bytes, inventory, save certificates or final
publication. The shipped bridge accepts already-evaluated reports and retains
their raw-reference evidence. A producer may additionally import its true conversation
through Scout's supported format once that conversation is available.

**SC12 — Pin a supported public API.** The integration calls `Transcript`,
`transcripts_db`, `transcripts_from`, `scan`, `Result`, `Reference`, `scanner` and
`scan_results_df`. It avoids private internal imports. The bridge checks the exact
Scout version at execution. Upgrades require rerunning its contract and persistence
tests; a package upgrade does not silently change stored interpretation.

**SC13 — Avoid the installed results-expansion metadata issue.** An initial
16-input integration scan emitted 112 dimension rows, but our reference comparison
caught that Scout 0.6.1's expanded DataFrame replaces the nested `metadata` with
`{}` and creates `metadata.*` columns. The persisted result objects still retain
their complete metadata. We now use the public `rows="transcripts"` option, then
read the nested result list ourselves. This checks the saved reference objects
directly and preserves all seven dimension results. The initial run was rejected
by the bridge and is not counted as acceptance evidence.

## Execution evidence

The reproducible commands are in [scout_setup/README.md](../scout_setup/README.md).
Executed verification records are stored in `scout_setup/verification/`; generated
Scout databases and scan artifacts live in ignored `scout_setup/results/`.
The acceptance record lists actual input IDs, report hashes, transcript IDs and
every persisted dimension, rather than claiming an unexecuted UI review.

Executed against the frozen `reports/reference-audit` batch:

| Check | Observed result | Evidence |
| --- | --- | --- |
| Optional bridge contract tests | 17 passed | `scout_setup/verification/tests.txt` |
| Complete import and deterministic scan | 19 inputs, 19 transcripts, 133 dimension results; no omissions | `acceptance.json` |
| Raw reference preservation | 4,507 reference occurrences matched exactly | `acceptance.json` |
| Repeat scan | Same identities, grades, metadata checks and source hashes | `repeat.json`, `repeatability.json` |
| Offline Docker scan | Same semantic result with `--network none` and source read-only | `docker.json`, `repeatability.json` |
| Explicit rejected-input control | All 3 inputs retained: 1 evaluated, 2 rejected; 21 dimension results | `rejected.json`, `rejected-inputs.json` |
| Dependency consistency and installed-file integrity | `pip check` passed; 10,345 installed RECORD hashes matched | `installation.json` |
| Scout database schema | Official `scout db validate` passed | `database-validation.txt` |
| Installed viewer entrypoint | `scout view --help` completed successfully; options recorded | `view-help.txt` |

All paths in the evidence column are relative to `scout_setup/verification` except
the explicitly spelled test path. The persisted scans recorded no model usage;
the bridge recorded zero attempted network operations. The acceptance source kinds
include real `live_agent` captures as well as preparation and synthetic examples.
Reading those existing captures did not make new API requests.

Integration hashes for `bridge.py`, `scanners.py` and `requirements.lock` are in
every acceptance record. The comparison excludes only Scout's generated scan
location; it does not exclude statuses, counts, references, source IDs or source
hashes. The local viewing/projection integration is complete. Mapping a new API's
actual conversation and raw tool capture still belongs to its producer adapter.
