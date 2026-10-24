#!/usr/bin/env python3
"""Deterministic bounded malformed-input sweep; no model, CLI or network calls.

Exercises one changed field at a time through the full evaluator. This detects
uncaught exceptions, not every semantic error or combination of malformed data.
Synthetic numeric results remain invented test values. Temporary bundles are
removed automatically; the optional JSON result file is never overwritten.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from bundle_factory import encoded, refresh_inventory, scenario_bundle, sha256
from evaluate import evaluate_one, load_cases

VALUES = [None, True, 0, 2.5, [], {}, ["bad"], {"bad": "value"}, ""]


def jsonl(events):
    return b"".join(json.dumps(event).encode() + b"\n" for event in events)


def altered(document, path, value):
    result = deepcopy(document)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = deepcopy(value)
    return result


def evaluate_trial(bundle, case, context):
    try:
        evaluate_one(bundle, case)
        return None
    except Exception as exc:
        frame = traceback.extract_tb(exc.__traceback__)[-1]
        return {**context, "error_type": type(exc).__name__, "error": str(exc),
                "location": f"{Path(frame.filename).name}:{frame.lineno}"}


def metadata_trials(bundle, case):
    docs = {name: json.loads((bundle / name).read_bytes())
            for name in ("manifest.json", "outcome.json")}
    docs["events.jsonl"] = [json.loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]
    fields = []
    for name, doc in docs.items():
        if isinstance(doc, dict):
            fields.extend((name, [key]) for key in doc)
            for key in ("producer", "original", "case"):
                if isinstance(doc.get(key), dict):
                    fields.extend((name, [key, nested]) for nested in doc[key])
        else:
            seen = set()
            for index, event in enumerate(doc):
                if event["kind"] in seen:
                    continue
                seen.add(event["kind"])
                fields.extend((name, [index, key]) for key in event)
                for key, value in event["data"].items():
                    fields.append((name, [index, "data", key]))
                    if isinstance(value, dict):
                        fields.extend((name, [index, "data", key, nested]) for nested in value)
    count, crashes = 0, []
    for name, path in fields:
        for value in VALUES:
            changed = altered(docs[name], path, value)
            (bundle / name).write_bytes(jsonl(changed) if name.endswith("jsonl") else encoded(changed))
            refresh_inventory(bundle)
            crash = evaluate_trial(bundle, case, {"file": name, "path": path, "value": value})
            if crash:
                crashes.append(crash)
            (bundle / name).write_bytes(jsonl(docs[name]) if name.endswith("jsonl") else encoded(docs[name]))
            count += 1
    return {"trials": count, "crashes": crashes}


def envelope_trials(bundle, case):
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]
    commands = {e["cli_id"]: e["data"]["argv"][1] for e in events if e["kind"] == "cli_requested"}
    seen, fields, originals = set(), [], {}
    for event in events:
        if event["kind"] != "cli_finished" or commands[event["cli_id"]] in seen:
            continue
        command = commands[event["cli_id"]]
        seen.add(command)
        name = event["data"]["stdout_ref"]["path"]
        originals[name] = (bundle / name).read_bytes()
        doc = json.loads(originals[name])
        fields.extend((name, [key], command, doc) for key in doc)
        if isinstance(doc.get("result"), dict):
            for key, value in doc["result"].items():
                fields.append((name, ["result", key], command, doc))
                if isinstance(value, dict):
                    fields.extend((name, ["result", key, nested], command, doc) for nested in value)
    count, crashes = 0, []
    for name, path, command, doc in fields:
        for value in VALUES:
            raw = encoded(altered(doc, path, value))
            (bundle / name).write_bytes(raw)
            changed_events = deepcopy(events)
            for event in changed_events:
                ref = event["data"].get("stdout_ref")
                if isinstance(ref, dict) and ref.get("path") == name:
                    ref.update(sha256=sha256(raw), bytes=len(raw))
            (bundle / "events.jsonl").write_bytes(jsonl(changed_events))
            refresh_inventory(bundle)
            crash = evaluate_trial(bundle, case, {"command": command, "path": path, "value": value})
            if crash:
                crashes.append(crash)
            (bundle / name).write_bytes(originals[name])
            count += 1
    return {"trials": count, "crashes": crashes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "metadata", "envelopes"), default="all")
    parser.add_argument("--output", type=Path, help="Optional new JSON result path")
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("Result destination already exists")
    case = load_cases()[0]["bracket_v3"]
    result = {"method": "single-field-deterministic-type-substitution/1", "suites": {}}
    with tempfile.TemporaryDirectory(prefix="eval-malformed-") as temporary:
        for name, runner in (("metadata", metadata_trials), ("envelopes", envelope_trials)):
            if args.suite not in ("all", name):
                continue
            bundle = scenario_bundle(Path(temporary) / name)
            result["suites"][name] = runner(bundle, case)
    result["trials"] = sum(suite["trials"] for suite in result["suites"].values())
    result["crash_count"] = sum(len(suite["crashes"]) for suite in result["suites"].values())
    result["status"] = "pass" if result["crash_count"] == 0 else "fail"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write(encoded(result))
    print(encoded(result).decode(), end="")
    return 0 if result["crash_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
