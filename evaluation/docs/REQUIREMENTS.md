# Take-home requirements

> Historical planning record from the independent evaluator checkout. For current
> implementation status and runnable commands, use [the evaluator index](../README.md),
> [the combined runbook](../../RUN.md), and [the integration decisions](../../docs/INTEGRATION_DECISIONS.md).

Derived from Noah's final email and the supplied [README](../../TASK.md), which
is the authoritative technical brief. This checklist records requirements;
unchecked boxes do not imply that work has been completed.

## Session

- [ ] Record the work with audio narration; describe the plan, assumptions,
      tradeoffs, debugging, and how results were verified.
- [ ] Time-box to **one hour total**, roughly 30 minutes for the agent and
      30 minutes for evaluation. The final email and README specify one hour;
      an earlier email estimated 2–3 hours.
- [ ] AI coding tools are encouraged; inspect and verify their output.

No calendar submission deadline is stated in the reviewed thread or README.

## Part 1: agent

- [ ] Implement an agent with a clear loop, system prompt, and tool interface.
- [ ] Run at least `bracket_v3` and `flange_v1`, resetting PartLab between runs.
- [ ] Apply each named part's default load, run FEA, and report its safety factor.
- [ ] If SF < 2.0, propose a **single-parameter** change that reaches SF ≥ 2.0,
      rerun analysis to verify it, and save `outputs/<part_name>.json`.
- [ ] Respect `flange_v1` manufacturing limits: `thickness_mm <= 5.0` and
      `hole_diameter_mm >= 4.0`. The SDK does not enforce these limits.
- [ ] Report clearly if no allowed fix exists; do not force an invalid change.
- [ ] Use the PartLab solve as the source of truth; do not hard-code named-part answers.
- [ ] Handle CLI ordering and errors, avoid unnecessary large results, and
      separate CLI interaction, decision logic, and trace capture.
- [ ] Persist raw messages, tool calls, and tool results for each run.
- [ ] Show one small repeatable non-happy-path check and explain what it proves.
      The `flange_v1` run may serve as this check.

## Part 2: evaluation

- [ ] Evaluate the raw Part 1 traces and produce a structured, actionable report.
- [ ] Use a general trace schema that can accommodate more cases or another harness.
- [ ] Make scoring and heuristics principled, tunable, and explainable.
- [ ] Include one deliberately flawed trace and demonstrate that the eval flags
      its specific problem. A reproducible command or deterministic assertion
      is enough; a test framework is optional.

## Handoff

- [ ] Complete `RUN.md`: clean-reset commands for agent, checks, and eval;
      dependencies; parts run; what passed; and the main limitation or unfinished item.
- [ ] Include source code and tests or check scripts.
- [ ] Include at least two raw agent traces plus the deliberately flawed trace.
- [ ] Include the evaluation output and any saved `outputs/` parts.
- [ ] Send Noah the recording and code/artifacts through a zip or accessible
      shared link. No submission has been sent during repository setup.

Production packaging and CI are not expected.
