# Local Harbor setup and verification

Harbor is installed separately from the zero-dependency offline-eval environment.
This follow-on setup was explicitly requested after the original preparation.
It does not make Harbor a requirement of the take-home's core evaluator.

## Installed environment

- Python 3.12.3 in `.venv-harbor/`; Harbor **0.24.0**.
- All resolved Python dependencies are pinned in
  [harbor_setup/requirements.lock](../harbor_setup/requirements.lock).
- Ubuntu Docker Engine **29.1.3**, Compose **2.40.3**, Buildx **0.30.1**.
- Docker's system service is enabled and running. User `ubuntu` belongs to the
  `docker` group. Existing shell processes may need a fresh group session.
- Agent and verifier containers use a digest-pinned
  `python:3.12-slim-bookworm` image. Runtime network access is disabled in both
  for this no-model smoke task.

The existing `.venv/`, original README, binary and parts remain intact. Local
environments and `.harbor-jobs/` are ignored by Git. This setup does not install
Scout, configure a paid model, or connect the planned producer/evaluator contract.
Keep actual submission traces outside this ignored infrastructure-check directory.

## Reproduce on this Ubuntu host

Docker installation requires host administration privileges. The exact Ubuntu
package versions used here were:

```sh
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  docker.io=29.1.3-0ubuntu3~24.04.2 \
  docker-compose-v2=2.40.3+ds1-0ubuntu1~24.04.1 \
  docker-buildx=0.30.1-0ubuntu1~24.04.1
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

The host's unrelated GitHub CLI apt repository produced a signing-key warning
during index refresh. Ubuntu's Docker packages installed successfully; no keys
or repository configuration were changed to bypass signature checks.

From the repository root:

```sh
python3 -m venv .venv-harbor
.venv-harbor/bin/python -m pip install --no-cache-dir -r harbor_setup/requirements.lock
.venv-harbor/bin/python -m pip check
HARBOR_TELEMETRY=0 .venv-harbor/bin/harbor --version
.venv-harbor/bin/python harbor_setup/check.py
```

The checker refreshes its group context with `sg docker` when the current user
already belongs to the group but the calling shell has old supplementary groups.
It does not change permissions or invoke sudo. For direct Harbor commands from
an old shell, start a fresh login/group session or use `sg docker -c 'COMMAND'`.

## What the smoke check proves

[check.py](../harbor_setup/check.py) stages a copy of the
[task template](../harbor_setup/task/task.toml), the supplied binary and original
parts under a new `.harbor-jobs/<UTC timestamp>/` directory. It runs:

1. Two serialized `oracle` attempts. The oracle executes a known script rather
   than an LLM. Each fresh container resets PartLab, opens `bracket_v3`, meshes,
   applies the original default load, solves, reads SF, and saves a baseline
   artifact. The verifier checks the exact recorded command results, default
   load, SF consistency, hashes and unchanged parameters. Expected reward: `1`.
2. One `nop` attempt using the same task and a fresh container. It creates no
   output, so verification must produce reward `0`. This checks that a valid
   pass is not hard-coded and earlier oracle output does not leak into a new run.

The task explicitly sets `environment_mode = "separate"` and exports only
`/logs/artifacts`. Trusted tests and pristine binary/part references are baked
into a separate verifier image under `/tests` and `/reference`; the verifier
does not use the agent's working copy as its reference. The agent image's startup
entrypoint checks that it contains neither tests nor a solution, before Harbor
uploads the scripted oracle. The oracle then creates an unexported marker under
`/app`; the verifier checks that neither this marker nor `/solution` arrived.
These are infrastructure isolation checks, not an adversarial security audit.

The wrapper checks expected trial counts, completion, zero execution errors,
agent identity, absence of a model, exact rewards, artifact collection and hashes,
and that the starter files remain unchanged. It also checks oracle script exit
status, the verifier's specific missing-output reason for the no-op, and that
the container's binary/part hashes match the staged host originals. It fails if
those checks fail, even when Harbor's own process exits successfully.
It additionally asserts separate mode in every trial result, both resolved
network policies, the exact successful artifact-manifest entry, the transferred
startup record and the verifier's isolation results. A no-op still transfers
the startup record but lacks the required outcome; it must fail for that reason.

This verifies local Docker build/start, Harbor trial orchestration, oracle
execution, verification, result persistence and artifact export. It is **not** a
model-driven agent demonstration, a repair attempt, an offline trace evaluator,
or the take-home's required semantic flawed-trace check. A baseline SF below 2.0
is acceptable here because the task is infrastructure verification, not repair.

## Results and evidence

Verified October 23, 2026 (ET). The final suite completed without execution
errors; all three trial results passed the wrapper's assertions:

| Trial | Observed result |
| --- | --- |
| Oracle attempt 1 | Reward 1; seven CLI commands; baseline SF 1.428; artifacts, hashes and separate-verifier isolation verified |
| Oracle attempt 2 | Reward 1; seven CLI commands; baseline SF 1.428; artifacts, hashes and separate-verifier isolation verified |
| No-op | Reward 0; expected missing `outcome.json`; startup evidence transferred; no inherited oracle output |

`pip check` reported no broken requirements. Docker was active and enabled.
A post-run Docker listing contained no remaining trial containers. The original
README, executable, six parts, RUN.md and prior setup/requirements notes were
compared to the initial Git commit and were unchanged.

Each run writes full Harbor results and console logs under its timestamped
`.harbor-jobs/` directory. `summary.json` is written only when the wrapper's
assertions pass. The checked setup result is copied to
[harbor_setup/verification.json](../harbor_setup/verification.json).
After staging this suite, the task instructions were expanded to spell out the
existing output fields and isolation checks. The runnable scripts, images and
task configuration match the recorded suite.

For each trial, Harbor 0.24.0 stores:

- `result.json`: timestamps, agent identity, execution status and verifier reward.
- `verifier/report.json` and `verifier/reward.txt`: the task's actual check result.
- `artifacts/logs/artifacts/`: exported raw CLI output, baseline summary and saved
  baseline JSON for successful oracle attempts; startup record for every trial.
- `artifacts/manifest.json`: the explicit `/logs/artifacts` collection entry and
  its status. A completed trial alone does not establish artifact completeness.

`HARBOR_TELEMETRY=0` is set before the smoke checker invokes Harbor. No `--upload`
or `--launch` is used. Only local Docker environments run; the task does not use
provider keys. `--delete` requests removal of each trial's containers after
results have been collected; the reusable Docker images remain cached.

## Versioned references

Harbor's [installation documentation](https://docs.harborframework.com/getting-started/installation)
describes its Python package and default Docker backend. Its
[solution documentation](https://docs.harborframework.com/tasks/solution) describes
the scripted oracle; its [verifier documentation](https://docs.harborframework.com/tasks/verifier)
describes reward files. The installed 0.24.0 source was used to confirm schema
version 1.4, CLI flags and artifact paths because the live documentation can
describe a different release. Task version 1.1.0 explicitly uses a separate
verifier; the earlier 1.0.0 smoke used a shared verifier. Current Harbor docs
describe separate mode as the default for new tasks starting in 0.25, so this
0.24 setup does not depend on that default.

The subsequent [Terminal-Bench 4.0 audit](BENCHMARK_AUDIT.md) motivated the
isolation and explicit transfer checks and records the remaining assignment
completion gates. See also Harbor's
[separate-verifier guide](https://docs.harborframework.com/tasks/separate-verifier)
and [artifact collection semantics](https://docs.harborframework.com/jobs/artifact-collection).

## Post-reference-audit recheck

The unchanged infrastructure task was executed again in suite
`.harbor-jobs/20261024T014508.152947Z` using
`.venv-harbor/bin/python harbor_setup/check.py`. The
[new verification record](../harbor_setup/verification-post-audit.json) retains
all three trial/report hashes, package versions, lock digest, explicit separate
verifier mode and both no-network policies. Both oracle attempts again returned
reward 1; the no-op returned 0 for the expected missing output. All isolation,
transfer, fresh-environment and original-file assertions passed. Model calls: 0.
The original verification record remains historical evidence, unchanged.
