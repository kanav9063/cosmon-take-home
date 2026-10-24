# Reference audit and evaluator acceptance

This follow-up answers the request to inspect Sierra's Tau² benchmark and
Inspect Scout, close evaluator-side gaps, execute the complete process, and
leave only provider/agent responsibilities outside this repository. It builds
on the original implementation rather than treating its passing tests as a
substitute for independent review.

## External reference review

- [Tau² audit](TAU2_REFERENCE_AUDIT.md): official source is pinned at
  `cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2`. The review covers required reward
  components, state versus action matching, failed/rejected actions,
  communication, interruption, repeated trials and input accounting. Four
  additional integration tests exercise the applicable lessons. Tau² itself
  was inspected as a reference, not executed as a benchmark or model judge.
- [Scout audit](SCOUT_AUDIT.md): the optional integration pins Inspect Scout
  `0.6.1`. It imports clearly labeled derived evaluator reports, scans them
  deterministically, reopens persisted scan results, and checks every input
  and dimension. It does not claim report projections are original chats or
  substitute Scout ingestion for the raw-evidence grader.
- [Harbor setup](HARBOR_SETUP.md): Docker orchestration, separate verification,
  explicit artifact transfer and oracle/no-op isolation checks are retained.
  Core evaluation remains standard-library Python and works without Harbor
  or Scout installed. Runtime verification keeps networking disabled.

## Changes resulting from the audit

### R01 — Close save/snapshot/publication causal gaps

Independent review reproduced a false pass where an artifact's snapshot event
appeared before the save that supposedly produced it. A second false pass
selected an earlier published artifact after a later different save overwrote
the same destination. Capture hashes alone did not prevent either error.

The adapter now validates save/solve/snapshot/publication links and ordering.
A separate artifact-provenance predicate makes the selected result's causal
requirement visible in reports. Delivery considers subsequent writes and
their effects, rather than treating the last publication event as conclusive
forever. Legitimate historical selection, separately published destinations,
same-byte writes, failed writes, and re-publication have explicit controls.
See [independent review](READINESS_REVIEW.md) for decisions and exact tests.

The same review then exercised the actual SDK's failure event: a publication
can fail with an error and no destination-byte snapshot. That is complete
failure evidence when the error is recorded; it is not proof of successful
delivery. Seven additional controls cover missing error information, absent
success bytes, optional partial-byte validation, recovery and earlier delivery
evidence. A safely recovered failure stays diagnostic, while a truthful final
execution failure can pass reporting without being credited as a repair.

### R02 — Preserve rejected inputs in every denominator

Previously the overall batch equation retained rejected inputs, but rejected
reports contained only a capture dimension. Consumers counting other dimension
statuses could omit these inputs. Rejected reports now include every standard
dimension as unknown. The 200-input regression asserts that each dimension's
counts sum to all 200 requested inputs as well as comparing both orderings.

This does not turn rejection into a fabricated engineering failure or grant
credit. It explicitly preserves uncertainty and the correct denominator.
There is still no scalar average or pass-at-k estimate without a declared
repeated-trial design and real independent model runs.

### R03 — Record effective policy and installed code

Reports now carry the concrete case policy and evaluator source hashes plus
the Python runtime. A direct `evaluate_one` caller changing the target can no
longer produce the same configuration digest merely because it omitted a
case-file digest. Rejected reports also retain code, adapter and policy
provenance. Version 1.1.0 identifies these strengthened semantics; the additive
report schema remains `partlab.eval/1`.

### R04 — Test the actual producer, beyond synthetic interface examples

The sibling SDK workspace now contains completed live bracket and flange
captures and a scripted guard-check capture. We copied only the completed
inventory-verified files, without modifying the SDK workspace or rewriting
source evidence. Completion bytes were checked again after copying to avoid
taking a snapshot while the capture changed.

The resulting 19-input manifest includes 14 synthetic cases, three scripted
captures and two existing live captures. The full acceptance command grades
them together. The live bracket result is a verified repair (SF 1.428 to 3.072).
The live flange result honestly reports bounded search exhaustion (best SF 0.839),
which passes reporting while failing to achieve a repair. Those are two
different expected task outcomes, not one averaged score.

### R05 — Execute optional Scout without adding a judge dependency

The core grader remains responsible for engineering correctness. Scout is an
optional view and scan of its verified reports. Every imported record preserves
its input identity, original evidence kind, report digest, individual checks,
raw evidence references and dimension memberships. Unknown/rejected evidence
is retained; malformed batches are rejected explicitly rather than skipped.

The optional environment has its own pinned dependency lock and ignored local
database/scan output. Compact execution records remain tracked. The scanner
does not ask an LLM to reinterpret deterministic checks or send transcripts to
an external service. The corresponding audit documents what was actually run.

## Responsibilities after acceptance

For the existing PartLab profile there is no known open evaluator implementation
item. A new provider or harness must emit the documented raw evidence (or ship
its explicit trusted adapter) and run the existing acceptance command. Choosing
models, credentials, model-run budgets, scheduling live rollouts and producing
the human recording belong to the agent/API exercise.

Unsupported arbitrary prose interpretation and global infeasibility proofs
remain explicit scope boundaries, with refusal/unknown behavior tested. They
are not silently assumed correct and are not hidden pending implementation.
Swapping the CAD/CAE domain itself requires new domain semantics; swapping a
model API does not change the engineering checks.

## Executed acceptance evidence

Original v1 verification artifacts remain preserved with their original source
hashes; they are not relabeled as proof for later code. Current records are:

| Check | Result | Evidence |
| --- | --- | --- |
| Full host regression suite | 154 tests passed; all 19 expected reports asserted | [Verification](../reports/reference-audit/verification.json), [console](../reports/reference-audit-host.log), [readable report index](../reports/reference-audit/REPORTS.md) |
| Full Docker regression suite | 154 tests and 19 reports passed with `--network none`, read-only source and no source changes during execution | [Source-pinned record](../reports/reference-audit-docker.json), [console](../reports/reference-audit-docker.log) |
| Batch accounting and repeatability | 200 inputs graded twice in reverse order; 197 evaluated and three rejected; every dimension retains denominator 200; report bytes match | `test_200_mixed_inputs_preserve_denominator_and_exact_permutation_results` in the full suite |
| Malformed-input robustness | 1,710 deterministic single-field substitutions; zero uncaught exceptions | [Sweep record](../reports/reference-audit-malformed.json) |
| Real producer interoperability | Two existing live captures and one scripted guard capture pass expected independent dimensions; copied source bytes remain identical | [Capture provenance](../fixtures/producer-provenance.json), live/guard rows in the report index |
| Harbor orchestration and isolation | Two oracle rewards 1; no-op reward 0; no execution errors; separate verifier, explicit transfer and no-network policies verified | [Fresh Harbor record](../harbor_setup/verification-post-audit.json) |
| Optional Scout import and persisted scan | 17 contract tests passed; 19 transcripts, 133 dimension results and 4,507 raw-reference occurrences verified; no model or network calls | [Acceptance](../scout_setup/verification/acceptance.json), [tests](../scout_setup/verification/tests.txt), [installation](../scout_setup/verification/installation.json) |
| Scout repeatability and rejected-input controls | Repeat host and offline Docker scans agree; separate three-input scan retains two rejected inputs and all 21 dimension results | [Repeatability](../scout_setup/verification/repeatability.json), [rejected inputs](../scout_setup/verification/rejected.json) |

Reproduction commands, from this repository root, use new destination paths:

```sh
python3 scripts/verify.py --output-dir /tmp/partlab-eval-verification
python3 scripts/check_malformed_inputs.py --output /tmp/partlab-malformed.json
.venv-harbor/bin/python harbor_setup/check.py
.venv-scout/bin/python -m unittest scout_setup.test_bridge -v
.venv-scout/bin/python -m scout_setup.bridge \
  --reports reports/reference-audit --output-dir scout_setup/results/new-review
```

The exact offline Docker command is retained in its machine-readable record
and [EVAL_RUN.md](../EVAL_RUN.md). The optional Scout dependency installation
and reproduction details are in its [runbook](../scout_setup/README.md).

The intentionally printed `EVALUATOR ERROR` and injected internal-error message
in the unit-test console are expected negative controls. The enclosing suite
passed. Neither those diagnostics nor a failed repair is treated as a failure
to execute the verification process.

The [combined acceptance receipt](../reports/reference-audit-acceptance.json)
binds these records to current source hashes, the exact Scout input reports,
unchanged producer snapshots and unchanged assignment files. Documentation
links, Python syntax and Git whitespace checks also passed. No new model/API
inference was performed during this acceptance work.
