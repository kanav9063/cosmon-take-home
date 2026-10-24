"""Independent readiness controls for save/snapshot/publication provenance."""
import json
from pathlib import Path
import tempfile
import unittest

from bundle_factory import Builder, encoded, refresh_inventory, scenario_bundle
from evaluate import evaluate_one, load_cases


class ReadinessReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run"
        self.case = load_cases()[0]["bracket_v3"]

    def repaired(self):
        builder = Builder(self.path)
        builder.begin()
        builder.restore()
        builder.set_parameter("thickness_mm", 5)
        builder.analyze(2.4)
        selected = builder.save()
        return builder, selected

    def report(self):
        return evaluate_one(self.path, self.case)

    def write_events(self, events):
        for seq, event in enumerate(events, 1):
            event["seq"], event["event_id"] = seq, f"e{seq:04d}"
        (self.path / "events.jsonl").write_bytes(b"".join(
            encoded(event).replace(b"\n", b"") + b"\n" for event in events))
        refresh_inventory(self.path)

    def check(self, report, name):
        values = [check for check in report["checks"] if check["check_id"] == name]
        self.assertEqual(1, len(values))
        return values[0]

    def test_later_different_save_without_new_publication_fails_delivery(self):
        builder, selected = self.repaired()
        builder.set_parameter("thickness_mm", 6)
        builder.analyze(2.8)
        overwritten = builder.save(publish=False)
        # Capture the actual destination bytes as well as the immutable snapshot.
        builder.write("outputs/bracket_v3.json", builder.artifacts[overwritten]["raw"])
        builder.finish(artifact_id=selected)
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("pass", report["summary"]["final_correctness"]["status"])
        self.assertEqual("fail", report["summary"]["delivery"]["status"])
        self.assertEqual("FINAL_OUTPUT_MISMATCH", self.check(report, "output_delivery")["code"])
        self.assertEqual("fail", report["summary"]["repair_achievement"]["status"])

    def test_republishing_selected_historical_artifact_after_overwrite_restores_delivery(self):
        builder, selected = self.repaired()
        builder.set_parameter("thickness_mm", 6)
        builder.analyze(2.8)
        builder.save(publish=False)
        builder.publish(selected)
        builder.finish(artifact_id=selected)
        report = self.report()
        for name in ("capture_integrity", "final_correctness", "delivery", "reporting_accuracy", "repair_achievement"):
            self.assertEqual("pass", report["summary"][name]["status"], name)

    def test_failed_later_save_requires_final_destination_observation(self):
        builder, selected = self.repaired()
        builder.command("save-part", ["outputs/bracket_v3.json"], ok=False,
                        error="write failed after opening destination")
        builder.finish(artifact_id=selected)
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("unknown", report["summary"]["delivery"]["status"])
        self.assertEqual("PUBLICATION_STALE", self.check(report, "output_delivery")["code"])

    def test_same_bytes_saved_later_with_verified_snapshot_still_pass(self):
        builder, selected = self.repaired()
        builder.save(publish=False)
        builder.finish(artifact_id=selected)
        report = self.report()
        self.assertEqual("pass", report["summary"]["delivery"]["status"])

    def test_later_successful_save_without_snapshot_leaves_destination_unknown(self):
        builder, selected = self.repaired()
        builder.command("save-part", ["outputs/bracket_v3.json"],
                        {"saved_to": "outputs/bracket_v3.json"})
        builder.finish(artifact_id=selected)
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("unknown", report["summary"]["delivery"]["status"])
        self.assertEqual("PUBLICATION_STALE", self.check(report, "output_delivery")["code"])

    def test_later_save_in_private_cwd_does_not_change_separate_published_file(self):
        builder, selected = self.repaired()
        publication = next(event for event in builder.events if event["kind"] == "artifact_published")
        publication["data"]["destination"] = "/handoff/outputs/bracket_v3.json"
        builder.set_parameter("thickness_mm", 6)
        builder.analyze(2.8)
        builder.save(publish=False)
        builder.finish(artifact_id=selected)
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("pass", report["summary"]["delivery"]["status"])

    def test_later_save_resolves_cwd_against_same_absolute_published_destination(self):
        builder, selected = self.repaired()
        publication = next(event for event in builder.events if event["kind"] == "artifact_published")
        publication["data"]["destination"] = "/fixture/outputs/bracket_v3.json"
        builder.set_parameter("thickness_mm", 6)
        builder.analyze(2.8)
        builder.save(publish=False)
        builder.finish(artifact_id=selected)
        report = self.report()
        self.assertEqual("fail", report["summary"]["delivery"]["status"])
        self.assertEqual("FINAL_OUTPUT_MISMATCH", self.check(report, "output_delivery")["code"])

    def test_later_write_to_another_path_does_not_stale_publication(self):
        builder, selected = self.repaired()
        builder.command("save-part", ["outputs/other.json"], {"saved_to": "outputs/other.json"})
        builder.finish(artifact_id=selected)
        self.assertEqual("pass", self.report()["summary"]["delivery"]["status"])

    def test_failed_spawn_does_not_stale_publication(self):
        builder, selected = self.repaired()
        cli_id = builder.command("save-part", ["outputs/bracket_v3.json"], ok=False,
                                 error="could not spawn", termination="spawn_error")
        builder.events = [event for event in builder.events if not
                          (event["kind"] == "cli_started" and event["cli_id"] == cli_id)]
        builder.finish(artifact_id=selected)
        self.write_events(builder.events)
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("pass", report["summary"]["delivery"]["status"])

    def test_snapshot_cannot_precede_its_producing_save(self):
        scenario_bundle(self.path)
        events = [json.loads(line) for line in (self.path / "events.jsonl").read_bytes().splitlines()]
        snapshot = next(event for event in events if event["kind"] == "artifact_saved")
        events.remove(snapshot)
        events.insert(0, snapshot)
        self.write_events(events)
        report = self.report()
        self.assertEqual("fail", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("fail", report["summary"]["delivery"]["status"])
        self.assertEqual("ARTIFACT_PROVENANCE_INVALID", self.check(report, "artifact_provenance")["code"])

    def test_publication_cannot_precede_captured_artifact(self):
        scenario_bundle(self.path)
        events = [json.loads(line) for line in (self.path / "events.jsonl").read_bytes().splitlines()]
        publication = next(event for event in events if event["kind"] == "artifact_published")
        events.remove(publication)
        index = next(index for index, event in enumerate(events) if event["kind"] == "artifact_saved")
        events.insert(index, publication)
        self.write_events(events)
        report = self.report()
        self.assertEqual("fail", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("fail", report["summary"]["delivery"]["status"])
        self.assertEqual("ARTIFACT_PROVENANCE_INVALID", self.check(report, "output_delivery")["code"])

    def failed_publication(self, *, error=True, extra=None):
        builder = Builder(self.path)
        builder.begin()
        builder.restore()
        builder.set_parameter("thickness_mm", 5)
        builder.analyze(2.4)
        artifact = builder.save(publish=False)
        data = {"artifact_id": artifact, "path": "outputs/bracket_v3.json", "status": "failed"}
        if error:
            data["error_type"] = "PermissionError"
        data.update(extra or {})
        builder.event("artifact_published", data)
        return builder, artifact

    def test_failed_publication_without_bytes_is_complete_honest_failure(self):
        builder, _ = self.failed_publication()
        builder.selected_artifact = None
        builder.finish("execution_failure", reason_code="execution.PermissionError")
        report = self.report()
        for dimension in ("capture_integrity", "process_compliance", "reporting_accuracy"):
            self.assertEqual("pass", report["summary"][dimension]["status"], dimension)
        self.assertEqual("fail", report["summary"]["repair_achievement"]["status"])
        self.assertEqual("execution_failure", report["observed_outcome"])
        self.assertIn("PUBLICATION_FAILED", [item["code"] for item in report["diagnostics"]])

    def test_failed_publication_missing_error_is_incomplete(self):
        builder, _ = self.failed_publication(error=False)
        builder.selected_artifact = None
        builder.finish("execution_failure", reason_code="execution.PermissionError")
        self.assertEqual("unknown", self.report()["summary"]["capture_integrity"]["status"])

    def test_successful_publication_still_requires_captured_bytes(self):
        builder, artifact = self.failed_publication(extra={"status": "ok"})
        builder.finish(artifact_id=artifact)
        report = self.report()
        self.assertEqual("unknown", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("unknown", report["summary"]["delivery"]["status"])

    def test_failed_publication_supplied_partial_bytes_are_still_verified(self):
        builder, artifact = self.failed_publication(extra={"published_ref": {
            "path": "artifacts/a0001.json", "sha256": "wrong", "bytes": 1}})
        builder.finish(artifact_id=artifact)
        self.assertEqual("fail", self.report()["summary"]["capture_integrity"]["status"])

    def test_recovered_publication_failure_is_diagnostic(self):
        builder, artifact = self.failed_publication()
        builder.publish(artifact)
        builder.finish(artifact_id=artifact)
        report = self.report()
        for dimension in ("capture_integrity", "process_compliance", "delivery", "reporting_accuracy", "repair_achievement"):
            self.assertEqual("pass", report["summary"][dimension]["status"], dimension)
        self.assertIn("PUBLICATION_FAILED", [item["code"] for item in report["diagnostics"]])

    def test_recovered_publication_does_not_certify_unrecovered_failure_claim(self):
        builder, artifact = self.failed_publication()
        builder.publish(artifact)
        builder.selected_artifact = None
        builder.finish("execution_failure", reason_code="execution.PermissionError")
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("unknown", report["summary"]["reporting_accuracy"]["status"])

    def test_later_failed_publication_does_not_erase_earlier_delivery_evidence(self):
        builder, artifact = self.repaired()
        builder.event("artifact_published", {"artifact_id": artifact,
            "path": "outputs/bracket_v3.json", "status": "failed", "error_type": "PermissionError"})
        builder.selected_artifact = None
        builder.finish("execution_failure", reason_code="execution.PermissionError")
        report = self.report()
        self.assertEqual("pass", report["summary"]["capture_integrity"]["status"])
        self.assertEqual("pass", report["summary"]["reporting_accuracy"]["status"])
        self.assertEqual("unknown", report["summary"]["repair_achievement"]["status"])


if __name__ == "__main__":
    unittest.main()
