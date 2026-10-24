#!/usr/bin/env python3
"""Small paid provider/tool smoke test; not a PartLab agent run or trace contract."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import uuid

os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

import httpx2
from openai import AsyncOpenAI
from openai.types.shared import Reasoning
from pydantic import TypeAdapter
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, RunConfig, Runner, function_tool
from agents.retry import ModelRetrySettings
from agents.tool_context import ToolContext

ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAMES = ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_REASONING_EFFORT")


def serialize_usage(usage):
    """SDK usage nests Pydantic models inside a dataclass."""
    return TypeAdapter(type(usage)).dump_python(usage, mode="json")


def load_config(path):
    """Read literal .env assignments, without shell execution or interpolation."""
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            name, separator, value = line.partition("=")
            name = name.strip().removeprefix("export ").strip()
            if name not in CONFIG_NAMES:
                continue
            if not separator:
                raise ValueError("Invalid configuration assignment")
            tokens = shlex.split(value, comments=True)
            if len(tokens) > 1:
                raise ValueError("Configuration values with spaces must be quoted")
            values[name] = tokens[0] if tokens else ""
    for name in CONFIG_NAMES:
        if name in os.environ:
            values[name] = os.environ[name]
        if not values.get(name):
            raise ValueError(f"Missing {name}; no request sent")
    if values["OPENROUTER_REASONING_EFFORT"] not in {"low", "medium", "high", "xhigh", "max"}:
        raise ValueError("Invalid reasoning effort; no request sent")
    return values


async def check(config, output):
    output.mkdir(parents=True, exist_ok=False)
    key = config["OPENROUTER_API_KEY"]
    model = config["OPENROUTER_MODEL"]
    effort = config["OPENROUTER_REASONING_EFFORT"]
    token = uuid.uuid4().hex
    events = []
    requests = 0
    tool_calls = 0
    report = {
        "kind": "live_provider_smoke", "is_partlab_agent_run": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "reasoning_effort": effort,
        "max_model_turns": 2, "max_tokens_per_response": 2048,
        "client_retries": 0, "sdk_retries": 0,
        "hosted_tracing": False, "status": "running",
    }

    def write_json(name, value):
        serialized = json.dumps(value, indent=2, allow_nan=False)
        (output / name).write_text(serialized.replace(key, "[REDACTED]") + "\n")

    def event(kind, **data):
        item = {"seq": len(events) + 1, "kind": kind, **data}
        events.append(item)
        with (output / "events.jsonl").open("a") as f:
            f.write(json.dumps(item, allow_nan=False).replace(key, "[REDACTED]") + "\n")

    async def on_request(request):
        nonlocal requests
        requests += 1
        if requests > 2 or request.url.host != "openrouter.ai" or request.url.path != "/api/v1/chat/completions":
            raise RuntimeError("Unexpected provider request blocked")
        body = json.loads(request.content)
        if body.get("model") != model or body.get("reasoning_effort") != effort:
            raise RuntimeError("Model/reasoning configuration did not reach the request")
        write_json(f"request-{requests}.json", body)  # Body only; never auth headers.
        event("http_request", request_number=requests, body_file=f"request-{requests}.json")

    async def on_response(response):
        body = await response.aread()
        sanitized = body.replace(key.encode(), b"[REDACTED]")
        name = f"response-{requests}.json"
        (output / name).write_bytes(sanitized)
        event("http_response", request_number=requests, status_code=response.status_code,
              body_file=name, redacted=sanitized != body)

    @function_tool(failure_error_function=None)
    async def get_probe_value(ctx: ToolContext[dict]) -> str:
        """Return a random verification value for this provider smoke test."""
        nonlocal tool_calls
        tool_calls += 1
        if tool_calls != 1:
            raise RuntimeError("Unexpected repeated tool invocation")
        event("tool_called", name=ctx.tool_name, call_id=ctx.tool_call_id, arguments=ctx.tool_arguments)
        event("tool_returned", call_id=ctx.tool_call_id, result=token)
        return token

    write_json("report.json", report)
    try:
        async with httpx2.AsyncClient(event_hooks={"request": [on_request], "response": [on_response]}) as http:
            async with AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1",
                                   max_retries=0, timeout=40, http_client=http) as client:
                agent = Agent(
                    name="OpenRouter provider smoke",
                    instructions="Call get_probe_value exactly once. Then reply with only OPENROUTER_SMOKE_OK followed by a space and the exact returned value. Do not call tools again.",
                    model=OpenAIChatCompletionsModel(model=model, openai_client=client),
                    tools=[get_probe_value], reset_tool_choice=True,
                    model_settings=ModelSettings(
                        tool_choice="required", max_tokens=2048,
                        reasoning=Reasoning(effort=effort),
                        retry=ModelRetrySettings(max_retries=0),
                        preserve_raw_usage=True,
                    ),
                )
                result = await asyncio.wait_for(
                    Runner.run(agent, "Run the provider smoke test.", max_turns=2,
                               run_config=RunConfig(tracing_disabled=True)), timeout=85,
                )
                final = str(result.final_output).strip()
                event("final_output", text=final)
                if tool_calls != 1 or requests != 2 or final != f"OPENROUTER_SMOKE_OK {token}":
                    raise RuntimeError("Tool round-trip verification failed")
                report.update(status="passed", usage=serialize_usage(result.context_wrapper.usage))
    except Exception as error:
        # Do not emit exception reprs, request headers, client objects or credentials.
        report.update(status="failed", error_type=type(error).__name__)
        status = getattr(error, "status_code", None)
        if status is not None:
            report["http_status"] = status
        event("failure", error_type=type(error).__name__)
    finally:
        report.update(http_requests=requests, tool_calls=tool_calls,
                      completed_at=datetime.now(timezone.utc).isoformat())
        write_json("report.json", report)
    print(json.dumps({**report, "artifacts": str(output)}, indent=2))
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        config = load_config(args.env_file)
    except ValueError as error:
        print(json.dumps({"status": "configuration_error", "message": str(error)}))
        return 2
    output = args.output or ROOT / "reports" / f"openrouter-smoke-{uuid.uuid4().hex}"
    return asyncio.run(check(config, output))


if __name__ == "__main__":
    raise SystemExit(main())
