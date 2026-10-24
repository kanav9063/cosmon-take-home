Exercise the original PartLab CLI baseline for `bracket_v3` in `/app`.

Reset the session, open the part, mesh it, apply its original default load,
solve, read the safety factor, and save the unchanged baseline part to
`/logs/artifacts/bracket_v3-baseline.json`. Record the exact command arguments,
exit codes, stdout, and stderr in `/logs/artifacts/commands.jsonl`, and write
the original input hashes, original parameters/default load, reported safety
factor, and saved-file hash to `/logs/artifacts/outcome.json`.

Use these seven CLI actions in order: `reset`, `open-part bracket_v3`,
`mesh`, `apply-load <original face_id> <original force_N>`, `solve`,
`get-safety-factor`, and `save-part /logs/artifacts/bracket_v3-baseline.json`.
Each executable path is `/app/partlab`. Keep the CLI's exact response text.

`commands.jsonl` must contain one JSON object per command, with these fields:

```json
{
  "purpose": "scripted-cli-infrastructure-preparation",
  "call_id": "cli-001",
  "argv": ["/app/partlab", "reset"],
  "returncode": 0,
  "stdout": "<exact CLI standard output>",
  "stderr": "<exact CLI standard error>"
}
```

Call IDs are sequential `cli-001` through `cli-007`. Every command must exit
successfully and return a JSON response whose `ok` field is `true`. The solve
must converge, and its load and the saved part's load must equal the original
default load. Safety factors in the solve, get-safety-factor, and outcome must
agree. Save the file produced by the CLI; preserve its unchanged parameters
and its solve result.

`outcome.json` must contain:

- `purpose`: `scripted-cli-infrastructure-preparation`.
- `part`: `bracket_v3`.
- `original_hashes`: SHA-256 hex digests under keys `partlab` and
  `parts/bracket_v3.json`, computed from their original `/app` files.
- `original_parameters` and `default_load`: the corresponding original part
  JSON objects, without changes.
- `safety_factor`: the finite positive number reported by the CLI.
- `saved_artifact`: `bracket_v3-baseline.json`.
- `saved_sha256` and `commands_sha256`: SHA-256 hex digests of the exact saved
  file and JSONL file bytes.
- `command_count`: `7`.
- `agent_only_marker_created`: `true`, after the marker check below.

The image writes `/logs/artifacts/environment-start.json` before the oracle
script is uploaded. Preserve this startup evidence exactly:

```json
{"purpose":"infrastructure-preparation-only","tests_absent_at_start":true,"solution_absent_at_start":true}
```

Confirm `/tests` is absent from the agent container, then create
`/app/unexported-agent-marker` containing `agent environment only` followed
by a newline. This marker must remain outside `/logs/artifacts`. Harbor
transfers only `/logs/artifacts` into a separate trusted verifier container;
the verifier checks that the marker and `/solution` are absent there. The
oracle's `/solution` directory is intentionally uploaded only after agent
container startup.

This is an infrastructure smoke check. Leave all parameters unchanged and
label the records as scripted CLI preparation. A low baseline safety factor
is expected and is not a failed infrastructure check. No model, search,
repair, or take-home agent/evaluation implementation is part of this task.
The reference oracle exercises this instruction. A separate no-op trial
intentionally produces no outcome and must receive reward zero.
