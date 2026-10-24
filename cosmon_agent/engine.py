"""Serialized PartLab transactions. The model proposes; observed CLI data decides."""

import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

from .trace import SCHEMA, now


class Blocked(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class ExecutionError(Exception):
    pass


class CLIError(ExecutionError):
    def __init__(self, command, kind, message):
        self.command, self.kind = command, kind
        super().__init__(message)


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def parse_json(payload):
    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(payload, parse_constant=invalid)


class Engine:
    def __init__(self, root, trace, part_name, policy, publish_dir):
        self.root, self.trace = Path(root).resolve(), trace
        self.part_name, self.policy = part_name, policy
        self.publish_dir = Path(publish_dir).resolve()
        self.lock = asyncio.Lock()
        self.temp = None
        self.workdir = None
        self.original = {}
        self.bounds = {}
        self.parameters = {}
        self.phase = "closed"
        self.revision = 0
        self.trial_id = None
        self.restoration_cli_id = None
        self.mesh_cli_id = self.load_cli_id = self.solve_cli_id = None
        self.initial_solve_cli_id = self.best_solve_cli_id = None
        self.initial_sf = self.latest_sf = self.best_sf = None
        self.solve_result = None
        self.solve_revision = None
        self.saved = None
        self.artifact_id = None
        self.trials = []
        self.tool_calls = self.cli_calls = 0
        self.needs_restore = False
        self.execution_error = None
        self.current_changed = None

    async def setup(self):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", self.part_name):
            raise ValueError("Invalid part identifier")
        raw = (self.root / "parts" / f"{self.part_name}.json").read_bytes()
        self.original = parse_json(raw)
        if self.original["name"] != self.part_name:
            raise ValueError("Original part identity mismatch")
        self.bounds = self.policy["exploration_ranges"][self.part_name]
        for name, limits in self.bounds.items():
            if name not in self.original["parameters"] or len(limits) != 2 or not all(finite_number(v) for v in limits) or limits[0] > limits[1]:
                raise ValueError("Invalid exploration range")
        for name in ("max_trials", "max_tool_calls", "max_model_turns", "run_timeout_seconds", "model_timeout_seconds", "cli_timeout_seconds", "max_output_tokens"):
            if not finite_number(self.policy[name]) or self.policy[name] <= 0:
                raise ValueError(f"Invalid policy setting {name}")
        self.constraints = {"thickness_mm": {"max": 5.0}, "hole_diameter_mm": {"min": 4.0}} if self.part_name == "flange_v1" else {}
        self.temp = tempfile.TemporaryDirectory(prefix="partlab-agent-")
        self.workdir = Path(self.temp.name)
        (self.workdir / "parts").mkdir()
        shutil.copy2(self.root / "partlab", self.workdir / "partlab")
        (self.workdir / "parts" / f"{self.part_name}.json").write_bytes(raw)
        part_ref = self.trace.write_bytes("inputs/part.json", raw)
        task_path = self.root / "TASK.md"
        if not task_path.exists():
            task_path = self.root / "README.md"  # Legacy starter/fixture layout.
        task_ref = self.trace.write_bytes("inputs/task.md", task_path.read_bytes())
        policy_ref = self.trace.write_json("inputs/policy.json", self.policy)
        self.trace.write_json("manifest.json", {
            "schema_version": SCHEMA, "capture_profile": "cosmon-eval/1", "run_id": self.trace.run_id,
            "evidence_kind": self.policy.get("evidence_kind", "live_agent"), "created_at": now(),
            "producer": {"name": "cosmon_agent", "version": "1", "python": sys.version.split()[0],
                         "binary_sha256": hashlib.sha256((self.root / "partlab").read_bytes()).hexdigest()},
            "case": {"part_name": self.part_name, "target_sf": 2.0, "output_path": f"outputs/{self.part_name}.json"},
            "original": {"part_ref": part_ref, "parameters": self.original["parameters"],
                         "default_load": self.original["default_load"], "revision": self.original["revision"]},
            "task_ref": task_ref, "policy_ref": policy_ref, "config": self.policy,
            "capture": {"model": "sdk_objects", "cli": "bytes", "hosted_tracing": False},
        })
        await self._cli("reset", purpose="isolated_session_initialization")
        self.revision += 1

    async def close(self):
        if self.temp:
            self.temp.cleanup()
            self.temp = None

    async def _cli(self, command, *args, purpose="model_action", call_id=None, model_call_id=None):
        self.cli_calls += 1
        cli_id = f"x{self.cli_calls:04d}"
        identity = dict(call_id=call_id, model_call_id=model_call_id, cli_id=cli_id, trial_id=self.trial_id)
        argv = [str(self.workdir / "partlab"), command, *map(str, args)]
        self.trace.event("cli_requested", {"argv": argv, "cwd": str(self.workdir), "attempt": 1,
                         "purpose": purpose, "timeout_seconds": self.policy["cli_timeout_seconds"]}, **identity)
        started = time.monotonic()
        proc = None
        stdout = stderr = b""
        termination, cancelled = "exit", False
        try:
            proc = await asyncio.create_subprocess_exec(*argv, cwd=self.workdir,
                       stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            self.trace.event("cli_started", {"pid": proc.pid}, **identity)
            # Shield communication so cancellation can still collect all emitted bytes.
            communication = asyncio.create_task(proc.communicate())
            try:
                stdout, stderr = await asyncio.wait_for(asyncio.shield(communication), self.policy["cli_timeout_seconds"])
            except (asyncio.TimeoutError, asyncio.CancelledError) as error:
                cancelled = isinstance(error, asyncio.CancelledError)
                termination = "signal" if cancelled else "timeout"
                if proc.returncode is None:
                    proc.kill()
                stdout, stderr = await communication
        except OSError as error:
            termination = "spawn_error"
            stderr = f"{type(error).__name__}: {error}".encode()
        if proc and proc.returncode is not None and proc.returncode < 0 and termination == "exit":
            termination = "signal"
        out_ref = self.trace.write_bytes(f"raw/cli/{cli_id}.stdout", stdout)
        err_ref = self.trace.write_bytes(f"raw/cli/{cli_id}.stderr", stderr)
        self.trace.event("cli_finished", {"stdout_ref": out_ref, "stderr_ref": err_ref,
                         "exit_code": proc.returncode if proc else None, "termination": termination,
                         "cancelled": cancelled,
                         "duration_seconds": time.monotonic() - started}, **identity)
        if cancelled:
            raise asyncio.CancelledError
        if termination != "exit":
            raise ExecutionError(f"CLI {command}: {termination}; session state is uncertain")
        try:
            envelope = parse_json(stdout)
        except (ValueError, UnicodeError) as error:
            raise ExecutionError(f"CLI {command}: invalid JSON response") from error
        if not isinstance(envelope, dict) or type(envelope.get("ok")) is not bool:
            raise ExecutionError(f"CLI {command}: malformed response envelope")
        if envelope["ok"] and proc.returncode == 0 and isinstance(envelope.get("result"), dict):
            return envelope["result"], cli_id
        if not envelope["ok"] and proc.returncode == 1:
            raise CLIError(command, envelope.get("error_type", "CLIError"), str(envelope.get("error", "CLI failed")))
        raise ExecutionError(f"CLI {command}: inconsistent exit status and response")

    def _validate(self, name, args):
        def block(code, message):
            raise Blocked(code, message)
        if self.tool_calls > self.policy["max_tool_calls"]:
            block("budget.tool_calls", "Tool-call limit reached. Report the best verified evidence.")
        if self.execution_error:
            block("execution.stopped", "Execution failed; report execution_failure.")
        signatures = {"open_part": set(), "get_parameters": set(), "set_parameter": {"name", "value"},
                      "mesh": set(), "apply_load": {"face_id", "force_N", "direction"}, "solve": set(), "save_part": set()}
        if name not in signatures or not isinstance(args, dict) or set(args) != signatures[name]:
            block("arguments.invalid", "Use exactly the tool's documented arguments.")
        if self.artifact_id:
            block("result.complete", "Verified repair is saved. Return the final result without further tools.")
        if name == "open_part":
            if self.latest_sf is not None and self.latest_sf >= 2:
                block("result.stop_at_first_fix", "The current solve meets the target. Save it, or report already_safe for baseline.")
            return
        if self.phase == "closed":
            block("state.closed", "Open the assigned original part first.")
        if name == "get_parameters":
            return
        if name == "set_parameter":
            param, value = args["name"], args["value"]
            if not isinstance(param, str) or param not in self.bounds or not finite_number(value):
                block("parameter.invalid", "Use a known parameter and finite JSON number.")
            candidate = {**self.original["parameters"], param: value}
            for field, rule in self.constraints.items():
                if ("max" in rule and candidate[field] > rule["max"]) or ("min" in rule and candidate[field] < rule["min"]):
                    block("manufacturing.constraint", f"{field} must satisfy {rule}; propose a legal value.")
            lo, hi = self.bounds[param]
            if not lo <= value <= hi:
                block("search.range", f"{param} must be within configured exploration range [{lo}, {hi}].")
            if value == self.original["parameters"][param]:
                block("parameter.unchanged", "The candidate must differ from the original parameter value.")
            if self.initial_sf is None:
                block("baseline.required", "Complete the original mesh, default load and solve before proposing a repair.")
            if self.initial_sf >= 2 or (self.latest_sf is not None and self.latest_sf >= 2):
                block("result.stop_at_first_fix", "Target already met; finalize the verified result.")
            if len(self.trials) >= self.policy["max_trials"]:
                block("budget.trials", "Candidate limit reached. Report no_repair_found with bounded search scope.")
            if self.phase != "open" or self.current_changed or self.needs_restore:
                block("trial.restore_required", "Call open_part to restore original geometry before each new candidate.")
            previous = next((trial for trial in self.trials if trial["name"] == param and trial["value"] == value), None)
            if previous:
                block("trial.duplicate", f"Candidate already attempted; prior evidence {previous}. Choose a different value.")
            return
        if self.needs_restore:
            block("trial.restore_required", "Call open_part before another candidate after a failed mesh.")
        if name in {"mesh", "apply_load", "solve"} and self.initial_sf is not None and self.current_changed is None:
            block("trial.candidate_required", "Original baseline is already solved; restore and set one candidate parameter first.")
        if name == "mesh":
            if self.latest_sf is not None and self.latest_sf >= 2:
                block("result.stop_at_first_fix", "Target met; save current result without invalidating it.")
        elif name == "apply_load":
            if not isinstance(args["face_id"], str) or not isinstance(args["direction"], str) or not finite_number(args["force_N"]) or args != self.original["default_load"]:
                block("load.default_required", f"Use the exact original default load: {self.original['default_load']}.")
            if self.phase not in {"meshed", "loaded", "solved"} or not self.mesh_cli_id:
                block("state.mesh_required", "Mesh the current geometry before applying the default load.")
            if self.latest_sf is not None and self.latest_sf >= 2:
                block("result.stop_at_first_fix", "Target met; save current result without invalidating it.")
        elif name == "solve":
            if self.phase != "loaded" or not self.mesh_cli_id or not self.load_cli_id:
                block("state.load_required", "Mesh and apply the default load before a fresh solve.")
        elif name == "save_part":
            if self.initial_sf is None or self.initial_sf >= 2 or not self.current_changed:
                block("save.repair_required", "Save requires a verified single-parameter repair after an unsafe baseline.")
            if self.phase != "solved" or self.solve_revision != self.revision or self.latest_sf is None or self.latest_sf < 2 or self.solve_result.get("converged") is not True:
                block("save.fresh_solve_required", "Save requires a fresh converged solve with SF >= 2.0.")

    def _invalidate(self, phase):
        self.revision += 1
        self.phase = phase
        self.solve_cli_id = self.solve_result = self.solve_revision = self.latest_sf = None
        if phase == "open":
            self.mesh_cli_id = None
        if phase in {"open", "meshed"}:
            self.load_cli_id = None

    async def invoke(self, name, args, call_id, model_call_id=None):
        async with self.lock:
            self.tool_calls += 1
            identity = dict(call_id=call_id, model_call_id=model_call_id)
            allowed = False
            try:
                self._validate(name, args)
                self.trace.event("guard_decision", {"decision": "allow", "reason_code": "policy.valid", "state_revision": self.revision}, actor="guard", **identity)
                allowed = True
                result = await self._dispatch(name, args, **identity)
                response = {"ok": True, "result": result}
            except Blocked as error:
                self.trace.event("guard_decision", {"decision": "block", "reason_code": error.code, "message": str(error)}, actor="guard", **identity)
                response = {"ok": False, "error_type": "PolicyError", "reason_code": error.code, "error": str(error)}
            except CLIError as error:
                recoverable = error.command == "mesh" and error.kind == "MeshError"
                self._invalidate("open" if recoverable else "unknown")
                self.needs_restore = True
                if not recoverable:
                    self.execution_error = f"cli.{error.kind}"
                response = {"ok": False, "error_type": error.kind, "error": str(error)[:512],
                            "recovery": "Call open_part before another candidate." if recoverable else "Report execution_failure."}
            except asyncio.CancelledError:
                self.execution_error = "execution.cancelled"
                self._invalidate("unknown")
                self._record_return({"ok": False, "error_type": "Cancelled", "error": "Execution interrupted."}, **identity)
                raise
            except Exception as error:
                if not allowed:
                    self.trace.event("guard_decision", {"decision": "error", "reason_code": "guard.exception", "error_type": type(error).__name__}, actor="guard", **identity)
                self.execution_error = f"execution.{type(error).__name__}"
                self._invalidate("unknown")
                response = {"ok": False, "error_type": type(error).__name__, "error": str(error)[:512], "recovery": "Report execution_failure."}
            return self._record_return(response, **identity)

    def _record_return(self, response, *, call_id, model_call_id=None):
        response.update(phase=self.phase, state_revision=self.revision, initial_sf=self.initial_sf,
                        best_sf=self.best_sf, best_solve_cli_id=self.best_solve_cli_id,
                        remaining_trials=max(0, self.policy["max_trials"] - len(self.trials)))
        encoded = json.dumps(response, separators=(",", ":"), allow_nan=False)
        ref = self.trace.write_bytes(f"raw/tools/c{self.tool_calls:04d}.result.txt", encoded.encode())
        self.trace.event("tool_returned", {"result_ref": ref, "model_visible_bytes": len(encoded.encode()),
                         "oversize": len(encoded.encode()) > self.policy.get("routine_result_bytes", 2048)},
                         call_id=call_id, model_call_id=model_call_id, trial_id=self.trial_id)
        return encoded

    async def _dispatch(self, name, args, **identity):
        async def cli(command, *values, purpose="model_action"):
            return await self._cli(command, *values, purpose=purpose, **identity)
        if name == "open_part":
            info, opened = await cli("open-part", self.part_name)
            params, _ = await cli("get-parameters", purpose="verify_original_restoration")
            if any(info[key] != self.original[key] for key in ("name", "revision", "material", "default_load")) or params != self.original["parameters"]:
                raise ExecutionError("Original identity, default load or parameters do not match")
            self.parameters = params
            self._invalidate("open")
            self.current_changed = None
            self.needs_restore = False
            self.restoration_cli_id = opened
            self.trial_id = "t0000" if self.initial_sf is None else f"t{len(self.trials) + 1:04d}"
            if self.initial_sf is None:
                self.trace.event("trial_started", {"restoration_cli_id": opened, "parameter": None, "type": "baseline"}, trial_id=self.trial_id, **identity)
            return {**info, "parameters": params, "constraints": self.constraints, "exploration_ranges": self.bounds,
                    "restored_original": True, "range_scope": "Exploratory, not an exhaustive feasible domain"}
        if name == "get_parameters":
            params, _ = await cli("get-parameters", purpose="explicit_parameter_inspection")
            if params != self.parameters:
                raise ExecutionError("Unexpected effective parameters")
            return params
        if name == "set_parameter":
            param, value = args["name"], args["value"]
            self.trials.append({"trial_id": self.trial_id, "name": param, "value": value, "solve_cli_id": None})
            self.trace.event("trial_started", {"restoration_cli_id": self.restoration_cli_id, "parameter": param, "type": "candidate"}, trial_id=self.trial_id, **identity)
            result, _ = await cli("set-parameter", param, value)
            params, _ = await cli("get-parameters", purpose="verify_effective_mutation")
            expected = {**self.original["parameters"], param: value}
            if params != expected or result.get("new_value") != value or result.get("downstream_invalidated") is not True:
                raise ExecutionError("Effective parameter readback disagrees with requested mutation")
            self.parameters = params
            self.current_changed = {"name": param, "from": self.original["parameters"][param], "to": value}
            self._invalidate("open")
            return {**result, "changed_parameter": self.current_changed}
        if name == "mesh":
            result, mesh_id = await cli("mesh")
            self._invalidate("meshed")
            self.mesh_cli_id = mesh_id
            return result
        if name == "apply_load":
            result, load_id = await cli("apply-load", "--direction", args["direction"], args["face_id"], args["force_N"])
            if result != self.original["default_load"]:
                raise ExecutionError("CLI returned a different load")
            self._invalidate("loaded")
            self.load_cli_id = load_id
            return result
        if name == "solve":
            result, solve_id = await cli("solve")
            sf = result.get("safety_factor")
            if not finite_number(sf) or result.get("converged") is not True or result.get("load") != self.original["default_load"]:
                raise ExecutionError("Solve is not a converged finite result under the required default load")
            self.phase, self.solve_revision, self.latest_sf = "solved", self.revision, sf
            self.solve_result, self.solve_cli_id = result, solve_id
            if self.initial_sf is None:
                if self.parameters != self.original["parameters"]:
                    raise ExecutionError("Baseline is not original geometry")
                self.initial_sf, self.initial_solve_cli_id = sf, solve_id
            else:
                self.trials[-1].update(solve_cli_id=solve_id, safety_factor=sf)
            if self.best_sf is None or sf > self.best_sf:
                self.best_sf, self.best_solve_cli_id = sf, solve_id
            self.trace.event("solve_observed", {"solve_cli_id": solve_id, "state_revision": self.revision,
                             "mesh_cli_id": self.mesh_cli_id, "load_cli_id": self.load_cli_id,
                             "parameters": self.parameters, "applied_load": result["load"],
                             "safety_factor": sf, "converged": result["converged"]}, trial_id=self.trial_id, **identity)
            return {key: result[key] for key in ("safety_factor", "max_stress_MPa", "converged", "iterations", "load")} | {"solve_cli_id": solve_id, "changed_parameter": self.current_changed}
        if name == "save_part":
            return await self._save(cli, identity)
        raise ExecutionError("Unhandled tool")

    async def _save(self, cli, identity):
        relative = f"outputs/{self.part_name}.json"
        (self.workdir / "outputs").mkdir(exist_ok=True)
        _, save_id = await cli("save-part", relative)
        payload = (self.workdir / relative).read_bytes()
        saved = parse_json(payload)
        expected_solve = {key: value for key, value in self.solve_result.items() if key != "log"}
        if (saved.get("name") != self.part_name or saved.get("revision") != self.original["revision"]
                or saved.get("parameters") != self.parameters or saved.get("applied_load") != self.original["default_load"]
                or saved.get("solve_result") != expected_solve):
            raise ExecutionError("Saved file disagrees with the verified solve and effective geometry")
        changed = [key for key in self.parameters if self.parameters[key] != self.original["parameters"][key]]
        if len(changed) != 1:
            raise ExecutionError("Saved repair does not change exactly one parameter")
        artifact_ref = self.trace.write_bytes(relative, payload)
        self.trace.event("artifact_saved", {"artifact_id": "a0001", "artifact_ref": artifact_ref,
                         "save_cli_id": save_id, "solve_cli_id": self.solve_cli_id}, trial_id=self.trial_id, **identity)
        destination = self.publish_dir / f"{self.part_name}.json"
        try:
            self.publish_dir.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.read_bytes() != payload:
                    raise ExecutionError("Output destination already contains different bytes; choose a new publish directory")
            else:
                # Hard-link a completed temporary file for atomic no-overwrite publication.
                fd, temporary = tempfile.mkstemp(prefix=".partlab-", dir=self.publish_dir)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(payload)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.link(temporary, destination)
                finally:
                    os.unlink(temporary)
            published = destination.read_bytes()
            if published != payload:
                raise ExecutionError("Published output bytes changed")
            published_ref = self.trace.write_bytes(f"published/{self.part_name}.json", published)
        except Exception as error:
            self.trace.event("artifact_published", {"artifact_id": "a0001", "path": relative, "status": "failed", "error_type": type(error).__name__}, **identity)
            raise
        self.trace.event("artifact_published", {"artifact_id": "a0001", "path": relative, "published_ref": published_ref,
                         "destination": str(destination), "status": "ok"}, **identity)
        self.saved, self.artifact_id = artifact_ref, "a0001"
        return {"path": relative, "artifact_id": self.artifact_id, "changed_parameter": self.current_changed,
                "safety_factor": self.latest_sf, "solve_cli_id": self.solve_cli_id, "sha256": artifact_ref["sha256"]}

    def outcome(self, final_message_ref, failure=None):
        failure = failure or self.execution_error
        if failure:
            status, reason = "execution_failure", failure
        elif self.artifact_id:
            status, reason = "repaired", "first_verified_fix_saved"
        elif self.initial_sf is not None and self.initial_sf >= 2:
            status, reason = "already_safe", "original_meets_target"
        elif self.initial_sf is not None:
            status, reason = "no_repair_found", "trial_limit" if len(self.trials) >= self.policy["max_trials"] else "agent_stopped"
            if self.latest_sf is not None and self.latest_sf >= 2:
                status, reason = "execution_failure", "qualifying_repair_not_saved"
        else:
            status, reason = "execution_failure", "baseline_not_completed"
        return {"run_id": self.trace.run_id, "status": status, "reason_code": reason,
                "initial_sf": self.initial_sf, "final_sf": self.latest_sf if self.artifact_id else self.best_sf,
                "initial_solve_cli_id": self.initial_solve_cli_id,
                "solve_cli_id": self.solve_cli_id if self.artifact_id else self.best_solve_cli_id,
                "changed_parameter": self.current_changed if self.artifact_id else None,
                "artifact_id": self.artifact_id, "artifact_ref": self.saved,
                "final_message_ref": final_message_ref, "final_message_format": "json/1",
                "search": {"scope": "bounded_exploration_not_infeasibility_proof", "ranges": self.bounds,
                           "budget": {"max_trials": self.policy["max_trials"], "max_tool_calls": self.policy["max_tool_calls"],
                                      "max_model_turns": self.policy["max_model_turns"], "run_timeout_seconds": self.policy["run_timeout_seconds"]},
                           "trials": self.trials, "max_trials": self.policy["max_trials"],
                           "tool_calls": self.tool_calls, "termination": reason}}
