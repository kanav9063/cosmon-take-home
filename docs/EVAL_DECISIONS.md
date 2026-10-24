# Evaluator implementation decision record

This records the implementation authorized after the design review on October
23, 2026. The user explicitly requested implementation of every evaluator part,
very detailed decision tracking, and readiness apart from connecting a different
API. Earlier preparation-only restrictions are historical, superseded for this
eval clone. The original assignment files and sibling SDK checkout remain
unchanged. No provider inference or internet access is required by this work.

Detailed component records complement this file:

- [State reconstruction decisions](EVAL_STATE_DECISIONS.md)
- [Predicate and scoring decisions](EVAL_CHECK_DECISIONS.md)
- [Fixture, raw-capture and adversarial decisions](EVAL_FIXTURE_DECISIONS.md)
- [Executed requirement coverage](EVAL_TEST_MATRIX.md)
- [Concrete capture contract](EVAL_IMPLEMENTATION_CONTRACT.md)
- [Connection and acceptance procedure](API_INTEGRATION.md)
- [Tau²/Scout reference acceptance and current verification](REFERENCE_ACCEPTANCE.md)

## D01 — Authority and scope

**Decision:** use the unchanged assignment plus the user's accepted policies as
the grading authority. Implement only in `cosmon-eval`. Read sibling SDK notes
for observed CLI behavior, without modifying its source or imposing a bilateral
contract. Preserve original README, RUN.md, executable, six parts and original
setup/requirements notes. Put actual evaluator commands in `EVAL_RUN.md`.

**Reason:** preparation and API ownership are distinct from authorization to
finish this evaluator. The user authorized the latter. Blocking all work on
another chat's acknowledgment would leave independently implementable work
unfinished. Calling our local schema mutually agreed would overstate evidence.

## D02 — Five modules with independent policy inputs

**Decision:** separate internal types, raw adapter, state reducer, checks, and
batch/CLI reporting (`eval_types.py`, `trace_adapter.py`, `eval_state.py`,
`eval_checks.py`, `evaluate.py`). Cases and manufacturing constraints live in
trusted `eval_cases.json`. No grading module imports the agent's guard, fixture
builder, model client or expected-results table.

**Reason:** failures can be located at capture, semantics, predicate, or output
boundaries. New case data does not require changes to checks. A harness can map
to the same internal evidence without rewriting domain rules.

**Rejected:** a single success regex, model judging, rerunning PartLab during
grading, or taking a producer success flag as an independent verdict.

## D03 — Explicit local profile, no silent compatibility

**Decision:** support `partlab.trace/0.1-proposal` only with local capture profile
`cosmon-eval/1` and the pinned PartLab binary digest. Document previously
unspecified publication, terminal inventory, final-claim and guard-error fields.
Unknown versions/actions become explicit unsupported evidence and state gaps.

**Reason:** recognizing a schema name alone cannot guarantee compatible command
or invalidation semantics. The profile is an implementation contract for this
repository, not a change to the SDK owner's proposal. Optional extensions may
be absent, but any predicate needing their evidence remains unknown.

## D04 — Trusted originals and exact numbers

**Decision:** select the case independently through the caller; validate original
bytes against pinned SHA-256. Parse JSON numbers as Decimal, reject duplicate
keys, NaN/infinity and booleans as numerical evidence. Preserve raw lexemes in
source bytes; serialize Decimal report values as strings.

**Reason:** a modified original with a freshly computed producer hash cannot
redefine baseline geometry or manufacturing policy. Binary float rounding must
not legalize SF below 2, flange thickness above 5, or holes below 4. There is no
implicit epsilon around hard limits. Equality is numerical, not textual.

## D05 — One byte source for hashing and parsing

**Decision:** cache bounded reads and hash/parse those same bytes. Require local,
canonical relative paths with no parent traversal, backslashes, NUL, symlinks or
nonregular files. Read limits default to 16 MiB per file, 64 MiB total, 2 MiB per
record, 4,096 files, and 100,000 events per bundle. All are explicit overrides.

**Reason:** references are untrusted. A file's later contents must not differ
from the contents used to verify its digest. Limits prevent accidental resource
exhaustion and must produce findings rather than silent truncation. Defaults
are resource ceilings, not learned engineering thresholds.

**Limit:** local references and hashes establish recorded consistency under
capture authenticity assumptions. They do not cryptographically authenticate
the producer or independently prove physical execution. Evaluate immutable
captured directories; this is not a hostile concurrent-filesystem sandbox.

## D06 — Capture failures remain visible

**Decision:** validate unique IDs, monotonic sequence, paired requests/results,
role-specific raw references, and a unique final `run_finished` pointing to the
actual loaded `outcome.json`. Completion inventories exclude themselves and
hash all referenced payloads. A malformed record creates a state-evidence gap;
the intact prefix remains available for affirmative findings.

**Reason:** EOF, an empty `model_returned` label, or a top-level success claim
does not prove capture ended correctly. A failed CLI command with complete
stdout/stderr differs from a missing terminal record. Live capture requires
model IDs and ordered tool boundaries; scripts cannot qualify merely by label.

## D07 — Replay executed evidence, not intentions

**Decision:** only raw executed CLI results update state. Proposals and guard
events remain separate. Every same-session overlapping stateful operation
creates ambiguity. Missing or malformed transitions invalidate the affected
knowledge; readback or verified restoration may recover later state.

**Reason:** a proposed illegal change is not an executed mutation. Conversely,
a guard claiming it blocked dispatch cannot erase a matching actual command.
Failed calls are not universally assumed atomic; readback can show effects.

## D08 — Proven generations and historical saves

**Decision:** geometry/open/reset/mesh/load transitions have explicit
invalidation rules. Same-value setters still invalidate analysis. A current
result must reference a solve for the selected state. A saved artifact keeps
its immutable save-time certificate even after later exploration, provided
the correct bytes remain at the required destination.

**Reason:** geometry equivalence alone cannot prove a fresh FEA workflow. The
other extreme—invalidating every historical result whenever the live session
changes—wrongly rejects legitimate selection of an earlier saved candidate.
The reducer decision record details each verified PartLab transition.

## D09 — Original restoration and one-parameter meaning

**Decision:** require session reset evidence before the original baseline, and
original restoration before each independent trial. Repeated changes to the
same parameter within a trial are allowed. Exactly one final parameter must
differ from the original on the repair branch; already-safe baselines need no
change. Observe every executed manufacturing-constrained value, even later
restored values. Whole-run compliance cannot be recovered by deleting history.

**Reason:** these implement the assignment's reset requirement and the user's
accepted trial policy. They do not silently adopt a stricter one-mutation-total
rule from an unagreed SDK proposal.

## D10 — Four statuses and separate dimensions

**Decision:** use pass/fail/unknown/not_applicable for scoped predicates. A
failure needs affirmative contradictory evidence. Missing/unsupported evidence
is unknown. Aggregate capture, process, selected result, delivery, reporting,
and repair separately; retain member predicate IDs. No weighted average.

**Reason:** a valid final repair can coexist with an earlier forbidden mutation;
both facts must remain visible. An honest exhausted search can pass reporting
while failing to achieve a repair. A harmless recovered error remains diagnostic.
The meaning of each aggregation is documented in the predicate decision record.

## D11 — Finite search does not prove infeasibility

**Decision:** accept honest bounded-search exhaustion only with coherent search
and outcome evidence. Reject unsupported global impossibility claims. No
complete-domain infeasibility verifier is implemented in this PartLab profile.

**Reason:** several failed candidates do not establish that no allowed parameter
value can work. This is an explicit limitation of the approved v1 design, not a
missing API connection that a provider swap automatically fixes.

## D12 — Save execution, content and delivery are separate

**Decision:** verify producing save ID/path and timing, immutable parsed content
against the selected certificate, and the latest observed publication at the
required logical destination. Cross-check name/revision/full parameters/load/
solve fields. A path string alone cannot pass these checks.

**Reason:** a successful save response can be followed by overwriting the file;
an intact earlier snapshot would conceal that delivery failure. Optional saves
of already-safe originals are checked without demanding an unnecessary repair.

## D13 — Deterministic final-claim checking

**Decision:** compare structured outcome with raw solves, selected artifact and
changed parameter, and separately compare visible `json/1` content. Unsupported
free prose is unknown rather than judged by a model. Extra visible fields are
not silently ignored. Preserve outcome aliases explicitly.

**Reason:** a correct structured record does not make contradictory user-visible
claims correct. Deterministic claim rendering is an integration responsibility.
Reports use `unverified` when achievement cannot be established and
`repair_not_achieved` for affirmatively failed repair requirements.

## D14 — Batch completeness and deterministic output

**Decision:** process independent runs in sorted input-ID order. A malformed
bundle gets an explicit report/rejection; reject every member of a duplicate
run-ID group, without order-dependent first-wins behavior. Assert requested =
evaluated + explicitly_rejected. Reports are `report-<id>.json`, separate from
reserved `summary.json`. Existing destinations and evidence overlap are refused.

**Reason:** losing troublesome inputs inflates success rates. Filename prefixes
prevent an input named `summary` from overwriting batch metadata. Atomic
temporary writes, flush/fsync, and rename prevent readers seeing partial JSON.
Repeated runs in fresh directories produce byte-identical reports.

## D15 — Evaluator failures are not agent failures

**Decision:** a normal completed batch exits 0 regardless of engineering grades.
Invalid invocation/configuration or an internal/output exception exits 2.
An exception during a batch attempts `aborted.json` with written and unevaluated
IDs, then remains an error. It is never converted into a fabricated trace verdict.

**Reason:** automation needs to distinguish grading failure from execution
failure. Regression injection deliberately raises a programming exception and
asserts that no successful per-run report or silent reduced denominator appears.

## D16 — Measured efficiency, opt-in warning budgets

**Decision:** report raw bytes/files/events, CLI and solve attempts, failed
attempts, model calls, verified request/response/tool-result bytes, and repeated
successful reads with unchanged intervening state. Provider token counts remain
null. A malformed byte reference produces an unknown metric, not an invented
zero. User-configured finite nonnegative budgets produce diagnostics only.

**Reason:** full retained evidence is not all model context. Bytes are not
tokens, repetitions across changed state may be necessary, and no universal
efficient trace-size threshold has been established. Case policy, resource
limits and warnings have distinct meanings and are recorded separately.

## D17 — Evidence classes and offline reproducibility

**Decision:** keep 14 complete synthetic examples and two actual scripted CLI
captures. Real captures use temporary private sessions with copied pristine
parts and the verified binary. Never relabel them as live agent runs. The
verifier asserts source labels, expected dimensions, specific defect codes and
evidence references. A 200-input mixed batch is run in both orders.

**Reason:** synthetic values isolate logic without pretending to establish
physics. Actual captures validate the parser against the binary's observed
output. Neither demonstrates model reasoning; that remains for the API owner.
Network-disabled Docker verification additionally tests runtime independence.

## D18 — API connection is an explicit remaining boundary

**Decision:** support persisted local bundles and trusted adapter registration.
Do not import an arbitrary adapter named inside a trace. Batch adapters share a
small identity manifest; single-run adapters may consume a different layout.
Document the exact outstanding mapping and acceptance steps.

**Reason:** a future model/harness swap should not alter engineering predicates.
A different CAD/CAE API does require validation of its state transitions and
artifact semantics. We do not claim every possible API can connect by renaming
fields, or that live interoperability has been tested without the producer.

## Review corrections recorded during implementation

| Initial defect or ambiguity | Final decision and regression evidence |
| --- | --- |
| Post-solve mutation first appeared only unknown because it cleared the load | Check affirmative generation mismatch first; `test_semantic_stale_detected_with_raw_evidence` requires `STALE_SOLVE` with raw provenance. |
| Optional already-safe save was treated as a repair | Branch-scoped one-parameter requirement; predicate tests cover unchanged baseline saves. |
| Missing/malformed IDs or reference paths could raise TypeError | Validate strings before hash/map/path operations; adapter review plus bounded scalar mutation sweep. |
| A recognized schema name could bypass a missing capture profile | Require the concrete profile and pinned binary; `test_unknown_capture_profile_not_certified`. |
| Context references were retained but not validated | Validate task/policy references with the same reader; `test_manifest_context_reference_is_validated`. |
| Empty model event labels could masquerade as live capture | Require ordered role-specific IDs/raw references; `test_empty_model_event_labels_do_not_prove_live_capture`. |
| Terminal event could precede commands or reference another file | Require unique final event and exact loaded outcome reference; three terminal-event regressions. |
| Input ID `summary` could collide with batch output | Prefix every per-run filename; `test_summary_input_id_does_not_overwrite_batch_metadata`. |
| Batch identity preflight initially bypassed bounded reads | Reuse `Reader` for preflight, retaining explicit rejection on read/integrity errors. |
| CLI options before positional arguments could confuse parsing | Parse the supported flags independently; recorded real CLI captures validate placement. |
| Malformed successful setter could disappear after restoration | Retain unestablished mutation effects in process aggregation; independent state-review regression. |
| Search exhaustion ignored a false changed-parameter claim | Compare every supported structured claim, including nonrepair outcomes. |
| Cleanup reset incorrectly made an already-safe baseline stale | Scope the baseline certificate to its actual selected analysis, while validating any explicit solve ID. |
| Safe analysis with a known failed save remained merely unknown | Retain known lack of delivered repair, separately from honest execution-failure reporting. |
| A run without the required initial reset could otherwise all-pass | Add baseline-scoped reset evidence check. |
| Housing portability fixture made a same-value change | Correct the test candidate to differ from its data-driven original; no weakening of one-parameter semantics. |
| A custom trusted case could omit revision/material and crash grading | Validate required identity fields before accepting configuration; `test_custom_case_rejects_missing_identity_fields_before_grading`. |
| A CLI or guard could name a nonexistent tool call while capture passed | Require tool-boundary resolution and temporal containment for non-null links; seven raw controls in `test_capture_links.py`. Harness actions retain legal null call IDs. |
| Custom adapter selection was absent from output provenance | Record adapter name and selected case profile; adapter parity test compares semantics while checking distinct adapter names. |
| New malformed-case regression tried to JSON-encode internal Decimal objects | Build the adversarial case from independently parsed raw part JSON; the fixture writer accepts wire numbers rather than internal evaluator types. Final verification is rerun after this test-harness correction. |

The component decision records contain further rejected alternatives and exact
test references. Generated verification records identify the source hashes and
counts actually tested; passing prose or a planned matrix alone is not evidence.

## Original 1.0.0 verification checkpoint

- **131 automated tests passed** on the host and in the pinned Docker image.
  The container had `--network none`, a read-only source mount and temporary
  writable `/tmp`. Its command, exit status and unchanged source digests are
  retained in [docker-offline-verification.json](../reports/docker-offline-verification.json).
- **16 example reports were generated and asserted:** fourteen synthetic
  bundles plus actual scripted bracket and flange captures. The independent
  assertion script checks dimension values, named defect codes, absence of
  unrelated defects in controls, and source labels.
- **200 mixed inputs were evaluated twice in opposite input order.** Both
  executions produced byte-identical reports, with 197 evaluated and 3 explicitly
  rejected entries (the duplicate pair and malformed input), preserving all 200.
- **1,710 deterministic malformed-field trials completed without an uncaught
  exception:** 1,197 metadata substitutions and 513 raw-envelope substitutions.
  This is bounded robustness evidence, not exhaustive input verification.
  [Result](../reports/malformed-input-sweep.json).
- The original assignment files still match commit `20b46cd`. Source Python
  parsed, local document links resolved, and `git diff --check` passed.

The expected `EVALUATOR ERROR` and injected `INTERNAL EVALUATOR ERROR` messages
in test logs come from tests asserting exit 2 and preserved aborted-batch
accounting. The enclosing unittest result is the verification outcome.

See [checked report index](../reports/eval-verification/REPORTS.md) and
[source-digested verification](../reports/eval-verification/verification.json).
No live model run was claimed at that checkpoint. The next integration step was the documented
provider/producer mapping, followed by those real captures through this same
offline evaluator.

## D19 — Reference audit and 1.1.0 acceptance

**Authority:** the user subsequently requested review of Sierra Tau²-bench and
Inspect Scout, execution of the complete process, and closure of evaluator-side
work. Reference research was authorized for this audit; evaluation runtime
remained offline. A reference benchmark's different reward policy does not
override this assignment or the user's accepted diagnostic/outcome decisions.

**Reference selection:** inspect the official Tau² source at a fixed commit and
Scout 0.6.1 at its release commit. Keep exact source links, interpretations and
applicability in [TAU2_REFERENCE_AUDIT.md](TAU2_REFERENCE_AUDIT.md) and
[SCOUT_AUDIT.md](SCOUT_AUDIT.md). Inspecting source is not executing Tau² or a
model judge. Scout is actually installed and exercised as an optional viewer.

**Corrections:** [READINESS_REVIEW.md](READINESS_REVIEW.md) records the reproduced
save/snapshot ordering and stale-publication false passes, path identity rules,
and legitimate publication-failure variant. Each correction has positive and
negative raw-bundle regression controls. Rejected inputs now retain all seven
dimension statuses as unknown, so every per-dimension denominator includes all
requested entries. Reports retain effective case policy, Python version, source
hashes and version 1.1.0; a changed direct-call case policy changes its digest.
The additive output contract remains `partlab.eval/1`.

**Actual producer evidence:** read completed SDK captures without invoking its
agent or modifying the sibling tree. Verify inventory references and hashes;
copy exact bytes only; verify the completion file is unchanged after copying.
The [provenance inventory](../fixtures/producer-provenance.json) identifies source
paths, observed git revision, completion hashes and evidence types. Git HEAD
alone is not treated as a hash of uncommitted producer evidence. Two captures
are real model runs made before this audit; the guard capture is scripted.
They augment the original 16 examples to 19; the original manifest and original
verification records remain available for historical reproduction.

**Outcome interpretation:** the live bracket's repaired state and saved output
pass. The live flange's bounded search did not find a repair; its truthful report
passes. The scripted guard capture is evidence of safe refusal, not an invented
model run or repair. No benchmark-wide success rate is inferred from these
purposefully selected examples, and no model calls are made by re-evaluation.

**Optional Scout:** keep its third-party packages in a separate pinned environment.
Import explicit derived report projections, preserving original evidence labels,
all dimensions, checks and raw references. Use a deterministic scanner with
active message loading; reopen persisted results and compare every expected
row and reference. Keep rejected inputs, test malformed import rejection,
repeat the projection, and execute with networking disabled. A successful
projection proves faithful display of grades; it does not independently prove
the engineering grades. Detailed SC01–SC12 decisions are in the Scout audit.

**Acceptance discipline:** changes invalidate earlier source-specific checks.
An intermediate host run overlapped the final publication-failure correction;
it and the concurrent malformed sweep were stopped and are not acceptance
evidence. Host, Docker and malformed-input checks were restarted after source
freeze. Harbor's unchanged infrastructure task was rerun independently. The
final proof locations and counts are in
[REFERENCE_ACCEPTANCE.md](REFERENCE_ACCEPTANCE.md).

The first Scout persistence attempt exposed an upstream 0.6.1 DataFrame behavior:
expanded rows flattened metadata into separate columns. The bridge rejected
that mismatch instead of declaring success, then switched to the public nested
transcript-result reader. SC13 records this correction. Final acceptance checks
19 transcripts, 133 independent dimension results and 4,507 raw-reference
occurrences, including repeat and offline Docker parity; a separate rejected
input scan retains both rejections and all 21 dimension results.

**Ownership boundary:** this release closes known evaluator-side work for the
supported PartLab profile. The current SDK's vendored evaluator does not update
automatically; choosing this release is an SDK integration action. New providers
must produce the supported evidence or supply a trusted adapter and run
conformance. Capturing a different provider, selecting credentials/models,
recording the exercise and assembling its combined submission are not hidden
evaluator implementation tasks. No sibling files were edited.

## D20 — Keep the five assignment requirements directly reviewable

The user reiterated the core Part 2 rubric: schema portability, principled
tuning, readable actionable reports, defensible scores, and a deliberately
flawed trace with specific detection. The concise
[rubric checklist](EVAL_RUBRIC.md) now links each requirement to implementation,
evidence and a short reproducible command. This is the primary review path for
those five requirements; the longer reference audits provide supporting detail.

The check found two evidence gaps in otherwise working extension points: the
extra-case regression used already-configured `housing_v1`, and the registered
adapter regression delegated the original layout unchanged. Two additional
regressions explicitly exercise an unseen trusted case and a different persisted
capture representation. They strengthen what the tests demonstrate without
rewriting grading logic or claiming compatibility with a future provider before
its adapter exists. Synthetic inputs retain their source labels.

Task thresholds and manufacturing limits remain trusted case data. Optional
efficiency budgets and resource limits remain named configuration. Single-
parameter changes, fresh solves and truthful evidence are correctness rules,
not arbitrary score weights. The reproducible flawed trace remains a complete,
hash-valid capture with a stale solve: `STALE_SOLVE` is the specific failure,
with linked evidence and a corrective action. Unrelated manufacturing and
multiple-parameter defects are explicitly excluded from that demonstration.
