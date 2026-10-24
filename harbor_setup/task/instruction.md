Exercise the original PartLab CLI baseline for `bracket_v3` in `/app`.

Reset the session, open the part, mesh it, apply its original default load,
solve, read the safety factor, and save the unchanged baseline part to
`/logs/artifacts/bracket_v3-baseline.json`. Record the exact command arguments,
exit codes, stdout, and stderr in `/logs/artifacts/commands.jsonl`, and write
the original input hashes, original parameters/default load, reported safety
factor, and saved-file hash to `/logs/artifacts/outcome.json`.

This is an infrastructure smoke check. Leave all parameters unchanged and
label the records as scripted CLI preparation. A low baseline safety factor
is expected and is not a failed infrastructure check. No model, search,
repair, or take-home agent/evaluation implementation is part of this task.
