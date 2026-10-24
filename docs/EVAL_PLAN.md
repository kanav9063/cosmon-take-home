# Offline evaluation plan

Status: **preparation and proposed design**, October 23, 2026 (ET). No evaluator,
live agent run, or recorded exercise has been completed in this track. The root
[README](../README.md) remains authoritative and unchanged. The
[Notion planning page](https://app.notion.com/p/4026333fbd2f807badd4d8f1d1c6fe6f)
was read without editing its notes or screenshots. Its later core-first decision
supersedes earlier suggestions to require Docker, Harbor, ATIF, and Scout.

The subsequent [Terminal-Bench reference audit](BENCHMARK_AUDIT.md) maps all
assignment requirements to evidence and distinguishes working infrastructure
from the core implementation and demonstration still required.

## Scope and decision checkpoint

The first deliverable during the exercise is a small, deterministic offline
evaluator that consumes persisted raw evidence. It must not import the agent's
decision logic or guard implementation, call a model, or run PartLab while
grading. Case data and an agreed interchange contract can be shared; an agent's
claim that its own guard or analysis passed is not independent evaluation.

Accepted decisions: individual named SDK actions; each parameter-search trial
starts from the original baseline; the final repair changes exactly one original
parameter; distinguish demonstrated infeasibility, exhausted search, and
execution failure. Integrations follow the core submission only if time allows.

Kanav also accepted both scoring recommendations during this preparation:

1. Correctly blocked proposals and recovered CLI errors are diagnostics, while
   actual forbidden mutations fail process compliance even if later restored.
2. Report repair achievement separately from reporting accuracy. An honest
   exhausted search is not a successful repair or proof of infeasibility.

These decisions guide this draft. The shared interface is not yet agreed. Do not
implement a competing wire schema: the SDK track owns its initial proposal.
[EVAL_TRACE_REQUIREMENTS.md](EVAL_TRACE_REQUIREMENTS.md) defines required evidence
and the integration checklist. Full implementation follows an explicit contract
review by both tracks; reading a proposal alone does not constitute agreement.

## Prepared workspace

Work only in `/home/ubuntu/work/cosmon-eval`, branch `setup/eval-plan`.

```sh
cd /home/ubuntu/work/cosmon-eval
python3 -m venv .venv
.venv/bin/python --version
.venv/bin/python eval_preparation/check_fixtures.py
```

Python 3.12.3 is the verified runtime. No runtime dependencies are required for
preparation or the proposed core evaluator: `json`, `decimal`, `hashlib`,
`pathlib`, `argparse`, and `unittest` are sufficient. No package download,
credentials, paid inference, Docker, or provider selection is needed here.
The ignored `.venv/` is local; reproduce it rather than committing it.

`eval_preparation/` contains labeled synthetic consumer examples and a packaging
check. Its checker is **not** an evaluator and deliberately does not grade
semantic correctness. Invented SF values test logic, not PartLab physics.
The [test matrix](EVAL_TEST_MATRIX.md) specifies future checks and expected
findings. Preserve the starter `RUN.md` template until actual exercise results
exist; the preparation record is [EVAL_SETUP.md](EVAL_SETUP.md).

## Proposed implementation sequence within the eval half-hour

Before recording, disclose exactly which preparation documents, environment,
and fixtures already exist. Do not retroactively label preparation as exercise
work. The complete exercise remains one hour, roughly 30 minutes per track.

| Minutes | Runnable increment | Verification and narration |
| --- | --- | --- |
| 0–4 | Load one persisted producer bundle through an explicit versioned adapter; retain source references | Print run identity and input completeness; explain unverified evidence |
| 4–10 | Reconstruct state from actual successful CLI actions; detect stale solves | Show a clean run and the schema-valid stale-solve fixture |
| 10–17 | Check original/default load, constraints, final single-parameter difference, SF and artifact | Inspect the saved bytes and cite the supporting solve |
| 17–22 | Emit structured report; distinguish outcome, correctness, integrity, efficiency | Explain a failure with event/call references and corrective action |
| 22–27 | Run bracket_v3 and flange_v1 raw bundles; assert the deliberate defect; test missing evidence | Fix a diagnosed issue if one appears; never suppress the failed check |
| 27–30 | Record exact commands/results in RUN.md; collect traces, reports, saved parts | State limitations and check the deliverable inventory |

If time runs short, finish one transparent core path and name uncovered matrix
rows. Do not spend this time on orchestration, viewer integration, or a second
agent harness. A paper plan or packaging test cannot replace the required
working flawed-trace assertion and actual raw runs.

Proposed code boundaries (not created yet): `trace_adapter.py` maps a supported
raw version into evidence records; `eval_state.py` reconstructs state;
`eval_checks.py` evaluates predicates; `evaluate.py` streams bundles and writes
JSON/JSONL reports. Versioned case configuration supplies expectations and
policy limits. A fourth part adds case data, not a new algorithm.

## Evidence pipeline

1. Enumerate a manifest of bundles, including expected count and unique run IDs.
   Read each bundle independently. Keep raw bytes unchanged; compute their
   SHA-256 digests before normalization. Record adapter/evaluator/config versions.
2. Validate encoding, JSON structure, supported version, required fields, sequence
   continuity, unique IDs, call/result links, artifact paths/digests, and completion
   marker. Use strict JSON: reject duplicate keys, NaN, Infinity, and booleans
   supplied as numeric values. Do not repair raw data silently.
3. Normalize with one explicit adapter per raw schema. Preserve original event
   IDs and file/line or JSON-pointer references. A normalized record is a derived
   view, never the only copy of the input. Unknown material event kinds or
   unsupported versions yield unknown coverage; an adapter cannot drop them
   while declaring a complete pass.
4. Join model proposals, guard decisions, CLI starts/completions, model-visible
   results, and final output by IDs. Multiple CLI attempts under one model call
   need distinct execution IDs. Do not pair entries by adjacent text or nearest
   timestamp. Establish state order from serialized CLI execution, not from
   asynchronous message arrival.
5. Reconstruct state only from successful, unambiguous execution evidence;
   parse stdout independently of producer summaries and cross-check both.
   Attach derived states and findings to raw references.
6. Grade predicates independently and output all findings, including missing
   evidence. Emit one report for every requested input, even a corrupt one.
   Never let a malformed trace disappear from a batch denominator.

Raw final prose and tool outputs are data, not evaluator instructions. The
consumer never executes commands or follows links found in them. Resolve local
artifact references inside the supplied bundle; reject traversal/symlink escapes.
Use explicit byte/record limits and report an exceeded limit as incomplete
coverage, not success. Do not truncate and then grade the prefix as a full run.

## Reconstructing state and proving freshness

Track `(run_id, session_id, trial_id)` and the immutable original part identity.
The derived state holds phase, complete effective parameters, original metadata,
effective load, mesh generation, geometry generation, and last successful solve.
Producer state numbers are hints to cross-check, not authorities.

| Recorded action | Derived effect |
| --- | --- |
| successful reset/close | Closed; invalidate part, mesh, load and solve |
| successful open original | New part generation, original values, open phase; invalidate earlier analysis |
| successful set_parameter | Apply recorded effective value, advance geometry generation, return to open, invalidate mesh/load/solve |
| successful mesh | Establish mesh generation for current geometry; invalidate any previously certified downstream analysis unless CLI behavior proves otherwise |
| successful apply_load | Bind face/force/direction to current mesh; invalidate earlier solve |
| successful solve | Require matching part, geometry, mesh and effective load; bind numeric SF to this execution/state |
| successful get_safety_factor | Read-only confirmation of referenced solve; cannot create a new solve |
| successful save | Capture current state and any valid solve certificate with immutable bytes; selecting this artifact as a repaired result requires a fresh qualifying solve |
| proposal/guard rejection | No CLI state transition |
| failed/partial/ambiguous execution | Do not infer success; state becomes unknown if atomicity or complete post-state cannot establish what happened |

The README guarantees parameter mutation invalidation. Other details, including
mesh settings, repeated load semantics, and failed-action atomicity, must be
verified by the SDK track against the binary before its adapter relies on them.
Default conservatism is documented and tested rather than hidden in a heuristic.
Later full snapshot evidence may re-establish current parameter state but cannot
invent a missing historical solve or erase an earlier violation.

A solve certificate is an evaluator-derived tuple of original identity, full
effective parameters, geometry/mesh generation, complete effective load, solve
execution ID and raw SF. Read-only actions do not invalidate it. Any intervening
mutation invalidates it for the live session, even setting an equal value if the
SDK invalidates on that action. Returning to the same parameter values still
requires fresh analysis. An old numerical SF is not evidence for a new state
merely because it is plausible.

Retain historical certificates for immutable saved artifacts. If safe state A
was solved and saved, later exploration of B does not invalidate saved A. Final
output may explicitly select A with its matching artifact and solve references.
Evaluate the selected artifact's save-time state, not the last live session
state. Conversely, saving B and citing A's solve is stale. An intermediate
unsolved checkpoint save is not itself a false success unless selected or claimed
as the verified repair. Check that the final required output path still contains
the selected artifact bytes; an earlier snapshot alone cannot prove that after
another save overwrites the path.

At each trial boundary, verify restoration from the original source and complete
parameters before trying a different parameter. Never union every explored
parameter into the final single-parameter count. At save/final acceptance compute
the changed-key set against the original, not the last trial or prior command.

## Deterministic hard checks

| Predicate | Sufficient evidence / failure rule |
| --- | --- |
| Part and baseline | Requested part identity matches original captured bytes and successful open; trusted task case matches baseline digest |
| Baseline analysis | Fresh converged initial solve used original geometry and default load; finite initial SF determines whether repair is required |
| Default load | Each solve used to substantiate baseline/final outcome matches original face, force and direction; an incomplete effective direction is unknown |
| Analysis source | Successful converged PartLab solve supports finite SF; a handbook estimate, reasoning text or guard decision cannot substitute |
| Manufacturing | Every actual candidate mutation and final artifact satisfy case limits; forbidden proposal alone is a diagnostic when blocked |
| Trial isolation | New parameter family begins from original baseline; restoration evidence must precede the mutation |
| Single parameter | Repaired final complete parameter map differs in exactly one original key, with no unrelated material/physics/load edits |
| Target and freshness | Full recorded final SF is at least 2.0 and its certificate matches final/saved state |
| Save | Repaired outcome has expected `outputs/<part_name>.json`, successful producing save, captured bytes and digest, matching state and solve summary |
| Final statement | Reported outcome, SF, parameter change, proof/termination reason and artifact references agree with evidence |

A successful process/envelope alone does not establish solver convergence. Use
the pinned CLI's observed convergence field/semantics; explicit nonconvergence
cannot certify baseline or repair, and missing convergence evidence is unknown.

For `flange_v1`, case limits are thickness ≤5.0 mm and hole diameter ≥4.0 mm.
Other unlisted parts do not inherit these limits. Preserve units explicitly.
Do not read the agent's guard return as proof of compliance: recompute the
inequalities from actual accepted values and artifact contents.

Compare saved material, physics, name/revision, default load, feature data and
other original fields too. Establish documented save-format transformations
(e.g. added solve summary) before allowing them. A parameter-controlled derived
feature may legitimately change, but an unexplained strength/material edit
cannot silently count as a single-parameter repair. Unknown serialization
semantics remain unknown until characterized.

For already-safe originals, verify fresh baseline SF ≥2 and reported SF;
repair/save checks are not applicable if no repair is claimed. For a selected or
claimed repaired output, no change or multiple changed keys fails the
single-parameter predicate. Honest unsuccessful outcomes mark this repair
predicate not applicable and record unachieved/unknown repair separately.
Do not demand a save for an honestly reported unsuccessful search. A final
prose statement that contradicts structured output is a finding; free-text
claims that cannot be deterministically extracted must remain explicitly
unverified rather than presumed consistent. Prefer a producer-rendered final
summary from the same structured result while preserving the exact shown text.

## Outcomes, missing evidence, and scoring

Record the agent-declared outcome separately from evaluator-observed outcome:
`already_safe`, `repaired`, `proven_infeasible`, `search_exhausted`,
`execution_failure`, or `unverified`. Do not merge “found no fix” with “no fix
exists.” A finite search over chosen samples is incomplete coverage unless the
task really defines that finite domain.

`proven_infeasible` requires a verifier-supported certificate covering every
permitted single-parameter family and its full allowed domain, with documented
assumptions and source bounds. An unsafely solved endpoint is not a monotonicity
proof. A model's formula or an assumed upper bound is not a certificate. The
starter supplies no complete search ranges, so the core design should normally
report exhausted search rather than promise a proof verifier in 30 minutes.
Unsupported proof formats yield unknown feasibility and fail a definitive
infeasibility claim (`UNSUPPORTED_INFEASIBILITY`); they do not prove feasibility.

Each predicate has exactly one status:

- `pass`: sufficient admissible evidence establishes it.
- `fail`: affirmative evidence contradicts it.
- `unknown`: missing, ambiguous, unsupported or incomplete evidence prevents a decision.
- `not_applicable`: the branch explicitly does not require it, with a reason.

Keep integrity, final correctness, process compliance, reporting accuracy,
achievement, and efficiency separate. No weighted score can allow efficient
failure to outweigh incorrectness. A correctness summary is fail if any required
predicate fails, else unknown if any required predicate is unknown, else pass
when all applicable requirements pass. Exclude not-applicable predicates from
denominators and report their count; an empty set is not automatically a pass.
The summary must name which predicates it aggregates.

Missing or truncated evidence does not prove bad engineering. Emit an integrity
finding and mark dependent checks unknown, while retaining earlier demonstrated
violations. For example, a known illegal mutation remains a fail when the tail
is missing. An orphan result cannot establish what command executed. A missing
CLI result can be a crashed process, not an unsuccessful solver. A missing
terminal marker prevents full-run compliance from passing even if the valid
prefix shows a plausible success.

An exhausted search can have `reporting_accuracy=pass`, `repair_achievement=fail`
(not achieved), `feasibility=unknown`, and compliant attempted trials. Execution
failure similarly need not be a dishonest result. A proven-infeasible case has
no repair artifact requirement. Separating achievement and reporting, and treating
safely recovered incidents as diagnostics, are accepted scoring policy. Exact
wire fields and implementation details still require the shared checkpoint.

## Numerical policy and configurable efficiency signals

Hard policies come from versioned task cases: `sf_target=2.0`, per-part limits,
expected default load/source part, single changed key, output path. They cannot
be weakened to improve scores. Use decimal values parsed directly from JSON
lexemes for comparisons: 5 equals 5.0, but 5.0001 exceeds 5. No generic epsilon
may turn SF 1.9999 into passing 2.0 or hole diameter 3.9999 into passing 4.0.
If the CLI exposes only rounded SF, record that precision and limit the claim to
the recorded SDK result; do not assert higher physical precision. Display-text
rounding is evaluated separately and must not change the target test.

Keep display precision/tolerance unset until producer formatting is verified.
Numerical comparison of parameters/load is exact in their declared units unless
an agreed, independently justified serialization rule requires otherwise. Reject
nonfinite/invalid numeric types before comparisons.

Efficiency metrics: model/tool/CLI counts, solve count, failed/retried operations,
model-visible result bytes, total raw bytes, repeated identical read-only calls
within the same state, duration, and token/cost usage when recorded. Missing
usage is unknown, never zero. Exact hidden reasoning is neither required nor
available; capture only provider-exposed messages/items and usage.

Recommended initial thresholds are **disabled**, with measurements reported.
During the exercise set named warning budgets from an explicit run budget or
observed unnecessary repetition, documenting rationale and config hash. Search
budget exhaustion is a termination fact, not proof of infeasibility. A larger
legitimate search is not automatically worse because it has more solves. A
verbose diagnostic read after an error can be useful. Do not invent thresholds
like “10 calls is bad” without a baseline. Changing efficiency config must not
change hard verdicts. Input byte/record limits are resource protection settings,
not performance scores; exceeding them produces an incomplete report.

## Actionable structured report example

Illustrative output only; **not generated by an implemented evaluator**. In the
future each evidence entry includes the raw file/pointer/line plus its digest.

```json
{
  "report_version": "proposal/0",
  "run_id": "synthetic-stale",
  "source_kind": "synthetic",
  "input_status": "complete",
  "declared_outcome": "repaired",
  "observed_outcome": "unverified",
  "summary": {
    "final_correctness": "fail",
    "reporting_accuracy": "fail",
    "repair_achievement": "unknown"
  },
  "findings": [{
    "code": "STALE_SOLVE",
    "status": "fail",
    "check": "fresh_final_analysis",
    "message": "A successful parameter mutation follows the cited solve.",
    "evidence": [
      {"event_id": "solve-result", "call_id": "solve-1"},
      {"event_id": "later-mutation", "call_id": "set-2"},
      {"event_id": "final-output"}
    ],
    "expected": "A successful solve after the final geometry change at the original default load",
    "observed": "Final output cites solve-1 from the prior geometry",
    "action": "Mesh the current geometry, apply the default load, solve, and save the verified state."
  }],
  "efficiency": {"warning_thresholds": "disabled", "model_tokens": null},
  "limitations": ["Offline evidence consistency; independent PartLab replay was not performed"]
}
```

Actual reports must also include schema/adapter/evaluator/config versions and
digests, part ID, required-check inventory with every status, input event counts,
artifact hashes, diagnostic severities, and elapsed evaluation time. Do not label
an intended expected finding as an observed one in demonstration output.

## Hundreds of traces and harness portability

Start with an explicit file manifest and streaming JSONL output; no database,
worker queue, web service, or orchestration framework is required. Use a
single-pass per-run reconstruction and bounded call-ID/state maps. Keep large
raw payloads on disk and cite offsets. Process bundles one at a time; optionally
parallelize independent offline bundles after correctness is established.
Never share mutable PartLab sessions because this evaluator never runs PartLab.

Sort output deterministically by manifest/run ID; cache only by all input and
artifact digests plus adapter/evaluator/config versions. Duplicate run IDs with
different bytes are conflicts, not replacements. Emit batch totals satisfying
`requested = evaluated + explicitly_rejected`, with known pass/fail/unknown
counts, rejection reasons, and coverage counts. Test hundreds of replicated
synthetic inputs with distinct IDs and one malformed bundle to verify isolation
and complete accounting; label such scale tests synthetic.

Re-evaluating identical evidence and reordering independent input bundles must
preserve semantic findings by run ID (excluding evaluation timestamps/timing).
Never reorder events within a run to obtain a passing result.

A second harness changes its raw-to-evidence adapter. The same canonical
fixtures must yield identical hard findings; optional metadata may remain
unknown. Do not fabricate missing execution evidence to make a message-only
export look complete. Keep source provenance through every conversion.

## Evidence limits and optional replay

Offline evaluation verifies consistency and compliance of the recorded history,
assuming capture is authentic and the trusted original/case is correct. Hashes
detect mismatches relative to recorded digests; they do not authenticate a
fabricated producer or prove an external process ran. Synthetic examples prove
neither model behavior nor PartLab outcomes.

Independent SDK replay is a separate, explicit verification mode using the
pinned binary digest, pristine part bytes, exact accepted parameter change,
mesh settings and original load in an isolated fresh directory. Compare the new
solve and saved part with the recorded certificate; preserve new evidence with
its own run ID. It can corroborate the final configuration's SDK outcome, not
prove the historical model's decisions or exhaust all possible repairs. PartLab
is a fake simulator; neither mode establishes real-world engineering safety.

## Conditional integrations, verified from official sources

No integration package was installed during the initial preparation. Kanav later
explicitly requested Harbor setup; see [HARBOR_SETUP.md](HARBOR_SETUP.md) for its
separate environment and infrastructure verification. This does not implement
the planned evaluator or establish the producer contract. The following remain
integration design notes:

- Scout documents ATIF ingestion via `inspect_scout.sources.atif` and an
  additional `harbor>=0.6.0` dependency requiring Python ≥3.12. It also accepts
  programmatically constructed transcripts. Import time filters use file mtime,
  not the event run time; do not use them as the authoritative run manifest.
  [Official importing documentation](https://meridianlabs-ai.github.io/inspect_scout/db_importing.html#harbor).
- Harbor documents ATIF messages, calls, observations and metrics, a trajectory
  validator, and extension metadata via `extra`. The current docs describe
  ATIF-v1.7, but any integration must pin a tested version. Keep PartLab state,
  guard/execution distinction, raw links and artifact references in supported
  extension fields; ATIF alone does not establish those semantics.
  [Official ATIF documentation](https://docs.harborframework.com/agents/atif).
- The documented Scout importer source includes warn-and-skip handling for
  malformed inputs. Validate before import and reconcile expected versus
  imported run IDs/counts; viewer ingestion success is not evidence completeness.
  [Official importer source](https://github.com/meridianlabs-ai/inspect_scout/blob/bef39729ae3a66084571cac3523e942d3feae561/src/inspect_scout/sources/_atif/transcripts.py).

Integrate only after the core evaluator works on both actual traces, detects the
deliberate semantic defect, and produces a reproducible report. Exporting to a
viewer must not replace the immutable raw source or change hard verdicts.
