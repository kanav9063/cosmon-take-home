# SDK preparation and reproducible checks

Prepared on October 23, 2026 (America/New_York) in the assigned clone
`/home/ubuntu/work/cosmon-sdk`, branch `setup/sdk-plan`. The original starter
commit is `20b46cd2ceb65f3b24a55ca1f9298cf066782968`.

This is **setup and planning only**. The agent, its guarded PartLab tools,
trace producer, offline evaluator and recorded demonstrations are not yet
implemented. The offline setup checks and a separate live provider smoke test
have passed. [RUN.md](../RUN.md) remains the
exercise handoff template; fill it with actual results during the recording.

## Reproduce the environment

The tested platform is Linux AMD64, Python 3.12.3 with pip 24.0. The supplied
binary is platform-specific. From this clone's root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip check
.venv/bin/python scripts/check_setup.py
```

Installation downloads dependencies; the final health check is offline and
requires no credentials. No uv, Docker, Harbor or Scout installation is needed
for this core setup. Use a fresh venv when reproducing the lock; do not install
into system Python. `.venv` is ignored by Git. The project runs directly from
the checkout and has no distribution/build step.

[pyproject.toml](../pyproject.toml) pins the direct dependency combination:

| Package | Verified version |
| --- | --- |
| `openai-agents` | 0.24.0 |
| `openai` | 3.37.0 |
| `pydantic` | 2.14.1 |

[requirements.lock](../requirements.lock) pins all 38 installed runtime
packages, including the SDK's transitive dependencies. It was generated from
the isolated environment using `python -m pip freeze`; it is a pip requirements
file, not a uv lock. It fixes versions but does not vendor wheels or pin their
hashes. `.python-version` records the tested interpreter. Other Python/platform
combinations have not been verified.

To retain a **new**, explicitly labeled setup report:

```bash
.venv/bin/python scripts/check_setup.py --report reports/setup-sdk-new.json
```

The script refuses to overwrite an existing report. Omit `--report` for routine
rechecks. Reports have `kind: preparation_health_check`, `is_agent_run: false`
and `model_calls: 0`; they are not the assignment's raw agent traces.

## What passed

[reports/setup-sdk.json](../reports/setup-sdk.json) records the reusable check:

- Import the SDK and construct an `Agent` without running a model.
- Construct a harmless typed `function_tool`, check its closed schema and invoke
  it locally with `ToolContext`, verifying call identity and output.
- Verify the needed lifecycle hooks, `Runner.run` turn-limit parameter, explicit
  disabled tracing and nonparallel tool settings are available.
- Block Python socket connection/DNS/send calls in the check process, disable
  hosted tracing, and make no model/provider request.
- Copy the binary and six parts into a temporary working directory; run help,
  listing, reset, a deliberately invalid closed-session solve, and the original
  bracket open → parameters → mesh → default load → solve → SF readback.
- Observe baseline SF **1.428** at `face_mounting`, 5000 N, `-Z`; check the
  solve/readback agree without hard-coding a successful repair.
- Require the invalid closed solve to return `StateError`; reset and read back
  closed state; remove the temporary directory.
- Verify the original README, binary and all six parts retain their hashes,
  and that this checkout's `.partlab` presence/content is unchanged.

`pip check` also passed. The shell has no configured `OPENAI_API_KEY`,
`OPENAI_BASE_URL` or `OPENAI_MODEL`; only presence was inspected, never values.
At that check, provider account access was unverified and no model was selected. Codex and Claude
CLIs are available; that does not establish OpenAI API access. uv and Docker
are not on PATH. No account credentials are required for these setup checks.

Subsequent configuration: Kanav selected OpenRouter model
`openai/gpt-6.1-sol` with medium reasoning. `.env` is ignored and owner-readable/
writable only; [.env.example](../.env.example) records the nonsecret settings.
`OPENROUTER_REASONING_EFFORT` is our application's configuration name: the
agent must load it and set
`ModelSettings(reasoning=Reasoning(effort="medium"))`. The PartLab agent and its
configuration loader are not implemented yet; the separate provider smoke script
described below now loads `.env` for its own check. The model exists in OpenRouter's public catalog
with tool calling and reasoning support; the installed SDK accepts medium
reasoning. Live access and tool calling were subsequently verified below.
The catalog does not advertise `temperature` or `parallel_tool_calls` for this
model; omit optional unsupported settings until compatibility is established,
and retain runner-side serialization regardless of provider options.
Sources: [model](https://openrouter.ai/openai/gpt-6.1-sol),
[reasoning settings](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Initial live provider test

The user requested initial testing after adding credentials and choosing the
model. The repeatable command is:

```bash
.venv/bin/python scripts/check_openrouter.py
```

This is a **paid-request smoke test**, separate from the offline setup check.
It allows at most two model turns, each capped at 2048 output tokens, with
medium reasoning, 40-second request timeout, 85-second overall timeout and
both client/SDK retries disabled. A harmless tool returns a random value that
the model must reproduce exactly in its final reply. No PartLab command runs.
It loads literal `.env` assignments without executing shell code; process
environment variables take precedence. Each attempt creates a new report
directory with request/response bodies and tool events. Authentication headers
are never saved, and occurrences of the configured key are redacted.

The first live attempt on October 23, 2026 **failed authentication before any
tool call**. OpenRouter returned HTTP 401, `Missing Authentication header`.
The request body correctly contained `openai/gpt-6.1-sol`, medium reasoning,
and the named probe tool. See the
[report](../reports/openrouter-smoke-b23ae4f685704a919f20fbb8cc039c40/report.json)
and [response](../reports/openrouter-smoke-b23ae4f685704a919f20fbb8cc039c40/response-1.json).
This is a real failed provider request, not a successful model demonstration.

A separate read-only `/api/v1/auth/key` request received the same 401. An
offline transport interception confirmed that the OpenAI client constructs
the expected Bearer header from the loaded value. A missing-key test confirmed
exit 2 with a local diagnostic before any request. The key in `.env` was left
unchanged.

The requested retry authenticated and completed the tool exchange, but exposed
a local report-writing bug: `dataclasses.asdict` left nested SDK token-detail
models that `json.dumps` could not serialize. That attempt's original
[report](../reports/openrouter-smoke-7e278270169a4e2ea4f01f1174fa7729/report.json)
remains `running` because finalization crashed; its two HTTP 200 responses and
final-output event are preserved. This is incomplete report finalization, not
an authentication failure.

The serializer now uses Pydantic's JSON mode, with an offline regression test
covering aggregate and per-request token details:

```bash
.venv/bin/python -m unittest discover -s scripts -p 'test_check_openrouter.py'
```

The subsequent clean rerun **passed** with `openai/gpt-6.1-sol` and medium
reasoning: two HTTP 200 responses, exactly one `get_probe_value` invocation,
and a final reply matching the returned random value. It used 215 input and
43 output tokens (258 total); the provider reported zero reasoning tokens for
this simple probe. See the completed
[report](../reports/openrouter-smoke-64ba6facbc914c29b186e0c68744773d/report.json)
and [events](../reports/openrouter-smoke-64ba6facbc914c29b186e0c68744773d/events.jsonl).
This verifies authentication, SDK/provider compatibility, tool-result handling,
and report persistence. It does not test PartLab agent behavior.

[reports/sdk-lock-replay.json](../reports/sdk-lock-replay.json) records a second
check in a newly created temporary venv: installation from `requirements.lock`,
an exact match of all 38 frozen package versions, `pip check`, and the same
offline health check all passed. That second environment was removed afterward.

Additional temporary-only CLI probes informed the plan: reopens restore the
baseline; same-value parameter sets, remeshing and reloading invalidate solves;
save accepts unsolved state; the solve result itself includes a large log;
and argument validation is insufficient for NaN. These observations are
documented in [SDK_PLAN.md](SDK_PLAN.md), not claimed as a finished agent test.

## SDK documentation and installed-code verification

The current official [Python quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart?lang=python)
uses `Agent`, `Runner` and `function_tool`. The
[agent context guide](https://developers.openai.com/api/docs/guides/agents/define-agents)
distinguishes local runtime context from model-visible inputs. The
[observability guide](https://developers.openai.com/api/docs/guides/agents/integrations-observability)
documents enabled-by-default SDK tracing. We therefore configure tracing
explicitly and plan a separate local evidence journal.

Checked against these installed package files, relative to
`.venv/lib/python3.12/site-packages/`:

| File | Verified interface |
| --- | --- |
| `agents/tool_context.py` | `ToolContext` exposes original arguments and native call ID; import from this module, not top-level `agents` |
| `agents/lifecycle.py` | `RunHooks` supports model-start/end and tool-start/end callbacks |
| `agents/result.py` | `RunResult` retains `raw_responses`, `new_items`; transformed continuation input is not a complete raw archive |
| `agents/run_config.py` | Per-run `tracing_disabled` setting |
| `agents/model_settings.py` | `parallel_tool_calls`, `store`, `timeout`, `max_tokens` settings |
| `agents/tool.py` | Typed function-tool schema generation and invocation |

Setup caught and corrected two integration assumptions: postponed annotations
cannot resolve a locally imported `ToolContext` when the SDK inspects a nested
function; and `reset` deletes the state file, while a later `get-active-part`
recreates closed state. The check now uses evaluated annotations and the public
state query. Those offline checks do not verify a live model or complete trace
capture; the separate provider probe above covers the basic live exchange.

## Next checkpoint

[SDK_PLAN.md](SDK_PLAN.md) gives the implementation sequence and executable
future test targets. [TRACE_CONTRACT_PROPOSAL.md](TRACE_CONTRACT_PROPOSAL.md)
defines the proposed evidence boundary and clearly synthetic example fragments.
The proposal has **not** been reconciled with or accepted by the evaluation
chat. The two chats have not messaged each other.

Accepted here: stop at the first valid verified fix, and use configurable
exploration ranges without claiming completeness. Still resolve the exact
numerical ranges and candidate order, agent budgets/retries/timeouts,
mesh and numeric policy, and the shared schema before live implementation.
The exercise must still produce both real agent traces, required checks,
saved repairs where found, offline eval and flawed-trace detection, the
recording, and a concise completed RUN.md.
