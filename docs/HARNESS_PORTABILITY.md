# Harness portability demonstrated

The same PartLab task now runs through two real agent loops: OpenAI Agents SDK
and Anthropic Python SDK's `beta.messages.tool_runner` (2.3.0). Both use the same
seven tool definitions, system instructions, guarded executor, PartLab binary,
search policy, final-claim validation and offline evaluator.

![Two harnesses, one execution and evaluation contract](assets/harness-portability.png)

The additional runner is [anthropic_runner.py](../cosmon_agent/anthropic_runner.py).
It captures native Anthropic Messages HTTP request/response bodies; the original
runner captures SDK-exposed OpenAI messages. Each retains its original payload
format, while emitting the shared `partlab.trace/0.1-proposal` bundle with
`capture_profile: cosmon-eval/1`. No evaluator or PartLab workflow rewrite was
needed.

## What changes at the boundary

The Anthropic adapter maps native `tool_use.id`, name and input objects into
proposal events, invokes the shared executor, and verifies that the SDK's next
request contains the exact returned tool text. Native arguments are objects,
so the normalized argument string is explicitly labeled as canonical JSON;
the original HTTP body remains available. Headers and credentials are not
captured. The pinned SDK runs these tools in response order.

Common events link model responses, proposals, guard decisions, CLI attempts,
tool returns, solves and artifacts through stable IDs and hashed references.
The evaluator reconstructs engineering state from CLI evidence, independently
of either SDK's success claim. Missing or unsupported evidence remains unknown.

## Observed proof

Using `anthropic/claude-sonnet-5.5` through OpenRouter:

| Task | Native ToolRunner result | Model / tool / CLI calls |
| --- | --- | --- |
| bracket_v3 | Thickness 3 → 5 mm; fresh SF 3.072; verified saved part | 11 / 10 / 14 |
| flange_v1 | Three legal trials; best SF 0.839; valid bounded no-repair report | 20 / 19 / 27 |

Both traces passed native message/tool continuity, completion-inventory hashes,
compact-context and artifact checks. The unchanged evaluator verified the
bracket repair and the flange process/reporting; flange repair achievement
remains a failure. These runs cost $0.298670 as reported by the provider.

An offline regression uses the actual ToolRunner and PartLab CLI with explicitly
mocked HTTP responses. It proposes flange thickness 5.5 mm and verifies rejection
before CLI dispatch, exact native request/response capture, and a valid final
report. It is labeled synthetic and is not counted among live runs.

- [Live results and evaluator links](../reports/anthropic-harness-20261024/comparison.md)
- [Bracket trace](../reports/anthropic-harness-20261024/bracket_v3/events.jsonl), [flange trace](../reports/anthropic-harness-20261024/flange_v1/events.jsonl), and [saved bracket](../reports/anthropic-harness-20261024/artifacts/bracket_v3/bracket_v3.json)
- [Native capture audit](../reports/anthropic-harness-20261024/capture-audit.json)
- [Shared-source and test verification](../reports/anthropic-harness-20261024/verification.json)
- [Offline regression](../tests/test_anthropic_runner.py)
- [Original five-model findings](../reports/model-benchmark-20261024/FINDINGS.md)

This proves a second harness can emit the existing contract. It does not mean
an arbitrary harness works without a capture adapter. Extra parts still need
configured ranges and trusted evaluator cases; different manufacturing rules
need explicit policy. Earlier additional-part checks used renamed synthetic
fixtures, not new CAD geometry.

The native API uses `output_config.effort=medium`; the original runner uses
Chat Completions reasoning settings. These runs demonstrate portability, not
a controlled claim that one harness improves model performance.

## Reproduce

```sh
.venv/bin/python -m pip install -r requirements-anthropic.txt
.venv/bin/python -m cosmon_agent.anthropic_runner --part bracket_v3 --output runs/native-001/bracket --publish-dir runs/native-001/outputs
.venv/bin/python -m cosmon_agent.anthropic_runner --part flange_v1 --output runs/native-001/flange --publish-dir runs/native-001/outputs
.venv/bin/python scripts/verify_anthropic_capture.py reports/anthropic-harness-20261024/bracket_v3 --publication-dir reports/anthropic-harness-20261024/artifacts/bracket_v3 --output reports/native-audit-001.json
.venv/bin/python evaluation/evaluate.py --inputs reports/anthropic-harness-20261024/inputs.json --output-dir reports/native-eval-001
```

The agent commands make paid calls. Audit and evaluation commands use persisted
evidence and need no API key. The optional dependency adds one native-harness
test to the 21 baseline agent tests; without it, that test is explicitly skipped.
