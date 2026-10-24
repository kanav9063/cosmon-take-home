#!/usr/bin/env python3
"""Exercise local Harbor/Docker, using scripted oracle and no-op agents only."""

from __future__ import annotations

import grp
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
HARBOR = ROOT / ".venv-harbor/bin/harbor"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def command(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, f"{shlex.join(args)} failed: {result.stderr[-2000:]}")
    return result.stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    os.chdir(ROOT)
    os.environ["HARBOR_TELEMETRY"] = "0"
    require(importlib.metadata.version("harbor") == "0.24.0", "Use the pinned .venv-harbor environment")
    if not os.access("/var/run/docker.sock", os.R_OK | os.W_OK):
        user = pwd.getpwuid(os.getuid()).pw_name
        group = grp.getgrnam("docker")
        require(user in group.gr_mem, "Current user needs Docker access; see docs/HARBOR_SETUP.md")
        require(not os.environ.get("COSMON_HARBOR_GROUP_REEXEC"), "Docker socket still inaccessible after group refresh")
        os.environ["COSMON_HARBOR_GROUP_REEXEC"] = "1"
        os.execvp("sg", ["sg", "docker", "-c", shlex.join([sys.executable, str(Path(__file__).resolve())])])

    versions = {
        "harbor": importlib.metadata.version("harbor"),
        "python": sys.version.split()[0],
        "docker_server": command(["docker", "version", "--format", "{{.Server.Version}}"]),
        "compose": command(["docker", "compose", "version", "--short"]),
    }
    originals = [ROOT / "README.md", ROOT / "partlab", *sorted((ROOT / "parts").glob("*.json"))]
    before = {str(path.relative_to(ROOT)): digest(path) for path in originals}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    suite = ROOT / ".harbor-jobs" / stamp
    task = suite / "task"
    shutil.copytree(ROOT / "harbor_setup/task", task,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "partlab", task / "environment/partlab")
    shutil.copytree(ROOT / "parts", task / "environment/parts")
    summary = {
        "purpose": "infrastructure-preparation-only",
        "model_calls": 0,
        "versions": versions,
        "dependency_lock_sha256": digest(ROOT / "harbor_setup/requirements.lock"),
        "suite": str(suite.relative_to(ROOT)),
        "original_sha256": before,
        "checks": [],
    }

    for agent, attempts, expected_reward in [("oracle", 2, 1.0), ("nop", 1, 0.0)]:
        args = [str(HARBOR), "run", "-p", str(task), "-a", agent,
                "-e", "docker", "-k", str(attempts), "-n", "1", "-r", "0",
                "-o", str(suite), "--job-name", agent, "--delete"]
        log = suite / f"{agent}.console.log"
        print(f"Running Harbor {agent}: {attempts} trial(s); log {log.relative_to(ROOT)}", flush=True)
        with log.open("w") as stream:
            result = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
        require(result.returncode == 0, f"Harbor command failed; inspect {log}")
        job = suite / agent
        job_result = json.loads((job / "result.json").read_text())
        require(job_result.get("finished_at") is not None, f"{agent}: job unfinished")
        require(job_result["n_total_trials"] == attempts, f"{agent}: wrong scheduled count")
        require(job_result["stats"]["n_completed_trials"] == attempts, f"{agent}: incomplete trials")
        require(job_result["stats"]["n_errored_trials"] == 0, f"{agent}: execution errors")
        trials = sorted(job.glob("*/result.json"))
        require(len(trials) == attempts, f"{agent}: expected {attempts} trial results, got {len(trials)}")
        for trial_file in trials:
            trial = json.loads(trial_file.read_text())
            require(trial.get("finished_at") is not None, f"Unfinished trial: {trial_file}")
            require(trial.get("exception_info") is None, f"Trial exception: {trial_file}")
            require(trial["agent_info"]["name"] == agent, f"Wrong agent: {trial_file}")
            require(trial["agent_info"].get("model_info") is None, f"Unexpected model: {trial_file}")
            rewards = (trial.get("verifier_result") or {}).get("rewards")
            require(rewards == {"reward": expected_reward}, f"Unexpected reward {rewards}: {trial_file}")
            directory = trial_file.parent
            verifier_report = json.loads((directory / "verifier/report.json").read_text())
            exit_file = directory / "agent/exit-code.txt"
            require(not exit_file.exists() or exit_file.read_text().strip() == "0",
                    f"Agent script exited unsuccessfully: {exit_file}")
            check = {
                "agent": agent, "reward": expected_reward,
                "trial_result": str(trial_file.relative_to(ROOT)),
                "trial_result_sha256": digest(trial_file),
                "verifier_report": str((directory / "verifier/report.json").relative_to(ROOT)),
                "verifier_report_sha256": digest(directory / "verifier/report.json"),
                "exception": None,
                "agent_exit": "success",
            }
            if agent == "oracle":
                require(verifier_report.get("passed") is True, "Oracle verifier did not finish successfully")
                artifacts = directory / "artifacts/logs/artifacts"
                outcome_file = artifacts / "outcome.json"
                outcome = json.loads(outcome_file.read_text())
                require(outcome["original_hashes"] == {
                    "partlab": before["partlab"],
                    "parts/bracket_v3.json": before["parts/bracket_v3.json"],
                }, "Container did not use the staged original binary/part")
                commands = artifacts / "commands.jsonl"
                raw = [json.loads(line) for line in commands.read_text().splitlines()]
                require(len(raw) == 7, "Missing captured CLI commands")
                require(digest(commands) == outcome["commands_sha256"], "Command log hash mismatch")
                saved = artifacts / "bracket_v3-baseline.json"
                require(digest(saved) == outcome["saved_sha256"], "Saved part hash mismatch")
                check.update(safety_factor=outcome["safety_factor"],
                             artifact_dir=str(artifacts.relative_to(ROOT)),
                             command_count=len(raw), artifact_capture="pass")
            else:
                finding = verifier_report.get("finding", {})
                require(verifier_report.get("passed") is False
                        and finding.get("type") == "FileNotFoundError"
                        and "outcome.json" in finding.get("message", ""),
                        "No-op failed for an unexpected reason")
                require(not (directory / "artifacts/logs/artifacts/outcome.json").exists(), "No-op inherited an oracle artifact")
                check["fresh_environment"] = "pass"
                check["expected_missing_output"] = "pass"
            summary["checks"].append(check)

    require(before == {str(path.relative_to(ROOT)): digest(path) for path in originals}, "Starter files changed")
    summary["starter_unchanged"] = True
    summary["status"] = "pass"
    report = suite / "summary.json"
    report.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"PASS: two oracle rewards=1, no-op reward=0; report {report.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
