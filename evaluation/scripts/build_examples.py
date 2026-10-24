#!/usr/bin/env python3
"""Build inspectable synthetic bundles, optionally capture real scripted CLI runs.

No API credentials, model calls or network access are used. Existing destinations
are refused. Synthetic solver numbers are test inputs, not physical predictions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
sys.path.insert(0, str(ROOT / "tests"))
from bundle_factory import BINARY_SHA256, Builder, SCENARIOS, scenario_bundle


def capture_scripted(destination: Path, part_name: str) -> Path:
    """Capture baseline and one permitted thickness trial without a model.

    Trial values are intentionally explicit scripted controls, not a repair
    search algorithm. Success is reported only if the actual CLI result reaches
    the task threshold. Flange may truthfully exhaust this one-candidate search.
    """
    if hashlib.sha256((REPOSITORY / "partlab").read_bytes()).hexdigest() != BINARY_SHA256:
        raise RuntimeError("PartLab binary differs from the pinned capture profile")
    with tempfile.TemporaryDirectory(prefix="partlab-eval-capture-") as temp:
        workdir = Path(temp)
        shutil.copy2(REPOSITORY / "partlab", workdir / "partlab")
        shutil.copytree(REPOSITORY / "parts", workdir / "parts")
        b = Builder(destination, "scripted-one-candidate", part_name,
                    evidence_kind="preparation_check", workdir=workdir)
        b.begin()
        if b.initial_sf >= 2:
            b.save()
            return b.finish("already_safe")
        b.restore()
        b.set_parameter("thickness_mm", 5)
        b.analyze()
        if b.solve_result["safety_factor"] >= 2 and b.solve_result.get("converged") is True:
            b.save()
            return b.finish("repaired")
        return b.finish("no_repair_found", reason_code="SEARCH_BUDGET_EXHAUSTED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures" / "examples")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS,
                        help="Generate selected synthetic scenarios; default all")
    parser.add_argument("--real", action="store_true", help="Also capture exact scripted PartLab runs")
    args = parser.parse_args()
    # Refuse overwrite before creating any output, including previously generated
    # evidence. Users can choose another destination to preserve historical runs.
    selected = list(dict.fromkeys(args.scenario or SCENARIOS))
    names = list(selected)
    if args.real:
        names += ["scripted_bracket_v3", "scripted_flange_v1"]
    collisions = [str(args.output / name) for name in [*names, "inputs.json"]
                  if (args.output / name).exists()]
    if collisions:
        parser.error("Refusing to overwrite: " + ", ".join(collisions))
    for name in selected:
        path = scenario_bundle(args.output / name, name)
        print(json.dumps({"bundle": str(path), "evidence_kind": "synthetic_fixture"}))
    if args.real:
        for part in ("bracket_v3", "flange_v1"):
            path = capture_scripted(args.output / f"scripted_{part}", part)
            outcome = json.loads((path / "outcome.json").read_bytes())
            print(json.dumps({"bundle": str(path), "evidence_kind": "preparation_check",
                              "status": outcome["status"], "initial_sf": outcome["initial_sf"],
                              "final_sf": outcome["final_sf"]}))
    entries = []
    for name in names:
        manifest = json.loads((args.output / name / "manifest.json").read_bytes())
        entries.append({"id": name, "case": manifest["case"]["part_name"], "path": name})
    with (args.output / "inputs.json").open("x") as file:
        json.dump({"inputs": entries}, file, indent=2, sort_keys=True)
        file.write("\n")
    print(json.dumps({"inputs": str(args.output / "inputs.json"), "count": len(entries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
