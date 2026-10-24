# Run and handoff

Status: starter repository prepared; agent and eval implementation pending.
This file is a template to complete during the recorded exercise.

## Dependencies

- Supplied `partlab`: Linux AMD64, self-contained. Run from the repository root.
- Agent/eval language, runtime, libraries, and model configuration: **TODO**.
- Installation commands and required environment variable names: **TODO**.
  Do not include secret values.

## Setup check

```sh
./partlab --help
./partlab list-parts
./partlab reset
```

See [docs/SETUP.md](docs/SETUP.md) for the provided manual SDK smoke workflow
and other platform bundles.

## Agent, checks, and eval

Replace each TODO with an exact reproducible command before submission.

1. `./partlab reset`, then **TODO: run agent on bracket_v3 and persist its raw trace**.
2. `./partlab reset`, then **TODO: run agent on flange_v1 and persist its raw trace**.
3. **TODO: run the non-happy-path check and explain what it proves**.
4. **TODO: run the eval over the raw traces and save the structured report**.
5. **TODO: evaluate the deliberately flawed trace and assert the specific finding**.

## Results and artifacts

| Item | Status / path |
| --- | --- |
| Supplied SDK setup | See docs/SETUP.md |
| Agent runs and safety-factor verification | Pending |
| Manufacturing-constraint verification | Pending |
| Non-happy-path check | Pending |
| Raw traces | Pending |
| Saved updated parts, when an allowed fix exists | Pending: outputs/<part_name>.json |
| Eval report | Pending |
| Flawed trace and demonstrated finding | Pending |
| Recording link | Pending |

Main unfinished item: agent and eval are not yet implemented. Replace this with
the actual remaining limitation after the exercise.
