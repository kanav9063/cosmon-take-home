# Model benchmark observations

One observed run per model and assigned part. A truthful bounded flange search with no repair is distinct from a provider, execution or reporting failure. Repair achievement is reported separately; no overall model ranking is inferred.

C/P/R/A = capture integrity / process compliance / reporting accuracy / repair achievement.

| Model | Part | Result | Baseline → best/final SF | C/P/R/A | Seconds | Model/tool/CLI calls | USD observed | Tokens in/out |
| --- | --- | --- | --- | --- | ---: | --- | ---: | --- |
| anthropic/claude-sonnet-5.5 | bracket_v3 | verified_repair | 1.428 → 3.072 | pass/pass/pass/pass | 13.69 | 11/10/14 | 0.0892380 | 41839/556 |
| anthropic/claude-sonnet-5.5 | flange_v1 | bounded_search_no_repair | 0.212 → 0.839 | pass/pass/pass/fail | 25.26 | 20/19/27 | 0.2094320 | 98786/1186 |

Model requests include failures; tool counts are captured returns; CLI counts include internal verification reads.

Elapsed time uses runner wall time when available, otherwise the captured event span. Unknown costs are not treated as zero; failed requests may have unreported charges.

Independent evaluator reports: [evaluation-20261024T015956Z-e5971b/](evaluation-20261024T015956Z-e5971b/)

## Limits

- Single stochastic runs do not establish reliability, statistical significance or a universal quality ranking.
- No repair found within configured ranges and trials is not a proof of infeasibility. The flange outcome is not assumed in advance.
- Provider routing, caching, supported reasoning behavior and transient load can affect latency, tokens and cost despite shared harness settings.
- Costs and tokens include only usage exposed in captured responses; failed requests may be unbilled or unreported, not necessarily free.
- Independent evaluation verifies recorded evidence consistency without replaying the solver or calling a model.
- Missing or unfinished planned runs remain listed and unverified. Raw trace bundles are never rewritten by this summary.
