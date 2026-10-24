# Benchmark results and evidence

Five models ran both assigned tasks (`bracket_v3` and `flange_v1`), for ten live runs using the same harness. All five bracket repairs were verified. Three flange runs returned valid bounded no-repair reports; Haiku and DeepSeek failed the required final JSON format. No flange repair was found.

All ten raw captures passed the separate message/tool continuity and file-hash audit. The two final-format failures remain unverified in the independent evaluator; intact capture bytes do not imply a successful task.

- [Detailed comparison, timing, tokens and cost](comparison.md)
- [Machine-readable comparison](comparison.json)
- [Verification receipt](verification.json) and [raw-capture audit](capture-audit.json)
- [Runner results](results.json) and [exact benchmark configuration](manifest.json)

| Model | Task | Result | Trace events | Final model reply | Independent evaluation | Saved part |
| --- | --- | --- | --- | --- | --- | --- |
| openai/gpt-6.1-sol | bracket_v3 | verified_repair | [Trace](runs/01-openai-gpt-6-1-sol-bracket_v3-r1/events.jsonl) | [Reply](runs/01-openai-gpt-6-1-sol-bracket_v3-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-01-openai-gpt-6-1-sol-bracket_v3-r1.json) | [JSON](artifacts/01-openai-gpt-6-1-sol-bracket_v3-r1/bracket_v3.json) |
| openai/gpt-6.1-sol | flange_v1 | bounded_search_no_repair | [Trace](runs/01-openai-gpt-6-1-sol-flange_v1-r1/events.jsonl) | [Reply](runs/01-openai-gpt-6-1-sol-flange_v1-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-01-openai-gpt-6-1-sol-flange_v1-r1.json) | None |
| openai/gpt-6-luna | bracket_v3 | verified_repair | [Trace](runs/02-openai-gpt-6-luna-bracket_v3-r1/events.jsonl) | [Reply](runs/02-openai-gpt-6-luna-bracket_v3-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-02-openai-gpt-6-luna-bracket_v3-r1.json) | [JSON](artifacts/02-openai-gpt-6-luna-bracket_v3-r1/bracket_v3.json) |
| openai/gpt-6-luna | flange_v1 | bounded_search_no_repair | [Trace](runs/02-openai-gpt-6-luna-flange_v1-r1/events.jsonl) | [Reply](runs/02-openai-gpt-6-luna-flange_v1-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-02-openai-gpt-6-luna-flange_v1-r1.json) | None |
| anthropic/claude-sonnet-5.5 | bracket_v3 | verified_repair | [Trace](runs/03-anthropic-claude-sonnet-5-5-bracket_v3-r1/events.jsonl) | [Reply](runs/03-anthropic-claude-sonnet-5-5-bracket_v3-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-03-anthropic-claude-sonnet-5-5-bracket_v3-r1.json) | [JSON](artifacts/03-anthropic-claude-sonnet-5-5-bracket_v3-r1/bracket_v3.json) |
| anthropic/claude-sonnet-5.5 | flange_v1 | bounded_search_no_repair | [Trace](runs/03-anthropic-claude-sonnet-5-5-flange_v1-r1/events.jsonl) | [Reply](runs/03-anthropic-claude-sonnet-5-5-flange_v1-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-03-anthropic-claude-sonnet-5-5-flange_v1-r1.json) | None |
| anthropic/claude-haiku-5.5 | bracket_v3 | verified_repair | [Trace](runs/04-anthropic-claude-haiku-5-5-bracket_v3-r1/events.jsonl) | [Reply](runs/04-anthropic-claude-haiku-5-5-bracket_v3-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-04-anthropic-claude-haiku-5-5-bracket_v3-r1.json) | [JSON](artifacts/04-anthropic-claude-haiku-5-5-bracket_v3-r1/bracket_v3.json) |
| anthropic/claude-haiku-5.5 | flange_v1 | reporting_failure | [Trace](runs/04-anthropic-claude-haiku-5-5-flange_v1-r1/events.jsonl) | [Reply](runs/04-anthropic-claude-haiku-5-5-flange_v1-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-04-anthropic-claude-haiku-5-5-flange_v1-r1.json) | None |
| deepseek/deepseek-v4.1-flash-1017 | bracket_v3 | verified_repair | [Trace](runs/05-deepseek-deepseek-v4-1-flash-1017-bracket_v3-r1/events.jsonl) | [Reply](runs/05-deepseek-deepseek-v4-1-flash-1017-bracket_v3-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-05-deepseek-deepseek-v4-1-flash-1017-bracket_v3-r1.json) | [JSON](artifacts/05-deepseek-deepseek-v4-1-flash-1017-bracket_v3-r1/bracket_v3.json) |
| deepseek/deepseek-v4.1-flash-1017 | flange_v1 | reporting_failure | [Trace](runs/05-deepseek-deepseek-v4-1-flash-1017-flange_v1-r1/events.jsonl) | [Reply](runs/05-deepseek-deepseek-v4-1-flash-1017-flange_v1-r1/raw/model/final.txt) | [Report](evaluation-20261024T015525Z-7c9a80/report-05-deepseek-deepseek-v4-1-flash-1017-flange_v1-r1.json) | None |

Each trace event references its raw model request/response, tool result or CLI stdout/stderr inside the same run directory. The final reply links retain the original model text, including the two formatting failures.

## Offline replay after moving this checkout

The original input manifest and verified reports are preserved. `inputs.portable.json` lists the same ten bundles using relative paths:

```sh
.venv/bin/python evaluation/evaluate.py --inputs reports/model-benchmark-20261024/inputs.portable.json --output-dir reports/benchmark-replay-001
```

One run per model and task is a pilot comparison, not a reliability estimate. No additional model calls are needed to inspect or evaluate these results.
