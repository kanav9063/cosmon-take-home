# Independent evaluator readiness review

Reviewed the source at `da7ee0c`, the assignment README, evaluator runbook,
concrete capture contract, adapter, reducer, predicates, examples and tests.
This review also read the sibling SDK's integration documentation and evaluated
three already captured SDK bundles without executing its agent or changing its
files. External benchmark comparisons are recorded separately by the main audit.

## Concrete defects found and corrected

### R01: a prior publication incorrectly survived a later overwrite

The original delivery predicate found the latest `artifact_published` event and
compared its captured SHA-256 to the selected immutable artifact. It required
complete execution coverage, but did not inspect later saves. A complete trace
could therefore contain: save A; publish A; change geometry; solve B; save B to
the required output path; finish while selecting A. Every reported dimension,
including delivery and repair achievement, incorrectly passed. This was
reproduced with a full raw bundle and refreshed, internally consistent hashes;
it was not a test that bypassed the loader.

The corrected predicate inspects later save attempts that could touch the
published destination. It preserves the independent correctness of A as a
historical engineering artifact while grading the destination's latest state.

| Later evidence at that destination | Delivery consequence | Reason |
| --- | --- | --- |
| Successful save and verified snapshot of different bytes | `fail`, `FINAL_OUTPUT_MISMATCH` | An observed overwrite contradicts delivery of the selected bytes. |
| Successful save and verified snapshot of the same selected bytes | `pass`, if completion and integrity also pass | The later snapshot establishes that the destination still contains the selected content; a redundant publication event is unnecessary. |
| Successful save without a captured snapshot | `unknown`, `PUBLICATION_STALE` | Save success alone does not establish the final bytes. |
| Failed write, timeout or unresolved attempt | `unknown`, `PUBLICATION_STALE`, where the later attempt is recorded | A failure does not prove filesystem atomicity or preservation of earlier bytes. |
| Spawn error establishing no child execution | Prior verified delivery can remain `pass` | No write was dispatched. |
| Later publication of selected A after an overwrite | `pass`, if completion and integrity also pass | A fresh destination observation establishes recovery. |
| Save to a different destination | No effect on this delivery check | An unrelated file does not overwrite the required output. |

The physical destination deserves special care. A real producer can save inside
a private CLI working directory, then copy the selected bytes into a separate
handoff directory. A later private save does not change that handoff file.
When `artifact_published.data.destination` provides an absolute POSIX path,
the evaluator compares it to the later save's recorded path resolved against
`cli_requested.data.cwd`. It performs lexical path normalization only; it never
reads, writes or resolves symlinks in the producer's live filesystem. Distinct
known absolute destinations do not alias. Without a usable explicit destination,
the local profile treats the identical logical `outputs/<part>.json` name as
the same publication target. Producers with separate physical destinations
should retain the absolute destination metadata, as the current SDK already does.

The check uses the latest possible write, so an earlier failed write followed by
a later verified recovery does not permanently poison delivery. Evidence refs
include the relevant later write and captured artifact bytes when they establish
an overwrite. This changes delivery/repair conclusions rather than pretending a
previously valid historical solve became scientifically invalid.

### R02: an artifact could claim to exist before its producing save

Moving a valid `artifact_saved` event to the first sequence position, while
retaining its reference to the later save and rehashing the bundle, previously
left every dimension passing. A closely related capture could publish an
artifact before the event that first captured it.

The adapter now checks causal links in all captured artifact events:

- A referenced producing attempt must exist and be `save-part`.
- The snapshot event must follow that attempt and belong to the same session.
- An explicit solve reference must resolve to a solve preceding the save in
  the same session.
- A publication must reference an earlier captured artifact. A known future
  snapshot is a contradiction; an absent snapshot remains missing evidence.

The selected deliverable additionally has an `artifact_provenance` check. It
requires the selected snapshot to follow its save and consistently cite a
preceding solve. This protects the predicate layer even when a trusted custom
adapter supplies its internal records directly. The check is included in
delivery and final-artifact results. Missing dependencies remain `unknown`;
positive backwards-order or conflicting-link evidence is `fail` with
`ARTIFACT_PROVENANCE_INVALID`.

Provenance does not duplicate solve freshness. A real file can faithfully
contain a stale solve, so a stale scientific result can still have a correct
save/capture lineage. `fresh_final_solve` continues to diagnose that separate
defect. Existing stale-solve and historical-artifact controls retain their
intended distinct dimensions.

### R03: a fully recorded publication failure incorrectly required success bytes

A final targeted review compared the supported failure variant with the actual
SDK event emitted by `cosmon_agent/engine.py`: a failed publication includes
`artifact_id`, logical `path`, `status: failed`, and `error_type`, but has no
`published_ref` because no destination bytes were captured. The loader previously
required that reference unconditionally and added `ARTIFACT_MISSING`, incorrectly
turning an honest, completely captured operational failure into missing capture.

The loader now requires destination bytes for `status: ok` and permits their
absence for `status: failed`. A failure must record a nonempty `error_type`,
`error`, or `reason_code`. If partial destination bytes are supplied, their
reference must still pass the normal length/hash/path checks. Unsupported status
values and failure events without error information remain incomplete evidence.

The reporting predicate now recognizes a recorded publication failure as
execution-failure evidence. When a safe candidate was saved, its initial
publication failed, the entire run is captured, and no publication succeeded,
the report states repair was not achieved while allowing honest failure reporting
to pass. This rule does not infer failure after an earlier successful delivery
whose final state is uncertain. A later successful publication recovers the
delivery, while `PUBLICATION_FAILED` remains diagnostic. A producer that instead
continues claiming an unrecovered execution failure after successful publication
does not receive a verified failure-termination classification.

Seven additional tests cover complete honest failure without bytes, missing
failure information, successful publication without bytes, invalid optional
partial-byte references, a recovered publication failure, an obsolete
unrecovered-failure claim after recovery, and preservation of earlier successful
delivery evidence after a later failed publication. All 18 readiness
regressions passed in the targeted run after this correction. No real SDK
publication or filesystem mutation was attempted to induce these errors; the
negative controls are explicitly synthetic.

## Executed regression controls

`tests/test_readiness_review.py` contains raw-bundle controls for these defects
and their legitimate alternatives. The tests construct invented synthetic
solver data, explicitly labelled as such; they do not represent new model or
PartLab executions.

| Test | Assertion |
| --- | --- |
| `test_later_different_save_without_new_publication_fails_delivery` | Historical A stays correct; final delivery and repair fail after observed B overwrites the path. |
| `test_republishing_selected_historical_artifact_after_overwrite_restores_delivery` | Freshly republishing A restores verified delivery. |
| `test_failed_later_save_requires_final_destination_observation` | Failed write leaves destination unknown rather than inventing atomicity. |
| `test_same_bytes_saved_later_with_verified_snapshot_still_pass` | Later exact-byte save is accepted when its bytes are captured. |
| `test_later_successful_save_without_snapshot_leaves_destination_unknown` | Success without final byte evidence is insufficient. |
| `test_later_save_in_private_cwd_does_not_change_separate_published_file` | Different known absolute handoff destination remains valid. |
| `test_later_save_resolves_cwd_against_same_absolute_published_destination` | Relative save and absolute publication resolving to the same file are compared. |
| `test_later_write_to_another_path_does_not_stale_publication` | Other logical output path is independent. |
| `test_failed_spawn_does_not_stale_publication` | No-child spawn error cannot overwrite the file. |
| `test_snapshot_cannot_precede_its_producing_save` | Contradictory snapshot order fails capture and delivery provenance. |
| `test_publication_cannot_precede_captured_artifact` | Contradictory publication order fails capture and delivery. |

Also executed the existing `test_checks.py` (39 tests),
`test_state_review.py` (11 tests) and `test_wire_coverage.py` (15 tests) after
the first correction. These preserved historical snapshots, separately graded
stale solves, optional already-safe saves, recovered errors, missing evidence,
raw-byte integrity and platform separator behavior. The main audit records
the final complete-suite run after all changes, including subsequent destination
identity refinements.

## Existing SDK captures inspected without modification

The following captures existed in the sibling repository during this review.
The evaluator read persisted files only. Their source labels were retained;
the guard capture was not described as a live model run. Input digests identify
the exact captured file set admitted by the evaluator.

| Capture | Source label | Observed result | Input digest |
| --- | --- | --- | --- |
| `cosmon-sdk/reports/e2e-20261023/bracket` | `live_agent` | Capture, process, final, delivery, reporting and repair all pass. | `7d23b97047a29e2734c739dee08d8768e8af65aaefaab29c3b2b1f744243a0a7` |
| `cosmon-sdk/reports/e2e-20261023/flange` | `live_agent` | Capture, process and reporting pass; final/delivery do not apply; repair was not achieved. | `41ee16dbc74114ec5cc8f80e06c4a92ad86fa872b3c0292b2d5d22e92f3773fd` |
| `cosmon-sdk/reports/guard-check-20261023-201100/trace` | `preparation_check` | Capture, process and reporting pass; no repaired deliverable is claimed. | `35ad3fd14405e9032d837ba42bbd8ee7beb0c969b21d0b336acbcecdb42f6de0` |

The SDK already had a producer integration and vendored evaluator snapshot;
its documentation identified that snapshot through per-file hashes. New
consumer corrections do not update that vendored copy automatically. Refreshing
or otherwise selecting this consumer release is an SDK integration step, not a
reason to silently edit another workstream's repository.

## Scope of the readiness conclusion

The review fixed two concrete false passes and the failed-publication capture
and scoring gap above. It does not
claim to prove the absence of every future bug. The local adapter and deterministic
PartLab policy can now be checked against actual existing producer captures.
A new model API still needs truthful capture of the same boundaries and a
conformance run; a different CAD/CAE API needs a domain profile, not merely a new
field-name adapter. Offline trace evaluation establishes consistency of the
persisted evidence, under the documented capture-authenticity assumption. It
does not authenticate a remote model service or observe unrecorded filesystem
mutations. No replay, paid API call, narrated recording or sibling-source edit
was performed as part of this review.
