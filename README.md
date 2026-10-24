# PartLab repair agent

Measure a part's safety factor, find a legal single-parameter repair, verify it
with PartLab and save the result. The model proposes changes, Python enforces
the rules, and an independent evaluator checks the recorded evidence.

![PartLab agent architecture](docs/assets/architecture.png)

[Run it](RUN.md) · [Full report](REPORT.md) · [Design decisions](DECISIONS.md) · [Code walkthrough](docs/REVIEWER_GUIDE.md) · [Original task](TASK.md)

## Results

Original live runs: OpenAI Agents SDK through OpenRouter, `openai/gpt-6.1-sol`,
medium reasoning.

| Part | Baseline SF | Verified outcome |
| --- | --- | --- |
| `bracket_v3` | 1.428 | Thickness 3 → 5 mm; **SF 3.072**; [saved repair](outputs/bracket_v3.json) |
| `flange_v1` | 0.212 | Six legal trials; best **SF 0.839**; no repair found |

No unsafe flange artifact was saved. The search was bounded; it does not prove
that a legal repair is impossible.

Two separate experiments extend these runs:

- **Five models, one harness:** all five repaired the bracket; three reported
  the bounded flange search correctly, and two failed the final JSON format.
  [Results and all ten traces](reports/model-benchmark-20261024/INDEX.md).
- **Two SDK harnesses:** OpenAI Agents SDK and Anthropic Python SDK ToolRunner
  use the same tools, executor, trace contract and evaluator. Two additional
  native Anthropic runs demonstrate the swap. [Proof and limits](docs/HARNESS_PORTABILITY.md).

<details>
<summary>See the five-model results and costs</summary>

Each model ran both required parts once through the same OpenAI Agents SDK
harness, prompt, tools and policy, with medium reasoning requested.

| Model | Bracket | Flange | Cost, both runs |
| --- | --- | --- | ---: |
| OpenAI GPT-6.1 Sol | Repaired | Valid bounded no-repair report | $0.0467495 |
| OpenAI GPT-6 Luna | Repaired | Valid bounded no-repair report | $0.00322642 |
| Anthropic Claude Sonnet 5.5 | Repaired | Valid bounded no-repair report | $0.299392 |
| Anthropic Claude Haiku 5.5 | Repaired | Final JSON failure | $0.0160262 |
| DeepSeek V4.1 Flash 1017 | Repaired | Final JSON failure | $0.005841511 |

The concurrent batch took about 66.6 seconds and cost $0.371235631 in
provider-reported usage. One run per model and part does not establish a
reliability ranking. [Findings and interpretation](reports/model-benchmark-20261024/FINDINGS.md).

</details>

## How we addressed the requirements

| Requirement | What we built | Evidence |
| --- | --- | --- |
| Clean agent loop and correct SDK use | Seven narrow tools; serialized execution; explicit state, load and recovery checks. | [Agent and executor](docs/ARCHITECTURE.md#workflow-and-tool-contracts) |
| Avoid over-fetching | Compact solve observations: 334–379 bytes. Full solver logs stay in the trace, outside model context. | [Capture audit](reports/main-integration-20261024/capture-audit.json) |
| Separate decisions, CLI and traces | Distinct agent, executor and trace modules. Every reported SF comes from PartLab. | [Code map](docs/ARCHITECTURE.md#code-map) |
| Generalize across cases and harnesses | Two real SDK loops; additional synthetic unseen-case and capture-adapter checks. | [Harness proof](docs/HARNESS_PORTABILITY.md), [case tests](evaluation/docs/EVAL_RUBRIC.md) |
| Principled, tunable evaluation | Trusted case constraints, configurable diagnostic budgets and bounded evidence loading. | [Evaluation policy](evaluation/EVAL_RUN.md) |
| Readable reports and defensible scoring | Separate correctness, compliance, delivery, reporting, capture and repair verdicts, with evidence and corrective actions. | [Report examples](reports/main-integration-20261024/evaluator/REPORTS.md), [scoring rationale](evaluation/docs/EVAL_CHECK_DECISIONS.md) |
| Demonstrate failure handling | Reject flange thickness 5.5 mm before mutation; detect `STALE_SOLVE` in a deliberately flawed trace; keep interrupted results unverified. | [Repeatable checks](reports/main-integration-20261024/README.md) |
| Explain choices and make runs reproducible | Documented tradeoffs, pinned dependencies, commands, raw traces and saved outputs. | [Decisions](DECISIONS.md), [run guide](RUN.md) |

The [complete acceptance map](REPORT.md#acceptance-criteria) covers each task,
agent, evaluator and handoff requirement individually, including the limits.

## Why Harbor, Docker, Scout and Sierra Tau²

| Tool or reference | Decision and reason | What we verified |
| --- | --- | --- |
| **Harbor — execution checks** | Use a separate verifier with trusted originals and explicit artifact transfer to check run isolation and delivery. | Two scripted oracle runs scored **1**; a no-op scored **0**. [Rationale](evaluation/docs/HARBOR_SETUP.md#what-the-smoke-check-proves) · [Evidence](reports/main-integration-20261024/harbor.json) |
| **Docker — reproducibility** | Run checks in a pinned container with networking disabled and source mounted read-only, so host-only success is not the sole evidence. | **156 evaluator tests and 19 expected cases** passed in the container. [Invocation](reports/main-integration-20261024/docker-execution.json) · [Results](reports/main-integration-20261024/docker/evaluator/verification.json) |
| **Inspect Scout — report browsing** | Display the existing evaluator's verdicts and raw-evidence references, preserving failed, unknown and rejected results. | **17 contract tests**, **19 transcripts** and **133 dimension results**. [Decisions](evaluation/docs/SCOUT_AUDIT.md#decisions-and-requirements) · [Evidence](reports/main-integration-20261024/scout.json) |
| **Sierra Tau² — design reference** | Audit explicit verdict coverage, valid alternative solutions, and accounting for failed or interrupted runs against pinned reference code. | Four focused regressions test the applicable lessons. [Reference audit and decisions](evaluation/docs/TAU2_REFERENCE_AUDIT.md) · [Tests](evaluation/tests/test_tau2_review.py) |

Harbor is an infrastructure smoke check; Scout presents existing grades.
Sierra Tau² was reviewed as a reference, not run as a benchmark. These are
separate from the live model and harness experiments above. The core evaluator
works without Harbor or Scout; container setup needs downloaded or cached
dependencies. [Full integration decisions](DECISIONS.md#19-keep-optional-viewers-and-execution-checks-outside-the-grading-core).

## Architecture

Each candidate starts from the original part: **restore → change one parameter
→ mesh → apply default load → solve → save if SF ≥ 2**. The agent stops at the
first verified repair. [Workflow and search policy](docs/ARCHITECTURE.md).

<details>
<summary>See how the two SDK harnesses share the same workflow and evaluator</summary>

![OpenAI Agents SDK and Anthropic ToolRunner share the executor and trace contract](docs/assets/harness-portability.png)

Each adapter retains its native messages and emits the common trace contract.
Changing the model within one SDK and replacing the SDK are separate checks.
The native Anthropic runs repaired the bracket at SF 3.072 and correctly
reported no flange repair, with best SF 0.839. They demonstrate portability,
not a measured performance advantage. [Implementation and live evidence](docs/HARNESS_PORTABILITY.md).

</details>

## Verify or run

**22 agent tests, 156 evaluator tests and 19 expected example outcomes passed.**
The evaluator tests and examples also passed in Docker with networking disabled.
[Verification receipts](reports/main-integration-20261024/README.md).

To verify the included evaluation evidence without an API key, from the repo
root with Python 3.12, choose a fresh output directory:

```sh
python3.12 evaluation/scripts/verify.py --output-dir /tmp/partlab-eval-check-001
```

To run the agent, follow [RUN.md](RUN.md) for the pinned environment and ignored
local `.env`. Live runs require an OpenRouter API key and the supplied Linux
AMD64 PartLab binary. Every run starts in an isolated, reset session.

**Remaining handoff item:** the human recording link. The repository does not
establish a recorded one-hour session. Search, portability and benchmark limits
are documented in the [report](REPORT.md#limits-and-reviewer-checks).
