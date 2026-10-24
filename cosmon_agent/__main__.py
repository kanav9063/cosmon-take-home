"""Command line entry point for the bounded PartLab repair agent."""

import argparse
import asyncio
import json
from pathlib import Path
import re
import uuid

from .agent import DEFAULT_POLICY, ROOT, load_config, load_policy, run_agent


def part_name(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        raise argparse.ArgumentTypeError("Part names may contain only letters, digits, underscores and hyphens")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", required=True, type=part_name, help="Named part under parts/, with exploration ranges in the policy")
    parser.add_argument("--output", type=Path, help="New exclusive trace directory")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--publish-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()
    try:
        config = load_config(args.env_file)
        policy = load_policy(args.policy)
    except (ValueError, OSError) as error:
        # Do not print parser or client exception text that might include secrets.
        print(json.dumps({"status": "configuration_error", "error_category": type(error).__name__}))
        return 2
    output = args.output or ROOT / "reports" / f"agent-{args.part}-{uuid.uuid4().hex}"
    try:
        outcome = asyncio.run(run_agent(args.part, output, config, policy, publish_dir=args.publish_dir))
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "trace": str(output)}))
        return 130
    except Exception as error:
        print(json.dumps({"status": "runner_error", "error_category": type(error).__name__, "trace": str(output)}))
        return 1
    print(json.dumps({"trace": str(output), **outcome}, indent=2, allow_nan=False))
    return 1 if outcome["status"] == "execution_failure" else 0


if __name__ == "__main__":
    raise SystemExit(main())
