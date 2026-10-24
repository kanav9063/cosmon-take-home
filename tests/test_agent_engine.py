"""Behavior checks against the real CLI in an isolated, temporary workspace.

No model/API access is required. Candidate values come from the configured
exploration domain; acceptance always depends on a fresh PartLab solve.
"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cosmon_agent.engine import Engine
from cosmon_agent.trace import Trace


ROOT = Path(__file__).resolve().parents[1]


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="partlab-check-")
        self.test_dir = Path(self.temporary.name)
        self.policy = json.loads((ROOT / "cosmon_agent/config.json").read_text())
        self.original_hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / "parts").glob("*.json")
        }
        self.engines = []
        self.call_number = 0

    async def asyncTearDown(self):
        for engine in self.engines:
            await engine.close()
        self.assertEqual(
            self.original_hashes,
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "parts").glob("*.json")
            },
            "Tests must not modify any supplied part",
        )
        self.temporary.cleanup()

    async def make_engine(self, part="bracket_v3", policy=None):
        index = len(self.engines)
        trace = Trace(self.test_dir / f"trace-{index}")
        engine = Engine(
            root=ROOT,
            trace=trace,
            part_name=part,
            policy=copy.deepcopy(policy or self.policy),
            publish_dir=self.test_dir / f"outputs-{index}",
        )
        self.engines.append(engine)
        await engine.setup()
        return engine

    async def invoke(self, engine, tool_name, **args):
        self.call_number += 1
        text = await engine.invoke(tool_name, args, f"test-call-{self.call_number}")
        self.assertIsInstance(text, str)
        return json.loads(text)

    async def accepted(self, engine, tool_name, **args):
        result = await self.invoke(engine, tool_name, **args)
        self.assertTrue(result["ok"], result)
        return result

    @staticmethod
    def commands(engine):
        return [
            event["data"]["argv"][1:]
            for event in engine.trace.events
            if event["kind"] == "cli_requested"
        ]

    @staticmethod
    def source(part="bracket_v3"):
        return json.loads((ROOT / "parts" / f"{part}.json").read_text())

    async def analyze(self, engine, part="bracket_v3"):
        await self.accepted(engine, "mesh")
        await self.accepted(engine, "apply_load", **self.source(part)["default_load"])
        result = await self.accepted(engine, "solve")
        self.assertNotIn('"log"', json.dumps(result))
        self.assertLessEqual(len(json.dumps(result).encode()), self.policy["routine_result_bytes"])
        return result

    async def baseline(self, engine, part="bracket_v3"):
        await self.accepted(engine, "open_part")
        result = await self.analyze(engine, part)
        self.assertLess(engine.initial_sf, 2.0)
        return result

    async def verified_candidate(self, engine):
        await self.baseline(engine)
        await self.accepted(engine, "open_part")
        candidate = self.policy["exploration_ranges"]["bracket_v3"]["thickness_mm"][1]
        await self.accepted(engine, "set_parameter", name="thickness_mm", value=candidate)
        result = await self.analyze(engine)
        self.assertGreaterEqual(engine.latest_sf, 2.0, result)
        return candidate

    async def test_invalid_operations_do_not_reach_cli(self):
        engine = await self.make_engine("flange_v1")
        commands_before = len(self.commands(engine))
        self.assertFalse((await self.invoke(engine, "solve"))["ok"])
        self.assertEqual(commands_before, len(self.commands(engine)))

        await self.accepted(engine, "open_part")
        await self.accepted(engine, "mesh")
        commands_before = len(self.commands(engine))
        wrong_load = dict(self.source("flange_v1")["default_load"], direction="SIDEWAYS")
        self.assertFalse((await self.invoke(engine, "apply_load", **wrong_load))["ok"])
        self.assertEqual(commands_before, len(self.commands(engine)))
        await self.accepted(engine, "apply_load", **self.source("flange_v1")["default_load"])
        await self.accepted(engine, "solve")
        await self.accepted(engine, "open_part")

        parameters_before = dict(engine.parameters)
        state_path = engine.workdir / ".partlab/state.json"
        state_before = state_path.read_bytes()
        commands_before = len(self.commands(engine))
        for parameter, value in (("thickness_mm", 5.5), ("hole_diameter_mm", 3.0)):
            with self.subTest(parameter=parameter):
                rejected = await self.invoke(engine, "set_parameter", name=parameter, value=value)
                self.assertFalse(rejected["ok"], rejected)
                self.assertEqual(commands_before, len(self.commands(engine)))
                self.assertEqual(parameters_before, engine.parameters)
                self.assertEqual(state_before, state_path.read_bytes())

        same_value = parameters_before["thickness_mm"]
        rejected = await self.invoke(engine, "set_parameter", name="thickness_mm", value=same_value)
        self.assertFalse(rejected["ok"], rejected)
        self.assertEqual(commands_before, len(self.commands(engine)))

    async def test_each_trial_requires_restore_and_one_assignment(self):
        engine = await self.make_engine()
        await self.baseline(engine)
        original = self.source()["parameters"]
        thickness = self.policy["exploration_ranges"]["bracket_v3"]["thickness_mm"][1]
        rejected = await self.invoke(engine, "set_parameter", name="thickness_mm", value=thickness)
        self.assertFalse(rejected["ok"], rejected)

        await self.accepted(engine, "open_part")
        await self.accepted(engine, "set_parameter", name="thickness_mm", value=thickness)
        commands_before = len(self.commands(engine))
        fillet = self.policy["exploration_ranges"]["bracket_v3"]["fillet_radius_mm"][1]
        rejected = await self.invoke(engine, "set_parameter", name="fillet_radius_mm", value=fillet)
        self.assertFalse(rejected["ok"], rejected)
        self.assertEqual(commands_before, len(self.commands(engine)))

        await self.accepted(engine, "open_part")
        self.assertEqual(original, engine.parameters)
        await self.accepted(engine, "set_parameter", name="fillet_radius_mm", value=fillet)
        differences = {key for key in original if original[key] != engine.parameters[key]}
        self.assertEqual({"fillet_radius_mm"}, differences)
        self.assertFalse((await self.invoke(engine, "save_part"))["ok"])

    async def test_verified_save_matches_fresh_solve_and_full_raw_evidence(self):
        engine = await self.make_engine()
        task_bytes = (engine.trace.path / "inputs/task.md").read_bytes()
        self.assertEqual(task_bytes, (ROOT / "TASK.md").read_bytes())
        self.assertNotEqual(task_bytes, (ROOT / "README.md").read_bytes(),
                            "Capture the original assignment, not the project guide")
        manifest = json.loads((engine.trace.path / "manifest.json").read_bytes())
        self.assertEqual(manifest["task_ref"], {
            "path": "inputs/task.md", "sha256": hashlib.sha256(task_bytes).hexdigest(),
            "bytes": len(task_bytes),
        })
        candidate = await self.verified_candidate(engine)

        # The model observation excludes the log; exact CLI evidence retains it.
        raw_solve = []
        for path in sorted((engine.trace.path / "raw/cli").rglob("*")):
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_bytes())
            except (ValueError, UnicodeDecodeError):
                continue
            result = payload.get("result", {}) if isinstance(payload, dict) else {}
            if isinstance(result, dict) and "log" in result:
                raw_solve.append(result)
        self.assertEqual(2, len(raw_solve), "Both exact solve stdout payloads must be retained")
        self.assertGreater(len(raw_solve[-1]["log"]), 2048)
        self.assertEqual(engine.latest_sf, raw_solve[-1]["safety_factor"])

        saved = await self.accepted(engine, "save_part")
        output = self.test_dir / "outputs-0/bracket_v3.json"
        self.assertTrue(output.is_file(), saved)
        output_bytes = output.read_bytes()
        self.assertEqual(output_bytes, (engine.trace.path / "outputs/bracket_v3.json").read_bytes())
        self.assertEqual(output_bytes, (engine.trace.path / "published/bracket_v3.json").read_bytes())
        self.assertEqual(hashlib.sha256(output_bytes).hexdigest(), saved["result"]["sha256"])
        artifact = json.loads(output_bytes)
        expected_parameters = dict(self.source()["parameters"], thickness_mm=candidate)
        self.assertEqual(expected_parameters, artifact["parameters"])
        self.assertEqual(self.source()["default_load"], artifact["applied_load"])
        self.assertEqual(engine.latest_sf, artifact["solve_result"]["safety_factor"])
        self.assertTrue(artifact["solve_result"]["converged"])
        self.assertNotIn("log", artifact["solve_result"])
        self.assertEqual("repaired", engine.outcome(None)["status"])
        commands = self.commands(engine)
        self.assertEqual(2, sum(command[0] == "solve" for command in commands))
        self.assertFalse(any(command[0] in {"get-safety-factor", "get-max-stress", "get-solve-log"} for command in commands))

    async def test_failed_publication_cannot_be_reported_as_repaired(self):
        engine = await self.make_engine()
        await self.verified_candidate(engine)
        blocked_output = self.test_dir / "outputs-0/bracket_v3.json"
        blocked_output.mkdir(parents=True)
        result = await self.invoke(engine, "save_part")
        self.assertFalse(result["ok"], result)
        self.assertNotEqual("repaired", engine.outcome(None)["status"])
        self.assertFalse(engine.artifact_id)

    async def test_concurrent_mutations_cannot_bypass_single_assignment(self):
        engine = await self.make_engine()
        await self.baseline(engine)
        await self.accepted(engine, "open_part")
        bounds = self.policy["exploration_ranges"]["bracket_v3"]
        commands_before = len(self.commands(engine))
        results = await asyncio.gather(
            self.invoke(engine, "set_parameter", name="thickness_mm", value=bounds["thickness_mm"][1]),
            self.invoke(engine, "set_parameter", name="fillet_radius_mm", value=bounds["fillet_radius_mm"][1]),
        )
        self.assertEqual(1, sum(result["ok"] for result in results), results)
        mutation_commands = [
            command for command in self.commands(engine)[commands_before:]
            if command[0] == "set-parameter"
        ]
        self.assertEqual(1, len(mutation_commands))
        original = self.source()["parameters"]
        self.assertEqual(1, sum(original[key] != engine.parameters[key] for key in original))

    async def test_rejected_calls_exhaust_tool_budget(self):
        policy = copy.deepcopy(self.policy)
        policy["max_tool_calls"] = 2
        engine = await self.make_engine(policy=policy)
        self.assertFalse((await self.invoke(engine, "solve"))["ok"])
        self.assertFalse((await self.invoke(engine, "solve"))["ok"])
        commands_before = len(self.commands(engine))
        result = await self.invoke(engine, "open_part")
        self.assertFalse(result["ok"], result)
        self.assertEqual(commands_before, len(self.commands(engine)))
        self.assertNotEqual("repaired", engine.outcome(None)["status"])

    async def test_completed_baseline_cannot_be_reloaded_without_candidate(self):
        engine = await self.make_engine()
        await self.baseline(engine)
        commands_before = len(self.commands(engine))
        result = await self.invoke(engine, "apply_load", **self.source()["default_load"])
        self.assertFalse(result["ok"], result)
        self.assertEqual(commands_before, len(self.commands(engine)))
        self.assertIsNone(engine.execution_error)
        await self.accepted(engine, "open_part")
        candidate = self.policy["exploration_ranges"]["bracket_v3"]["thickness_mm"][1]
        await self.accepted(engine, "set_parameter", name="thickness_mm", value=candidate)

    async def test_cancelled_cli_preserves_partial_output_and_marks_unknown_state(self):
        engine = await self.make_engine()
        await self.accepted(engine, "open_part")
        # Replace only the copied executable with a deterministic interrupted CLI.
        (engine.workdir / "partlab").write_text(
            "#!/usr/bin/python3\n"
            "from pathlib import Path\n"
            "import time\n"
            "print('partial solver output', flush=True)\n"
            "Path('started').touch()\n"
            "time.sleep(60)\n"
        )
        task = asyncio.create_task(self.invoke(engine, "mesh"))
        try:
            async with asyncio.timeout(2):
                while not (engine.workdir / "started").exists():
                    await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.assertEqual("unknown", engine.phase)
        self.assertEqual("execution_failure", engine.outcome(None)["status"])
        finished = [event for event in engine.trace.events if event["kind"] == "cli_finished"][-1]
        self.assertEqual("signal", finished["data"]["termination"])
        self.assertTrue(finished["data"]["cancelled"])
        stdout_ref = finished["data"]["stdout_ref"]
        self.assertEqual(b"partial solver output\n", (engine.trace.path / stdout_ref["path"]).read_bytes())


if __name__ == "__main__":
    unittest.main()
