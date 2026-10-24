# Model benchmark observations

One observed run per model and assigned part. A truthful bounded flange search with no repair is distinct from a provider, execution or reporting failure. Repair achievement is reported separately; no overall model ranking is inferred.

C/P/R/A = capture integrity / process compliance / reporting accuracy / repair achievement.

| Model | Part | Result | Baseline → best/final SF | C/P/R/A | Seconds | Model/tool/CLI calls | USD observed | Tokens in/out |
| --- | --- | --- | --- | --- | ---: | --- | ---: | --- |
| openai/gpt-6.1-sol | bracket_v3 | verified_repair | 1.428 → 3.072 | pass/pass/pass/pass | 23.91 | 11/10/14 | 0.0116115 | 21900/291 |
| openai/gpt-6.1-sol | flange_v1 | bounded_search_no_repair | 0.212 → 0.839 | pass/pass/pass/fail | 66.58 | 35/34/48 | 0.0351380 | 129417/746 |
| openai/gpt-6-luna | bracket_v3 | verified_repair | 1.428 → 11.421 | pass/pass/pass/pass | 17.7 | 11/10/14 | 0.0006747 | 21840/292 |
| openai/gpt-6-luna | flange_v1 | bounded_search_no_repair | 0.212 → 0.839 | pass/pass/pass/fail | 46.88 | 35/34/48 | 0.0025518 | 129330/1107 |
| anthropic/claude-sonnet-5.5 | bracket_v3 | verified_repair | 1.428 → 3.072 | pass/pass/pass/pass | 17.02 | 11/10/14 | 0.0892600 | 41695/587 |
| anthropic/claude-sonnet-5.5 | flange_v1 | bounded_search_no_repair | 0.212 → 0.839 | pass/pass/pass/fail | 30.8 | 20/19/27 | 0.2101320 | 98476/1318 |
| anthropic/claude-haiku-5.5 | bracket_v3 | verified_repair | 1.428 → 3.072 | pass/pass/pass/pass | 14.53 | 9/10/14 | 0.0038779 | 33479/1060 |
| anthropic/claude-haiku-5.5 | flange_v1 | reporting_failure | 0.212 → 0.839 | unknown/unknown/unknown/unknown | 39.39 | 21/20/29 | 0.0121483 | 107458/2805 |
| deepseek/deepseek-v4.1-flash-1017 | bracket_v3 | verified_repair | 1.428 → 3.072 | pass/pass/pass/pass | 8.92 | 11/10/14 | 0.0019376 | 30892/739 |
| deepseek/deepseek-v4.1-flash-1017 | flange_v1 | reporting_failure | 0.212 → 0.839 | unknown/unknown/unknown/unknown | 29.18 | 20/19/27 | 0.0039040 | 92324/4452 |

Model requests include failures; tool counts are captured returns; CLI counts include internal verification reads.

Elapsed time uses runner wall time when available, otherwise the captured event span. Unknown costs are not treated as zero; failed requests may have unreported charges.

Independent evaluator reports: [evaluation-20261024T015525Z-7c9a80/](evaluation-20261024T015525Z-7c9a80/)

## Limits

- Single stochastic runs do not establish reliability, statistical significance or a universal quality ranking.
- No repair found within configured ranges and trials is not a proof of infeasibility. The flange outcome is not assumed in advance.
- Provider routing, caching, supported reasoning behavior and transient load can affect latency, tokens and cost despite shared harness settings.
- Costs and tokens include only usage exposed in captured responses; failed requests may be unbilled or unreported, not necessarily free.
- Independent evaluation verifies recorded evidence consistency without replaying the solver or calling a model.
- Missing or unfinished planned runs remain listed and unverified. Raw trace bundles are never rewritten by this summary.
