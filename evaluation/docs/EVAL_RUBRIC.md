# The five evaluation acceptance requirements

These are the core Part 2 requirements from the assignment. The evaluator's
acceptance evidence must address each one directly.

| Requirement | Implemented behavior | Inspectable evidence |
| --- | --- | --- |
| Generalize to another case or harness | Trusted case data supplies original identity, parameters, default load, target, constraints and output path. A registered adapter converts persisted capture into the same internal records; reconstruction and scoring stay unchanged. | [Case configuration](../eval_cases.json), [capture contract](EVAL_IMPLEMENTATION_CONTRACT.md), [adapter integration](API_INTEGRATION.md), [unseen-case and foreign-layout regressions](../tests/test_rubric.py) |
| Principled, tunable heuristics | Engineering limits come from the trusted task configuration. Optional warning budgets cover measured efficiency; read limits control resource consumption. Reports retain applied configuration and its digest. | [Runbook and configuration examples](../EVAL_RUN.md), [policy validation and reporting](../evaluate.py), `test_warning_budgets_are_explicit_and_do_not_change_correctness` |
| Readable, actionable report | A compact index shows each outcome dimension. Per-check findings identify the check, subject, status, explanation, raw evidence and corrective action; expected/observed values appear when available. Rejected inputs retain their rejection reason. Scout optionally displays the same checks and evidence. | [Report index](../reports/reference-audit/REPORTS.md), [specific stale-solve report](../reports/reference-audit/report-stale_solve.json), [Scout view](../scout_setup/README.md) |
| Defensible scoring | Repair, reporting, compliance, final correctness, delivery and capture are separate. Observed violations fail; missing evidence is unknown; inapplicable obligations are explicit. Recovered errors remain diagnostic, and an honest exhausted search can report accurately without achieving a repair. | [Scoring decisions and rejected alternatives](EVAL_CHECK_DECISIONS.md), [implementation decisions](EVAL_DECISIONS.md), outcome and recovery regressions |
| Deliberately flawed trace with specific detection | A synthetic, hash-valid capture mutates geometry after its cited solve. The grader flags `STALE_SOLVE` while capture integrity passes. Its mutation stays within the manufacturing/single-parameter rules, so those unrelated defects do not explain the failure. | [Raw flawed trace](../fixtures/examples/stale_solve/events.jsonl), [valid control](../fixtures/examples/repaired/events.jsonl), reproducible assertion below |

The fixed SF 2.0 and flange bounds are explicit assignment requirements, not
heuristic guesses. They live in trusted case data and cannot be weakened by the
trace. There is no hidden weighted success score or rounding tolerance that
turns a below-target result into a pass. Optional diagnostic budgets can be
tuned without changing engineering correctness.

A new harness still needs a capture adapter. The portability guarantee is that
it does not require rewriting the grader's state model or scoring. A different
CAD/CAE tool with different physical or state semantics requires its own profile.
The additional portability test fixtures are explicitly synthetic; they do not
claim to be new model runs or measured solver results.

The unseen-case test supplies `unseen_fixture_v7`, parameter `web_depth_mm`,
default load `face_attachment` / 1735 N / `+X`, target SF 3, and bounds [3, 4.25].
It accepts exact equality and rejects both a below-target solve and an
out-of-bounds mutation. The harness test uses one `capture.json` with renamed
timeline fields and embedded raw documents; its test-local adapter preserves
both healthy grades and stale-solve failures, with references back to that file.

## Reproduce the specific flawed-trace detection

From the combined repository’s `evaluation/` directory, with Python 3.12 and no additional packages:

```sh
python3 - <<'PY'
from evaluate import evaluate_one, load_cases

cases, _ = load_cases()
report = evaluate_one("fixtures/examples/stale_solve", cases["bracket_v3"])
finding = next(f for f in report["findings"] if f["code"] == "STALE_SOLVE")
assert report["summary"]["capture_integrity"]["status"] == "pass"
assert finding["status"] == "fail" and len(finding["refs"]) >= 3
assert not {"MANUFACTURING_VIOLATION", "SINGLE_PARAMETER_VIOLATION"} & {
    f["code"] for f in report["findings"]
}
print(finding["code"], finding["status"])
print(finding["action"])
PY
```

Observed output:

```text
STALE_SOLVE fail
Run mesh, default load and a fresh converged solve after the last invalidation, then save that state.
```

The report also identifies the supporting raw evidence. It can contain related
downstream findings, such as the unsupported success claim; the assertion does
not hide those consequences or mistake missing bytes for the intended defect.

## Focused requirement checks

```sh
PYTHONPATH=tests python3 -m unittest -v \
  test_rubric \
  test_pipeline.PipelineTests.test_added_case_uses_data_including_non_mounting_default \
  test_pipeline.PipelineTests.test_explicit_api_adapter_seam_preserves_grade \
  test_pipeline.PipelineTests.test_warning_budgets_are_explicit_and_do_not_change_correctness \
  test_pipeline.PipelineTests.test_semantic_stale_detected_with_raw_evidence \
  test_pipeline.PipelineTests.test_guard_and_recovery_are_diagnostics \
  test_pipeline.PipelineTests.test_exhaustion_reporting_separate_from_achievement
```

The broader source-pinned acceptance evidence remains in
[REFERENCE_ACCEPTANCE.md](REFERENCE_ACCEPTANCE.md). These targeted portability
checks strengthen its demonstrations without changing grading semantics.

The focused command above passed **8 tests** on the host and in the pinned Docker
image with networking disabled and source read-only. See the
[verification receipt](../reports/rubric-verification.json),
[host output](../reports/rubric-host.txt) and
[Docker output](../reports/rubric-docker.txt). The two new tests supplement the
previous full 154-test run; these receipts do not relabel that historical run as
a 156-test execution. Grading source hashes remain unchanged.
