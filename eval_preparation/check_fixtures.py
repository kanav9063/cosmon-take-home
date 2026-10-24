#!/usr/bin/env python3
"""Validate synthetic fixture packaging, never evaluate task correctness."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


class InvalidFixture(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidFixture(message)


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def read_json(text: str) -> dict:
    value = json.loads(text, object_pairs_hook=unique_object)
    require(isinstance(value, dict), "JSON document must be an object")
    return value


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def indexed(items: list[dict], key: str) -> dict[str, dict]:
    require(isinstance(items, list), f"{key} collection must be a list")
    result = {}
    for item in items:
        require(isinstance(item, dict), f"{key} item must be an object")
        identifier = item[key]
        require(isinstance(identifier, str) and bool(identifier), f"invalid {key}")
        require(identifier not in result, f"duplicate {key}: {identifier}")
        result[identifier] = item
    return result


def walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)
    elif isinstance(value, float):
        require(math.isfinite(value), "non-finite number")


def check(path: Path) -> dict:
    doc = read_json(path.read_text(encoding="utf-8"))
    # Exhaust the walker even when there are no reference-bearing objects.
    objects = list(walk(doc))
    require(doc["schema_version"] == "eval-fixture-proposal/0", "unknown fixture schema")
    require(doc["source_kind"] == "synthetic", "missing synthetic label")
    require(doc["run_id"].startswith("synthetic-"), "run ID must identify synthetic data")
    require("Invented" in doc["provenance"]["safety_factor_values"], "missing invented-SF warning")
    require("No model or CLI actions" in doc["provenance"]["execution"], "missing execution warning")
    snapshots = indexed(doc["snapshots"], "snapshot_id")
    states = indexed(doc["states"], "state_id")
    solves = indexed(doc["solves"], "solve_id")
    artifacts = indexed(doc["artifacts"], "artifact_id")
    events = indexed(doc["events"], "event_id")
    require(bool(events), "no events")
    reference_maps = {
        "snapshot_id": snapshots, "baseline_snapshot_id": snapshots,
        "state_id": states, "pre_state_id": states, "post_state_id": states,
        "current_state_id": states, "solved_state_id": states, "saved_state_id": states,
        "solve_id": solves, "most_recent_solve_id": solves,
        "artifact_id": artifacts, "saved_artifact_id": artifacts,
        "event_id": events, "execution_event_id": events, "result_event_id": events,
        "guard_decision_event_id": events, "proposal_event_id": events,
        "save_result_event_id": events,
    }
    for obj in objects:
        for key, value in obj.items():
            if key in reference_maps and value is not None:
                require(value in reference_maps[key], f"dangling {key}: {value}")
    for snapshot in snapshots.values():
        actual = hashlib.sha256(canonical(snapshot["part"])).hexdigest()
        require(snapshot["sha256"] == actual, f"snapshot digest mismatch: {snapshot['snapshot_id']}")
    for artifact in artifacts.values():
        require(artifact["capture_kind"] == "synthetic_saved_snapshot", "unlabeled artifact")
        content = artifact["content_utf8"]
        require(isinstance(content, str), "artifact content must be UTF-8 text")
        require(artifact["sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest(), "artifact digest mismatch")
        list(walk(read_json(content)))
        event = events[artifact["save_result_event_id"]]
        require(event["kind"] == "cli_result" and event["data"]["action"] == "save_part", "artifact has no save result")
    calls: dict[str, list[dict]] = {}
    decisions: dict[str, list[dict]] = {}
    kinds = {"cli_execution", "cli_result", "guard_proposal", "guard_decision", "final_claim"}
    for sequence, event in enumerate(doc["events"], start=1):
        require(type(event["seq"]) is int and event["seq"] == sequence, "event sequence gap or reordering")
        require(event["run_id"] == doc["run_id"], "event run ID mismatch")
        require(event["kind"] in kinds, "unknown event kind")
        require(isinstance(event["data"], dict), "event data must be an object")
        kind, data = event["kind"], event["data"]
        if kind in {"cli_execution", "cli_result"}:
            require(isinstance(event.get("call_id"), str), "CLI event has no call ID")
            calls.setdefault(event["call_id"], []).append(event)
        if kind == "guard_decision":
            proposal = events[data["proposal_event_id"]]
            require(proposal["kind"] == "guard_proposal", "decision references wrong event kind")
            require(proposal["seq"] < sequence, "decision precedes proposal")
            require(type(data["allowed"]) is bool, "decision needs boolean allowed")
            decisions.setdefault(proposal["event_id"], []).append(event)
        if kind == "cli_execution" and "guard_decision_event_id" in data:
            decision = events[data["guard_decision_event_id"]]
            require(decision["kind"] == "guard_decision", "execution references wrong guard event")
            require(decision["seq"] < sequence, "execution precedes guard decision")
    for call_id, pair in calls.items():
        require(len(pair) == 2, f"missing or duplicate CLI call/result: {call_id}")
        execution, result = pair
        require(execution["kind"] == "cli_execution" and result["kind"] == "cli_result", f"invalid call order: {call_id}")
        require(result["data"]["execution_event_id"] == execution["event_id"], f"wrong execution link: {call_id}")
        require(result["data"]["action"] == execution["data"]["action"], f"action link mismatch: {call_id}")
        require(type(result["data"]["ok"]) is bool and type(result["data"]["exit_code"]) is int, "invalid CLI status fields")
    for event in events.values():
        if event["kind"] == "guard_proposal":
            require(len(decisions.get(event["event_id"], [])) == 1, "missing or duplicate guard decision")
    for solve_id, solve in solves.items():
        event = events[solve["result_event_id"]]
        require(event["kind"] == "cli_result" and event["data"]["action"] == "solve", "solve has wrong result link")
        require(event["data"]["result"]["solve_id"] == solve_id, "solve ID is not linked from result")
    finals = [e for e in events.values() if e["kind"] == "final_claim"]
    require(len(finals) == 1 and finals[0] == doc["events"][-1], "expected one final claim at end")
    return {"fixture_id": doc["fixture_id"], "packaging": "pass", "events": len(events), "calls": len(calls)}


def main() -> int:
    paths = [Path(arg) for arg in sys.argv[1:]] or sorted((Path(__file__).parent / "fixtures").glob("*.json"))
    if not paths:
        print(json.dumps({"packaging": "fail", "error": "no fixture files"}))
        return 1
    failures = 0
    for path in paths:
        try:
            result = check(path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            failures += 1
            result = {"file": str(path), "packaging": "fail", "error": str(error)}
        print(json.dumps(result, sort_keys=True))
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
