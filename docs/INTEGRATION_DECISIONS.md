# Consolidating the submission on main

## Scope and source history

The submission combines the agent implementation and presentation branch with
the complete evaluator evidence from `cadf11e`. The evaluator was developed
independently and already used by the agent at version 1.1.0 (`b60473c`).
`cadf11e` adds two portability regressions, rubric documentation and verification
receipts; it does not change the grading rules. The consolidated branch preserves
both development histories and keeps one implementation of the evaluator.

## One current layout

The agent, supplied PartLab executable, trusted original parts, architecture
images, live captures and primary submission documents remain at the repository
root. The evaluator, its tests, synthetic and scripted fixtures, audits, decision
records, optional Scout bridge and Harbor task are under `evaluation/`.

The evaluator's trusted part paths and test fixture lookups now address the
shared root `parts/` directory. The fixture-generation and Harbor launch scripts
also locate the root executable. These are location changes, not weaker identity
checks: configured SHA-256 values still pin the original part bytes and binary.
The relative-path change alters the case configuration digest; new reports record
that digest. Historical receipts retain their original digest and source paths.

## Evidence preservation

Raw captures, fixture manifests, completion inventories and historical verification
receipts are copied byte-for-byte from their committed source. They are not edited
to disguise the old layout or to increase historical test counts. The 154-test
acceptance run remains a 154-test run; the enlarged suite is verified separately.
Current packaging provenance identifies the original commit and each relocated
or edited implementation file.

The intentionally flawed capture remains flawed. `STALE_SOLVE` must fail while
capture integrity passes. A rejected manufacturing proposal or recovered command
error remains diagnostic when safely recovered; an executed forbidden mutation
fails compliance. Honest search exhaustion can pass reporting while failing repair
achievement. None of these outcomes is replaced with one averaged success score.

## Cleanup boundaries

Only committed source and inspectable evidence are imported. Virtual environments,
credentials, local PartLab sessions, Scout databases, Harbor job directories,
recordings and build caches are excluded. Git stores Docker build and task
source, not image layers. No project image is published to a registry; fresh
setup needs downloaded or pre-cached dependencies, while runtime checks are offline. The old simplified `eval_preparation/`
prototype is preserved in source history rather than added to the submission's
current runnable surface. Detailed design and decision documents remain available;
early plans are explicitly labelled as historical.

The active agent and presentation checkouts are not reset or cleaned. Consolidation
uses an isolated worktree and incorporates the latest committed agent results
before publishing `main`. A normal fast-forward push prevents overwriting an
intervening remote update.

## Verification and limits

The combined tree is checked using offline evaluator regressions, the 19 expected
example outcomes, the agent suite, negative trace checks, and relocated optional
integration checks. Fresh receipts live in `reports/main-integration-20261024/`.
No new paid model run is required for this packaging work. Existing model and
harness results retain their original scope and limitations.

The human recording link remains a submission item unless supplied separately.
Neither a clean branch nor successful tests establish that a recording exists.
