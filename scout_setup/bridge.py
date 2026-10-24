#!/usr/bin/env python3
"""Import complete evaluator reports into Scout and check a deterministic scan.

This is a derived report projection, not an agent conversation or another grader.
Install the optional pinned Scout environment to run; the evaluator never imports it.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

DIMENSIONS = ("capture_integrity", "process_compliance", "final_correctness",
              "delivery", "reporting_accuracy", "repair_achievement", "efficiency")
STATUSES = {"pass", "fail", "unknown", "not_applicable"}
MAX_REPORT_BYTES = 16 * 1024 * 1024
MAX_REPORTS = 10000
MAX_TOTAL_BYTES = 256 * 1024 * 1024
PROJECTION_VERSION = "cosmon.scout-projection/1"
SCOUT_VERSION = "0.6.1"


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> tuple[dict, bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular, non-symlink report file: {path}")
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError(f"Report exceeds byte limit: {path}")
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    data = json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject_constant)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data, raw


def load_reports(directory: Path) -> tuple[dict, bytes, list[dict]]:
    """Read every manifest entry; never glob, filter, or silently skip rejects."""
    directory = directory.resolve(strict=True)
    summary, summary_raw = read_json(directory / "summary.json")
    entries = summary.get("reports")
    if (summary.get("status") != "complete"
            or summary.get("report_version") != "partlab.eval-batch/1"
            or not isinstance(entries, list) or not entries or len(entries) > MAX_REPORTS
            or type(summary.get("requested")) is not int
            or summary["requested"] != len(entries)):
        raise ValueError("Expected a complete evaluator batch with every requested report")
    counts = {"evaluated": 0, "rejected": 0}
    ids, paths, records = set(), set(), []
    total_bytes = len(summary_raw)
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Report manifest entry must be an object")
        input_id, name = entry.get("input_id"), entry.get("report")
        if (not isinstance(input_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", input_id)
                or input_id in ids or name != f"report-{input_id}.json" or name in paths):
            raise ValueError("Malformed, unsafe, or duplicated report identity")
        ids.add(input_id)
        paths.add(name)
        report, raw = read_json(directory / name)
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Report batch exceeds total byte limit")
        status = report.get("evaluation_status")
        if (report.get("input_id") != input_id
                or report.get("report_version") != "partlab.eval/1"
                or not isinstance(status, str) or status not in counts
                or entry.get("status") != status):
            raise ValueError(f"Report and manifest disagree: {input_id}")
        counts[status] += 1
        dims = report.get("summary")
        if not isinstance(dims, dict) or set(dims) != set(DIMENSIONS):
            raise ValueError(f"Missing or extra evaluation dimension: {input_id}")
        checks = report.get("checks")
        if not isinstance(checks, list):
            raise ValueError(f"Missing check list: {input_id}")
        check_ids = set()
        for check in checks:
            if (not isinstance(check, dict) or not isinstance(check.get("instance_id"), str)
                    or check["instance_id"] in check_ids
                    or not isinstance(check.get("status"), str) or check["status"] not in STATUSES
                    or not isinstance(check.get("refs"), list)):
                raise ValueError(f"Malformed or duplicated check: {input_id}")
            check_ids.add(check["instance_id"])
        for dimension, data in dims.items():
            if (not isinstance(data, dict) or not isinstance(data.get("status"), str)
                    or data["status"] not in STATUSES or not isinstance(data.get("members"), list)
                    or any(not isinstance(member, str) or member not in check_ids for member in data["members"])):
                raise ValueError(f"Invalid dimension or unresolved check: {input_id}/{dimension}")
        records.append({"input_id": input_id, "path": str(directory / name), "name": name,
                        "report": report, "raw": raw, "sha256": sha(raw)})
    if (type(summary.get("evaluated")) is not int or type(summary.get("explicitly_rejected")) is not int
            or counts["evaluated"] != summary["evaluated"]
            or counts["rejected"] != summary["explicitly_rejected"]):
        raise ValueError("Batch evaluated/rejected counts disagree with manifest entries")
    return summary, summary_raw, records


def project(record: dict, batch_sha256: str):
    from inspect_ai.model import ChatMessageUser
    from inspect_scout import Transcript

    report = record["report"]
    metadata = {"projection_version": PROJECTION_VERSION,
                "projection_kind": "derived_evaluator_report_not_agent_conversation",
                "input_id": record["input_id"], "report_sha256": record["sha256"],
                "evaluation_status": report["evaluation_status"],
                "source_kind": report.get("source_kind", "unknown"), "report": report}
    messages = [ChatMessageUser(
        id="overview", content="Derived evaluator report, not an agent message.\n" + encoded({
            "input_id": record["input_id"], "source_kind": metadata["source_kind"],
            "evaluation_status": report["evaluation_status"], "summary": report["summary"],
            "diagnostics": report.get("diagnostics", []), "report_sha256": record["sha256"]}).decode(),
        metadata={"role_label": "Evaluator report (derived)"})]
    for index, check in enumerate(report["checks"]):
        messages.append(ChatMessageUser(id=f"check-{index}", content=encoded(check).decode(),
                                       metadata={"role_label": "Evaluator check (derived)",
                                                 "check_instance_id": check["instance_id"]}))
    return Transcript(
        transcript_id=sha(encoded([PROJECTION_VERSION, batch_sha256, record["input_id"], record["sha256"]])),
        source_type="cosmon_evaluator_report", source_id=batch_sha256,
        source_uri=record["path"], task_set="partlab", task_id=report.get("case_id"),
        metadata=metadata, score={key: report["summary"][key]["status"] for key in DIMENSIONS},
        success=None, messages=messages,
    )


def block_network():
    """Keep this optional integration offline, including accidental scanner calls."""
    attempts = []
    def audit(event, args):
        if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.sendto"}:
            attempts.append(event)
            raise RuntimeError("Scout report bridge prohibits network access")
    sys.addaudithook(audit)
    return attempts


def run(reports: Path, output: Path, *, network_attempts=None) -> dict:
    if importlib.metadata.version("inspect-scout") != SCOUT_VERSION:
        raise ValueError(f"Use pinned inspect-scout=={SCOUT_VERSION}")
    summary, summary_raw, records = load_reports(reports)
    output = output.resolve()
    reports = reports.resolve()
    if output.exists() or output == reports or output in reports.parents or reports in output.parents:
        raise ValueError("Use a new output directory outside the input report directory")
    output.mkdir(parents=True)
    os.environ["SCOUT_SCANBUFFER_DIR"] = str(output / "buffer")
    from inspect_scout import scan, transcripts_db, transcripts_from
    from scout_setup.scanners import evaluation_dimensions

    raw_dir = output / "reports"
    raw_dir.mkdir()
    (raw_dir / "summary.json").write_bytes(summary_raw)
    for record in records:
        (raw_dir / record["name"]).write_bytes(record["raw"])
    batch_sha = sha(summary_raw)
    transcripts = [project(record, batch_sha) for record in records]
    database = output / "transcripts"
    async def insert():
        async with transcripts_db(str(database)) as db:
            await db.insert(transcripts)
    asyncio.run(insert())
    scan_result = scan(scanners=[evaluation_dimensions()],
                       transcripts=transcripts_from(str(database)),
                       scans=str(output / "scans"), max_transcripts=1,
                       max_processes=1, fail_on_error=True, display="none")
    # Read the actual persisted Scout output, not in-memory scanner return values.
    from inspect_scout import scan_results_df
    # Keep nested Result metadata intact. Scout 0.6.1's expanded DataFrame path
    # flattens metadata into metadata.* columns; the documented transcript-row
    # mode preserves the full persisted result set without that conversion.
    frames = scan_results_df(scan_result.location, rows="transcripts")
    if not frames.complete or frames.errors:
        raise ValueError("Scout scan did not finish without errors")
    scanner_summary = frames.summary.scanners["evaluation_dimensions"]
    if scanner_summary.scans != len(transcripts) or scanner_summary.tokens or scanner_summary.model_usage:
        raise ValueError("Scout scan skipped inputs or used a model")
    frame = frames.scanners["evaluation_dimensions"]
    expected = {(transcript.transcript_id, dimension): transcript.score[dimension]
                for transcript in transcripts for dimension in DIMENSIONS}
    expected_metadata = {}
    for transcript in transcripts:
        report = transcript.metadata["report"]
        checks = {check["instance_id"]: check for check in report["checks"]}
        for dimension in DIMENSIONS:
            members = report["summary"][dimension]["members"]
            expected_metadata[(transcript.transcript_id, dimension)] = {
                "input_id": report["input_id"],
                "raw_refs": [ref for member in members for ref in checks[member]["refs"]],
                "check_instances": members,
                "report_sha256": transcript.metadata["report_sha256"],
                "projection_kind": "derived_evaluator_report_not_agent_conversation",
            }
    observed = {}
    rows = []
    raw_reference_count = 0
    seen_transcripts = set()
    for row in frame.to_dict(orient="records"):
        if row["transcript_id"] in seen_transcripts:
            raise ValueError("Duplicate Scout transcript result row")
        seen_transcripts.add(row["transcript_id"])
        result_set = row["value"]
        if isinstance(result_set, str):
            result_set = json.loads(result_set)
        if not isinstance(result_set, list):
            raise ValueError("Expected a persisted Scout result set")
        for result in result_set:
            key = (row["transcript_id"], result["label"])
            if key in observed:
                raise ValueError(f"Duplicate Scout result: {key}")
            observed[key] = result["value"]
            metadata = result["metadata"]
            if metadata != expected_metadata.get(key):
                raise ValueError(f"Scout changed or omitted supporting evidence metadata: {key}")
            raw_reference_count += len(metadata["raw_refs"])
            rows.append({"transcript_id": row["transcript_id"], "dimension": result["label"], "value": result["value"]})
    if observed != expected:
        raise ValueError("Scout output omitted, added, or changed dimension results")
    if network_attempts:
        raise ValueError("Network access was attempted")
    verification = {
        "status": "pass", "projection_version": PROJECTION_VERSION,
        "inspect_scout": importlib.metadata.version("inspect-scout"),
        "inspect_ai": importlib.metadata.version("inspect-ai"),
        "input_batch_sha256": batch_sha, "requested": summary["requested"],
        "evaluated": summary["evaluated"], "explicitly_rejected": summary["explicitly_rejected"],
        "transcripts": len(transcripts), "dimension_results": len(rows),
        "raw_reference_occurrences_verified": raw_reference_count,
        "scan_complete": True, "scan_errors": 0,
        "model_calls": 0, "projection_kind": "derived_evaluator_report_not_agent_conversation",
        "network_audit_hook": network_attempts is not None,
        "network_attempts": len(network_attempts) if network_attempts is not None else None,
        "source_kinds": sorted({record["report"].get("source_kind", "unknown") for record in records}),
        "integration_sha256": {name: sha((Path(__file__).parent / name).read_bytes())
                               for name in ("bridge.py", "scanners.py", "requirements.lock")},
        "scan_location": str(scan_result.location),
        "inputs": [{"input_id": record["input_id"], "report_sha256": record["sha256"],
                    "transcript_id": transcript.transcript_id} for record, transcript in zip(records, transcripts)],
        "rows": sorted(rows, key=lambda row: (row["transcript_id"], row["dimension"])),
    }
    (output / "verification.json").write_bytes(encoded(verification))
    return verification


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    attempts = block_network()
    try:
        result = run(args.reports, args.output_dir, network_attempts=attempts)
        if attempts:
            raise ValueError("Network access was attempted")
    except Exception as exc:
        print(f"Scout bridge failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({key: result[key] for key in ("status", "requested", "transcripts", "dimension_results")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
