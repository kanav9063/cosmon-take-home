#!/usr/bin/env python3
"""Capture baseline CLI I/O in temporary workspaces; not an agent or repair run."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(directory):
    return {str(p.relative_to(directory)): sha256(p.read_bytes())
            for p in directory.rglob("*") if p.is_file()} if directory.exists() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    originals = [ROOT / "TASK.md", ROOT / "partlab", *sorted((ROOT / "parts").glob("*.json"))]
    hashes = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in originals}
    session_exists = (ROOT / ".partlab").exists()
    session = snapshot(ROOT / ".partlab")
    manifest = {
        "kind": "partlab_cli_io_inspection", "is_agent_run": False, "model_calls": 0,
        "started_at": datetime.now(timezone.utc).isoformat(), "starter_sha256": hashes,
        "purpose": "Inspect unchanged baselines, including deliberately saving unsafe baseline outputs.",
        "commands": [], "baselines": {},
    }
    with tempfile.TemporaryDirectory(prefix="partlab-io-baseline-") as temp:
        work = Path(temp)
        shutil.copy2(ROOT / "partlab", work / "partlab")
        shutil.copytree(ROOT / "parts", work / "parts")

        def call(case, *arguments, help_text=False):
            command_id = f"c{len(manifest['commands']) + 1:03}"
            argv = ["./partlab", *arguments]
            result = subprocess.run(argv, cwd=work, capture_output=True, timeout=15,
                                    env={"PATH": os.defpath, "LANG": "C.UTF-8", "TMPDIR": temp})
            stdout_name, stderr_name = f"{command_id}.stdout", f"{command_id}.stderr"
            (output / stdout_name).write_bytes(result.stdout)
            (output / stderr_name).write_bytes(result.stderr)
            record = {"id": command_id, "case": case, "argv": argv, "cwd": "isolated temporary workspace",
                      "exit_code": result.returncode, "stdout": stdout_name, "stderr": stderr_name,
                      "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr)}
            manifest["commands"].append(record)
            assert result.returncode == 0, record
            if help_text:
                return None
            envelope = json.loads(result.stdout)
            assert envelope["ok"] is True, record
            value = envelope["result"]
            record["result_shape"] = sorted(value) if isinstance(value, dict) else type(value).__name__
            return value

        call("discovery", "--help", help_text=True)
        call("discovery", "state-dir")
        call("discovery", "list-parts")
        for name in ("bracket_v3", "flange_v1"):
            original = json.loads((work / "parts" / f"{name}.json").read_bytes())
            (output / f"{name}.original.json").write_bytes((work / "parts" / f"{name}.json").read_bytes())
            call(name, "reset")
            call(name, "open-part", name)
            call(name, "get-active-part")
            call(name, "get-parameters")
            call(name, "list-features")
            load = original["default_load"]
            call(name, "get-feature", load["face_id"])
            call(name, "mesh")
            call(name, "apply-load", "--direction", load["direction"], load["face_id"], str(load["force_N"]))
            solve = call(name, "solve")
            sf = call(name, "get-safety-factor")
            call(name, "get-max-stress")
            call(name, "get-solve-log")
            call(name, "get-active-part")
            save_path = f"outputs/{name}-unsafe-baseline.json"
            call(name, "save-part", save_path)
            saved = (work / save_path).read_bytes()
            (output / f"{name}.baseline-save.json").write_bytes(saved)
            assert solve["safety_factor"] == sf["safety_factor"]
            manifest["baselines"][name] = {
                "parameters": original["parameters"], "default_load": load,
                "safety_factor": solve["safety_factor"], "solve_fields": sorted(solve),
                "saved_fields": sorted(json.loads(saved)), "save_sha256": sha256(saved),
                "is_repair": False,
            }
        call("cleanup", "reset")

    assert hashes == {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in originals}
    assert session_exists == (ROOT / ".partlab").exists() and session == snapshot(ROOT / ".partlab")
    manifest.update(completed_at=datetime.now(timezone.utc).isoformat(),
                    temporary_workspace_removed=not work.exists(), starter_and_checkout_session_unchanged=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), "commands": len(manifest['commands']),
                      "baselines": manifest["baselines"], "starter_and_checkout_session_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
