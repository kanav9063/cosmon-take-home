#!/usr/bin/env python3
"""Audit native Anthropic HTTP/message evidence offline, without API calls."""

import argparse
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def private_fields(value):
    if isinstance(value, dict):
        return bool(set(value) & {"log", "physics", "K_stress"}) or any(private_fields(v) for v in value.values())
    if isinstance(value, list):
        return any(private_fields(v) for v in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return False
        return not isinstance(decoded, str) and private_fields(decoded)
    return False


def text_content(content):
    if isinstance(content, str):
        return content
    require(isinstance(content, list), "tool_result content must be a string or text-block list")
    require(all(isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str) for b in content),
            "Unexpected non-text block in a tool_result")
    return "".join(block["text"] for block in content)


def audit(bundle, publication_dir=None):
    bundle = Path(bundle).resolve()

    def payload(ref):
        relative = Path(ref["path"])
        path = (bundle / relative).resolve()
        require(not relative.is_absolute() and path.is_relative_to(bundle), "Evidence path escapes bundle")
        raw = path.read_bytes()
        require(len(raw) == ref["bytes"], f"Byte count mismatch: {relative}")
        require(hashlib.sha256(raw).hexdigest() == ref["sha256"], f"Hash mismatch: {relative}")
        return raw

    def read(ref):
        return json.loads(payload(ref))

    manifest = json.loads((bundle / "manifest.json").read_bytes())
    outcome = json.loads((bundle / "outcome.json").read_bytes())
    completion = json.loads((bundle / "completion.json").read_bytes())
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]
    require(manifest.get("evidence_kind") == "live_agent", "Expected a live-agent evidence bundle")
    run_id = manifest["run_id"]
    require(outcome.get("run_id") == completion.get("run_id") == run_id, "Run identity mismatch")
    require(completion.get("status") == "completed", "Completion inventory is not terminal")
    require(completion.get("event_count") == completion.get("last_seq") == len(events), "Completion event count mismatch")
    require([e.get("seq") for e in events] == list(range(1, len(events) + 1)), "Non-contiguous event sequence")
    require(all(e.get("run_id") == run_id for e in events), "Event run identity mismatch")
    require(len({e.get("event_id") for e in events}) == len(events), "Duplicate event IDs")
    files = completion["files"]
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()} - {"completion.json"}
    require(set(files) == actual, "Completion inventory does not cover exactly the bundle files")
    for relative, ref in files.items():
        payload({**ref, "path": relative})

    native_calls, proposals, tool_results, responses = {}, {}, {}, {}
    requests, consumed, commands = {}, set(), {}
    raw_solve_bytes, compact_solve_bytes = [], []
    for event in events:
        data, kind = event["data"], event["kind"]
        model_id, call_id = event.get("model_call_id"), event.get("call_id")
        if kind == "model_requested":
            require(model_id not in requests, "Duplicate model request ID")
            request = read(data["request_ref"])
            require(isinstance(request.get("messages"), list), "Native HTTP request lacks messages")
            require(not private_fields(request), "Verbose log or simulator physics entered model context")
            requests[model_id] = request
            seen = set()
            for message in request["messages"]:
                content = message.get("content", [])
                if isinstance(content, str):
                    continue
                for block in content:
                    if block.get("type") == "tool_result":
                        used_id = block.get("tool_use_id")
                        require(used_id in tool_results, "Native tool_result has no previously captured return")
                        require(used_id not in seen, "Duplicate native tool_result in one request")
                        require(text_content(block.get("content")) == tool_results[used_id], "Native tool_result differs from captured exact string")
                        seen.add(used_id)
                    elif block.get("type") == "tool_use":
                        used_id = block.get("id")
                        require(used_id in native_calls, "Historical tool_use has no prior response")
                        require(block == native_calls[used_id]["block"], "Historical tool_use changed in continuation")
            require(seen == set(tool_results), "Completed tool returns missing from native continuation")
            consumed.update(seen)
        elif kind == "model_returned":
            require(model_id in requests and model_id not in responses, "Response request association is invalid")
            response = read(data["response_ref"])
            require(isinstance(response.get("content"), list), "Native HTTP response lacks content blocks")
            responses[model_id] = response
            for block in response["content"]:
                if block.get("type") == "tool_use":
                    used_id = block.get("id")
                    require(isinstance(used_id, str) and used_id not in native_calls, "Duplicate/missing native tool-use ID")
                    native_calls[used_id] = {"block": block, "model_id": model_id}
        elif kind == "tool_proposed":
            require(call_id in native_calls and call_id not in proposals, "Proposal missing or duplicating native tool use")
            native = native_calls[call_id]
            require(native["model_id"] == model_id, "Proposal linked to wrong native response")
            require(data["name"] == native["block"]["name"], "Normalized proposal name mismatch")
            canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            require(canonical(json.loads(data["arguments"])) == canonical(native["block"]["input"]),
                    "Normalized proposal arguments differ from native object")
            require(data.get("arguments_format") == "canonical_json_from_native_object", "Native normalization must be explicitly labelled")
            require(canonical(data.get("native_input")) == canonical(native["block"]["input"]), "Captured native_input mismatch")
            proposals[call_id] = data
        elif kind == "tool_returned":
            require(call_id in proposals and call_id not in tool_results, "Return missing or duplicating proposal")
            result = payload(data["result_ref"]).decode()
            require(not private_fields(result), "Private simulator fields in compact tool result")
            tool_results[call_id] = result
            if proposals[call_id]["name"] == "solve":
                compact_solve_bytes.append(len(result.encode()))
        elif kind == "cli_requested":
            commands[event["cli_id"]] = data["argv"][1]
        elif kind == "cli_finished":
            raw = payload(data["stdout_ref"])
            payload(data["stderr_ref"])
            if commands.get(event["cli_id"]) == "solve" and data.get("exit_code") == 0:
                solved = json.loads(raw)
                if solved.get("ok"):
                    require(isinstance(solved["result"].get("log"), str) and bool(solved["result"]["log"]), "Full solver log missing from raw stdout")
                    raw_solve_bytes.append(len(raw))

    require(set(native_calls) == set(proposals), "Native tool use missing normalized proposal")
    require(not set(commands.values()) & {"get-safety-factor", "get-max-stress", "get-solve-log"}, "Redundant solver output fetch")
    final_ref = outcome.get("final_message_ref")
    if final_ref is not None:
        require(bool(responses), "Final answer without a native response")
        last = list(responses.values())[-1]
        text = "".join(block["text"] for block in last["content"] if block.get("type") == "text")
        require(payload(final_ref).decode() == text, "Final text differs from last native HTTP response")
        require(set(tool_results) == consumed, "Final answer predates an unconsumed tool return")
    else:
        require(outcome.get("status") == "execution_failure", "Non-failure outcome lacks final model text")
    original = payload(manifest["original"]["part_ref"])
    source = Path(__file__).resolve().parents[1] / "parts" / f"{manifest['case']['part_name']}.json"
    require(original == source.read_bytes(), "Original supplied part changed")
    published = 0
    for event in events:
        if event["kind"] == "artifact_published" and event["data"].get("status") == "ok":
            data = event["data"]
            destination = Path(data["destination"])
            if publication_dir is not None:
                logical = Path(data["path"])
                require(logical == Path("outputs") / f"{manifest['case']['part_name']}.json", "Invalid logical publication path")
                destination = Path(publication_dir) / logical.name
            require(destination.read_bytes() == payload(data["published_ref"]), "Published artifact differs from captured bytes")
            published += 1
    maximum = max((len(result.encode()) for result in tool_results.values()), default=0)
    require(maximum <= manifest["config"]["routine_result_bytes"], "Compact result exceeds configured budget")
    return {"status": "passed", "run_id": run_id, "outcome": outcome["status"],
            "model_requests": len(requests), "model_responses": len(responses), "tool_calls": len(tool_results),
            "published_artifacts": published, "max_tool_result_bytes": maximum,
            "raw_solve_bytes": raw_solve_bytes, "compact_solve_bytes": compact_solve_bytes,
            "final_text_present": final_ref is not None,
            "unconsumed_returns_on_failure": sorted(set(tool_results) - consumed),
            "checks": ["completion_inventory_hashes", "event_sequence_and_identity", "native_proposals_match_normalized_arguments",
                       "tool_results_match_exact_native_messages", "no_duplicate_or_missing_tool_results", "no_private_model_context",
                       "full_logs_retained", "final_text_matches_native_response_without_json_requirement", "original_unchanged",
                       "published_bytes_match", "compact_result_budget"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--publication-dir", type=Path)
    args = parser.parse_args()
    results = []
    for bundle in args.bundles:
        try:
            results.append({"bundle": str(bundle), **audit(bundle, args.publication_dir)})
        except (ValueError, OSError, KeyError, TypeError) as error:
            results.append({"bundle": str(bundle), "status": "failed", "error_type": type(error).__name__, "error": str(error)})
    status = "passed" if all(r["status"] == "passed" for r in results) else "failed"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump({"status": status, "runs": results}, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": status, "runs": len(results), "report": str(args.output)}))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
