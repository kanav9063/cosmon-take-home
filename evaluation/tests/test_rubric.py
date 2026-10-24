"""Executable portability proofs using only explicitly synthetic evidence."""
from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

from bundle_factory import Builder, encoded, scenario_bundle
from eval_types import EvidenceRun, InputError, digest
from evaluate import evaluate_batch, evaluate_one, load_cases
from trace_adapter import ADAPTERS, Limits, Reader, load_run, register_adapter


def export_foreign_capture(bundle: Path, destination: Path) -> Path:
    """A test harness's single-file export with different event field names.

    Preserve every raw document byte and the original completion inventory.
    The adapter must translate the timeline back before that inventory passes.
    No expected verdict or normalized evaluator state is stored in this export.
    """
    events = [json.loads(line) for line in (bundle / "events.jsonl").read_bytes().splitlines()]
    payload = {
        "format": "synthetic-harness-export/1",
        "timeline": [{"position": event["seq"], "type": event["kind"],
                      "payload": event["data"],
                      "context": {key: value for key, value in event.items()
                                  if key not in {"seq", "kind", "data"}}}
                     for event in events],
        "documents": {path.relative_to(bundle).as_posix():
                      base64.b64encode(path.read_bytes()).decode("ascii")
                      for path in sorted(bundle.rglob("*"))
                      if path.is_file() and path.name != "events.jsonl"},
    }
    destination.mkdir()
    (destination / "capture.json").write_bytes(encoded(payload))
    return destination


def load_foreign_capture(path, case, limits):
    """Test-local trusted adapter; reuse the complete built-in validator.

    This demonstrates a representation boundary, not a new CAD/CAE profile.
    Report references point at the durable export, not the temporary conversion.
    """
    path, limits = Path(path), limits or Limits()
    raw, source_ref = Reader(path, limits, EvidenceRun(path)).read("capture.json")
    payload = json.loads(raw)
    if payload.get("format") != "synthetic-harness-export/1":
        raise InputError("Unsupported foreign capture format")
    timeline, documents = payload.get("timeline"), payload.get("documents")
    if not isinstance(timeline, list) or not isinstance(documents, dict):
        raise InputError("Foreign capture requires a timeline and documents")
    if len(timeline) > limits.max_events or len(documents) + 1 > limits.max_files:
        raise InputError("Foreign capture exceeds configured record limits")
    events = []
    for item in timeline:
        context = item["context"]
        if not isinstance(context, dict) or set(context) & {"seq", "kind", "data"}:
            raise InputError("Ambiguous foreign event context")
        events.append({**context, "seq": item["position"], "kind": item["type"],
                       "data": item["payload"]})
    ledger = b"".join((json.dumps(event, sort_keys=True, allow_nan=False) + "\n").encode()
                      for event in events)
    with tempfile.TemporaryDirectory() as temporary:
        normalized = Path(temporary)
        total = len(ledger)
        if total > limits.max_file_bytes:
            raise InputError("Foreign timeline exceeds configured file limit")
        (normalized / "events.jsonl").write_bytes(ledger)
        for name, value in documents.items():
            logical = PurePosixPath(name)
            if (logical.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/"))
                    or "\\" in name or name == "events.jsonl"):
                raise InputError("Invalid foreign document path")
            try:
                content = base64.b64decode(value, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise InputError("Invalid foreign document encoding") from exc
            total += len(content)
            if len(content) > limits.max_file_bytes or total > limits.max_total_bytes:
                raise InputError("Foreign documents exceed configured byte limits")
            target = normalized.joinpath(*logical.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        run = load_run(normalized, case, limits)
    # Each Ref now authenticates the actual persisted export. JSON pointers
    # locate the original timeline row or base64-encoded raw document within it.
    groups = [run.refs, *(action.refs for action in run.actions),
              *(event.refs for event in run.events),
              *(artifact.refs for artifact in run.artifacts.values()),
              *(issue.refs for issue in run.issues)]
    seen = set()
    for refs in groups:
        for reference in refs:
            if id(reference) in seen:
                continue
            seen.add(id(reference))
            reference.pointer = (f"/timeline/{reference.line - 1}"
                                 if reference.path == "events.jsonl" and reference.line
                                 else "/timeline" if reference.path == "events.jsonl"
                                 else "/documents/" + reference.path.replace("~", "~0").replace("/", "~1"))
            reference.path, reference.sha256 = source_ref.path, source_ref.sha256
            reference.bytes, reference.line = source_ref.bytes, None
    run.bundle, run.input_digest = path, digest(raw)
    return run


class RubricPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_unseen_case_uses_trusted_data_for_load_target_and_parameter_bounds(self):
        case_id = "unseen_fixture_v7"
        standard_cases, _ = load_cases()
        self.assertNotIn(case_id, standard_cases)
        repository = Path(__file__).resolve().parents[2]
        original = json.loads((repository / "parts/bracket_v3.json").read_bytes())
        original["name"] = case_id
        original["parameters"]["web_depth_mm"] = original["parameters"].pop("thickness_mm")
        original["default_load"] = {"face_id": "face_attachment", "force_N": 1735, "direction": "+X"}
        original["valid_load_faces"] = ["face_attachment"]
        original["features"] = [{"id": "face_attachment", "type": "face", "area_mm2": 800}]
        trusted = self.root / "trusted"
        (trusted / "parts").mkdir(parents=True)
        raw = encoded(original)
        (trusted / "parts" / f"{case_id}.json").write_bytes(raw)
        config = {"cases": [{"case_id": case_id, "original_path": f"parts/{case_id}.json",
                             "original_sha256": digest(raw), "target_sf": 3,
                             "limits": {"web_depth_mm": {"min": 3, "max": 4.25}},
                             "output_path": f"outputs/{case_id}.json"}]}
        cases_path = trusted / "cases.json"
        cases_path.write_bytes(encoded(config))
        cases, _ = load_cases(cases_path)
        self.assertEqual(cases[case_id].default_load["face_id"], "face_attachment")
        inputs = []
        for name, value, sf in (("valid", 4.25, 3), ("below_target", 4.25, 2.99999999),
                                ("outside_limit", 4.25000001, 3)):
            # Only the synthetic writer's input directory changes; production
            # loading, reconstruction and scoring all run without patches.
            with patch("bundle_factory.ROOT", trusted):
                builder = Builder(self.root / name, name, case_id)
            builder.manifest["policy_ref"] = builder.write("inputs/policy.json", encoded({
                "target_safety_factor": 3, "single_parameter": True,
                "limits": config["cases"][0]["limits"]}))
            builder.manifest["task_ref"] = builder.write("inputs/task.md", (
                f"Synthetic case {case_id}: achieve SF >= 3 with one parameter change; "
                "web_depth_mm must remain within [3, 4.25]. Use the original default load.\n").encode())
            builder.write("manifest.json", encoded(builder.manifest))
            builder.begin(1.4)
            builder.restore("web_depth_mm")
            builder.set_parameter("web_depth_mm", value)
            builder.analyze(sf)
            builder.save()
            builder.finish()
            inputs.append({"id": name, "case": case_id, "path": name})
        manifest = self.root / "inputs.json"
        manifest.write_bytes(encoded({"inputs": inputs}))
        output = self.root / "reports"
        batch = evaluate_batch(manifest, output, cases_path=cases_path)
        self.assertEqual((batch["evaluated"], batch["explicitly_rejected"]), (3, 0))
        reports = {entry["id"]: json.loads((output / f"report-{entry['id']}.json").read_bytes())
                   for entry in inputs}
        for dimension in ("capture_integrity", "process_compliance", "final_correctness",
                          "delivery", "reporting_accuracy", "repair_achievement"):
            self.assertEqual(reports["valid"]["summary"][dimension]["status"], "pass", dimension)
        for name, code in (("below_target", "SF_BELOW_TARGET"),
                           ("outside_limit", "MANUFACTURING_VIOLATION")):
            with self.subTest(name=name):
                self.assertEqual(reports[name]["summary"]["capture_integrity"]["status"], "pass")
                self.assertTrue(any(finding["code"] == code and finding["status"] == "fail"
                                    for finding in reports[name]["findings"]))

    def test_foreign_harness_layout_preserves_grading_and_stale_solve_detection(self):
        cases, _ = load_cases()
        name = "test-synthetic-foreign-harness-v1"
        register_adapter(name, load_foreign_capture)
        self.addCleanup(ADAPTERS.pop, name)
        for scenario in ("repaired", "stale_solve"):
            with self.subTest(scenario=scenario):
                source = scenario_bundle(self.root / scenario, scenario)
                foreign = export_foreign_capture(source, self.root / f"foreign-{scenario}")
                self.assertEqual([path.name for path in foreign.iterdir()], ["capture.json"])
                normal = evaluate_one(source, cases["bracket_v3"])
                adapted = evaluate_one(foreign, cases["bracket_v3"], adapter=name)
                self.assertEqual(normal["summary"], adapted["summary"])
                self.assertEqual([{key: value for key, value in check.items() if key != "refs"}
                                  for check in normal["checks"]],
                                 [{key: value for key, value in check.items() if key != "refs"}
                                  for check in adapted["checks"]])
                self.assertEqual(adapted["summary"]["capture_integrity"]["status"], "pass")
                self.assertEqual(adapted["adapter"], name)
                self.assertEqual(adapted["input_digest"], digest((foreign / "capture.json").read_bytes()))
                if scenario == "stale_solve":
                    finding = next(item for item in adapted["findings"] if item["code"] == "STALE_SOLVE")
                    self.assertEqual(finding["status"], "fail")
                    self.assertGreaterEqual(len(finding["refs"]), 3)
                    for reference in finding["refs"]:
                        self.assertEqual(reference["path"], "capture.json")
                        self.assertTrue(reference["pointer"].startswith(("/timeline", "/documents/")))
                        self.assertEqual(reference["sha256"], adapted["input_digest"])


if __name__ == "__main__":
    unittest.main()
