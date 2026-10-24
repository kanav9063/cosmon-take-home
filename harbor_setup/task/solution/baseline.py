"""Scripted CLI infrastructure check; this is not a captured model run."""

import hashlib
import json
from pathlib import Path
import subprocess


APP = Path("/app")
ARTIFACTS = Path("/logs/artifacts")
PART = "bracket_v3"
PURPOSE = "scripted-cli-infrastructure-preparation"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if Path("/tests").exists():
        raise RuntimeError("Trusted verifier tests leaked into the agent environment")
    # This file is intentionally not exported. The verifier must never see it.
    (APP / "unexported-agent-marker").write_text("agent environment only\n")
    original_path = APP / "parts" / f"{PART}.json"
    original = json.loads(original_path.read_text())
    original_hashes = {
        "partlab": digest(APP / "partlab"),
        f"parts/{PART}.json": digest(original_path),
    }
    saved_path = ARTIFACTS / f"{PART}-baseline.json"
    commands_path = ARTIFACTS / "commands.jsonl"
    results = {}
    load = original["default_load"]
    commands = [
        ["reset"],
        ["open-part", PART],
        ["mesh"],
        ["apply-load", load["face_id"], str(load["force_N"])],
        ["solve"],
        ["get-safety-factor"],
        ["save-part", str(saved_path)],
    ]
    with commands_path.open("x") as evidence:
        for sequence, args in enumerate(commands, start=1):
            process = subprocess.run(
                ["/app/partlab", *args], cwd=APP,
                capture_output=True, text=True, timeout=30,
            )
            evidence.write(json.dumps({
                "purpose": PURPOSE,
                "call_id": f"cli-{sequence:03d}",
                "argv": ["/app/partlab", *args],
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }) + "\n")
            evidence.flush()
            envelope = json.loads(process.stdout)
            if process.returncode != 0 or envelope.get("ok") is not True:
                raise RuntimeError(f"CLI smoke command failed: {args[0]}")
            results[args[0]] = envelope["result"]

    outcome = {
        "purpose": PURPOSE,
        "part": PART,
        "original_hashes": original_hashes,
        "original_parameters": original["parameters"],
        "default_load": load,
        "safety_factor": results["get-safety-factor"]["safety_factor"],
        "saved_artifact": saved_path.name,
        "saved_sha256": digest(saved_path),
        "commands_sha256": digest(commands_path),
        "command_count": len(commands),
        "agent_only_marker_created": True,
    }
    (ARTIFACTS / "outcome.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome, indent=2))


if __name__ == "__main__":
    main()
