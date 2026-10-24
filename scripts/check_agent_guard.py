#!/usr/bin/env python3
"""Capture a real blocked flange proposal and grade its persisted evidence."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from cosmon_agent.engine import Engine  # noqa: E402
from cosmon_agent.trace import Trace  # noqa: E402
from evaluate import evaluate_batch  # noqa: E402


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


async def capture(output: Path) -> dict:
    """Harness proposals exercise real guards/CLI without pretending to be a model."""
    trace = Trace(output / "trace")
    policy = json.loads((ROOT / "cosmon_agent/config.json").read_bytes())
    policy["evidence_kind"] = "preparation_check"
    engine = Engine(ROOT, trace, "flange_v1", policy, output / "unused-publication")
    calls = 0

    async def invoke(name: str, arguments: dict) -> dict:
        nonlocal calls
        calls += 1
        call_id = f"harness-{calls:04d}"
        trace.event("tool_proposed", {"name": name,
                    "arguments": json.dumps(arguments, separators=(",", ":"))},
                    actor="harness", call_id=call_id)
        raw = await engine.invoke(name, arguments, call_id)
        return json.loads(raw)

    try:
        await engine.setup()
        for name, arguments in (
            ("open_part", {}), ("mesh", {}),
            ("apply_load", engine.original["default_load"]), ("solve", {}),
            ("open_part", {}),
        ):
            result = await invoke(name, arguments)
            if result.get("ok") is not True:
                raise AssertionError(f"Guard test setup failed at {name}: {result}")
        state_path = engine.workdir / ".partlab/state.json"
        before = state_path.read_bytes()
        trace.write_bytes("checks/state-before.json", before)
        cli_count, revision = engine.cli_calls, engine.revision
        parameters = dict(engine.parameters)
        result = await invoke("set_parameter", {"name": "thickness_mm", "value": 5.5})
        after = state_path.read_bytes()
        trace.write_bytes("checks/state-after.json", after)
        checks = {
            "proposal_blocked": result.get("ok") is False and result.get("reason_code") == "manufacturing.constraint",
            "no_cli_dispatch": engine.cli_calls == cli_count,
            "state_bytes_unchanged": before == after,
            "engine_parameters_unchanged": parameters == engine.parameters,
            "state_revision_unchanged": revision == engine.revision,
            "no_accepted_candidate": engine.trials == [],
        }
        if not all(checks.values()):
            raise AssertionError(f"Guard regression failed: {checks}")
        outcome = engine.outcome(None)
        visible = {key: outcome[key] for key in (
            "status", "initial_sf", "final_sf", "changed_parameter", "artifact_id")}
        final_ref = trace.write_json("raw/messages/final.json", visible)
        trace.finish(engine.outcome(final_ref))
        return {"checks": checks, "blocked_result": result,
                "baseline_sf": engine.initial_sf,
                "state_sha256": hashlib.sha256(before).hexdigest(),
                "model_calls": 0, "evidence_kind": "preparation_check"}
    finally:
        await engine.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New directory for trace/, evaluation/, and verification.json")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    verification = asyncio.run(capture(output))
    inputs = output / "inputs.json"
    dump(inputs, {"inputs": [{"id": "blocked-flange", "case": "flange_v1", "path": "trace"}]})
    evaluate_batch(inputs, output / "evaluation")
    report = json.loads((output / "evaluation/report-blocked-flange.json").read_bytes())
    diagnostic = [item for item in report["diagnostics"] if item["code"] == "PROPOSAL_BLOCKED"]
    verification["checks"].update({
        "capture_integrity_passes": report["summary"]["capture_integrity"]["status"] == "pass",
        "process_compliance_passes": report["summary"]["process_compliance"]["status"] == "pass",
        "reporting_accuracy_passes": report["summary"]["reporting_accuracy"]["status"] == "pass",
        "blocked_proposal_is_diagnostic": bool(diagnostic),
    })
    verification["status"] = "passed" if all(verification["checks"].values()) else "failed"
    verification["observed_outcome"] = report["observed_outcome"]
    verification["report"] = "evaluation/report-blocked-flange.json"
    dump(output / "verification.json", verification)
    print(json.dumps(verification, indent=2))
    return 0 if verification["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
