# Combined-repository verification

All checks below passed from the consolidated layout. No model API calls were
made during this verification. [verification.json](verification.json) pins the
tested source files and supporting receipts.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Agent suite, including Anthropic ToolRunner | 22 tests passed | [Console](agent-tests.log) |
| Evaluator suite and expected cases | 156 tests; 19 cases passed | [Receipt](evaluator/verification.json), [readable reports](evaluator/REPORTS.md), [console](evaluator-host.log) |
| Evaluator in Docker | Same 156 tests and 19 cases; identical source hashes and expected outcomes; network disabled, source read-only | [Receipt](docker/evaluator/verification.json), [invocation](docker-execution.json), [console](docker-evaluator.log) |
| Scout | 17 contract tests; 19 transcripts and 133 dimension results | [Tests](scout-tests.log), [scan verification](scout.json) |
| Harbor | Two oracle rewards 1; no-op reward 0; separate verifier; runtime networking disabled | [Receipt](harbor.json), [console](harbor.log), [copied trial and verifier reports](harbor-details/manifest.json) |
| Invalid flange proposal | All 10 assertions passed; 5.5 mm rejected before CLI dispatch with state unchanged | [Receipt](guard/verification.json) |
| Deliberately flawed and interrupted captures | All 8 assertions passed; stale solve detected despite valid capture hashes; interrupted capture remains incomplete | [Receipt](agent-evaluation/verification.json) |
| Both harnesses' original captures | Two OpenAI and two Anthropic captures passed their continuity and artifact audits | [OpenAI](capture-audit.json), [Anthropic](native-capture.json) |
| Saved benchmark and native runs | All 12 reports retain their original dimension statuses and findings | [Replay parity](replay-parity.json) |

A passing verification does not turn every agent run into a successful repair.
The flange remains an honestly reported bounded search without a repair. The two
malformed benchmark final messages remain flagged. Scout displays those separate
outcomes; it is not an independent judge.

Historical 154-test receipts under `evaluation/reports/` and the earlier SDK
submission directories describe earlier executions and have not been rewritten.
The new 156-test suite includes the unseen-case and foreign-layout adapter proofs.

The host evaluator reports were generated in a temporary output directory and
moved here after completion. Their console is retained with its final newline
normalized; report and receipt bytes are unchanged. Docker output was written
directly here. Local Scout databases and complete Harbor working environments
remain ignored; their compact receipts and the Harbor JSON reports are included.

Reproduction commands are in [RUN.md](../../RUN.md), the
[evaluator runbook](../../evaluation/EVAL_RUN.md),
[Scout setup](../../evaluation/scout_setup/README.md), and
[Harbor setup](../../evaluation/docs/HARBOR_SETUP.md). Use fresh output paths.

The repository contains Docker build source and task definitions. It does not
publish a prebuilt project image to a registry. Initial setup requires downloaded
or pre-cached dependencies; the verified task runtime is offline.
