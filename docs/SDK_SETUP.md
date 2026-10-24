# SDK preparation and reproducible checks

Prepared on October 23, 2026 (America/New_York) in the assigned clone
`/home/ubuntu/work/cosmon-sdk`, branch `setup/sdk-plan`. The original starter
commit is `20b46cd2ceb65f3b24a55ca1f9298cf066782968`.

This is **setup and planning only**. The agent, its guarded PartLab tools,
trace producer, offline evaluator and recorded demonstrations are not yet
implemented. No paid model request was made. [RUN.md](../RUN.md) remains the
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
future agent must load it and set
`ModelSettings(reasoning=Reasoning(effort="medium"))`. File loading and the live
agent are not implemented yet. The model exists in OpenRouter's public catalog
with tool calling and reasoning support; the installed SDK accepts medium
reasoning. No paid request or credential validation was performed.
The catalog does not advertise `temperature` or `parallel_tool_calls` for this
model; omit optional unsupported settings until compatibility is established,
and retain runner-side serialization regardless of provider options.
Sources: [model](https://openrouter.ai/openai/gpt-6.1-sol),
[reasoning settings](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

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
state query. None of this verifies a live model or complete trace capture.

## Next checkpoint

[SDK_PLAN.md](SDK_PLAN.md) gives the implementation sequence and executable
future test targets. [TRACE_CONTRACT_PROPOSAL.md](TRACE_CONTRACT_PROPOSAL.md)
defines the proposed evidence boundary and clearly synthetic example fragments.
The proposal has **not** been reconciled with or accepted by the evaluation
chat. The two chats have not messaged each other.

Accepted here: stop at the first valid verified fix, and use configurable
exploration ranges without claiming completeness. Still resolve the exact
live model access, numerical ranges and candidate order, budgets/retries/timeouts,
mesh and numeric policy, and the shared schema before live implementation.
The exercise must still produce both real agent traces, required checks,
saved repairs where found, offline eval and flawed-trace detection, the
recording, and a concise completed RUN.md.
