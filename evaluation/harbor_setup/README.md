# Optional Harbor smoke check

From the repository root, with the pinned `.venv-harbor` environment and Docker
available:

```sh
.venv-harbor/bin/python evaluation/harbor_setup/check.py
```

The checker stages `task/` together with the root `partlab` binary and `parts/`
into `.harbor-jobs/`. Two scripted oracle trials must receive reward 1, and a
fresh no-op trial must receive reward 0. Agent and verifier networking is
disabled; verification runs in a separate container and checks transferred
evidence. No model or API key is used.

Setup, scope and recorded results: [Harbor runbook](../docs/HARBOR_SETUP.md).
Historical receipts are preserved unchanged in this directory.
Use `--output /path/to/new-receipt.json` to retain a fresh compact receipt outside
the ignored job directory. Existing receipt files are refused. The checker uses
the Harbor CLI beside its Python interpreter, so an existing pinned environment
at another location also works.
