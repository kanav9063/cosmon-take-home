# Evaluation preparation record

Prepared October 23, 2026 (ET), in `/home/ubuntu/work/cosmon-eval` on
`setup/eval-plan`, starting from `20b46cd`.

This record describes the initial preparation. Later, Kanav explicitly requested
Harbor setup; its separate environment and infrastructure checks are documented
in [HARBOR_SETUP.md](HARBOR_SETUP.md). The core `.venv/` remains dependency-free.

This is preparation for the narrated one-hour exercise. No evaluator, model run,
actual raw agent trace, repaired PartLab output, or exercise recording was made
here. The starter `RUN.md` is still a submission template. Its actual agent/eval
commands and results must be filled during the exercise.

## Reproduce the preparation check

```sh
cd /home/ubuntu/work/cosmon-eval
python3 -m venv .venv
.venv/bin/python --version
.venv/bin/python eval_preparation/check_fixtures.py
```

The verified interpreter is Python 3.12.3. The environment contains pip 24.0 and
no third-party runtime packages; no installation from the network was needed.
`agents`, `harbor`, and `inspect_scout` are absent from this isolated environment.
There are zero runtime dependencies to lock for this preparation. Use the same
Python release for exact environment reproduction; the checker is standard-library
Python. `.venv/` is ignored by the existing repository rules.

Observed packaging output:

```jsonl
{"calls":5,"events":11,"fixture_id":"already_safe","packaging":"pass"}
{"calls":5,"events":13,"fixture_id":"guard_rejected","packaging":"pass"}
{"calls":11,"events":25,"fixture_id":"repaired","packaging":"pass"}
{"calls":12,"events":29,"fixture_id":"stale_solve","packaging":"pass"}
```

All four fixtures are explicitly synthetic. The stale example **passing packaging
is expected**: the checker verifies structure, references and digests, not solve
freshness. Future evaluation must flag `STALE_SOLVE`; that detection has not yet
been implemented or demonstrated. Temporary corrupted-digest, nonfinite-number,
and orphan-call copies were rejected by the packaging checker. These are checks
of preparation data, not the assignment's agent non-happy-path demonstration.

The original snapshots embedded in the fixtures were compared with their source
`parts/*.json` and matched semantically. Fixture snapshot digests use documented
canonical JSON; they are distinct from hashes of original on-disk bytes. Actual
producer capture must preserve and hash the original bytes too.

## Other checks actually performed

- Read unchanged root README, setup notes and requirements; inspected all six
  original part definitions. Read the Notion planning page and shared-memory
  facts without editing them or their screenshots.
- Verified clean starting branch and private Git remote identity. Created only
  this track's environment and preparation files. Did not edit either sibling
  clone, merge branches, push, or call a model/provider API.
- Ran top-level `./partlab --help`. The read-only audit also tried command-specific
  `--help`; the CLI does not consistently support it and returned argument or
  no-open-part errors. No successful state-changing PartLab workflow ran here.
- Confirmed the binary SHA-256 remains
  `9b202e1ba07861f52f12005108e81815ef14d92f2db3ba322fc51422746ab183`.
- Checked original README, binary, all six parts, existing setup/requirements,
  and RUN.md against the starting Git tree. They remain unchanged.
- Verified optional integration capabilities from official Harbor/Scout
  documentation and Scout importer source; references and limitations are in
  [EVAL_PLAN.md](EVAL_PLAN.md). These frameworks were not installed or exercised.

## Deliverables and remaining checkpoint

- [EVAL_PLAN.md](EVAL_PLAN.md): sequence, state model, check/status/report design,
  numerical policy, scaling and evidence limits.
- [EVAL_TRACE_REQUIREMENTS.md](EVAL_TRACE_REQUIREMENTS.md): producer evidence
  needs and explicit shared-contract review checklist.
- [EVAL_TEST_MATRIX.md](EVAL_TEST_MATRIX.md): 43 planned semantic/integrity cases
  (including the convergence case added during the benchmark reference audit),
  plus boundary, isolation and batch checks; none run by a semantic evaluator yet.
- [Synthetic fixtures](../eval_preparation/README.md) and their packaging checker.

Kanav accepted safely recovered incidents as diagnostics and separate repair
achievement/reporting accuracy. Remaining integration work is to reconcile the
SDK-owned schema, evidence coverage, actual CLI/save behavior, and final-output
fields, and record both tracks' acknowledgment of one revision. The provisional
consumer fixture format must not silently become the producer contract. Full
agent/evaluator implementation remains exercise work. Model choice and live-run
budgets belong to the SDK planning track and do not block this offline setup.
