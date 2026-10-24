"""Contract tests for the optional Scout projection (run in .venv-scout)."""
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from scout_setup.bridge import DIMENSIONS, encoded, load_reports, project, sha


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.check = {"instance_id": "check:scope:id", "status": "pass", "reason": "raw evidence",
                      "refs": [{"path": "raw/a.stdout", "sha256": "a" * 64, "bytes": 123,
                                "event_id": "e1", "line": 2, "pointer": "/value"}]}
        self.report = {
            "report_version": "partlab.eval/1", "input_id": "example", "case_id": "bracket_v3",
            "evaluation_status": "evaluated", "source_kind": "synthetic_fixture",
            "checks": [self.check], "summary": {name: {"status": "pass", "reason": name,
                       "members": [self.check["instance_id"]]} for name in DIMENSIONS},
        }
        self.summary = {"report_version": "partlab.eval-batch/1", "status": "complete",
                        "requested": 1, "evaluated": 1, "explicitly_rejected": 0,
                        "reports": [{"input_id": "example", "report": "report-example.json",
                                     "status": "evaluated"}]}
        self.write()

    def write(self):
        (self.root / "summary.json").write_bytes(encoded(self.summary))
        (self.root / "report-example.json").write_bytes(encoded(self.report))

    def test_valid_keeps_exact_report_bytes(self):
        _, _, records = load_reports(self.root)
        self.assertEqual(records[0]["raw"], encoded(self.report))
        self.assertEqual(records[0]["sha256"], sha(encoded(self.report)))

    def test_missing_report_fails(self):
        (self.root / "report-example.json").unlink()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_incomplete_batch_fails(self):
        self.summary["status"] = "partial"
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_unknown_status_fails(self):
        self.report["summary"]["delivery"]["status"] = "probably"
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_rejected_input_remains_present(self):
        self.report["evaluation_status"] = "rejected"
        self.report["checks"] = []
        for data in self.report["summary"].values():
            data.update(status="unknown", members=[])
        self.summary.update(evaluated=0, explicitly_rejected=1)
        self.summary["reports"][0]["status"] = "rejected"
        self.write()
        _, _, records = load_reports(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["report"]["evaluation_status"], "rejected")

    def test_missing_dimension_fails(self):
        self.report["summary"].pop("reporting_accuracy")
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_manifest_count_mismatch_fails(self):
        self.summary["requested"] = 2
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_rejected_count_mismatch_fails(self):
        self.summary.update(evaluated=0, explicitly_rejected=1)
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_duplicate_report_fails(self):
        self.summary["reports"] *= 2
        self.summary["requested"] = 2
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_unsafe_paths_fail(self):
        for path in ("../report-example.json", "/tmp/report-example.json", "link.json"):
            with self.subTest(path=path):
                self.summary["reports"][0]["report"] = path
                self.write()
                with self.assertRaises(ValueError):
                    load_reports(self.root)

    def test_symlink_report_fails(self):
        path = self.root / "report-example.json"
        path.rename(self.root / "target.json")
        path.symlink_to(self.root / "target.json")
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_unresolved_check_fails(self):
        self.report["summary"]["delivery"]["members"].append("missing")
        self.write()
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_duplicate_json_keys_fail(self):
        (self.root / "summary.json").write_text('{"status":"complete","status":"incomplete"}')
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_nonfinite_json_fails(self):
        (self.root / "summary.json").write_text('{"status":NaN}')
        with self.assertRaises(ValueError):
            load_reports(self.root)

    def test_projection_keeps_dimensions_origin_and_no_boolean_success(self):
        _, raw, records = load_reports(self.root)
        transcript = project(records[0], sha(raw))
        self.assertEqual(transcript.metadata["source_kind"], "synthetic_fixture")
        self.assertEqual(transcript.metadata["report"], self.report)
        self.assertEqual(set(transcript.score), set(DIMENSIONS))
        self.assertIsNone(transcript.success)
        self.assertEqual(transcript.source_type, "cosmon_evaluator_report")
        self.assertEqual(transcript.messages[0].metadata["role_label"], "Evaluator report (derived)")

    def test_transcript_identity_changes_with_report_or_batch(self):
        _, raw, records = load_reports(self.root)
        initial = project(records[0], sha(raw)).transcript_id
        changed = deepcopy(records[0])
        changed["sha256"] = "changed"
        self.assertNotEqual(initial, project(changed, sha(raw)).transcript_id)
        self.assertNotEqual(initial, project(records[0], "changed").transcript_id)

    def test_scanner_keeps_raw_refs_and_each_dimension(self):
        from scout_setup.scanners import evaluation_dimensions
        _, raw, records = load_reports(self.root)
        transcript = project(records[0], sha(raw))
        results = asyncio.run(evaluation_dimensions()(transcript))
        self.assertEqual({result.label for result in results}, set(DIMENSIONS))
        for result in results:
            self.assertEqual(result.value, "pass")
            self.assertEqual(result.metadata["raw_refs"], self.check["refs"])
            self.assertEqual(len(result.references), 1)


if __name__ == "__main__":
    unittest.main()
