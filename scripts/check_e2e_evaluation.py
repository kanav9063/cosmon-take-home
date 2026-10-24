#!/usr/bin/env python3
"""Evaluate captures and explicit synthetic derivatives without any API calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
from evaluate import evaluate_batch  # noqa: E402


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def reference(root: Path, relative: str, raw: bytes) -> dict:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def refresh(root: Path, events: list[dict], status: str) -> None:
    manifest = json.loads((root / "manifest.json").read_bytes())
    for seq, event in enumerate(events, 1):
        event["seq"] = seq
        event["run_id"] = manifest["run_id"]
    (root / "events.jsonl").write_bytes(b"".join(
        (json.dumps(event, sort_keys=True, allow_nan=False) + "\n").encode()
        for event in events))
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "completion.json":
            continue
        raw = path.read_bytes()
        files[path.relative_to(root).as_posix()] = {
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    write(root / "completion.json", {"run_id": manifest["run_id"], "status": status,
          "event_count": len(events), "last_seq": len(events), "files": files})


def copy_derivative(source: Path, target: Path, kind: str) -> tuple[dict, list[dict]]:
    """Keep originals immutable and label every edited trace as synthetic."""
    shutil.copytree(source, target, symlinks=False)
    manifest_raw = (source / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    original_run_id = manifest["run_id"]
    manifest["run_id"] = f"synthetic-{kind}-{original_run_id}"
    manifest["evidence_kind"] = "synthetic_fixture"
    manifest["capture"] = {"description":
        "Synthetic derivative of a persisted capture; edited events are not live execution.",
        "source_run_id": original_run_id, "mutation": kind}
    write(target / "manifest.json", manifest)
    write(target / "DERIVATION.json", {
        "kind": kind, "source_run_id": original_run_id,
        "source_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "source_events_sha256": hashlib.sha256((source / "events.jsonl").read_bytes()).hexdigest(),
        "synthetic": True, "source_unchanged": True})
    events = [json.loads(line) for line in (target / "events.jsonl").read_bytes().splitlines()]
    return manifest, events


def selected_save(root: Path, events: list[dict]) -> tuple[dict, dict]:
    outcome = json.loads((root / "outcome.json").read_bytes())
    if outcome.get("status") != "repaired":
        raise ValueError("Derivative source must report a repaired outcome")
    saved = next(event for event in events if event["kind"] == "artifact_saved"
                 and event["data"]["artifact_id"] == outcome["artifact_id"])
    request = next(event for event in events if event["kind"] == "cli_requested"
                   and event["cli_id"] == saved["data"]["save_cli_id"])
    return saved, request


def stale_derivative(source: Path, target: Path) -> None:
    manifest, events = copy_derivative(source, target, "stale-solve")
    saved, save_request = selected_save(target, events)
    artifact_path = saved["data"]["artifact_ref"]["path"]
    artifact = json.loads((target / artifact_path).read_bytes())
    outcome = json.loads((target / "outcome.json").read_bytes())
    parameter = outcome["changed_parameter"]["name"]
    value = artifact["parameters"][parameter]
    cli_id = "synthetic-stale-assignment"
    if any(event.get("cli_id") == cli_id for event in events):
        raise ValueError("Synthetic CLI ID would collide")
    stdout = reference(target, "raw/cli/synthetic-stale.stdout", encoded({
        "ok": True, "result": {"name": parameter, "previous_value": value,
        "new_value": value, "downstream_invalidated": True}}))
    stderr = reference(target, "raw/cli/synthetic-stale.stderr", b"")
    base = {"run_id": manifest["run_id"], "actor": "synthetic_fixture",
            "session_id": save_request.get("session_id", "main"),
            "trial_id": save_request.get("trial_id"), "call_id": None, "cli_id": cli_id}
    command = {"argv": [save_request["data"]["argv"][0], "set-parameter", parameter, str(value)],
               "cwd": save_request["data"].get("cwd", "/synthetic"), "attempt": 1,
               "purpose": "Synthetic same-value mutation invalidating the selected solve"}
    inserted = [dict(base, event_id=f"synthetic-stale-{i}", kind=kind, data=data)
                for i, (kind, data) in enumerate((
                    ("cli_requested", command), ("cli_started", {}),
                    ("cli_finished", {"stdout_ref": stdout, "stderr_ref": stderr,
                                      "exit_code": 0, "termination": "exit"})), 1)]
    insertion = events.index(save_request)
    if save_request.get("call_id"):
        insertion = next(i for i, event in enumerate(events)
                         if event["kind"] == "tool_proposed"
                         and event.get("call_id") == save_request["call_id"])
    events[insertion:insertion] = inserted
    refresh(target, events, "completed")


def refs_in(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        if {"path", "sha256", "bytes"}.issubset(value) and isinstance(value["path"], str):
            found.add(value["path"])
        for child in value.values():
            found.update(refs_in(child))
    elif isinstance(value, list):
        for child in value:
            found.update(refs_in(child))
    return found


def interrupted_derivative(source: Path, target: Path) -> None:
    manifest, events = copy_derivative(source, target, "interrupted")
    _, save_request = selected_save(target, events)
    cut = next(i for i, event in enumerate(events) if event["kind"] == "cli_started"
               and event.get("cli_id") == save_request["cli_id"]) + 1
    events = events[:cut]
    keep = refs_in(manifest) | refs_in(events) | {"manifest.json", "events.jsonl", "DERIVATION.json"}
    for path in target.rglob("*"):
        if path.is_file() and path.relative_to(target).as_posix() not in keep:
            path.unlink()
    refresh(target, events, "interrupted")


def run(inputs: Path, output: Path) -> dict:
    payload = json.loads(inputs.read_bytes())
    entries = payload["inputs"] if isinstance(payload, dict) else payload
    normalized = [dict(entry, path=str((inputs.parent / entry["path"]).resolve())) for entry in entries]
    seed = next((Path(entry["path"]) for entry in normalized
                 if json.loads((Path(entry["path"]) / "outcome.json").read_bytes()).get("status") == "repaired"), None)
    if seed is None:
        raise ValueError("At least one completed repaired capture is required for derivatives")
    output.mkdir(parents=True, exist_ok=False)
    derivative_root = output / "derivatives"
    derivative_root.mkdir()
    stale, interrupted = derivative_root / "stale-solve", derivative_root / "interrupted"
    stale_derivative(seed, stale)
    interrupted_derivative(seed, interrupted)
    seed_case = next(entry["case"] for entry in normalized if Path(entry["path"]) == seed)
    combined = normalized + [
        {"id": "synthetic-stale", "path": str(stale), "case": seed_case},
        {"id": "synthetic-interrupted", "path": str(interrupted), "case": seed_case}]
    manifest = output / "inputs.json"
    reverse = output / "inputs-reversed.json"
    write(manifest, {"inputs": combined})
    write(reverse, {"inputs": list(reversed(combined))})
    evaluate_batch(manifest, output / "reports")
    evaluate_batch(reverse, output / "reports-repeat")
    first, second = output / "reports", output / "reports-repeat"
    equal = all((second / path.name).read_bytes() == path.read_bytes() for path in first.glob("*.json"))
    stale_report = json.loads((first / "report-synthetic-stale.json").read_bytes())
    interrupted_report = json.loads((first / "report-synthetic-interrupted.json").read_bytes())
    stale_caught = any(item["code"] == "STALE_SOLVE" and item["status"] == "fail"
                       for item in stale_report["findings"])
    stale_integrity = stale_report["summary"]["capture_integrity"]["status"] == "pass"
    incomplete = (interrupted_report["coverage"]["capture_complete"] is False
                  and interrupted_report["coverage"]["execution_complete"] is False
                  and interrupted_report["summary"]["repair_achievement"]["status"] != "pass")
    source_reports = {entry["id"]: json.loads((first / f"report-{entry['id']}.json").read_bytes())
                      for entry in normalized}
    checks = {"report_determinism_and_order_independence": equal,
              "stale_solve_detected": stale_caught,
              "stale_capture_integrity_passes": stale_integrity,
              "interrupted_capture_is_incomplete": incomplete}
    for dimension in ("capture_integrity", "process_compliance", "reporting_accuracy"):
        checks[f"source_{dimension}_passes"] = all(
            report["summary"][dimension]["status"] == "pass"
            for report in source_reports.values())
    checks["source_outcomes_are_verified"] = all(
        report["observed_outcome"] in {"repaired", "already_safe", "search_exhausted"}
        for report in source_reports.values())
    result = {"status": "passed" if all(checks.values()) else "failed",
              "checks": checks,
              "source_results": {key: {"observed_outcome": report["observed_outcome"],
                   "summary": {name: value["status"] for name, value in report["summary"].items()}}
                   for key, report in source_reports.items()},
              "derivatives_are_synthetic": True}
    write(output / "verification.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.inputs.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
