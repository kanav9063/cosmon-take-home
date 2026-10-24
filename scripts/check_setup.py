#!/usr/bin/env python3
"""Offline preparation check. This is not an agent run or an evaluation harness."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): digest(p) for p in root.rglob("*") if p.is_file()}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_sdk() -> dict:
    # Prevent hosted telemetry in this short-lived check, even if credentials exist.
    os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

    def prohibit_network(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            raise RuntimeError("Network use is forbidden during this offline check")

    sys.addaudithook(prohibit_network)
    from agents import Agent, ModelSettings, RunConfig, RunHooks, Runner, function_tool
    from agents.tool_context import ToolContext

    @function_tool
    def setup_echo(ctx: ToolContext[dict], value: str) -> str:
        """Echo a setup value locally; never touches PartLab or a model."""
        require(ctx.tool_call_id == "setup-only-call", "Tool call identity was lost")
        return value

    settings = ModelSettings(parallel_tool_calls=False, store=False)
    run_config = RunConfig(tracing_disabled=True)
    agent = Agent(
        name="setup-only",
        instructions="Not executed. This object only verifies SDK construction.",
        model="offline-not-run",
        tools=[setup_echo],
        model_settings=settings,
    )
    schema = setup_echo.params_json_schema
    require(schema["additionalProperties"] is False, "Expected closed JSON schema")
    require(set(schema["required"]) == {"value"}, "Context leaked into tool arguments")
    ctx = ToolContext(
        context={}, tool_name="setup_echo", tool_call_id="setup-only-call",
        tool_arguments='{"value":"offline-ok"}',
    )
    result = asyncio.run(setup_echo.on_invoke_tool(ctx, ctx.tool_arguments))
    require(result == "offline-ok", "Local SDK tool invocation failed")
    for method in ("on_llm_start", "on_llm_end", "on_tool_start", "on_tool_end"):
        require(hasattr(RunHooks, method), f"Missing expected SDK hook: {method}")
    require("max_turns" in inspect.signature(Runner.run).parameters, "Missing turn limit")
    require(agent.tools == [setup_echo] and run_config.tracing_disabled, "Invalid setup")

    return {
        "versions": {p: importlib.metadata.version(p) for p in ("openai-agents", "openai", "pydantic")},
        "agent_constructed": True,
        "function_tool_schema_and_local_invocation": "passed",
        "lifecycle_hooks_and_turn_limit_available": True,
        "hosted_tracing_disabled": True,
        "python_network_calls_prohibited": True,
        "model_calls": 0,
    }


def check_cli() -> dict:
    require(platform.system() == "Linux" and platform.machine() in {"x86_64", "AMD64"},
            "The supplied binary requires Linux AMD64")
    starter = [ROOT / "TASK.md", ROOT / "partlab", *sorted((ROOT / "parts").glob("*.json"))]
    before = {str(p.relative_to(ROOT)): digest(p) for p in starter}
    session_existed = (ROOT / ".partlab").exists()
    session_before = file_snapshot(ROOT / ".partlab")
    checks: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="cosmon-sdk-setup-") as directory:
        work = Path(directory)
        shutil.copy2(ROOT / "partlab", work / "partlab")
        shutil.copytree(ROOT / "parts", work / "parts")

        def cli(*args: str, expected_ok: bool = True, parse_json: bool = True) -> dict:
            proc = subprocess.run(
                [str(work / "partlab"), *args], cwd=work, capture_output=True,
                text=True, timeout=15, check=False,
                env={"PATH": os.defpath, "LANG": "C.UTF-8", "TMPDIR": directory},
            )
            require(proc.returncode == (0 if expected_ok else 1), f"Unexpected exit: {args}")
            if parse_json:
                envelope = json.loads(proc.stdout)
                require(envelope.get("ok") is expected_ok, f"Unexpected envelope: {args}")
            else:
                require("Usage" in proc.stderr or "Usage" in proc.stdout, "No CLI help")
                envelope = {}
            checks.append({"argv": list(args), "exit_code": proc.returncode, "passed": True})
            return envelope

        cli("--help", parse_json=False)
        cli("list-parts")
        cli("reset")
        closed = cli("solve", expected_ok=False)
        require(closed["error_type"] == "StateError", "Closed solve did not fail as expected")
        cli("open-part", "bracket_v3")
        original = json.loads((work / "parts/bracket_v3.json").read_text())
        cli("get-parameters")
        cli("mesh")
        load = original["default_load"]
        cli("apply-load", "--direction", load["direction"], load["face_id"], str(load["force_N"]))
        solved = cli("solve")["result"]
        sf = cli("get-safety-factor")["result"]["safety_factor"]
        require(isinstance(sf, (int, float)) and math.isfinite(sf), "Non-finite safety factor")
        require(sf == solved["safety_factor"], "Solve/readback SF mismatch")
        cli("reset")
        cleared = cli("get-active-part")["result"]
        require(cleared["phase"] == "closed", "Final reset did not close state")
    require(before == {str(p.relative_to(ROOT)): digest(p) for p in starter}, "Starter changed")
    require(session_existed == (ROOT / ".partlab").exists()
            and session_before == file_snapshot(ROOT / ".partlab"), "Checkout session changed")
    return {
        "checks": checks, "part": "bracket_v3", "default_load": load,
        "observed_baseline_safety_factor": sf,
        "closed_solve_error_type": closed["error_type"],
        "temporary_directory_removed": not work.exists(),
        "checkout_session_unchanged": True, "starter_sha256": before,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Write a new preparation report; refuses overwrite")
    args = parser.parse_args()
    report = {
        "kind": "preparation_health_check", "is_agent_run": False,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "sdk": check_sdk(), "cli": check_cli(),
    }
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as f:
            f.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
