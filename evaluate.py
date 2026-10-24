#!/usr/bin/env python3
"""Offline evaluator CLI: exit 0 means reports written, not agent success."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys

from eval_types import (Case, EVALUATOR_VERSION, InputError, canonical,
                        digest, jsonable, number, strict_json)
from trace_adapter import ADAPTERS, Limits, Reader
from eval_types import EvidenceRun
from eval_state import reconstruct
from eval_checks import evaluate

ROOT = Path(__file__).resolve().parent
WARNING_METRICS = frozenset({
    "raw_bytes", "raw_files", "events", "cli_attempts", "solve_attempts",
    "failed_cli_attempts", "model_calls", "model_request_bytes",
    "model_response_bytes", "model_visible_tool_bytes", "repeated_read_calls",
})


def validate_policy(policy=None):
    """Budgets only annotate measurements; they never relax engineering checks."""
    policy = {} if policy is None else policy
    if not isinstance(policy, dict) or set(policy) - {"warning_budgets"}:
        raise InputError("Policy supports only warning_budgets")
    budgets = policy.get("warning_budgets", {})
    if not isinstance(budgets, dict) or set(budgets) - WARNING_METRICS:
        raise InputError("Warning budgets require supported measurement names")
    if any(number(value) is None or number(value) < 0 for value in budgets.values()):
        raise InputError("Warning budgets must be finite nonnegative numbers")
    return {"warning_budgets": dict(budgets)}


def load_cases(path: str | Path = ROOT / "eval_cases.json") -> tuple[dict[str, Case], str]:
    path = Path(path).resolve()
    raw = path.read_bytes()
    config = strict_json(raw)
    if not isinstance(config, dict) or not isinstance(config.get("cases"), list):
        raise InputError("Case configuration must contain a cases array")
    cases = {}
    for entry in config["cases"]:
        if not isinstance(entry, dict):
            raise InputError("Case entry must be an object")
        name, original_path = entry.get("case_id"), entry.get("original_path")
        if not isinstance(name, str) or not name or name in cases or not isinstance(original_path, str):
            raise InputError("Cases require unique IDs and original paths")
        original_raw = (path.parent / original_path).read_bytes()
        if digest(original_raw) != entry.get("original_sha256"):
            raise InputError(f"Trusted original digest mismatch: {name}")
        original = strict_json(original_raw)
        if not isinstance(original, dict) or original.get("name") != name:
            raise InputError(f"Original identity does not match case {name}")
        material = original.get("material")
        if (type(original.get("revision")) is not int or original["revision"] < 1
            or not isinstance(material, dict) or not isinstance(material.get("name"), str)
            or not material["name"] or number(material.get("yield_MPa")) is None
            or number(material["yield_MPa"]) <= 0):
            raise InputError(f"Invalid original revision/material for {name}")
        parameters, load = original.get("parameters"), original.get("default_load")
        if (not isinstance(parameters, dict) or not parameters
            or any(number(v) is None for v in parameters.values())
            or not isinstance(load, dict) or not isinstance(load.get("face_id"), str)
            or not isinstance(load.get("direction"), str) or number(load.get("force_N")) is None):
            raise InputError(f"Invalid original parameters/default load: {name}")
        target, constraints = number(entry.get("target_sf")), entry.get("limits", {})
        if target is None or target <= 0 or not isinstance(constraints, dict):
            raise InputError(f"Invalid target or limits for {name}")
        limits = {}
        for parameter, bounds in constraints.items():
            if parameter not in parameters or not isinstance(bounds, dict) or not bounds:
                raise InputError(f"Invalid constraint parameter {parameter}")
            if any(k not in ("min", "max") or number(v) is None for k, v in bounds.items()):
                raise InputError(f"Invalid numeric bounds for {parameter}")
            limits[parameter] = {k: number(v) for k, v in bounds.items()}
            if "min" in limits[parameter] and "max" in limits[parameter] and limits[parameter]["min"] > limits[parameter]["max"]:
                raise InputError(f"Inverted bounds for {parameter}")
        output = entry.get("output_path")
        if not isinstance(output, str) or not output or Path(output).is_absolute() or ".." in Path(output).parts:
            raise InputError(f"Invalid logical output path for {name}")
        cases[name] = Case(name, original, digest(original_raw), target, limits, output)
    if not cases:
        raise InputError("No trusted cases configured")
    return cases, digest(raw)


def report_run(run, case, *, input_id="run", policy_digest="", policy=None, limits=None, adapter="partlab"):
    policy = validate_policy(policy)
    run.metrics["warning_thresholds"] = "configured" if policy["warning_budgets"] else "disabled"
    history = reconstruct(run, case)
    result = evaluate(run, history, case, policy)
    checks = []
    for check in result.checks:
        value = jsonable(check)
        value["instance_id"] = check.instance_id
        checks.append(value)
    checks.sort(key=lambda c: c["instance_id"])
    return {
        "report_version": "partlab.eval/1", "evaluator_version": EVALUATOR_VERSION,
        "profile": case.profile, "adapter": adapter, "input_id": input_id, "run_id": run.run_id,
        "source_kind": run.origin, "case_id": case.case_id,
        "input_digest": run.input_digest, "policy_digest": policy_digest,
        "configuration_digest": digest(canonical({"case_policy_digest": policy_digest,
            "warning_policy": policy, "limits": limits or Limits()})),
        "warning_policy": jsonable(policy), "resource_limits": jsonable(limits or Limits()),
        "trusted_original_sha256": case.original_sha256,
        "evaluation_status": "evaluated",
        "coverage": {"capture_complete": run.complete,
                     "execution_complete": run.execution_complete,
                     "profile_supported": run.profile_supported},
        "declared_outcome": (run.outcome or {}).get("status"),
        "observed_outcome": result.observed_outcome,
        "summary": jsonable(result.summary), "checks": checks,
        "findings": [c for c in checks if c["code"] and c["status"] in ("fail", "unknown")],
        "diagnostics": jsonable(result.diagnostics),
        "details": jsonable(result.details), "metrics": jsonable(run.metrics),
        "limitations": ["Recorded consistency under capture-authenticity assumptions; no SDK replay or model call performed."],
    }


def evaluate_one(path, case: Case, *, input_id="run", adapter="partlab", limits=None, policy_digest="", policy=None):
    policy = validate_policy(policy)
    if not isinstance(adapter, str) or adapter not in ADAPTERS:
        raise InputError(f"Unregistered adapter: {adapter}")
    run = ADAPTERS[adapter](path, case, limits)
    return report_run(run, case, input_id=input_id, policy_digest=policy_digest, policy=policy, limits=limits, adapter=adapter)


def rejected(entry, reason, *, run_id=None, policy_digest=""):
    return {
        "report_version": "partlab.eval/1", "evaluator_version": EVALUATOR_VERSION,
        "input_id": entry["id"], "case_id": entry["case"], "run_id": run_id,
        "evaluation_status": "rejected", "policy_digest": policy_digest,
        "reason": reason, "observed_outcome": "unverified", "checks": [],
        "findings": [{"code": "INPUT_REJECTED", "status": "unknown", "reason": reason}],
        "summary": {"capture_integrity": {"status": "unknown", "members": [], "reason": reason}},
    }


def _atomic(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def evaluate_batch(manifest_path, output_dir, *, cases_path=ROOT / "eval_cases.json", limits=None, policy=None):
    policy = validate_policy(policy)
    manifest_path, output_dir = Path(manifest_path).resolve(), Path(output_dir).resolve()
    cases, policy_digest = load_cases(cases_path)
    payload = strict_json(manifest_path.read_bytes())
    entries = payload.get("inputs") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise InputError("Input manifest must contain a nonempty inputs array")
    identities, prepared = set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            raise InputError("Every input entry must be an object")
        identity = entry.get("id")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", identity) or identity in identities:
            raise InputError("Input IDs must be unique safe names of 1-120 characters")
        identities.add(identity)
        if not isinstance(entry.get("case"), str) or entry["case"] not in cases or not isinstance(entry.get("path"), str):
            raise InputError(f"Input {identity} requires a known trusted case and path")
        adapter = entry.get("adapter", "partlab")
        if not isinstance(adapter, str) or adapter not in ADAPTERS:
            raise InputError(f"Unregistered adapter: {adapter}")
        source = (manifest_path.parent / entry["path"]).resolve()
        if output_dir == source or output_dir in source.parents or source in output_dir.parents:
            raise InputError("Report destination must not overlap input evidence")
        prepared.append({**entry, "source": source, "adapter": adapter})
    if output_dir.exists():
        raise InputError("Report destination already exists; choose a new directory")

    # Small preflight identities ensure duplicate rejection is independent of input order.
    runs = {}
    preliminary_errors = {}
    for entry in prepared:
        try:
            raw, _ = Reader(entry["source"], limits or Limits(), EvidenceRun(entry["source"])).read("manifest.json")
            data = strict_json(raw)
            run_id = data.get("run_id") if isinstance(data, dict) else None
            if isinstance(run_id, str) and run_id:
                runs.setdefault(run_id, []).append(entry["id"])
        except (InputError, OSError, RecursionError) as exc:
            preliminary_errors[entry["id"]] = str(exc)
    duplicate_ids = {identity: run_id for run_id, ids in runs.items() if len(ids) > 1 for identity in ids}
    output_dir.mkdir(parents=True)
    evaluated, rejected_count = 0, 0
    dimension_counts: dict[str, Counter] = {}
    results = []
    try:
        for entry in sorted(prepared, key=lambda e: e["id"]):
            if entry["id"] in duplicate_ids:
                report = rejected(entry, "Duplicate run ID across manifest entries", run_id=duplicate_ids[entry["id"]], policy_digest=policy_digest)
            elif entry["id"] in preliminary_errors:
                report = rejected(entry, preliminary_errors[entry["id"]], policy_digest=policy_digest)
            else:
                report = evaluate_one(entry["source"], cases[entry["case"]], input_id=entry["id"],
                                      adapter=entry["adapter"], limits=limits, policy_digest=policy_digest, policy=policy)
            if report["evaluation_status"] == "rejected":
                rejected_count += 1
            else:
                evaluated += 1
            _atomic(output_dir / f"report-{entry['id']}.json", report)
            results.append({"input_id": entry["id"], "report": f"report-{entry['id']}.json",
                            "status": report["evaluation_status"]})
            for dimension, value in report["summary"].items():
                status = value.get("status", "unknown") if isinstance(value, dict) else value
                dimension_counts.setdefault(dimension, Counter())[str(status)] += 1
        summary = {"report_version": "partlab.eval-batch/1", "status": "complete",
                   "requested": len(prepared), "evaluated": evaluated,
                   "explicitly_rejected": rejected_count, "policy_digest": policy_digest,
                   "warning_policy": jsonable(policy), "resource_limits": jsonable(limits or Limits()),
                   "dimensions": {k: dict(v) for k, v in sorted(dimension_counts.items())},
                   "reports": results}
        _atomic(output_dir / "summary.json", summary)
        return summary
    except Exception:
        # Preserve evidence of an evaluator/output failure; never turn it into a trace finding.
        remaining = sorted(identities - {item["input_id"] for item in results})
        try:
            _atomic(output_dir / "aborted.json", {"status": "aborted", "written": results,
                                                  "unevaluated": remaining})
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=ROOT / "eval_cases.json")
    parser.add_argument("--limits", type=Path, help="Optional trusted JSON overrides for resource limits")
    parser.add_argument("--policy", type=Path, help="Optional trusted JSON diagnostic warning budgets")
    args = parser.parse_args(argv)
    try:
        overrides = strict_json(args.limits.read_bytes()) if args.limits else {}
        if not isinstance(overrides, dict) or set(overrides) - set(Limits.__dataclass_fields__):
            raise InputError("Unknown resource limit setting")
        limits = Limits(**overrides)
        policy = strict_json(args.policy.read_bytes()) if args.policy else None
        summary = evaluate_batch(args.inputs, args.output_dir, cases_path=args.cases, limits=limits, policy=policy)
    except (InputError, OSError, RecursionError) as exc:
        print(f"EVALUATOR ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"INTERNAL EVALUATOR ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: summary[k] for k in ("status", "requested", "evaluated", "explicitly_rejected")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
