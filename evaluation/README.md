# Offline PartLab evaluation

The evaluator reconstructs executed state from persisted raw evidence and reports
capture integrity, compliance, final correctness, delivery, reporting accuracy,
repair achievement and efficiency separately. It uses Python 3.12's standard
library and makes no model or network calls.

From the repository root:

```sh
python3 evaluation/scripts/verify.py --output-dir /tmp/partlab-eval-check-001
```

Choose a new output directory. This runs the complete evaluator regression suite
and asserts the expected outcomes of 19 supplied bundles. Two bundles are captured
live agent runs, three are scripted checks, and fourteen are explicitly synthetic.

- [Runbook and configurable policies](EVAL_RUN.md)
- [Five acceptance requirements and reproducible failure detection](docs/EVAL_RUBRIC.md)
- [Capture contract](docs/EVAL_IMPLEMENTATION_CONTRACT.md) and [new harness integration](docs/API_INTEGRATION.md)
- [Implementation decisions](docs/EVAL_DECISIONS.md), [scoring rationale](docs/EVAL_CHECK_DECISIONS.md), and [state semantics](docs/EVAL_STATE_DECISIONS.md)
- [Executed reference acceptance](docs/REFERENCE_ACCEPTANCE.md) and [readable example reports](reports/reference-audit/REPORTS.md)
- [Optional Scout results viewer](scout_setup/README.md) and [Harbor/Docker smoke task](docs/HARBOR_SETUP.md)
- [Consolidation decisions and provenance](../docs/INTEGRATION_DECISIONS.md)

Scout displays the evaluator's findings; it is not an independent engineering
judge. Harbor verifies the offline execution environment with an oracle and a
no-op control. Neither optional package is needed to grade traces.

`fixtures/` retains immutable evidence, including deliberate defects. `reports/`
and integration verification directories retain source-pinned historical results;
their original paths, hashes and test counts describe the executions that produced
them. Current combined-repository checks live under the root `reports/` directory.
Early planning documents are retained as labelled history, not unfinished work.

The supplied binary and trusted original parts are shared at the repository root.
The original assignment is preserved in [TASK.md](../TASK.md).
