#!/usr/bin/env python3
"""Evaluate every planned benchmark run and compare observed evidence offline."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
from evaluate import evaluate_batch  # noqa: E402


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def events_at(bundle):
    events, malformed = [], 0
    try:
        lines = (bundle / "events.jsonl").read_text().splitlines()
    except OSError:
        return events, malformed
    for line in lines:
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("event object required")
            events.append(event)
        except ValueError:
            malformed += 1
    return events, malformed


def dimension(report, name):
    value = report.get("summary", {}).get(name, "unknown")
    return value.get("status", "unknown") if isinstance(value, dict) else value


def elapsed(events, metadata):
    for key in ("elapsed_seconds", "duration_seconds"):
        if finite(metadata.get(key)):
            return metadata[key], "runner_wall_clock"
    try:
        stamps = [datetime.fromisoformat(e["time"].replace("Z", "+00:00")) for e in events if e.get("time")]
        if len(stamps) >= 2:
            return (max(stamps) - min(stamps)).total_seconds(), "captured_event_span"
    except (ValueError, TypeError):
        pass
    return None, "unavailable"


def category(outcome, events, report, metadata):
    status = outcome.get("status")
    reason = str(outcome.get("reason_code", ""))
    if any(e.get("kind") == "model_failed" for e in events):
        return "run_timeout" if reason == "run_timeout" else "provider_or_model_request_failure"
    if status == "execution_failure":
        if "final" in reason or "claim" in reason:
            return "reporting_failure"
        if any(e.get("kind") == "cli_finished" and (
            e.get("data", {}).get("exit_code") != 0 or e.get("data", {}).get("termination") != "exit"
        ) for e in events):
            return "cli_execution_failure"
        return "run_timeout" if "timeout" in reason.lower() else "runner_or_budget_failure"
    if status in ("repaired", "already_safe", "no_repair_found"):
        valid = all(dimension(report, key) == "pass" for key in (
            "capture_integrity", "process_compliance", "reporting_accuracy"
        ))
        if not valid:
            return "result_not_independently_verified"
        if status == "repaired":
            return "verified_repair" if dimension(report, "repair_achievement") == "pass" else "repair_not_verified"
        return "verified_original_safe" if status == "already_safe" else "bounded_search_no_repair"
    if metadata.get("error_category"):
        return "launcher_or_runner_failure"
    return "incomplete_or_not_started"


def collect(entry, base, metadata, report):
    bundle = (base / entry["path"]).resolve()
    manifest = read_json(bundle / "manifest.json", {}) or {}
    outcome = read_json(bundle / "outcome.json", {}) or {}
    events, malformed = events_at(bundle)
    counts = Counter(e.get("kind") for e in events)
    responses = [e.get("data", {}) for e in events if e.get("kind") == "model_returned"]
    requests = [e.get("data", {}) for e in events if e.get("kind") == "model_requested"]
    config = manifest.get("config", {})
    model_config = config.get("_model_config", {})
    model = model_config.get("model") or (requests[0].get("model") if requests else None) or metadata.get("model") or entry.get("model") or entry["id"]
    costs = [r.get("raw_usage", {}).get("cost") for r in responses if isinstance(r.get("raw_usage"), dict)]
    costs = [value for value in costs if finite(value)]
    tokens = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        values = [r.get("usage", {}).get(key) for r in responses]
        known = [value for value in values if finite(value)]
        tokens[key] = sum(known) if known else None
    seconds, timing_source = elapsed(events, metadata)
    return {
        "id": entry["id"], "part": entry["case"], "model": model,
        "bundle": entry["path"], "run_id": manifest.get("run_id"),
        "launcher_status": metadata.get("status"), "launcher_error_category": metadata.get("error_category"),
        "declared_outcome": outcome.get("status"), "reason_code": outcome.get("reason_code"),
        "observed_outcome": report.get("observed_outcome", "unverified"),
        "result_category": category(outcome, events, report, metadata),
        "baseline_sf": outcome.get("initial_sf"), "best_or_final_sf": outcome.get("final_sf"),
        "changed_parameter": outcome.get("changed_parameter"),
        "evaluation": {key: dimension(report, key) for key in (
            "capture_integrity", "process_compliance", "reporting_accuracy", "repair_achievement", "final_correctness", "delivery"
        )},
        "evaluation_status": report.get("evaluation_status", "unavailable"),
        "evaluation_findings": [{key: finding.get(key) for key in ("code", "status", "reason")}
                                for finding in report.get("findings", [])],
        "elapsed_seconds": seconds, "timing_source": timing_source,
        "model_requests": counts["model_requested"], "model_responses": counts["model_returned"],
        "model_failures": [e.get("data", {}) for e in events if e.get("kind") == "model_failed"],
        "tool_proposals": counts["tool_proposed"], "tool_returns": counts["tool_returned"],
        "cli_requests": counts["cli_requested"], "cli_completions": counts["cli_finished"],
        "trial_count": len(outcome.get("search", {}).get("trials", [])),
        "provider_reported_cost_usd": sum(costs) if costs else None,
        "costed_responses": len(costs), "cost_complete_for_returned_responses": bool(responses) and len(costs) == len(responses),
        "tokens_from_returned_responses": tokens,
        "completion_present": (bundle / "completion.json").is_file(), "malformed_event_lines": malformed,
        "prompt_sha256": model_config.get("prompt_sha256"), "tool_schema_sha256": model_config.get("tool_schema_sha256"),
        "reasoning_effort": model_config.get("reasoning_effort"),
        "policy": {key: config.get(key) for key in (
            "max_trials", "max_model_turns", "max_tool_calls", "run_timeout_seconds", "model_timeout_seconds", "cli_timeout_seconds", "max_output_tokens", "exploration_ranges"
        )},
    }


def text_value(value):
    return "—" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


def markdown(summary):
    lines = ["# Model benchmark observations", "", summary["interpretation"], "",
             "C/P/R/A = capture integrity / process compliance / reporting accuracy / repair achievement.", "",
             "| Model | Part | Result | Baseline → best/final SF | C/P/R/A | Seconds | Model/tool/CLI calls | USD observed | Tokens in/out |",
             "| --- | --- | --- | --- | --- | ---: | --- | ---: | --- |"]
    for row in summary["runs"]:
        ev, tok = row["evaluation"], row["tokens_from_returned_responses"]
        values = [row["model"], row["part"], row["result_category"],
                  f"{text_value(row['baseline_sf'])} → {text_value(row['best_or_final_sf'])}",
                  "/".join(ev[key] for key in ("capture_integrity", "process_compliance", "reporting_accuracy", "repair_achievement")),
                  None if row["elapsed_seconds"] is None else round(row["elapsed_seconds"], 2),
                  f"{row['model_requests']}/{row['tool_returns']}/{row['cli_requests']}",
                  None if row["provider_reported_cost_usd"] is None else f"{row['provider_reported_cost_usd']:.7f}",
                  f"{text_value(tok['input_tokens'])}/{text_value(tok['output_tokens'])}"]
        lines.append("| " + " | ".join(text_value(value) for value in values) + " |")
    lines += ["", "Model requests include failures; tool counts are captured returns; CLI counts include internal verification reads.", "",
              "Elapsed time uses runner wall time when available, otherwise the captured event span. Unknown costs are not treated as zero; failed requests may have unreported charges.", "",
              f"Independent evaluator reports: [{summary['evaluation_directory']}/]({summary['evaluation_directory']}/)", "",
              "## Limits", ""]
    lines.extend("- " + item for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Benchmark directory containing inputs.json")
    args = parser.parse_args(argv)
    base = args.input.resolve()
    manifest = read_json(base / "inputs.json")
    entries = manifest.get("inputs") if isinstance(manifest, dict) else manifest
    if not isinstance(entries, list) or not entries:
        parser.error("inputs.json must contain a nonempty inputs array")
    raw_results = read_json(base / "results.json", {})
    result_rows = raw_results.get("runs", raw_results.get("results", [])) if isinstance(raw_results, dict) else raw_results
    result_rows = result_rows if isinstance(result_rows, list) else []
    metadata = {row.get("id", row.get("input_id")): row for row in result_rows if isinstance(row, dict)}
    evaluation_dir = base / ("evaluation-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6])
    batch = evaluate_batch(base / "inputs.json", evaluation_dir)
    reports = {item["input_id"]: read_json(evaluation_dir / item["report"], {}) for item in batch["reports"]}
    rows = [collect(entry, base, metadata.get(entry["id"], {}), reports.get(entry["id"], {})) for entry in entries]
    groups = defaultdict(list)
    for row in rows:
        groups[row["model"]].append(row)
    totals = []
    for model, group in groups.items():
        known_costs = [row["provider_reported_cost_usd"] for row in group if row["provider_reported_cost_usd"] is not None]
        totals.append({"model": model, "planned_runs": len(group),
                       "result_categories": dict(Counter(row["result_category"] for row in group)),
                       "observed_cost_usd": sum(known_costs) if known_costs else None,
                       "runs_with_reported_cost": len(known_costs)})
    summary = {
        "schema_version": "partlab.model-comparison/1", "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_runs": len(entries), "runs": rows, "models": totals,
        "evaluation_directory": evaluation_dir.name, "evaluator": batch.get("evaluator"),
        "interpretation": "One observed run per model and assigned part. A truthful bounded flange search with no repair is distinct from a provider, execution or reporting failure. Repair achievement is reported separately; no overall model ranking is inferred.",
        "limitations": [
            "Single stochastic runs do not establish reliability, statistical significance or a universal quality ranking.",
            "No repair found within configured ranges and trials is not a proof of infeasibility. The flange outcome is not assumed in advance.",
            "Provider routing, caching, supported reasoning behavior and transient load can affect latency, tokens and cost despite shared harness settings.",
            "Costs and tokens include only usage exposed in captured responses; failed requests may be unbilled or unreported, not necessarily free.",
            "Independent evaluation verifies recorded evidence consistency without replaying the solver or calling a model.",
            "Missing or unfinished planned runs remain listed and unverified. Raw trace bundles are never rewritten by this summary.",
        ],
    }
    (base / "comparison.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (base / "comparison.md").write_text(markdown(summary))
    print(json.dumps({"planned_runs": len(rows), "comparison": str(base / "comparison.md"), "evaluation": str(evaluation_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
