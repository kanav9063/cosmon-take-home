"""Verify the local Harbor plumbing, not the take-home agent's correctness."""

import hashlib
import json
import math
from pathlib import Path


APP = Path("/app")
ARTIFACTS = Path("/logs/artifacts")
VERIFIER = Path("/logs/verifier")
PURPOSE = "scripted-cli-infrastructure-preparation"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    original_path = APP / "parts/bracket_v3.json"
    original = json.loads(original_path.read_text())
    outcome = json.loads((ARTIFACTS / "outcome.json").read_text())
    commands_path = ARTIFACTS / "commands.jsonl"
    records = [json.loads(line) for line in commands_path.read_text().splitlines()]
    expected_names = [
        "reset", "open-part", "mesh", "apply-load", "solve",
        "get-safety-factor", "save-part",
    ]
    require(outcome["purpose"] == PURPOSE, "incorrect preparation label")
    require(outcome["part"] == "bracket_v3", "incorrect part")
    require(len(records) == outcome["command_count"] == len(expected_names),
            "missing or extra CLI records")
    require([r["argv"][1] for r in records] == expected_names,
            "incorrect workflow ordering")
    require([r["call_id"] for r in records] == [f"cli-{i:03d}" for i in range(1, 8)],
            "missing or duplicate call IDs")
    results = {}
    for record in records:
        require(record["purpose"] == PURPOSE, "incorrect CLI record label")
        require(record["argv"][0] == "/app/partlab", "incorrect executable")
        require(record["returncode"] == 0, "failed CLI command")
        require(isinstance(record["stderr"], str), "missing stderr")
        envelope = json.loads(record["stdout"])
        require(envelope.get("ok") is True, "unsuccessful CLI envelope")
        results[record["argv"][1]] = envelope["result"]

    require(outcome["original_hashes"] == {
        "partlab": digest(APP / "partlab"),
        "parts/bracket_v3.json": digest(original_path),
    }, "original input hash mismatch")
    require(outcome["commands_sha256"] == digest(commands_path),
            "CLI record hash mismatch")
    require(outcome["original_parameters"] == original["parameters"],
            "original parameter mismatch")
    require(outcome["default_load"] == original["default_load"],
            "original default load mismatch")
    require(results["open-part"]["name"] == "bracket_v3", "wrong opened part")
    for load in [results["open-part"]["default_load"], results["apply-load"],
                 results["solve"]["load"]]:
        require(load == original["default_load"], "incorrect analysis load")
    require(results["solve"]["converged"] is True, "solve did not converge")
    sf = outcome["safety_factor"]
    require(type(sf) in (float, int) and math.isfinite(sf) and sf > 0,
            "safety factor must be finite and positive")
    require(sf == results["solve"]["safety_factor"] ==
            results["get-safety-factor"]["safety_factor"], "safety factor mismatch")

    require(outcome["saved_artifact"] == "bracket_v3-baseline.json",
            "unexpected saved artifact path")
    saved_path = ARTIFACTS / "bracket_v3-baseline.json"
    require(results["save-part"]["saved_to"] == str(saved_path),
            "CLI saved a different path")
    require(outcome["saved_sha256"] == digest(saved_path),
            "saved artifact hash mismatch")
    saved = json.loads(saved_path.read_text())
    require(saved["name"] == "bracket_v3", "wrong saved part")
    require(saved["parameters"] == original["parameters"],
            "baseline parameters were modified")
    require(saved["applied_load"] == original["default_load"],
            "saved load mismatch")
    require(saved["solve_result"] == {
        k: v for k, v in results["solve"].items() if k != "log"
    }, "saved solve mismatch")
    return {"safety_factor": sf, "command_count": len(records)}


def main():
    VERIFIER.mkdir(parents=True, exist_ok=True)
    report = {"purpose": "infrastructure-preparation-only", "passed": False}
    try:
        report.update(verify())
        report["passed"] = True
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        report["finding"] = {"type": type(error).__name__, "message": str(error)}
    (VERIFIER / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (VERIFIER / "reward.txt").write_text("1\n" if report["passed"] else "0\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
