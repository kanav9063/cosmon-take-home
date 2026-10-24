# Repository setup

> Historical planning record from the independent evaluator checkout. For current
> implementation status and runnable commands, use [the evaluator index](../README.md),
> [the combined runbook](../../RUN.md), and [the integration decisions](../../docs/INTEGRATION_DECISIONS.md).

This repository contains the original PartLab Linux AMD64 starter bundle.
The supplied root `README.md`, six `parts/*.json` files, and `partlab` binary
are unchanged. The binary has its executable permission set.

The agent and evaluation harness have not been implemented. This is preparation
for the recorded exercise. No agent framework or model provider has been chosen.

## Start here

1. Read [the original brief](../../TASK.md) and [the requirements checklist](REQUIREMENTS.md).
2. Start a screen recording with audio and check that your narration is audible.
3. Keep the exercise to one hour, approximately 30 minutes per part.
4. Work from the repository root, where the CLI finds `parts/` and maintains `.partlab/`.

The supplied Linux binary has no installation dependencies. Check it with:

```sh
chmod +x partlab
./partlab --help
./partlab list-parts
./partlab reset
```

The README's manual setup smoke check is:

```sh
./partlab open-part bracket_v3
./partlab mesh
./partlab apply-load face_mounting 5000
./partlab solve
./partlab get-safety-factor
./partlab reset
```

This only checks the supplied SDK. It does not establish that an agent or eval
works. Use each part's default load in the eventual agent, as the brief requires.
Reset between runs. `set-parameter` invalidates the mesh and solve and returns
the session to `open`; analysis must be rerun after a change.

Setup verification completed on October 23, 2026: help and part listing worked;
the manual open/mesh/load/solve/safety-factor sequence returned `ok: true` for
every command. A final reset succeeded. All eight original files were compared
byte-for-byte with the downloaded archive and matched. These are SDK setup
checks, not the required agent runs or evaluation checks.

`.partlab/`, credentials, caches, and recordings are ignored by Git. Raw traces,
evaluation reports, checks, and saved `outputs/` parts are submission artifacts
and are intentionally not ignored. Review them for credentials before committing.
Keep a recording link with the submission; don't commit large video files.

## Platform bundles from Noah

This checkout includes the Linux AMD64 binary. For another platform, use the
matching bundle, run from its directory, and copy your implementation there:

- [Linux AMD64](https://drive.google.com/file/d/1NKFQDAbAHd0klfHktIPFnrK2XAGT5FoS/view)
- [macOS AMD64](https://drive.google.com/file/d/11X0m3zFG_sJ9wxL-w_fgfLseoPlPQvZS/view)
- [macOS ARM64](https://drive.google.com/file/d/1RXfST4ssNrz6A-19vwNj5K_jetyKiS21/view)
- [Windows](https://drive.google.com/file/d/19zZV7uMyNevAWaeHLF5i6dDDnbv9cPKq/view)

On Windows use `partlab.exe`. If the provided build does not run, Noah asks you
to reply to the email thread for a compatible build before starting the clock.

## Source and integrity

Source: Noah Weber, “Re: Materials for our discussion,” October 23, 2026,
4:14 p.m. Eastern. [Open the email](https://mail.google.com/mail/u/?authuser=kanavarora9063%40gmail.com#all/1a16a667019ed2ea).

Downloaded file: `partlab-linux-amd64 (1).zip`.

```text
Archive SHA-256: 2760f9c7eca420f050354eaee3992e08a2158ea8d3cfaadfea5550bc00fdf870
Binary SHA-256:  9b202e1ba07861f52f12005108e81815ef14d92f2db3ba322fc51422746ab183
```

Preparation added only repository housekeeping and documentation. Complete
[RUN.md](../../RUN.md) during the exercise with the actual commands and results.
