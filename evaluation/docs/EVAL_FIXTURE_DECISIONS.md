# Fixture and scripted-capture decisions

This record describes the implemented fixture builder and examples. It is a
consumer integration profile, not a claim that the SDK producer has adopted the
same field names. It also does not turn preparation runs into model-agent runs.
The profile definition is [EVAL_IMPLEMENTATION_CONTRACT.md](EVAL_IMPLEMENTATION_CONTRACT.md).

## What was implemented

- `tests/bundle_factory.py`: standard-library writer and reusable scenario helpers.
- `scripts/build_examples.py`: command-line generation of selected or all synthetic
  examples, plus optional exact scripted CLI capture.
- `fixtures/examples/`: fourteen synthetic examples and two scripted PartLab
  captures. Reports must show their evidence kind.

The factory's public entrypoint is `scenario_bundle(path, scenario,
part_name=None) -> Path`. `SCENARIOS` lists supported names. `Builder` exposes
`begin`, `restore`, `set_parameter`, `analyze`, `block`, `save`, `publish`,
`finish`, lower-level `command` and `event`, and raw `write`. Tests can compose
adversarial histories without copying the evaluator's state implementation.
`refresh_inventory(path, status=...)` rehashes deliberately edited examples;
it does not correct their ordering, identity or semantic defects.

## Separation from evaluator implementation

The factory imports no adapter, reducer or checks. Its only dependencies are
Python's standard library. It does not ask the evaluator what result to encode,
and expected grades are not present in the bundle. This prevents the evaluator
from receiving an answer key and reduces the chance that a matching bug in a
fixture producer and the evaluator hides a defect.

Synthetic PartLab responses were shaped using observed CLI responses from the
pinned original binary. In particular:

- `get-parameters` returns a bare parameter map inside the result envelope.
- `set-parameter` returns `name`, `new_value`, `previous_value`, and
  `downstream_invalidated`.
- `solve` returns the applied load, SF, stress, yield, convergence, iterations and
  verbose log. The synthetic log explicitly identifies itself as invented.
- `save-part` returns `saved_to`; the saved file contains name, revision,
  parameters, applied load, and a solve summary without the verbose solver log.

Synthetic SF values are intentionally convenient test data. They are not
predictions made by PartLab and must not be presented as engineering results.

## Provenance and origin

`Builder` accepts only `synthetic_fixture` and `preparation_check`. It explicitly
rejects `live_agent`. Supplying a real working directory requires
`preparation_check`, and that evidence kind requires a working directory.
There are no model requests, provider responses, or fabricated model events in
these bundles. The final JSON message is a scripted visible result, not a
provider response. Synthetic guard examples use a runner-authored proposal and
a guard decision; they do not pretend that a model requested the action.

The original part is copied as exact bytes from this repository's original
`parts/<name>.json`. The manifest records its reference, the pinned binary hash,
producer version, schema, capture profile, trusted-case name, task reference and
policy reference. Captured task/policy text is context to cross-check, not the
source of authority for grading; callers must still supply a trusted case.

## Raw references and completion inventory

Every command attempt has a unique CLI ID and request/start/terminal events.
Requests retain argv, cwd, attempt number, and scenario purpose. Terminal events
reference separate stdout and stderr files and record process exit code and
termination. Empty stderr is retained as an actual zero-byte file.

References contain relative path, SHA-256 and byte length. Files are written
before references are created. JSON uses finite numeric values as JSON numbers,
not quoted decimal strings. The evaluator is responsible for independently
parsing these values with Decimal.

The completion inventory includes all captured files except itself. Excluding
`completion.json` avoids an impossible self-hash. It includes the manifest,
event ledger, outcome, final message, task/policy, original part, command streams,
saved artifacts, publication snapshots, and observed final output file.

For ordinary completed examples, `completion.status` is `completed`, event
count and last sequence match the ledger, and all CLI attempts terminate. An
adversarial missing-result example deliberately violates the last condition
while retaining a plausible complete envelope. This tests that envelope status
alone cannot prove execution completeness. The partial-tail example marks the
capture `interrupted` and retains an actual malformed last JSONL record.

## State, recovery and saved artifacts

A baseline explicitly executes reset, original open, parameter readback, mesh,
default load, solve, and SF readback. A new trial explicitly reopens the original
part and records the restoration CLI ID in `trial_started`; the label itself
never substitutes for the open execution.

Parameter sets retain the previously observed solve object inside the *fixture
builder*. This is intentional, so a stale-save example can falsely claim that
an old solve applies after a mutation. The evaluator must invalidate that solve
from raw execution order. The builder does not encode or import the evaluator's
correctness decision.

Each saved artifact is captured under immutable `artifacts/aNNNN.json`. A
publication records a separate immutable `published/pNNNN.json` snapshot and its
logical destination, `outputs/<part>.json`; the destination copy contains the
last observed publication. Consequently, two different histories can be tested:

1. Save and publish valid A, then explore B: A's save-time evidence remains valid.
2. Save and publish A, then overwrite the destination with B but claim A: A's
   historical validity does not establish that the promised final file is A.

The guard-blocked example has a raw tool-result file and no associated CLI child
attempt. The illegal-restored example does execute a thickness of 6 on the
flange before restoring and trying a legal candidate. Its later recovery must
not erase the observed manufacturing violation. The recovered-CLI example
contains a failed command followed by an explicit original restoration and
fully verified subsequent analysis; the error should remain visible as a
diagnostic rather than force a false final failure.

## Canonical examples

The `repaired` example is the positive control for modifications below. Unless
stated otherwise the part is `bracket_v3`, baseline SF is the invented value 1.4,
and a thickness of 4 is analyzed with the invented SF 2.4.

| Scenario | Evidence difference being exercised |
| --- | --- |
| `repaired` | Full default-load baseline, one changed parameter, fresh converged solve, saved/published part and matching final claim. |
| `already_safe` | Invented original SF 2.3; zero changes and a saved original. |
| `guard_blocked` | Flange thickness 6 proposal is blocked without execution; legal recovery follows. |
| `illegal_restored` | Flange thickness 6 actually executes; original is restored before the final legal candidate. |
| `stale_solve` | Thickness changes after a converged solve; old solve is attached to a newly saved part. |
| `missing_artifact` | A referenced saved-artifact file is removed after completion, retaining its inventory entry. |
| `wrong_load` | Candidate solve uses half the original default force. |
| `multi_parameter` | Candidate changes both thickness and hole diameter. |
| `historical_artifact` | Saved A is selected after later independent exploration of B. |
| `overwritten_publication` | B replaces the output destination while the final claim still selects A. |
| `missing_result` | A mutation request/start has no terminal event after an otherwise plausible repair. |
| `partial_tail` | Malformed JSONL suffix and interrupted completion preserve the usable earlier prefix. |
| `recovered_cli` | Failed CLI call precedes restored, complete final analysis. |
| `honest_exhaustion` | One candidate remains below target; outcome reports `no_repair_found` and a limited search scope. |

These descriptions are test intentions. Passing raw-structure validation does
not establish that a scenario is semantically correct. That is the job of the
independent reconstruction and checks tests.

## Real scripted capture

`python3 scripts/build_examples.py --output <new-directory> --real` creates the
synthetic examples and captures two additional scripted runs. `--scenario`
can be repeated to select fewer synthetic examples. The command refuses to
overwrite any selected destination before it starts generating output.

For real capture, the script checks the binary's SHA-256, copies the original
binary and parts to a new temporary directory, and runs commands only there.
The working directory, exact argv, exact stdout/stderr and process codes are
recorded. The original files and the repository's `.partlab` state are not
used as working state and are not mutated. Temporary execution state is removed
when capture finishes; captured evidence stays at the selected destination.

The script runs one explicit thickness-5 trial after an insufficient baseline.
This is a deterministic integration control, not an adaptive repair agent or
proof of an exhaustive search. It saves a candidate only if actual returned SF
is at least 2 and the solve explicitly converged. Otherwise it reports a
one-candidate budget exhaustion. No API, credentials or network call is used.

The checked-in captures produced these actual binary observations:

| Capture | Initial SF | Candidate | Final SF | Reported outcome |
| --- | --- | --- | --- | --- |
| `scripted_bracket_v3` | 1.428 | thickness 5 | 3.072 | `repaired` |
| `scripted_flange_v1` | 0.212 | thickness 5 | 0.839 | `no_repair_found` |

Both are `preparation_check`. They demonstrate the capture/consumer boundary on
real command bytes. They do not satisfy requirements for two model-agent traces,
do not establish global flange infeasibility, and do not create any recording.

## Verification performed

All sixteen generated bundles were loaded through the implementation's
`trace_adapter.load_run` using an independently constructed trusted `Case` from
original part bytes and explicit flange limits. Thirteen complete bundles and three intentionally
incomplete or unavailable-evidence cases were distinguished correctly: all examples other than `missing_artifact`, `missing_result`, and `partial_tail`
had complete execution coverage and no adapter issues. `missing_artifact`
reported missing referenced bytes, `missing_result` reported the unterminated
CLI attempt, and `partial_tail` reported the malformed tail and incomplete
capture. No fixture-shape compatibility changes were needed.

Syntax compilation passed for the builder and command-line script. Additional
independent reconstruction and predicate tests are recorded with the evaluator
rather than being inferred from this packaging validation.

## Adversarial adapter review and reproducible type sweep

A separate review exercised the raw adapter and public evaluator entrypoints,
without importing their implementation decisions into the fixture generator.
The review added `tests/test_adapter_review.py`. Its regression cases cover
malformed event/artifact IDs, embedded-null paths, unsupported capture profiles,
malformed case identity, missing raw live-model capture, missing or incorrectly
ordered completion, and a terminal event referencing the wrong outcome bytes.
The batch tests also compare full report bytes under input permutation and
reversed duplicate-run order.

The review found that an input ID of `summary` could overwrite its own report
with batch metadata. Report filenames now use the distinct `report-<id>.json`
namespace. The regression allows the legitimate ID `summary` and checks that
`report-summary.json` contains the individual report while `summary.json`
contains batch metadata. This avoids silently dropping a requested input or
introducing an unnecessary reserved user-visible ID.

`scripts/check_malformed_inputs.py` preserves the bounded malformed-type sweep
used during review. It substitutes nine representative JSON values into one
present field at a time: null, true, integer zero, decimal 2.5, empty list/object,
nonempty list/object, and empty string. The first suite mutates manifest and
outcome fields plus the envelope/data of one representative event per kind.
The second mutates the raw envelope/result of one representative CLI command
per command name. Each trial goes through `evaluate_one`, including loading,
state reconstruction, checks and report construction.

Raw response mutations update their explicit stdout references and completion
inventory so that malformed command data reaches the intended parser. Metadata
mutations retain deliberate semantic inconsistencies, while their containing
file is rehashed in the inventory. The test target is that malformed evidence
produces a report instead of raising an uncaught exception. Predicate-specific
expected failures remain the responsibility of the named unit/regression tests.

The reviewed fixed implementation completed **1,197 metadata trials and 513 raw
CLI envelope trials, 1,710 total, with zero crashes**. The reproducible command is:

```sh
python3 scripts/check_malformed_inputs.py --output reports/malformed-input-sweep.json
```

The optional result destination must be new. It records exact trial counts,
error locations and status. Temporary input bundles are removed automatically.
This is deterministic bounded testing, not an assertion that every malformed
combination has been exhausted. It also does not establish authenticity of
captured evidence or prove that every mutation receives the ideal semantic
finding. No subprocess, PartLab, model or network call is made by the sweep.

## Generated batch manifest and additional-part fixture behavior

`build_examples.py` now creates `inputs.json` after generating the requested
examples. Each entry contains a unique scenario ID, the generated bundle's part
name, and its relative directory. Selecting `--real` adds both scripted captures
to the same manifest. Repeated identical `--scenario` selections are deduplicated
in their original order. The manifest is a convenience for this trusted example
producer; the evaluator still validates each case against its independent
trusted case registry.

An existing `inputs.json` is refused during preflight, before new bundle folders
are created. This preserves previous evidence rather than quietly changing
which runs a saved command would evaluate. The script's selected-example plus
real-capture manifest was loaded end to end by `evaluate_batch`; a repeated
invocation was checked to fail before writing any new scenario directory.

The generic repaired fixture selects a thickness different from the trusted
original: it uses 4 unless the original thickness is already 4, in which case
it uses 5. This matters for `housing_v1`, whose original thickness is 4. The
choice supplies a synthetic one-parameter positive control; it is not an
engineering search strategy. Stale and subsequent-exploration variants use
that selected thickness plus 0.5. Existing bracket and flange examples retain
their previous values.

Two adapter tests exercise positive role-boundary capture, rather than only
rejecting missing fields. The first constructs temporary simulated model
request/response files, an explicit `model_call_id`, a tool proposal/result pair,
and a CLI attempt carrying the same `call_id`. The second captures a simulated
model transport failure, permits a complete failed run with no tool invocation,
and checks honest `execution_failure` reporting. These tests deliberately set
`live_agent` only inside their temporary wire-profile examples and prominently
label the bytes as simulated. They do not alter the checked-in examples or
claim that an actual model was executed. A failed model terminal event must not
be treated as a successful response capable of authorizing a tool proposal.
