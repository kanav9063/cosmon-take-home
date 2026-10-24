#!/usr/bin/env python3
"""Compare model IDs using the existing, unchanged PartLab agent harness."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cosmon_agent.agent import DEFAULT_POLICY, load_config, load_policy, run_agent

DEFAULT_MODELS = [
    "openai/gpt-6.1-sol", "openai/gpt-6-luna", "anthropic/claude-sonnet-5.5",
    "anthropic/claude-haiku-5.5", "deepseek/deepseek-v4.1-flash-1017",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def trace_metrics(path):
    metrics = {"model_calls": 0, "tool_calls": 0, "cli_calls": 0,
               "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
               "reported_cost_usd": None, "cost_reported_calls": 0,
               "model_returned_calls": 0, "incomplete_event_lines": 0}
    event_path = path / "events.jsonl"
    if not event_path.exists():
        return metrics
    for line in event_path.read_text().splitlines():
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            metrics["incomplete_event_lines"] += 1
            continue
        kind = event.get("kind")
        for expected, key in (("model_requested", "model_calls"), ("tool_returned", "tool_calls"), ("cli_requested", "cli_calls")):
            if kind == expected:
                metrics[key] += 1
        if kind != "model_returned":
            continue
        metrics["model_returned_calls"] += 1
        data = event.get("data", {})
        usage = data.get("usage") or {}
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if type(value) in (int, float) and math.isfinite(value):
                metrics[key] += value
        raw_usage = data.get("raw_usage") or {}
        cost = raw_usage.get("cost")
        if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
            metrics["reported_cost_usd"] = (metrics["reported_cost_usd"] or 0) + cost
            metrics["cost_reported_calls"] += 1
    return metrics


async def benchmark(args, config, policy):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows = []
    for model_index, model in enumerate(args.models):
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", model).strip("-")
        for part in args.parts:
            for repeat in range(1, args.repeats + 1):
                run_name = f"{model_index + 1:02d}-{slug}-{part}-r{repeat}"
                rows.append({"id": run_name, "index": len(rows), "model": model, "part": part, "repeat": repeat,
                             "run_path": f"runs/{run_name}", "artifact_dir": f"artifacts/{run_name}",
                             "status": "pending", "outcome": None, "metrics": None, "wall_seconds": None,
                             "elapsed_seconds": None, "error_category": None})
    write_json(output / "inputs.json", {"inputs": [
        {"id": row["id"], "path": row["run_path"], "case": row["part"], "model": row["model"]}
        for row in rows
    ], "reasoning_effort": "medium"})
    write_json(output / "manifest.json", {
        "kind": "model_benchmark", "created_at": now(), "models": args.models,
        "parts": args.parts, "repeats": args.repeats, "concurrency": args.concurrency,
        "policy": policy, "reasoning_effort": "medium", "provider": "openrouter",
        "budget_target_usd": args.budget_usd,
        "budget_semantics": "Observed-cost target, not a hard cap. Queued runs stop after completed reported cost reaches target; in-flight runs and unreported costs can exceed it.",
        "harness_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                           for name in ("cosmon_agent/agent.py", "cosmon_agent/engine.py", "cosmon_agent/trace.py")},
    })

    def observed_cost():
        costs = [row["metrics"]["reported_cost_usd"] for row in rows
                 if row["metrics"] and row["metrics"]["reported_cost_usd"] is not None]
        return sum(costs) if costs else None

    def save_results():
        write_json(output / "results.json", {
            "updated_at": now(), "wall_seconds": time.monotonic() - started,
            "budget_target_usd": args.budget_usd, "observed_reported_cost_usd": observed_cost(),
            "budget_is_hard_cap": False,
            "completed_runs": sum(row["status"] not in {"pending", "running"} for row in rows),
            "planned_runs": len(rows), "runs": rows,
        })

    semaphore = asyncio.Semaphore(args.concurrency)
    save_results()

    async def one(row):
        async with semaphore:
            cost = observed_cost()
            if cost is not None and cost >= args.budget_usd:
                row["status"] = "skipped_budget_target"
                save_results()
                print(json.dumps({"model": row["model"], "part": row["part"], "status": row["status"]}), flush=True)
                return
            row["status"] = "running"
            row["started_at"] = now()
            save_results()
            run_started = time.monotonic()
            try:
                run_config = {**config, "OPENROUTER_MODEL": row["model"], "OPENROUTER_REASONING_EFFORT": "medium"}
                outcome = await run_agent(row["part"], output / row["run_path"], run_config,
                                          policy, publish_dir=output / row["artifact_dir"])
                row["outcome"] = outcome
                row["status"] = outcome["status"]
            except (Exception, asyncio.CancelledError) as error:
                row["status"] = "cancelled" if isinstance(error, asyncio.CancelledError) else "execution_failure"
                row["error_category"] = type(error).__name__
            finally:
                row["wall_seconds"] = time.monotonic() - run_started
                row["elapsed_seconds"] = row["wall_seconds"]
                row["finished_at"] = now()
                row["metrics"] = trace_metrics(output / row["run_path"])
                save_results()
                print(json.dumps({"model": row["model"], "part": row["part"], "repeat": row["repeat"],
                                  "status": row["status"], "wall_seconds": round(row["wall_seconds"], 2),
                                  "cost_usd": row["metrics"]["reported_cost_usd"]}), flush=True)

    await asyncio.gather(*(one(row) for row in rows))
    save_results()
    print(json.dumps({"output": str(output), "runs": len(rows), "observed_reported_cost_usd": observed_cost(),
                      "wall_seconds": round(time.monotonic() - started, 2)}), flush=True)
    return int(any(row["status"] in {"execution_failure", "cancelled", "skipped_budget_target", "pending", "running"} for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--parts", nargs="+", default=["bracket_v3", "flange_v1"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--budget-usd", type=float, default=5.0, help="Observed-cost target; in-flight runs can exceed it")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()
    if args.concurrency < 1 or args.repeats < 1 or not math.isfinite(args.budget_usd) or args.budget_usd <= 0:
        parser.error("Concurrency, repeats and budget target must be positive")
    if any(not re.fullmatch(r"[a-zA-Z0-9_-]+", part) for part in args.parts):
        parser.error("Part names must be simple identifiers")
    if len(set(args.parts)) != len(args.parts):
        parser.error("Part names must be unique")
    try:
        config = load_config(args.env_file)
        policy = load_policy(args.policy)
        if any(part not in policy["exploration_ranges"] for part in args.parts):
            raise ValueError("Missing configured part")
        return asyncio.run(benchmark(args, config, policy))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({"status": "benchmark_error", "error_category": type(error).__name__}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
