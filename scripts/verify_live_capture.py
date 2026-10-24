#!/usr/bin/env python3
"""Check actual SDK messages against tool/CLI capture without network access."""

import argparse
import hashlib
import json
from pathlib import Path


def audit(bundle, publication_dir=None):
    bundle = Path(bundle)
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    outcome = json.loads((bundle / "outcome.json").read_bytes())
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]

    def raw(ref):
        path = bundle / ref["path"]
        assert path.resolve().is_relative_to(bundle.resolve())
        payload = path.read_bytes()
        assert len(payload) == ref["bytes"] and hashlib.sha256(payload).hexdigest() == ref["sha256"]
        return payload

    def read(ref):
        return json.loads(raw(ref))

    def has_private_fields(value):
        if isinstance(value, dict):
            return bool(set(value) & {"log", "physics", "K_stress"}) or any(has_private_fields(v) for v in value.values())
        if isinstance(value, list):
            return any(has_private_fields(v) for v in value)
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except ValueError:
                return False
            return has_private_fields(decoded) if not isinstance(decoded, str) else False
        return False

    model_responses, tool_results = {}, {}
    raw_solve_bytes = []
    compact_solve_bytes = []
    request_count = 0
    consumed = set()
    cost = 0
    commands = {}
    proposals = {}
    for event in events:
        data, kind = event["data"], event["kind"]
        if kind == "model_requested":
            request_count += 1
            request = read(data["request_ref"])
            assert not has_private_fields(request), "Verbose log or private simulator fields entered model context"
            seen = set()
            for item in request["input"]:
                if item.get("type") == "function_call_output":
                    call_id = item["call_id"]
                    assert call_id in tool_results and item["output"] == tool_results[call_id]
                    assert call_id not in seen, "Duplicate tool result in one model input"
                    seen.add(call_id)
            assert seen == set(tool_results), "A completed tool result is missing from SDK continuation"
            consumed.update(seen)
        elif kind == "model_returned":
            response = read(data["response_ref"])
            model_responses[event["model_call_id"]] = response
            cost += (response.get("raw_usage") or {}).get("cost", 0)
        elif kind == "tool_proposed":
            proposals[event["call_id"]] = data
            matches = [item for item in model_responses[event["model_call_id"]]["output"]
                       if item.get("type") == "function_call" and item["call_id"] == event["call_id"]]
            assert len(matches) == 1
            assert matches[0]["name"] == data["name"] and matches[0]["arguments"] == data["arguments"]
        elif kind == "tool_returned":
            result = raw(data["result_ref"]).decode()
            tool_results[event["call_id"]] = result
            assert not has_private_fields(json.loads(result))
            if proposals[event["call_id"]]["name"] == "solve":
                compact_solve_bytes.append(len(result.encode()))
        elif kind == "cli_requested":
            commands[event["cli_id"]] = data["argv"][1]
        elif kind == "cli_finished" and commands[event["cli_id"]] == "solve":
            payload = raw(data["stdout_ref"])
            result = json.loads(payload)
            if result.get("ok"):
                assert isinstance(result["result"].get("log"), str) and result["result"]["log"]
                raw_solve_bytes.append(len(payload))

    assert manifest["evidence_kind"] == "live_agent"
    assert set(tool_results) == consumed, "Final tool results were not observed by the model"
    assert not set(commands.values()) & {"get-safety-factor", "get-max-stress", "get-solve-log"}
    last_response = list(model_responses.values())[-1]
    final_text = "".join(content["text"] for item in last_response["output"] if item["type"] == "message"
                         for content in item["content"] if content["type"] == "output_text")
    assert final_text == raw(outcome["final_message_ref"]).decode()
    original = raw(manifest["original"]["part_ref"])
    assert original == (Path(__file__).resolve().parents[1] / "parts" / f"{manifest['case']['part_name']}.json").read_bytes()
    for event in events:
        if event["kind"] == "artifact_published" and event["data"]["status"] == "ok":
            destination = Path(event["data"]["destination"])
            if publication_dir is not None:
                logical = Path(event["data"]["path"])
                assert logical == Path("outputs") / f"{manifest['case']['part_name']}.json"
                destination = Path(publication_dir) / logical.name
            assert destination.read_bytes() == raw(event["data"]["published_ref"])
    max_result = max((len(result.encode()) for result in tool_results.values()), default=0)
    assert max_result <= manifest["config"]["routine_result_bytes"]
    return {"status": "passed", "run_id": manifest["run_id"], "outcome": outcome["status"],
            "model_calls": request_count, "tool_calls": len(tool_results), "max_tool_result_bytes": max_result,
            "raw_solve_bytes": raw_solve_bytes, "compact_solve_bytes": compact_solve_bytes,
            "provider_reported_cost_usd": cost, "checks": ["raw_proposals_match_model_responses",
            "tool_results_match_exact_sdk_inputs", "no_duplicate_or_missing_tool_results", "no_verbose_logs_in_model_context",
            "full_logs_preserved_locally", "no_duplicate_sf_stress_log_fetch", "final_text_matches_raw_model_response",
            "original_part_unchanged", "published_bytes_match_snapshot", "compact_result_budget"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path,
                        help="Check published bytes in this trusted directory after relocating a checkout")
    args = parser.parse_args()
    results = [audit(bundle, args.publication_dir) for bundle in args.bundles]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump({"status": "passed", "runs": results}, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": "passed", "runs": len(results), "report": str(args.output)}))


if __name__ == "__main__":
    main()
