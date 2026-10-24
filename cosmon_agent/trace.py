"""Append-only local evidence; raw files are written before their references."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

SCHEMA = "partlab.trace/0.1-proposal"


def now():
    return datetime.now(timezone.utc).isoformat()


def reference(path, payload):
    return {"path": path, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}


class Trace:
    def __init__(self, path: Path, run_id=None):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=False)
        self.run_id = run_id or str(uuid.uuid4())
        self.events = []
        self.finished = False

    def write_bytes(self, relative, payload):
        relative = str(relative)
        dest = self.path / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or not dest.resolve().is_relative_to(self.path):
            raise ValueError("Evidence path must stay inside bundle")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(payload)
            stream.flush()
        return reference(relative, payload)

    def write_json(self, relative, value):
        return self.write_bytes(relative, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode())

    def event(self, kind, data, *, actor="runner", call_id=None,
              model_call_id=None, cli_id=None, trial_id=None):
        if self.finished:
            raise RuntimeError("Trace already complete")
        seq = len(self.events) + 1
        event = {"schema_version": SCHEMA, "run_id": self.run_id,
                 "event_id": f"e{seq:06d}", "seq": seq, "time": now(),
                 "kind": kind, "actor": actor, "call_id": call_id,
                 "model_call_id": model_call_id, "cli_id": cli_id,
                 "trial_id": trial_id, "data": data}
        encoded = json.dumps(event, allow_nan=False) + "\n"
        with (self.path / "events.jsonl").open("a") as stream:
            stream.write(encoded)
            stream.flush()
        self.events.append(event)
        return event

    def finish(self, outcome):
        outcome_ref = self.write_json("outcome.json", outcome)
        self.event("run_finished", {"outcome_ref": outcome_ref, "status": outcome["status"]})
        files = {}
        for path in sorted(self.path.rglob("*")):
            if path.is_file():
                ref = reference(path.relative_to(self.path).as_posix(), path.read_bytes())
                files[ref.pop("path")] = ref
        self.write_json("completion.json", {"run_id": self.run_id, "status": "completed",
                        "event_count": len(self.events), "last_seq": len(self.events), "files": files})
        self.finished = True
