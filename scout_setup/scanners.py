"""Deterministic projection of evaluator dimensions into Scout findings."""
from inspect_scout import Reference, Result, Scanner, Transcript, scanner


@scanner(messages="all", version=1)
def evaluation_dimensions() -> Scanner[Transcript]:
    """Keep every dimension and its supporting raw evidence references visible."""
    async def scan(transcript: Transcript) -> list[Result]:
        if transcript.metadata.get("projection_version") != "cosmon.scout-projection/1":
            raise ValueError("This scanner accepts only validated evaluator report projections")
        report = transcript.metadata["report"]
        checks = {check["instance_id"]: check for check in report["checks"]}
        message_ids = {message.metadata.get("check_instance_id"): message.id
                       for message in transcript.messages if message.metadata}
        results = []
        for dimension, data in sorted(report["summary"].items()):
            members = [checks[key] for key in data["members"]]
            refs = [ref for check in members for ref in check["refs"]]
            results.append(Result(
                label=dimension, value=data["status"], answer=data["status"],
                explanation=data["reason"],
                references=[Reference(type="message", id=message_ids[key]) for key in data["members"]],
                metadata={"input_id": report["input_id"], "raw_refs": refs,
                          "check_instances": data["members"],
                          "report_sha256": transcript.metadata["report_sha256"],
                          "projection_kind": "derived_evaluator_report_not_agent_conversation"},
            ))
        return results
    return scan
