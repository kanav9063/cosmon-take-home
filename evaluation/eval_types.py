"""Internal evaluator records. These are not a producer wire format."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any

EVALUATOR_VERSION = "1.1.0"
PROFILE = "partlab-cli/9b202e1b"
BINARY_SHA256 = "9b202e1ba07861f52f12005108e81815ef14d92f2db3ba322fc51422746ab183"
SCHEMA = "partlab.trace/0.1-proposal"


class InputError(ValueError):
    """Defined invalid/unavailable input; never use for programming errors."""


def strict_json(raw: bytes | str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InputError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise InputError(f"Nonfinite JSON number: {value}")
    try:
        return json.loads(raw, parse_float=Decimal, object_pairs_hook=pairs,
                          parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise InputError(str(exc)) from exc


def number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return None
    result = Decimal(value)
    return result if result.is_finite() else None


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(jsonable(value), sort_keys=True, indent=2,
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass
class Ref:
    path: str
    sha256: str
    bytes: int
    event_id: str | None = None
    line: int | None = None
    pointer: str | None = None


@dataclass
class Issue:
    code: str
    message: str
    status: str = "unknown"
    refs: list[Ref] = field(default_factory=list)
    seq: int | None = None


@dataclass
class Case:
    case_id: str
    original: dict
    original_sha256: str
    target_sf: Decimal = Decimal("2.0")
    limits: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    output_path: str = ""
    binary_sha256: str = BINARY_SHA256
    profile: str = PROFILE

    @property
    def parameters(self):
        return self.original["parameters"]

    @property
    def default_load(self):
        return self.original["default_load"]


@dataclass
class Event:
    event_id: str
    seq: int
    kind: str
    data: dict
    refs: list[Ref] = field(default_factory=list)
    trial_id: str | None = None
    call_id: str | None = None
    cli_id: str | None = None
    session_id: str = "main"
    model_call_id: str | None = None


@dataclass
class Action:
    cli_id: str
    name: str
    argv: list[str]
    start_seq: int
    end_seq: int
    result: Any = None
    success: bool | None = None
    termination: str = "incomplete"
    exit_code: int | None = None
    refs: list[Ref] = field(default_factory=list)
    trial_id: str | None = None
    call_id: str | None = None
    session_id: str = "main"
    error: str | None = None
    uncertain_order: bool = False


@dataclass
class Artifact:
    artifact_id: str
    save_cli_id: str
    solve_cli_id: str | None
    path: str
    content: dict | None
    refs: list[Ref] = field(default_factory=list)
    sha256: str | None = None
    integrity: str = "unknown"
    event_seq: int = 0


@dataclass
class EvidenceRun:
    bundle: Path
    manifest: dict = field(default_factory=dict)
    run_id: str | None = None
    origin: str = "unknown"
    actions: list[Action] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    outcome: dict | None = None
    final_message: Any = None
    final_message_format: str | None = None
    completion: dict | None = None
    issues: list[Issue] = field(default_factory=list)
    complete: bool = False
    execution_complete: bool = False
    original_matches: bool | None = None
    profile_supported: bool = False
    refs: list[Ref] = field(default_factory=list)
    input_digest: str = ""
    metrics: dict = field(default_factory=dict)


@dataclass
class State:
    part_name: str | None = None
    revision: Any = None
    parameters: dict | None = None
    phase: str = "unknown"
    generation: int = 0
    mesh_id: str | None = None
    load: dict | None = None
    load_id: str | None = None
    live_solve_id: str | None = None
    original_verified: bool = False
    restored: bool = False
    trial_id: str | None = None
    trial_parameter: str | None = None
    refs: list[Ref] = field(default_factory=list)


@dataclass
class Certificate:
    cli_id: str
    seq: int
    state: State
    result: dict
    sf: Decimal | None
    converged: bool | None
    valid: bool
    refs: list[Ref] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class Mutation:
    cli_id: str
    seq: int
    parameters: dict | None
    parameter: str | None
    restored: bool | None
    refs: list[Ref] = field(default_factory=list)
    observed_after_failure: bool = False


@dataclass
class Save:
    cli_id: str
    seq: int
    path: str | None
    state: State
    certificate_id: str | None
    refs: list[Ref] = field(default_factory=list)


@dataclass
class History:
    states: dict[str, State] = field(default_factory=dict)
    before: dict[str, State] = field(default_factory=dict)
    solves: dict[str, Certificate] = field(default_factory=dict)
    saves: dict[str, Save] = field(default_factory=dict)
    mutations: list[Mutation] = field(default_factory=list)
    baseline: Certificate | None = None
    baseline_candidates: list[Certificate] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    final_states: dict[str, State] = field(default_factory=dict)


@dataclass
class Check:
    check_id: str
    scope: str
    subject_id: str
    status: str
    reason: str
    code: str | None = None
    refs: list[Ref] = field(default_factory=list)
    expected: Any = None
    observed: Any = None
    action: str | None = None

    @property
    def instance_id(self):
        return f"{self.check_id}:{self.scope}:{self.subject_id}"


@dataclass
class Evaluation:
    checks: list[Check]
    summary: dict
    observed_outcome: str
    diagnostics: list[Issue] = field(default_factory=list)
    details: dict = field(default_factory=dict)
