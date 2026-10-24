# What the five-model benchmark shows

All five models produced a solver-verified, saved one-parameter repair for
`bracket_v3`. Three models also reported the unsuccessful bounded flange search
correctly. Two models failed the required final-response format. This pilot
therefore demonstrates both working model substitution and a concrete reporting
failure that the evaluation pipeline catches.

| Model | Bracket | Flange | Reported cost, both runs |
| --- | --- | --- | ---: |
| OpenAI GPT-6.1 Sol | Repaired, SF 3.072 | Valid bounded no-repair outcome | $0.0467495 |
| OpenAI GPT-6 Luna | Repaired, SF 11.421 | Valid bounded no-repair outcome | $0.00322642 |
| Anthropic Claude Sonnet 5.5 | Repaired, SF 3.072 | Valid bounded no-repair outcome | $0.299392 |
| Anthropic Claude Haiku 5.5 | Repaired, SF 3.072 | Final JSON failure | $0.0160262 |
| DeepSeek V4.1 Flash 1017 | Repaired, SF 3.072 | Final JSON failure | $0.005841511 |

Luna changed bracket thickness from 3 to 12 mm; the other models chose 5 mm.
Its higher safety factor does not make it the better result under this task:
the objective was the first legal passing repair, with no minimization of
material or parameter change. All five bracket artifacts satisfy that objective.

Sol, Luna and Sonnet correctly reported no flange repair, with best observed
SF 0.839 against the required 2.0. Sonnet stopped after three candidates; Sol
and Luna used six. These are bounded search observations, not proofs that a
legal repair is impossible. Haiku and DeepSeek also recorded best SF 0.839,
but returned prose or code fences instead of the required final JSON. Their
reports contain `TRACE_PARSE_ERROR`; independent capture, process, reporting
and repair dimensions remain **unknown**, rather than being counted as passes.

The separate trace audit passed for all ten runs: byte inventories and event
sequences were consistent, tool returns reached the next SDK request intact,
and verbose solver logs stayed out of model context. The audit also confirmed
the same prompt per part, tool schema, bounds and budgets, requested medium
reasoning setting, and unchanged harness source. This establishes comparable
configured inputs; providers can still implement reasoning, routing and caching
differently. Passing this byte audit does not validate a malformed final claim.

The concurrent batch took approximately 66.6 seconds and reported total cost
$0.371235631. Individual bracket runs ranged from 8.92 to 23.91 seconds;
flange runs ranged from 29.18 to 66.58 seconds and performed different amounts
of work. Luna had the lowest observed two-run cost; DeepSeek had the shortest
bracket run. With one run per model and part, neither observation establishes
a reliability ranking or a general winner.

These ten runs varied the model and provider while retaining the OpenAI Agents
SDK harness. A separate [Anthropic ToolRunner demonstration](../../docs/HARNESS_PORTABILITY.md)
now supplies two additional live runs with native HTTP messages, the same trace
contract, and the unchanged evaluator. That establishes a second harness;
its results are kept separate from this five-model comparison. The earlier
extra-part checks used renamed synthetic fixtures, not new CAD geometry.

Evidence: [artifact index](INDEX.md), [full comparison](comparison.md),
[machine-readable comparison](comparison.json), [verification](verification.json),
and [trace audit](capture-audit.json).
