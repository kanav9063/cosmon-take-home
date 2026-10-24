"""Actual Anthropic SDK ToolRunner adapter over the shared PartLab executor."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

import anthropic
import httpx2
from anthropic.lib.tools import BetaAsyncBuiltinFunctionTool

from .agent import ROOT, DEFAULT_POLICY, TOOL_DEFINITIONS, build_instructions, load_config, load_policy, parse_arguments, strict_json, validate_final_claim
from .engine import Engine
from .trace import Trace


class AdapterStop(asyncio.CancelledError):
    """Stop without ToolRunner converting an adapter fault into an invented result."""


class NativeCapture:
    def __init__(self, trace, engine, policy, model):
        self.trace, self.engine, self.policy, self.model = trace, engine, policy, model
        self.model_calls = 0
        self.current = None
        self.pending = False
        self.proposals = []
        self.completed = {}
        self.stop_reason = None

    def stop(self, reason):
        self.stop_reason = reason
        raise AdapterStop(reason)

    def budget(self):
        if len(self.completed) >= self.policy["max_tool_calls"]:
            self.stop("tool_call_budget")

    async def request(self, request):
        self.budget()
        if request.url.host != "openrouter.ai" or request.url.path != "/api/v1/messages":
            self.stop("unexpected_provider_endpoint")
        body = strict_json(request.content)
        if body.get("model") != self.model:
            self.stop("unexpected_provider_model")
        # Verify what ToolRunner actually sends back, including its text-block
        # representation, against the exact shared-executor return string.
        for message in body.get("messages", []):
            content = message.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_result":
                    continue
                result = block.get("content")
                if isinstance(result, list):
                    result = "".join(item.get("text", "") for item in result if item.get("type") == "text")
                if self.completed.get(block.get("tool_use_id")) != result:
                    self.stop("tool_result_capture_mismatch")
        self.model_calls += 1
        if self.model_calls > self.policy["max_model_turns"]:
            self.stop("model_turn_budget")
        self.current = f"m{self.model_calls:04d}"
        ref = self.trace.write_bytes(f"raw/model/{self.current}.request.json", request.content)
        self.trace.event("model_requested", {"request_ref": ref, "model": self.model,
                         "capture_format": "anthropic.messages.http/1", "reasoning_effort": "medium",
                         "native_effort_field": "output_config.effort"}, model_call_id=self.current)
        self.pending = True

    async def response(self, response):
        raw = await response.aread()
        ref = self.trace.write_bytes(f"raw/model/{self.current}.response.json", raw)
        if response.status_code >= 400:
            self.trace.event("model_failed", {"response_ref": ref, "http_status": response.status_code,
                             "error_category": "provider_http_error", "attempt": 1, "retry_eligible": False}, model_call_id=self.current)
            self.pending = False
            return
        body = strict_json(raw)
        usage = body.get("usage", {})
        event = self.trace.event("model_returned", {"response_ref": ref, "response_id": body.get("id"),
                                 "usage": usage, "raw_usage": usage, "capture_format": "anthropic.messages.http/1"},
                                 actor="model", model_call_id=self.current)
        self.pending = False
        for block in body.get("content", []):
            if block.get("type") != "tool_use":
                continue
            arguments = json.dumps(block.get("input"), sort_keys=True, separators=(",", ":"), allow_nan=False)
            data = {"name": block["name"], "native_call_id": block["id"], "native_item_id": block["id"],
                    "arguments": arguments, "arguments_format": "canonical_json_from_native_object",
                    "native_input": block.get("input"), "source_response_event_id": event["event_id"]}
            self.trace.event("tool_proposed", data, actor="model", call_id=block["id"], model_call_id=self.current)
            if any(item["id"] == block["id"] for item in self.proposals) or block["id"] in self.completed:
                self.stop("duplicate_native_call_id")
            self.proposals.append({**block, "arguments": arguments, "model_call_id": self.current})


class ExecutorTool(BetaAsyncBuiltinFunctionTool):
    def __init__(self, name, capture):
        self.tool_name, self.capture = name, capture

    def to_dict(self):
        description, schema = TOOL_DEFINITIONS[self.tool_name]
        return {"name": self.tool_name, "description": description, "input_schema": schema}

    async def call(self, input):
        capture = self.capture
        capture.budget()
        if not capture.proposals:
            capture.stop("uncaptured_tool_call")
        proposal = capture.proposals[0]
        if proposal["name"] != self.tool_name or proposal["input"] != input:
            capture.stop("native_call_order_or_input_mismatch")
        capture.proposals.pop(0)
        try:
            result = await capture.engine.invoke(self.tool_name, parse_arguments(self.tool_name, proposal["arguments"]),
                                                 proposal["id"], proposal["model_call_id"])
        except Exception:
            capture.stop("executor_error")
        capture.completed[proposal["id"]] = result
        return result


async def run_anthropic_agent(part, output, config, policy, *, root=ROOT, publish_dir=None):
    instructions = build_instructions(part, policy)
    model = config["OPENROUTER_MODEL"]
    metadata = {"provider": "openrouter", "model": model, "harness": "anthropic.beta.messages.tool_runner",
                "anthropic_version": anthropic.__version__, "reasoning_effort": "medium",
                "native_effort_field": "output_config.effort", "client_retries": 0,
                "prompt_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
                "tool_schema_sha256": hashlib.sha256(json.dumps(TOOL_DEFINITIONS, sort_keys=True).encode()).hexdigest()}
    policy = {**policy, "_model_config": metadata}
    trace = Trace(Path(output))
    engine = Engine(root, trace, part, policy, publish_dir or Path(root) / "outputs")
    capture = NativeCapture(trace, engine, policy, model)
    failure = final_ref = final_text = None
    try:
        async with asyncio.timeout(policy["run_timeout_seconds"]):
            await engine.setup()
            # This run's manifest has not been sealed. Describe this adapter's
            # native capture faithfully instead of inheriting SDK-object labels.
            manifest_path = trace.path / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["capture"] = {"model": "provider_http_bytes", "model_format": "anthropic.messages.http/1", "cli": "bytes", "hosted_tracing": False}
            manifest["producer"]["harness"] = "anthropic.beta.messages.tool_runner"
            manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
            async with httpx2.AsyncClient(event_hooks={"request": [capture.request], "response": [capture.response]}) as http:
                async with anthropic.AsyncAnthropic(
                    api_key=None, auth_token=config["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api",
                    max_retries=0, timeout=policy["model_timeout_seconds"], http_client=http,
                ) as client:
                    runner = client.beta.messages.tool_runner(
                        model=model, max_tokens=policy["max_output_tokens"], max_iterations=policy["max_model_turns"],
                        messages=[{"role": "user", "content": f"Complete the assigned PartLab task for {part}. Begin by opening the original part."}],
                        system=instructions, tools=[ExecutorTool(name, capture) for name in TOOL_DEFINITIONS],
                        output_config={"effort": "medium"}, thread=False,
                    )
                    result = await runner.until_done()
                    if capture.proposals or result.stop_reason == "tool_use":
                        capture.stop("incomplete_tool_loop")
                    final_text = "".join(block.text for block in result.content if block.type == "text")
                    final_ref = trace.write_bytes("raw/model/final.txt", final_text.encode())
    except (Exception, asyncio.CancelledError) as error:
        failure = capture.stop_reason or ("run_timeout" if isinstance(error, TimeoutError) else type(error).__name__)
        if capture.pending:
            trace.event("model_failed", {"error_category": type(error).__name__, "attempt": 1, "retry_eligible": False}, model_call_id=capture.current)
    finally:
        await engine.close()
    outcome = engine.outcome(final_ref, failure=failure)
    if failure is None and final_text is not None:
        valid, reason = validate_final_claim(final_text, outcome)
        if not valid:
            outcome = engine.outcome(final_ref, failure=reason)
        outcome["final_claim_check"] = {"valid": valid, "reason_code": reason}
    outcome["model_calls"] = capture.model_calls
    outcome["harness"] = "anthropic.beta.messages.tool_runner"
    outcome["unexecuted_tool_call_ids"] = [item["id"] for item in capture.proposals]
    trace.finish(outcome)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="anthropic/claude-sonnet-5.5")
    parser.add_argument("--publish-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()
    try:
        config = {**load_config(args.env_file), "OPENROUTER_MODEL": args.model}
        outcome = asyncio.run(run_anthropic_agent(args.part, args.output, config, load_policy(args.policy), publish_dir=args.publish_dir))
        print(json.dumps(outcome, indent=2, allow_nan=False))
        return int(outcome["status"] == "execution_failure")
    except Exception as error:
        print(json.dumps({"status": "adapter_error", "error_category": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
