"""Strict local evidence loading and the explicit PartLab proposal adapter.

No commands, imports named in traces, provider calls, or remote references run here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import stat
from typing import Callable

from eval_types import (Action, Artifact, Case, Event, EvidenceRun, InputError,
                        Issue, Ref, SCHEMA, canonical, digest, strict_json)


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 16 * 1024 * 1024
    max_total_bytes: int = 64 * 1024 * 1024
    max_record_bytes: int = 2 * 1024 * 1024
    max_files: int = 4096
    max_events: int = 100000

    def __post_init__(self):
        for value in vars(self).values():
            if type(value) is not int or value <= 0:
                raise InputError("Limits must be positive integers")


class Reader:
    def __init__(self, root: Path, limits: Limits, run: EvidenceRun):
        self.root, self.limits, self.run = root.resolve(), limits, run
        self.cache: dict[str, bytes] = {}
        self.inventory: dict | None = None
        self.total = 0

    def issue(self, code, message, status="unknown", refs=None, seq=None):
        self.run.issues.append(Issue(code, message, status, refs or [], seq))

    def read(self, name: str) -> tuple[bytes, Ref]:
        if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
            raise InputError("Invalid local reference path")
        path = PurePosixPath(name)
        if path.is_absolute() or any(p in ("..", ".", "") for p in name.split("/")):
            raise InputError(f"Escaping/noncanonical reference: {name}")
        target = self.root.joinpath(*path.parts)
        cursor = self.root
        for part in path.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise InputError(f"Symlink references are unsupported: {name}")
        if name not in self.cache:
            if len(self.cache) >= self.limits.max_files:
                raise InputError("Evidence file-count limit exceeded")
            if not stat.S_ISREG(target.stat().st_mode):
                raise InputError(f"Evidence must be a regular file: {name}")
            with target.open("rb") as stream:
                raw = stream.read(self.limits.max_file_bytes + 1)
            if len(raw) > self.limits.max_file_bytes:
                raise InputError(f"Evidence file size limit exceeded: {name}")
            if self.total + len(raw) > self.limits.max_total_bytes:
                raise InputError("Total evidence size limit exceeded")
            self.cache[name] = raw
            self.total += len(raw)
        raw = self.cache[name]
        return raw, Ref(name, digest(raw), len(raw))

    @staticmethod
    def verify(raw: bytes, reference: dict):
        if not isinstance(reference, dict):
            raise InputError("Reference must be an object")
        if type(reference.get("bytes")) is not int or reference["bytes"] != len(raw):
            raise InputError("Reference byte length mismatch")
        if reference.get("sha256") != digest(raw):
            raise InputError("Reference digest mismatch")

    def get(self, name: str, *, inventory=True) -> tuple[bytes, Ref] | None:
        try:
            raw, ref = self.read(name)
            if inventory and self.inventory is not None:
                if name not in self.inventory:
                    raise InputError(f"File omitted from completion inventory: {name}")
                self.verify(raw, self.inventory[name])
            return raw, ref
        except (InputError, OSError) as exc:
            code = "EVIDENCE_INTEGRITY_ERROR" if isinstance(exc, InputError) else "EVIDENCE_MISSING"
            self.issue(code, f"{name}: {exc}", "fail" if isinstance(exc, InputError) else "unknown")
            return None

    def reference(self, reference: object, *, missing_code="EVIDENCE_MISSING"):
        if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
            self.issue(missing_code, "Missing or malformed evidence reference")
            return None
        item = self.get(reference["path"])
        if item is None:
            return None
        try:
            self.verify(item[0], reference)
        except InputError as exc:
            self.issue("EVIDENCE_INTEGRITY_ERROR", str(exc), "fail", [item[1]])
            return None
        return item

    def document(self, name, *, inventory=True):
        item = self.get(name, inventory=inventory)
        if item is None:
            return None
        try:
            value = strict_json(item[0])
            if not isinstance(value, dict):
                raise InputError("Expected an object")
            self.run.refs.append(item[1])
            return value
        except (InputError, RecursionError) as exc:
            self.issue("TRACE_PARSE_ERROR", f"{name}: {exc}", refs=[item[1]])
            return None


KINDS = {"model_requested", "model_returned", "model_failed", "tool_proposed",
         "guard_decision", "cli_requested", "cli_started", "cli_finished",
         "state_observed", "trial_started", "solve_observed", "artifact_saved",
         "tool_returned", "run_finished", "artifact_published"}
READ_ONLY = {"get-parameters", "get-active-part", "get-safety-factor", "get-max-stress",
             "get-solve-log", "list-parts", "list-features", "get-feature", "state-dir",
             "compute-stress-from-handbook", "--help"}
COMMANDS = READ_ONLY | {"reset", "close-part", "open-part", "set-parameter", "mesh",
                        "apply-load", "solve", "save-part"}


def _gap(run, seq, reason, session="main"):
    run.events.append(Event(f"gap-{seq}-{len(run.events)}", seq, "evidence_gap",
                            {"scope": "all", "reason": reason}, session_id=session))


def _events(reader: Reader, run: EvidenceRun):
    item = reader.get("events.jsonl")
    if item is None:
        _gap(run, 0, "Missing/untrusted execution ledger")
        return
    raw, source = item
    ids, expected = set(), 1
    for line_no, line in enumerate(raw.splitlines(), 1):
        if line_no > reader.limits.max_events:
            reader.issue("TRACE_LIMIT_EXCEEDED", "Event count limit exceeded", seq=expected)
            _gap(run, expected, "Event count limit")
            break
        ref = Ref(source.path, source.sha256, source.bytes, line=line_no)
        try:
            if len(line) > reader.limits.max_record_bytes:
                raise InputError("Record size limit exceeded")
            value = strict_json(line)
            if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
                raise InputError("Event and data must be objects")
            seq, identity = value.get("seq"), value.get("event_id")
            if type(seq) is not int or seq != expected:
                raise InputError(f"Expected sequence {expected}, found {seq}")
            if not isinstance(identity, str) or not identity or identity in ids:
                raise InputError("Missing or duplicate event identity")
            if value.get("run_id") != run.run_id:
                raise InputError("Event run ID mismatch")
            kind = value.get("kind")
            if not isinstance(kind, str) or kind not in KINDS:
                raise InputError(f"Unsupported event kind: {kind}")
            session = value.get("session_id", "main")
            if not isinstance(session, str) or not session:
                raise InputError("Invalid session identity")
            for field in ("cli_id", "call_id", "trial_id", "model_call_id"):
                if value.get(field) is not None and not isinstance(value[field], str):
                    raise InputError(f"Invalid {field}")
            ref.event_id = identity
            ids.add(identity)
            event = Event(identity, seq, kind, value["data"], [ref],
                          value.get("trial_id"), value.get("call_id"), value.get("cli_id"), session,
                          value.get("model_call_id"))
            # Private projection fields can only be created by this adapter.
            event.data = {k: v for k, v in event.data.items() if not k.startswith("_")}
            run.events.append(event)
        except (InputError, RecursionError) as exc:
            reader.issue("TRACE_PARSE_ERROR", f"events.jsonl:{line_no}: {exc}", refs=[ref], seq=expected)
            _gap(run, expected, str(exc))
        expected += 1


def _actions(reader: Reader, run: EvidenceRun):
    groups: dict[str, list[Event]] = {}
    for event in run.events:
        if event.kind.startswith("cli_"):
            if not event.cli_id:
                reader.issue("CALL_LINK_INVALID", "CLI event has no attempt ID", refs=event.refs, seq=event.seq)
                _gap_pending = Event(f"unlinked-{event.event_id}", event.seq, "evidence_gap",
                                     {"scope": "all", "reason": "Unlinked CLI event"}, session_id=event.session_id)
                # Defer appending so iteration remains bounded.
                groups.setdefault("", []).append(_gap_pending)
            else:
                groups.setdefault(event.cli_id, []).append(event)
    run.events.extend(groups.pop("", []))
    for cli_id, events in groups.items():
        requests = [e for e in events if e.kind == "cli_requested"]
        starts = [e for e in events if e.kind == "cli_started"]
        finishes = [e for e in events if e.kind == "cli_finished"]
        refs = [r for e in events for r in e.refs]
        if len(requests) != 1 or len(starts) > 1 or len(finishes) > 1:
            reader.issue("EXECUTION_AMBIGUOUS", f"Conflicting/unlinked attempt {cli_id}", "fail", refs)
            _gap(run, min(e.seq for e in events), "Conflicting CLI attempt")
            continue
        request = requests[0]
        argv = request.data.get("argv")
        if not isinstance(argv, list) or len(argv) < 2 or not all(isinstance(x, str) for x in argv):
            reader.issue("CALL_LINK_INVALID", f"Invalid argv for {cli_id}", refs=refs)
            _gap(run, request.seq, "Unknown attempted action", request.session_id)
            continue
        action = Action(cli_id, argv[1], argv, request.seq,
                        finishes[0].seq if finishes else request.seq,
                        refs=refs, trial_id=request.trial_id, call_id=request.call_id,
                        session_id=request.session_id)
        if PurePosixPath(argv[0]).name != "partlab":
            reader.issue("UNSUPPORTED_EVIDENCE", "CLI executable is not PartLab", refs=refs)
            action.uncertain_order = True
        if action.name not in COMMANDS:
            reader.issue("UNSUPPORTED_EVIDENCE", f"Unknown action {action.name}", refs=refs)
            action.uncertain_order = True
        if not finishes:
            reader.issue("CALL_RESULT_MISSING", f"No terminal record for {cli_id}", refs=refs, seq=request.seq)
            run.actions.append(action)
            continue
        finish = finishes[0]
        same_identity = all(e.session_id == request.session_id and e.call_id == request.call_id
                            for e in events)
        term = finish.data.get("termination")
        order_ok = finish.seq > request.seq and (not starts or request.seq < starts[0].seq < finish.seq)
        if not same_identity or not order_ok or (not starts and term != "spawn_error"):
            reader.issue("EXECUTION_AMBIGUOUS", f"Attempt ordering/identity mismatch: {cli_id}", "fail", refs)
            action.uncertain_order = True
        action.termination = term if isinstance(term, str) else "incomplete"
        action.exit_code = finish.data.get("exit_code")
        if type(action.exit_code) is not int and action.exit_code is not None:
            reader.issue("INVALID_NUMERIC_EVIDENCE", f"Invalid exit code: {cli_id}", refs=refs)
            action.exit_code = None
        stdout = reader.reference(finish.data.get("stdout_ref"))
        stderr = reader.reference(finish.data.get("stderr_ref"))
        if stdout:
            action.refs.append(stdout[1])
        if stderr:
            action.refs.append(stderr[1])
        if stdout is not None and stderr is not None:
            try:
                envelope = strict_json(stdout[0])
                if not isinstance(envelope, dict) or type(envelope.get("ok")) is not bool:
                    raise InputError("Invalid CLI envelope")
                action.result = envelope.get("result")
                if term == "exit" and action.exit_code == 0 and envelope["ok"]:
                    action.success = True
                elif term == "exit" and type(action.exit_code) is int and action.exit_code != 0 and not envelope["ok"]:
                    action.success = False
                elif term in ("timeout", "signal", "spawn_error"):
                    action.success = False
                else:
                    reader.issue("EVIDENCE_CONTRADICTION", f"Exit/envelope disagree: {cli_id}", "fail", action.refs)
                action.error = envelope.get("error")
                if "parsed_envelope" in finish.data and finish.data["parsed_envelope"] != envelope:
                    reader.issue("EVIDENCE_CONTRADICTION", f"Producer parse disagrees: {cli_id}", "fail", action.refs)
            except (InputError, RecursionError) as exc:
                # Errors/interruptions may legitimately have non-JSON output; retain the failed execution.
                if term in ("timeout", "signal", "spawn_error") or (term == "exit" and action.exit_code not in (0, None)):
                    action.success = False
                    action.error = str(exc)
                elif action.name == "--help" and term == "exit" and action.exit_code == 0:
                    action.success = True
                else:
                    reader.issue("TRACE_PARSE_ERROR", f"CLI {cli_id}: {exc}", refs=action.refs, seq=finish.seq)
        run.actions.append(action)
    run.actions.sort(key=lambda action: (action.end_seq, action.cli_id))
    active: dict[str, list[Action]] = {}
    for action in sorted(run.actions, key=lambda a: a.start_seq):
        candidates = [a for a in active.get(action.session_id, []) if a.end_seq >= action.start_seq]
        for other in candidates:
            if action.name not in READ_ONLY or other.name not in READ_ONLY:
                action.uncertain_order = other.uncertain_order = True
                reader.issue("EXECUTION_AMBIGUOUS", "Overlapping stateful CLI attempts", "fail", action.refs + other.refs)
        candidates.append(action)
        active[action.session_id] = candidates


def _payloads(reader: Reader, run: EvidenceRun):
    solve_events = {e.event_id: e.data.get("solve_cli_id") for e in run.events if e.kind == "solve_observed"}
    actions = {action.cli_id: action for action in run.actions}
    artifact_sequences = {}
    for event in run.events:
        if event.kind == "artifact_saved":
            identity = event.data.get("artifact_id", event.event_id)
            if isinstance(identity, str):
                artifact_sequences.setdefault(identity, event.seq)
    for event in run.events:
        if event.kind == "artifact_saved":
            data = event.data
            identity = data.get("artifact_id", event.event_id)
            if not isinstance(identity, str) or not isinstance(data.get("save_cli_id"), str):
                reader.issue("CALL_LINK_INVALID", "Invalid artifact identity", refs=event.refs)
                continue
            reference = data.get("artifact_ref")
            item = reader.reference(reference, missing_code="ARTIFACT_MISSING")
            solve_id, solve_event = data.get("solve_cli_id"), data.get("solve_event_id")
            if ((solve_id is not None and not isinstance(solve_id, str))
                    or (solve_event is not None and not isinstance(solve_event, str))):
                reader.issue("CALL_LINK_INVALID", "Artifact solve identifiers must be strings", refs=event.refs)
                solve_id = solve_event = None
            if solve_id is None and isinstance(solve_event, str):
                solve_id = solve_events.get(solve_event)
                if not isinstance(solve_id, str):
                    reader.issue("CALL_LINK_INVALID", "Artifact solve event has no valid CLI ID", refs=event.refs)
                    solve_id = None
            artifact = Artifact(identity, data["save_cli_id"],
                                solve_id,
                                reference.get("path", "") if isinstance(reference, dict) and isinstance(reference.get("path"), str) else "", None,
                                refs=list(event.refs), event_seq=event.seq)
            save_action = actions.get(artifact.save_cli_id)
            if save_action is None:
                reader.issue("CALL_LINK_INVALID", "Artifact references an absent save attempt", refs=event.refs)
            elif save_action.name != "save-part" or save_action.end_seq >= event.seq:
                reader.issue("EVIDENCE_CONTRADICTION", "Artifact snapshot must follow its producing save attempt", "fail", event.refs + save_action.refs)
            elif save_action.session_id != event.session_id:
                reader.issue("CALL_LINK_INVALID", "Artifact and producing save use different sessions", "fail", event.refs + save_action.refs)
            if isinstance(solve_id, str):
                solve_action = actions.get(solve_id)
                if solve_action is None:
                    reader.issue("CALL_LINK_INVALID", "Artifact references an absent solve attempt", refs=event.refs)
                elif (solve_action.name != "solve" or
                      (save_action is not None and
                       (solve_action.end_seq >= save_action.start_seq or
                        solve_action.session_id != save_action.session_id))):
                    reader.issue("EVIDENCE_CONTRADICTION", "Artifact solve must precede its save in the same session", "fail", event.refs + solve_action.refs)
            if item:
                artifact.refs.append(item[1])
                artifact.sha256 = item[1].sha256
                try:
                    content = strict_json(item[0])
                    if not isinstance(content, dict):
                        raise InputError("Saved artifact must be an object")
                    artifact.content, artifact.integrity = content, "pass"
                except (InputError, RecursionError) as exc:
                    reader.issue("TRACE_PARSE_ERROR", f"Artifact: {exc}", refs=artifact.refs)
            elif isinstance(reference, dict) and isinstance(reference.get("path"), str) and reference["path"] in reader.cache:
                artifact.integrity = "fail"
                reader.issue("ARTIFACT_HASH_MISMATCH", f"Untrusted artifact {identity}", "fail", artifact.refs)
            if identity in run.artifacts:
                reader.issue("EVIDENCE_CONTRADICTION", f"Duplicate artifact ID {identity}", "fail", event.refs)
                artifact.content, artifact.integrity = None, "fail"
            run.artifacts[identity] = artifact
        elif event.kind == "artifact_published":
            event.data["_verified"] = False
            identity = event.data.get("artifact_id")
            artifact = run.artifacts.get(identity) if isinstance(identity, str) else None
            if artifact is None or artifact.event_seq >= event.seq:
                known_later = (isinstance(identity, str) and
                               artifact_sequences.get(identity, -1) >= event.seq)
                reader.issue("CALL_LINK_INVALID", "Publication must reference an earlier captured artifact",
                             "fail" if known_later else "unknown", event.refs)
            status = event.data.get("status")
            has_error = any(isinstance(event.data.get(key), str) and event.data[key].strip()
                            for key in ("error_type", "error", "reason_code"))
            if status == "failed" and not has_error:
                reader.issue("TRACE_INCOMPLETE", "Failed publication lacks recorded error information", refs=event.refs)
            elif status not in ("ok", "failed"):
                reader.issue("TRACE_PARSE_ERROR", "Publication status must be ok or failed", refs=event.refs)
            # A failed copy may produce no destination bytes. If partial bytes
            # were nevertheless captured, their reference must still validate.
            item = (reader.reference(event.data.get("published_ref"), missing_code="ARTIFACT_MISSING")
                    if status != "failed" or "published_ref" in event.data else None)
            if item:
                event.data["_verified"] = True
                event.data["_sha256"] = item[1].sha256
                event.refs.append(item[1])
        else:
            # Capture references are validated even if their content isn't needed for state reduction.
            for key, value in event.data.items():
                if key.endswith("_ref") and isinstance(value, dict) and "path" in value:
                    item = reader.reference(value)
                    if item:
                        event.refs.append(item[1])
    if run.outcome:
        item = reader.reference(run.outcome.get("final_message_ref"))
        if item:
            run.refs.append(item[1])
            run.final_message_format = run.outcome.get("final_message_format")
            try:
                run.final_message = (strict_json(item[0]) if run.final_message_format == "json/1"
                                     else item[0].decode("utf-8"))
            except (InputError, UnicodeError, RecursionError) as exc:
                reader.issue("TRACE_PARSE_ERROR", f"Final message: {exc}", refs=[item[1]])


def _capture(reader: Reader, run: EvidenceRun):
    """Check required role-specific raw capture and causal IDs, not mere labels."""
    terminal = [e for e in run.events if e.kind == "run_finished"]
    real_events = [e for e in run.events if e.kind != "evidence_gap"]
    terminal_ok = (len(terminal) == 1 and bool(real_events)
                   and terminal[0].seq == max(e.seq for e in real_events))
    if not terminal_ok:
        reader.issue("TRACE_INCOMPLETE", "Exactly one run_finished must be the last event")
    for event in terminal:
        ref = event.data.get("outcome_ref")
        item = reader.reference(ref)
        expected = reader.cache.get("outcome.json")
        if item is None or not isinstance(ref, dict) or ref.get("path") != "outcome.json" or item[0] != expected:
            reader.issue("EVIDENCE_CONTRADICTION", "run_finished does not reference the loaded outcome", "fail", event.refs)
            terminal_ok = False

    model_requests, model_returns, proposals, returns = {}, {}, {}, {}
    for event in real_events:
        required_ref = {"model_requested": "request_ref", "model_returned": "response_ref",
                        "tool_returned": "result_ref"}.get(event.kind)
        if required_ref:
            item = reader.reference(event.data.get(required_ref))
            if item is None:
                reader.issue("TRACE_INCOMPLETE", f"{event.kind} lacks verified {required_ref}", refs=event.refs)
        if event.kind in {"model_requested", "model_returned", "model_failed"}:
            identity = event.model_call_id
            if not identity:
                reader.issue("CALL_LINK_INVALID", "Model event lacks model_call_id", refs=event.refs)
                continue
            target = model_requests if event.kind == "model_requested" else model_returns
            if identity in target:
                reader.issue("CALL_LINK_INVALID", "Duplicate model boundary ID", "fail", event.refs)
            target[identity] = event
        if event.kind in {"tool_proposed", "tool_returned"}:
            if not event.call_id:
                reader.issue("CALL_LINK_INVALID", "Tool boundary lacks call_id", refs=event.refs)
                continue
            target = proposals if event.kind == "tool_proposed" else returns
            if event.call_id in target:
                reader.issue("CALL_LINK_INVALID", "Duplicate tool boundary ID", "fail", event.refs)
            target[event.call_id] = event
            if event.kind == "tool_proposed":
                if not isinstance(event.data.get("name"), str) or not isinstance(event.data.get("arguments"), str):
                    reader.issue("TRACE_INCOMPLETE", "Tool proposal lacks name/raw argument string", refs=event.refs)
                model = model_returns.get(event.model_call_id)
                if run.origin == "live_agent" and (model is None or model.kind != "model_returned"):
                    reader.issue("CALL_LINK_INVALID", "Live tool proposal lacks preceding raw model response", refs=event.refs)
    for identity, event in model_requests.items():
        end = model_returns.get(identity)
        if end is None or end.seq <= event.seq:
            reader.issue("CALL_RESULT_MISSING", "Model request lacks later terminal record", refs=event.refs)
    for identity, event in model_returns.items():
        if identity not in model_requests:
            reader.issue("CALL_LINK_INVALID", "Model terminal record lacks request", refs=event.refs)
    for identity in proposals.keys() | returns.keys():
        start, end = proposals.get(identity), returns.get(identity)
        if start is None or end is None or end.seq <= start.seq:
            reader.issue("CALL_LINK_INVALID", "Tool proposal/return pair incomplete or unordered")
    for action in run.actions:
        if action.call_id is None:
            continue  # Explicit harness initialization/restoration need not be a tool call.
        proposal, returned = proposals.get(action.call_id), returns.get(action.call_id)
        if proposal is None or returned is None:
            reader.issue("CALL_LINK_INVALID", "CLI attempt refers to an absent tool boundary", refs=action.refs)
        elif not proposal.seq < action.start_seq <= action.end_seq < returned.seq:
            reader.issue("CALL_LINK_INVALID", "CLI attempt is not contained within its tool call", "fail", action.refs + proposal.refs + returned.refs)
    for event in real_events:
        if event.kind != "guard_decision":
            continue
        proposal, returned = proposals.get(event.call_id), returns.get(event.call_id)
        if proposal is None or returned is None:
            reader.issue("CALL_LINK_INVALID", "Guard decision lacks its proposal/return boundaries", refs=event.refs)
        elif not proposal.seq < event.seq < returned.seq:
            reader.issue("CALL_LINK_INVALID", "Guard decision is outside its tool call", "fail", event.refs)
        for action in run.actions:
            if action.call_id == event.call_id and action.start_seq <= event.seq:
                reader.issue("CALL_LINK_INVALID", "Guard decision follows linked CLI dispatch", "fail", event.refs + action.refs)
    if run.origin == "live_agent" and not model_requests:
        reader.issue("TRACE_INCOMPLETE", "Live agent capture lacks raw model requests")
    return terminal_ok


def load_run(path: str | Path, case: Case, limits: Limits | None = None) -> EvidenceRun:
    run = EvidenceRun(Path(path).resolve())
    reader = Reader(run.bundle, limits or Limits(), run)
    completion = reader.document("completion.json", inventory=False)
    run.completion = completion
    if completion and isinstance(completion.get("files"), dict):
        reader.inventory = completion["files"]
        for name in reader.inventory:
            if name == "completion.json":
                reader.issue("EVIDENCE_INTEGRITY_ERROR", "Completion inventory cannot hash itself", "fail")
            else:
                reader.get(name)
    else:
        reader.issue("TRACE_INCOMPLETE", "No usable completion inventory")
    run.manifest = reader.document("manifest.json") or {}
    run.run_id = run.manifest.get("run_id")
    if not isinstance(run.run_id, str) or not run.run_id:
        run.run_id = None
        reader.issue("TRACE_PARSE_ERROR", "Missing/invalid run ID")
    run.origin = run.manifest.get("evidence_kind", "unknown")
    if run.origin not in ("live_agent", "synthetic_fixture", "preparation_check"):
        reader.issue("UNSUPPORTED_EVIDENCE", "Unknown evidence origin")
    producer = run.manifest.get("producer")
    run.profile_supported = (run.manifest.get("schema_version") == SCHEMA
                             and run.manifest.get("capture_profile") == "cosmon-eval/1"
                             and isinstance(producer, dict)
                             and producer.get("binary_sha256") == case.binary_sha256)
    if isinstance(producer, dict) and producer.get("binary_profile", case.profile) != case.profile:
        run.profile_supported = False
    if not run.profile_supported:
        reader.issue("UNSUPPORTED_EVIDENCE", "Unsupported trace schema or CLI binary profile")
        _gap(run, 0, "Unsupported CLI profile")
    original = run.manifest.get("original", {})
    item = reader.reference(original.get("part_ref") if isinstance(original, dict) else None)
    if item:
        run.original_matches = item[1].sha256 == case.original_sha256
        if not run.original_matches:
            reader.issue("UNAPPROVED_PART_MUTATION", "Captured original differs from trusted case", "fail", [item[1]])
        elif isinstance(original, dict):
            for key in ("parameters", "default_load", "material", "revision"):
                if key in original and original[key] != case.original.get(key):
                    reader.issue("EVIDENCE_CONTRADICTION", f"Original summary differs: {key}", "fail", [item[1]])
    claimed_case = run.manifest.get("case", {})
    if not isinstance(claimed_case, dict) or not isinstance(claimed_case.get("part_name"), str):
        reader.issue("TRACE_PARSE_ERROR", "Manifest requires a case object and part_name")
    elif claimed_case["part_name"] != case.case_id:
        reader.issue("WRONG_PART", "Manifest case differs from caller's trusted case", "fail")
    for name in ("task_ref", "policy_ref"):
        reader.reference(run.manifest.get(name))
    run.outcome = reader.document("outcome.json")
    _events(reader, run)
    _actions(reader, run)
    _payloads(reader, run)
    terminal_ok = _capture(reader, run)
    # Reconcile full completion, not merely a plausible success prefix.
    actual_events = [e for e in run.events if e.kind != "evidence_gap"]
    run.complete = bool(completion and reader.inventory is not None
                        and completion.get("run_id") == run.run_id
                        and completion.get("status") in ("completed", "failed")
                        and type(completion.get("event_count")) is int
                        and completion["event_count"] == len(actual_events)
                        and type(completion.get("last_seq")) is int
                        and completion.get("last_seq") == len(actual_events)
                        and terminal_ok)
    if not run.complete:
        reader.issue("TRACE_INCOMPLETE", "Missing or inconsistent terminal evidence")
    # Even unrelated capture omissions prevent claiming a complete execution ledger.
    run.execution_complete = (run.complete and not run.issues
                              and all(a.success is not None and not a.uncertain_order for a in run.actions))
    run.events.sort(key=lambda e: (e.seq, e.event_id))
    run.input_digest = digest(canonical({name: digest(raw) for name, raw in sorted(reader.cache.items())}))
    run.metrics = {"raw_bytes": reader.total, "raw_files": len(reader.cache),
                   "events": len(actual_events), "cli_attempts": len(run.actions),
                   "solve_attempts": sum(a.name == "solve" for a in run.actions),
                   "failed_cli_attempts": sum(a.success is False for a in run.actions),
                   "model_calls": sum(e.kind == "model_requested" for e in run.events),
                   "model_tokens": None, "warning_thresholds": "disabled"}
    for metric, kind, field in (("model_request_bytes", "model_requested", "request_ref"),
                                ("model_response_bytes", "model_returned", "response_ref"),
                                ("model_visible_tool_bytes", "tool_returned", "result_ref")):
        boundaries = [event for event in run.events if event.kind == kind]
        sizes = []
        for event in boundaries:
            reference = event.data.get(field)
            match = next((ref for ref in event.refs if isinstance(reference, dict)
                          and ref.path == reference.get("path")), None)
            sizes.append(match.bytes if match else None)
        run.metrics[metric] = None if any(size is None for size in sizes) else sum(sizes)
    seen_reads = set()
    repeats = 0
    for action in run.actions:
        if action.name not in READ_ONLY:
            # Same query after a state-changing attempt is not a redundant read.
            seen_reads.clear()
        elif action.success is True:
            signature = (action.session_id, tuple(action.argv[1:]))
            repeats += signature in seen_reads
            seen_reads.add(signature)
    run.metrics["repeated_read_calls"] = repeats
    return run


Adapter = Callable[[str | Path, Case, Limits | None], EvidenceRun]
ADAPTERS: dict[str, Adapter] = {"partlab": load_run}


def register_adapter(name: str, adapter: Adapter) -> None:
    """Explicit host-code integration only; never invoked from input trace data."""
    if not isinstance(name, str) or not name or name in ADAPTERS or not callable(adapter):
        raise InputError("Adapter needs a new nonempty name and a callable")
    ADAPTERS[name] = adapter
